#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper - Extended matching for header variants and blue color variants

Key improvements:
- RESEARCH_HEADER_KEYWORDS: configurable header keywords (e.g., '研究方向', '研究领域', '研究兴趣', 'Research Interest')
- BLUE_COLOR_PATTERNS: configurable hex / rgb / numeric patterns used to recognize the blue header TDs
- Robust detection of blue header TDs via style attribute or descendant color:white
- All previous extractors and fallbacks preserved
"""
import os
import argparse
import json
import logging
import random
import re
import time
import html
from pathlib import Path
from typing import Dict, Optional, Set, List
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup, Tag, NavigableString

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DualTemplateFacultyProfileScraper:
    """Scraper supporting multiple templates with flexible header/color matching."""
    # --- Header keyword variants to recognize "research" section ---
    RESEARCH_HEADER_KEYWORDS = [
        '研究方向',        # standard
        '研究领域',        # alternative
        '研究兴趣',        # alternative phrasing
        'Research Interest',
        'Research Interests',
        'Research Direction',
        '研究方向：', '研究领域：', '研究兴趣：'
    ]

    # --- Stop variants (existing) ---
    STOP_HEADING_VARIANTS = [
        '教育及工作经历', '近五年承担项目', '近五年代表性论文', '代表论著', '获奖及荣誉',
        'Representative Papers (Last Five Years)', 'Selected Publications', 'Education'
    ]

    # --- Blue color patterns to recognize blue header TDs ---
    # Add hex (with or without '#') and rgb patterns commonly used on these sites.
    BLUE_COLOR_PATTERNS = {
        # hex (lowercase no #), common hexes from your examples
        '548dd4', '4d6abb', '548DD4', '4D6ABB', '3765A8', '2E74B5',
        # we will match hex with or without '#'
    }
    # Also accept approximate rgb tuples as strings, e.g. "rgb(84,141,212)"
    BLUE_RGB_PATTERNS = {
        'rgb(84,141,212)', 'rgb(77,106,187)', 'rgb(52,141,212)', 'rgb(77,106,187)'
    }

    # Other constants
    YEAR_PATTERN = r'\b(19|20)\d{2}\b'
    DOI_PATTERN = r'(doi|DOI)[\s:]*10\.\d{4,}'
    MISLEADING_CONTENT = [
        'doi', 'DOI', '10.', 'http://', 'https://',
        'ISBN', 'ISSN', '期刊', '会议', 'pp.', 'Vol.',
        '年第', '月第', 'IF=', '影响因子', 'SCI', 'EI',
        '第一作者', '通讯作者', '发表于', 'Email', 'email'
    ]

    PEOPLE_STOP_HEADINGS = ['承担科研项目情况', '代表论著', '获奖及荣誉', '个人简历', '社会任职']
    BLUE_TABLE_STOP_MARKER = '教育及工作经历'

    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls: Set[str] = set()

    # ---------------- Helpers ----------------
    @staticmethod
    def normalize_text(s: Optional[str]) -> str:
        if not s:
            return ''
        return re.sub(r'\s+', ' ', s).strip()

    @staticmethod
    def text_of_tag(tag: Tag) -> str:
        if not tag:
            return ''
        parts = []
        for child in tag.descendants:
            if isinstance(child, NavigableString):
                parts.append(str(child))
            elif isinstance(child, Tag) and child.name in ('li', 'p', 'div'):
                parts.append('\n')
        text = ''.join(parts)
        text = html.unescape(text)
        text = re.sub(r'\s+\n\s+', '\n', text)
        text = re.sub(r'\n{2,}', '\n\n', text)
        return text.strip()

    # Robust hex normalization
    @staticmethod
    def normalize_hex(s: str) -> str:
        s = s.strip().lower()
        s = s.lstrip('#')
        return s

    def is_blue_style_td(self, td: Tag) -> bool:
        """
        Determine if a <td> looks like a blue header cell.
        Checks:
         - style attribute containing background or background-color with hex or rgb
         - descendant bold/span/strong with inline style color:white
         - explicit presence of known header keywords (research header) within this td
        """
        try:
            style = (td.get('style') or '').lower()
            # check for hex codes in style
            hex_matches = re.findall(r'#?([0-9a-f]{3,6})', style, flags=re.I)
            for h in hex_matches:
                nh = self.normalize_hex(h)
                if nh in {c.lower() for c in self.BLUE_COLOR_PATTERNS}:
                    return True
            # check rgb(...) pattern
            rgb_match = re.search(r'rgb\([^\)]+\)', style, flags=re.I)
            if rgb_match:
                rs = rgb_match.group(0).lower()
                if rs in {r.lower() for r in self.BLUE_RGB_PATTERNS}:
                    return True
                # approximate heuristic: if r,g,b values have moderate-high blue component
                m = re.findall(r'(\d{1,3})', rs)
                if len(m) >= 3:
                    r_val, g_val, b_val = int(m[0]), int(m[1]), int(m[2])
                    # if blue component is largest and reasonably high, guess blue
                    if b_val >= max(r_val, g_val) and b_val > 80:
                        return True
            # check inline 'background' with rgb or hex but not exact match
            if 'background' in style or 'background-color' in style:
                # if any color-like token in style, consider as candidate
                if re.search(r'#([0-9a-f]{3,6})', style, flags=re.I) or re.search(r'rgb\([^\)]+\)', style, flags=re.I):
                    return True
            # check descendant bold/span with inline color:white
            for descendant in td.find_all(['b', 'strong', 'span']):
                st = (descendant.get('style') or '').lower()
                if 'color' in st and 'white' in st:
                    return True
            # also check if td contains any research header keyword and has style with background; treat as blue header
            td_text = self.normalize_text(td.get_text(separator=' ', strip=True)).lower()
            if any(k.lower() in td_text for k in self.RESEARCH_HEADER_KEYWORDS) and ('background' in style or style):
                return True
            return False
        except Exception:
            return False

    def header_keyword_in_text(self, text: str) -> bool:
        t = (text or '').lower()
        for kw in self.RESEARCH_HEADER_KEYWORDS:
            if kw.lower() in t:
                return True
        return False

    # ---------------- Template detection ----------------
    def detect_template_type(self, soup) -> str:
        # Blue table: look for td with background style and research header text nearby
        td_candidate = soup.find('td', attrs={'style': re.compile(r'background', re.I)})
        if td_candidate:
            if any(self.header_keyword_in_text((td.get_text() or '')) for td in soup.find_all('td') if td):
                return 'BLUE_TABLE'
        if soup.find('h1', class_=lambda c: c and 'text-center' in c):
            return 'H1_TEXTCENTER'
        if soup.find('li', class_=lambda c: c and 'people-info' in c):
            return 'PEOPLE_INFO'
        # retain previous detections
        if soup.find('div', class_='naspool_tab'):
            return 'NASPOOL'
        if soup.find('div', class_='people-detail'):
            return 'PEOPLE_DETAIL'
        if soup.find('div', class_='teacher-box'):
            return 'TEMPLATE_1'
        if soup.find('h1', class_='arti_title'):
            return 'TEMPLATE_2'
        if soup.find('div', class_='content'):
            return 'TEMPLATE_CONTENT_DIV'
        return 'UNKNOWN'

    # ---------------- Name extractors ----------------
    def extract_name_h1_textcenter(self, soup) -> Optional[str]:
        h1 = soup.find('h1', class_=lambda c: c and 'text-center' in c)
        if h1:
            return h1.get_text(strip=True)
        fh1 = soup.find('h1')
        if fh1:
            return fh1.get_text(strip=True)
        return None

    def extract_name_people_info(self, soup) -> Optional[str]:
        for li in soup.find_all('li', class_=lambda c: c and 'people-info' in c):
            txt = li.get_text(separator=' ', strip=True)
            if '姓名' in txt:
                name = re.sub(r'^\s*姓名[:：\s]*', '', txt).strip()
                if name:
                    return name
            strong = li.find('strong')
            if strong and '姓名' in strong.get_text():
                # return following text nodes
                remainder = strong.next_sibling
                if remainder:
                    return self.normalize_text(str(remainder))
        return None

    # ---------------- Email extractors ----------------
    def extract_email_h1page(self, soup) -> Optional[str]:
        for p in soup.find_all(['p', 'td', 'li', 'span']):
            text = p.get_text(separator=' ', strip=True)
            if '电子邮箱' in text or '电子邮件' in text or '邮箱' in text:
                m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', text)
                if m:
                    return m.group(1)
                span = p.find('span', attrs={'lang': re.compile(r'en', re.I)})
                if span:
                    stext = span.get_text(strip=True)
                    m2 = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', stext)
                    if m2:
                        return m2.group(1)
                parts = re.split(r'电子邮箱[:：\s]+|电子邮件[:：\s]+', text, maxsplit=1)
                if len(parts) > 1:
                    cand = parts[1].strip()
                    cand = cand.strip('：:;.,; ')
                    m3 = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', cand)
                    if m3:
                        return m3.group(1)
                    cand = cand.replace(' at ', '@').replace('[at]', '@').replace('(at)', '@')
                    if '@' in cand:
                        return cand.split()[0].strip()
        return None

    def deobfuscate_email(self, s: str) -> str:
        if not s:
            return s
        s = s.strip()
        s = s.replace(' at ', '@').replace('[at]', '@').replace('(at)', '@')
        s = re.sub(r'\s+', '', s)
        m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', s)
        return m.group(1) if m else s

    def extract_email_people_info(self, soup) -> Optional[str]:
        for li in soup.find_all('li', class_=lambda c: c and 'people-info' in c):
            txt = li.get_text(separator=' ', strip=True)
            if '电子邮件' in txt or '电子邮箱' in txt or '邮箱' in txt:
                m = re.search(r'([A-Za-z0-9._%+\-]+\s*(?:@|at|\[at\]|\(at\))\s*[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', txt, flags=re.I)
                if m:
                    return self.deobfuscate_email(m.group(1))
                parts = re.split(r'电子邮件[:：\s]+|电子邮箱[:：\s]+', txt, maxsplit=1)
                if len(parts) > 1:
                    cand = parts[1].strip()
                    return self.deobfuscate_email(cand)
        m = re.search(r'([A-Za-z0-9._%+\-]+(?:@| at | AT )[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', soup.get_text(separator=' ', strip=True))
        if m:
            return self.deobfuscate_email(m.group(1))
        return None

    def extract_email_template1(self, soup) -> Optional[str]:
        try:
            email_elem = soup.select_one('div.teacher-field.dh > span.field-info.i2')
            if email_elem:
                text = email_elem.get_text(strip=True).replace('邮箱：', '').replace('邮箱:', '').strip()
                m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', text)
                if m:
                    return m.group(1)
            return self.extract_email_from_contact_section(soup) or self.extract_email_from_content_div(soup)
        except Exception:
            return None

    def extract_email_template2(self, soup) -> Optional[str]:
        try:
            for p in soup.find_all('p'):
                text = p.get_text(separator=' ', strip=True)
                if re.search(r'\b(e-?mail|email|邮箱|电子邮件)\b', text, flags=re.IGNORECASE):
                    m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', text)
                    if m:
                        return m.group(1)
            return self.extract_email_from_contact_section(soup) or self.extract_email_from_content_div(soup)
        except Exception:
            return None

    def extract_email_from_contact_section(self, soup) -> Optional[str]:
        try:
            for h3 in soup.find_all('h3'):
                h3_text = (h3.get_text(strip=True) or '').lower()
                if 'contact' in h3_text or '联系方式' in h3_text:
                    for sib in h3.find_next_siblings():
                        if sib.name and sib.name.lower() == 'p':
                            text = sib.get_text(separator=' ', strip=True)
                            if re.search(r'\b(e-?mail|email|邮箱)\b', text, flags=re.IGNORECASE):
                                m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', text)
                                if m:
                                    return m.group(1).strip()
                        if sib.name and sib.name.lower().startswith('h'):
                            break
            return None
        except Exception:
            return None

    def extract_email_from_content_div(self, soup) -> Optional[str]:
        try:
            content_div = soup.find('div', class_='content')
            if not content_div:
                return None
            m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', content_div.get_text(separator=' ', strip=True))
            if m:
                return m.group(1)
            return None
        except Exception:
            return None

    # ---------------- Research extractors ----------------
    def extract_research_blue_table(self, soup) -> str:
        try:
            header_td = None
            for td in soup.find_all('td'):
                t = self.normalize_text(td.get_text(separator=' ', strip=True))
                if self.header_keyword_in_text(t) and self.is_blue_style_td(td):
                    header_td = td
                    break
            if not header_td:
                # looser search: find td containing any research header keyword
                for td in soup.find_all('td'):
                    t = self.normalize_text(td.get_text(separator=' ', strip=True))
                    if self.header_keyword_in_text(t):
                        header_td = td
                        break
            if not header_td:
                return ""
            collected = []
            stop_marker = self.BLUE_TABLE_STOP_MARKER
            found = False
            # iterate over all td tags preserving document order and start collecting after header_td
            for td in soup.find_all('td'):
                if not found:
                    if td is header_td:
                        found = True
                    continue
                ttxt = self.text_of_tag(td)
                if not ttxt.strip():
                    continue
                if any(stop in ttxt for stop in self.STOP_HEADING_VARIANTS) or stop_marker in ttxt or '教育及' in ttxt:
                    break
                if any(keyword in ttxt for keyword in ['近五年承担项目', '近五年代表性论文', '代表论著', '获奖及荣誉']):
                    break
                collected.append(ttxt)
                if len(collected) >= 8:
                    break
            if not collected:
                inner_text = header_td.get_text(separator='\n', strip=True)
                inner_text = re.sub(r'.*?研究方向[:：\s]*', '', inner_text, count=1)
                inner_text = inner_text.strip()
                if inner_text:
                    candidate = self.clean_research_text(inner_text)
                    return candidate if candidate else ""
                return ""
            candidate = '\n\n'.join([c for c in collected if c and len(c.strip()) > 0])
            candidate = self.clean_research_text(candidate)
            return candidate
        except Exception as e:
            logger.debug("Error in extract_research_blue_table: %s", e)
            return ""

    def extract_research_people_info(self, soup) -> str:
        try:
            for h4 in soup.find_all('h4'):
                ht = self.normalize_text(h4.get_text(strip=True))
                if self.header_keyword_in_text(ht):
                    collected = []
                    for sib in h4.find_next_siblings():
                        if isinstance(sib, Tag) and sib.name == 'h4':
                            break
                        if isinstance(sib, Tag):
                            stext = self.text_of_tag(sib)
                            if stext and len(stext.strip()) > 3:
                                collected.append(stext)
                    if collected:
                        candidate = '\n\n'.join(collected)
                        candidate = self.clean_research_text(candidate)
                        if candidate and len(candidate) > 5:
                            return candidate
            # fallback to CV search (简历)
            for h4 in soup.find_all('h4'):
                ht = self.normalize_text(h4.get_text(strip=True))
                if '简' in ht and '历' in ht:
                    for sib in h4.find_next_siblings():
                        stext = self.text_of_tag(sib)
                        if not stext:
                            continue
                        m = re.search(r'(主要从事[^。；\n]+[。；]?)', stext)
                        if not m:
                            m = re.search(r'(研究方向(?:包括|：)?[^。；\n]+[。；]?)', stext)
                        if m:
                            candidate = self.clean_research_text(m.group(1))
                            if candidate:
                                return candidate
                        if ('研究' in stext or '从事' in stext) and len(stext) > 30:
                            candidate = self.clean_research_text(stext.split('。')[0])
                            if candidate:
                                return candidate
            return ""
        except Exception as e:
            logger.debug("Error in extract_research_people_info: %s", e)
            return ""

    def extract_research_from_content_div(self, soup) -> str:
        try:
            content_div = soup.find('div', class_='content')
            if not content_div:
                return ""
            for keyword in self.RESEARCH_HEADER_KEYWORDS:
                for tag in content_div.find_all(['h3', 'p', 'div']):
                    txt = self.normalize_text(tag.get_text())
                    if keyword in txt:
                        parts = []
                        for sib in tag.find_next_siblings():
                            if sib.name and sib.name.lower().startswith('h'):
                                break
                            stext = self.normalize_text(sib.get_text(strip=True))
                            if stext:
                                parts.append(stext)
                        candidate = '\n\n'.join(parts)
                        return self.clean_research_text(candidate) if candidate else ""
            return ""
        except Exception:
            return ""

    # ---------------- Meta and cleaning ----------------
    def extract_from_meta_description(self, soup) -> str:
        try:
            for meta_name in ['description', 'og:description', 'twitter:description']:
                meta = soup.find('meta', attrs={'name': meta_name}) or soup.find('meta', attrs={'property': meta_name})
                if meta and meta.get('content'):
                    content = meta.get('content')
                    content = html.unescape(content)
                    m = re.search(r'(研究方向[:：]?\s*[^。；]+)', content)
                    if m:
                        return self.clean_research_text(m.group(1))
            return ""
        except Exception:
            return ""

    def clean_research_text(self, text: str) -> str:
        if not text:
            return ""
        text = html.unescape(text)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;|\xa0', ' ', text)
        text = re.sub(r'(doi|DOI)[\s:]*10\.\d{4,}[^\s]*', '', text)
        text = re.sub(r'https?://[^\s]+', '', text)
        for keyword in self.MISLEADING_CONTENT:
            if keyword in ['doi', 'DOI', 'http://', 'https://']:
                continue
            lines = text.split('\n')
            lines = [line for line in lines if keyword not in line]
            text = '\n'.join(lines)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = '\n'.join([ln.strip() for ln in text.splitlines() if ln.strip()])
        text = text.strip()
        if getattr(self.args, 'truncate', 0) and self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        return text

    # ---------------- Driver ----------------
    def setup_driver(self):
        options = Options()
        if self.args.headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        options.add_argument('--disable-gpu')
        options.add_argument('--lang=zh-CN')
        try:
            driver_path = ChromeDriverManager().install()
            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.implicitly_wait(10)
        except Exception as e:
            logger.error("WebDriver start error: %s", e)
            raise

    def close_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

    def random_delay(self):
        delay = random.uniform(self.args.delay_min, self.args.delay_max)
        time.sleep(delay)

    # ---------------- Main scraping flow ----------------
    def scrape_profile(self, url: str) -> Optional[Dict[str, str]]:
        normalized_url = url.strip()
        if normalized_url in self.processed_urls:
            logger.info(f"Skipping duplicate URL: {url}")
            return None
        logger.info(f"Processing: {url}")
        for attempt in range(self.args.retries + 1):
            try:
                self.driver.get(url)
                WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(0.8)
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                template = self.detect_template_type(soup)
                if self.args.debug:
                    logger.debug(f"Template detected: {template}")
                name = "Unknown"
                email = "Not found"
                research = "Not found"

                if template == 'BLUE_TABLE':
                    name = self.extract_name_h1_textcenter(soup) or self.extract_name_template2(soup) or "Unknown"
                    e = self.extract_email_h1page(soup)
                    email = e if e else (self.extract_email_from_content_div(soup) or "Not found")
                    research = self.extract_research_blue_table(soup) or \
                               self.extract_research_from_content_div(soup) or \
                               self.extract_from_meta_description(soup) or "Not found"

                elif template == 'H1_TEXTCENTER':
                    name = self.extract_name_h1_textcenter(soup) or "Unknown"
                    email = self.extract_email_h1page(soup) or (self.extract_email_from_content_div(soup) or "Not found")
                    research = self.extract_research_blue_table(soup) or self.extract_research_from_content_div(soup) or "Not found"

                elif template == 'PEOPLE_INFO':
                    name = self.extract_name_people_info(soup) or "Unknown"
                    email = self.extract_email_people_info(soup) or "Not found"
                    research = self.extract_research_people_info(soup) or self.extract_research_from_content_div(soup) or "Not found"

                elif template == 'PEOPLE_DETAIL':
                    name = self.extract_name_template2(soup) or self.extract_name_template1(soup) or "Unknown"
                    email = self.extract_email_template2(soup) or "Not found"
                    research = self.extract_research_people_info(soup) or self.extract_research_template2(soup) or "Not found"

                elif template == 'NASPOOL':
                    name = self.extract_name_template1(soup) or "Unknown"
                    email = self.extract_email_template1(soup) or "Not found"
                    research = self.extract_research_from_content_div(soup) or "Not found"

                else:
                    name = self.extract_name_template1(soup) or self.extract_name_template2(soup) or self.extract_name_h1_textcenter(soup) or "Unknown"
                    email = (self.extract_email_template1(soup) or self.extract_email_template2(soup) or self.extract_email_people_info(soup) or self.extract_email_h1page(soup) or "Not found")
                    research = (self.extract_research_blue_table(soup) or self.extract_research_people_info(soup) or self.extract_research_from_content_div(soup) or self.extract_from_meta_description(soup) or "Not found")

                name = name or "Unknown"
                email = email or "Not found"
                if email and ' at ' in email:
                    email = self.deobfuscate_email(email)
                research = research or "Not found"
                if research and len(research) < 5:
                    research = "Not found"

                self.processed_urls.add(normalized_url)
                logger.info(f"Extraction -> Name: {name}, Email: {email}, Research: {research[:140]}{'...' if len(research)>140 else ''}")
                return {
                    'name': name,
                    'email': email,
                    'research_interest': research,
                    'profile_link': url
                }
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                if attempt == self.args.retries:
                    self.processed_urls.add(normalized_url)
                    return {'name': 'Unknown', 'email': 'Not found', 'research_interest': 'Not found', 'profile_link': url}
                time.sleep(1.5)
        return None

    # ---------------- Output ----------------
    def write_profile(self, profile: Dict[str, str], output_file: Path):
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"Name: {profile['name']}\n")
            f.write(f"Email: {profile['email']}\n")
            f.write(f"Research interest: {profile['research_interest']}\n")
            f.write(f"Profile link: {profile['profile_link']}\n")
            f.write("---\n\n")

    def write_json_profile(self, profiles: List[Dict], output_file: Path):
        json_file = output_file.with_suffix('.json')
        json_file.parent.mkdir(parents=True, exist_ok=True)
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)

    def run(self):
        input_file = Path(self.args.input_file)
        if not input_file.exists():
            logger.error(f"Input file not found: {input_file}")
            return
        with open(input_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
        logger.info(f"Found {len(urls)} URLs to process")
        output_file = Path(self.args.output_file)
        if output_file.exists() and not self.args.append:
            output_file.unlink()
        output_file.parent.mkdir(parents=True, exist_ok=True)

        self.setup_driver()
        profiles_list = []
        try:
            processed_count = 0
            for i, url in enumerate(urls):
                if self.args.max_profiles > 0 and processed_count >= self.args.max_profiles:
                    logger.info(f"Reached maximum profile limit: {self.args.max_profiles}")
                    break
                profile = self.scrape_profile(url)
                if profile:
                    self.write_profile(profile, output_file)
                    profiles_list.append(profile)
                    processed_count += 1
                if i < len(urls) - 1:
                    self.random_delay()
            if self.args.json_output and profiles_list:
                self.write_json_profile(profiles_list, output_file)
                logger.info(f"Saved JSON output to {output_file.with_suffix('.json')}")
        finally:
            self.close_driver()
        logger.info(f"Completed! Processed {processed_count} profiles")
        logger.info(f"Results saved to: {output_file}")

# ---------------- CLI ----------------
def main():
    parser = argparse.ArgumentParser(description='Faculty Profile Scraper (extended header/color matching)')
    parser.add_argument('--input-file', default='urls.txt', help='Input file containing URLs (one per line)')
    parser.add_argument('--output-file', default='output.txt', help='Output file for results')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--delay-min', type=float, default=1.0, help='Minimum delay between requests (seconds)')
    parser.add_argument('--delay-max', type=float, default=3.0, help='Maximum delay between requests (seconds)')
    parser.add_argument('--max-profiles', type=int, default=0, help='Max number of profiles to process (0=unlimited)')
    parser.add_argument('--retries', type=int, default=2, help='Number of retries for failed requests')
    parser.add_argument('--truncate', type=int, default=4000, help='Max length for research text (0=no limit)')
    parser.add_argument('--append', action='store_true', help='Append to output file instead of overwriting')
    parser.add_argument('--json-output', action='store_true', help='Also save output as JSON')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with diagnostic output')
    args = parser.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    scraper = DualTemplateFacultyProfileScraper(args)
    scraper.run()

if __name__ == '__main__':
    main()
