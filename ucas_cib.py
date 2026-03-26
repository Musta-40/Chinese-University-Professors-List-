#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper - Dual Template + People/Naspool Support
Updated to handle:
 - Source 1: div.naspool_tab -> td.pname, Research Interest in p.ptitle + div.pool_textcon
 - Sources 2/3: div.people-detail -> li.people-list.name, email li with '电子邮件：', research in h3.tit -> following div.people-des mt20
Includes previous robustness improvements (safe regex, output dir handling, meta fallback, year/DOI checks).
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
    """Scraper supporting multiple templates (no AI)."""

    # ---------- Heading / stop variants (kept & reused) ----------
    START_HEADING_VARIANTS = [
        'Main Research Areas (Recruitment Fields) and Content',
        'Primary Research Areas (Graduate Programs) and Content',
        'Research Interests',
        'Main Research Directions (Recruitment Fields) and Content',
        'Research Focus',
        'Research Areas',
        'Research Focus (Recruitment Fields)',
        'Main Research Areas (Graduate Programs)',
        'Main Research Directions (Recruitment Specialties) and Content',
        'Primary Research Directions and Specializations',
        'Main Research Directions (Admissions Major) and Content',
        'Main Research Directions',
        'Research Fields of Interests',
        'Research Interest',
        '　RESEARCH INTERESTS',
        'Research Field of Interest:',
    ]

    STOP_HEADING_VARIANTS = [
        'Representative Papers (Last Five Years)',
        'Selected Publications',
        'Publication',
        'Pulications (Chronologically, First Author, Corresponding Author):',
        'Awards and Honors',
        'Education',
        'Selected Publications (Last Five Years)',
        'Professional Titles and Honors',
        'Lab Recruitment',
        'Honors & Awards',
        'Job Opportunities',
        'Study Experience',
    ]

    MISLEADING_HEADINGS = [
        'Education and Work Experience',
        'Academic Achievements and Impact',
        'Ongoing Projects (Principal Investigator Only)',
        'Current Research Projects (Main Investigator Only)',
        'Current Projects (as Principal Investigator)',
        'Contact Information',
        'Personal Profile',
        'Recruitment',
        'Major Research Achievements'
    ]

    YEAR_PATTERN = r'\b(19|20)\d{2}\b'
    DOI_PATTERN = r'(doi|DOI)[\s:]*10\.\d{4,}'
    MISLEADING_CONTENT = [
        'doi', 'DOI', '10.', 'http://', 'https://',
        'ISBN', 'ISSN', '期刊', '会议', 'pp.', 'Vol.',
        '年第', '月第', 'IF=', '影响因子', 'SCI', 'EI',
        '第一作者', '通讯作者', '发表于', 'Email', 'email'
    ]

    # Source1-specific stop keywords (English as provided)
    NASPOOL_STOP_KEYWORDS = [
        'Public Services', 'Honors', 'Seleted Publication', 'Supported Projects',
        'Public Services'.lower(), 'honors'.lower(), 'seleted publication'.lower(), 'supported projects'.lower()
    ]

    # Sources 2/3 Chinese stop headings for research direction
    PEOPLE_STOP_HEADINGS = [
        '获奖及荣誉', '承担科研项目情况', '代表论著', '个人简历',
        '社会任职'
    ]

    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls: Set[str] = set()

    # ---------- Helpers ----------
    @staticmethod
    def normalize_heading_text(text: Optional[str]) -> str:
        if not text:
            return ''
        return re.sub(r'\s+', ' ', text).strip()

    @staticmethod
    def text_of_tag(tag: Tag) -> str:
        """Return cleaned text of a tag, preserving common list punctuation and newlines."""
        if not tag:
            return ''
        # join text nodes but keep list items separated by newlines
        parts = []
        for child in tag.descendants:
            if isinstance(child, NavigableString):
                parts.append(str(child))
            elif isinstance(child, Tag) and child.name in ('li', 'p', 'div'):
                # add a newline boundary for block items to keep structure
                parts.append('\n')
        text = ''.join(parts)
        text = html.unescape(text)
        text = re.sub(r'\s+\n\s+', '\n', text)
        text = re.sub(r'\n{2,}', '\n\n', text)
        return text.strip()

    def is_messy_heading(self, h: Tag) -> bool:
        try:
            raw_text = self.normalize_heading_text(h.get_text(separator=' ', strip=True))
            if not raw_text:
                contents = (h.decode_contents() or '').strip()
                if re.search(r'<br\s*/?>', contents, flags=re.IGNORECASE):
                    return True
                if re.sub(r'<[^>]+>', '', contents).strip() == '':
                    return True
                return True
            if re.match(r'^[\W_]+$', raw_text):
                return True
            return False
        except Exception:
            return False

    # ---------- Template detection ----------
    def detect_template_type(self, soup) -> str:
        # Priority: NASPOOL, PEOPLE_DETAIL, teacher-box, arti_title, content
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

    # ---------- Name extraction ----------
    def extract_name_from_title(self, soup) -> Optional[str]:
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        return None

    def extract_name_template1(self, soup) -> str:
        try:
            name_elem = soup.select_one('div.teacher-field.title > span.field-info')
            if name_elem:
                name = name_elem.get_text(strip=True)
                name = re.sub(r'\s*(博士|硕士|教授|副教授|讲师|助理研究员|研究员)\s*', '', name)
                if name:
                    return name
            return self.extract_name_from_title(soup) or "Unknown"
        except Exception:
            return "Unknown"

    def extract_name_template2(self, soup) -> str:
        try:
            h1 = soup.find('h1', class_='arti_title')
            if h1:
                n = h1.get_text(strip=True)
                if n:
                    return n
            return self.extract_name_from_title(soup) or "Unknown"
        except Exception:
            return "Unknown"

    # ---------- NASPOOL (Source 1) extractors ----------
    def extract_name_naspool(self, soup) -> Optional[str]:
        try:
            el = soup.select_one('div.naspool_tab table td.pname b')
            if el:
                return el.get_text(strip=True)
            # fallback: try td.pname text
            el2 = soup.select_one('div.naspool_tab table td.pname')
            if el2:
                return el2.get_text(strip=True)
            return None
        except Exception:
            return None

    def extract_email_naspool(self, soup) -> Optional[str]:
        try:
            table = soup.select_one('div.naspool_tab table')
            if table:
                for tr in table.find_all('tr'):
                    # check any 'th' or first child text for 'Email' or '邮箱'
                    th = tr.find(['th', 'td'])
                    if th:
                        th_text = (th.get_text() or '').strip().lower()
                        if 'email' in th_text or '邮箱' in th_text or '电子邮件' in th_text:
                            # find the td cell for email
                            td = tr.find_all(['td'])
                            # if table row has at least one td, select the last or the first after th
                            if len(td) >= 1:
                                candidate = td[-1].get_text(separator=' ', strip=True)
                                m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', candidate)
                                if m:
                                    return m.group(1).strip()
                                # if no explicit email pattern, return raw candidate
                                return candidate
                # fallback: search whole table text for an email
                m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', table.get_text(separator=' ', strip=True))
                if m:
                    return m.group(1)
            # last resort: search whole page
            m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', soup.get_text(separator=' ', strip=True))
            if m:
                return m.group(1)
            return None
        except Exception:
            return None

    def extract_research_naspool(self, soup) -> str:
        """
        Find <p class="ptitle"><b>Research Interest</b></p> then the immediately following
        <div class="pool_textcon">, extract its text, and optionally collect subsequent
        non-heading siblings until a stop p.ptitle is encountered.
        """
        try:
            # find all p.ptitle elements
            for p in soup.find_all('p', class_='ptitle'):
                # check for a <b> child with expected heading
                b = p.find('b')
                heading = (b.get_text(strip=True) if b else p.get_text(strip=True)).lower()
                if 'research' in heading and 'interest' in heading or '研究' in heading and '兴趣' in heading:
                    # find next sibling div.pool_textcon (skip whitespace)
                    pool_div = p.find_next_sibling(lambda t: isinstance(t, Tag) and t.name == 'div' and 'pool_textcon' in (t.get('class') or []))
                    collected = []
                    if pool_div:
                        collected.append(self.text_of_tag(pool_div))
                        # collect further siblings until stop p.ptitle encountered
                        for sib in pool_div.find_next_siblings():
                            if isinstance(sib, Tag) and sib.name == 'p' and 'ptitle' in (sib.get('class') or []):
                                # find the inner <b> text and check for stop keywords
                                b2 = sib.find('b')
                                sib_heading = (b2.get_text(strip=True) if b2 else sib.get_text(strip=True)).strip().lower()
                                # stop if matches any stop keyword
                                if any(sk.lower() in sib_heading for sk in self.NASPOOL_STOP_KEYWORDS):
                                    break
                                else:
                                    # if it's a non-stop heading, continue (but conservative: break)
                                    break
                            # if it's another block tag, include until stop
                            if isinstance(sib, Tag):
                                # if sibling contains a stop keyword inside text, break
                                stext = sib.get_text(separator=' ', strip=True)
                                if any(sk.lower() in stext.lower() for sk in self.NASPOOL_STOP_KEYWORDS):
                                    break
                                # if it's a heading-like tag (<h3> etc) that looks like publications/awards, break
                                if sib.name and sib.name.lower().startswith('h'):
                                    if any(stop.lower() in stext.lower() for stop in self.STOP_HEADING_VARIANTS):
                                        break
                                collected.append(self.text_of_tag(sib))
                    # fallback: sometimes research provided inline in a <div class="pool_textcon"> without siblings
                    if collected:
                        candidate = '\n\n'.join([c for c in collected if c and len(c.strip()) > 0])
                        candidate = self.clean_research_text(candidate)
                        if candidate and len(candidate) > 5:
                            return candidate
            return ""
        except Exception as e:
            logger.debug("Error in extract_research_naspool: %s", str(e))
            return ""

    # ---------- PEOPLE_DETAIL (Sources 2 & 3) extractors ----------
    def extract_name_people_detail(self, soup) -> Optional[str]:
        try:
            container = soup.find('div', class_='people-detail')
            if not container:
                return None
            # li with class containing both 'people-list' and 'name'
            for li in container.find_all('li'):
                cls = li.get('class') or []
                if 'people-list' in cls and 'name' in cls:
                    span = li.find('span')
                    if span:
                        return span.get_text(strip=True)
            # fallback: first li.people-list with 'name' in class attribute string
            for li in container.find_all('li'):
                if 'name' in ' '.join(li.get('class') or []):
                    span = li.find('span')
                    if span:
                        return span.get_text(strip=True)
            return None
        except Exception:
            return None

    def extract_email_people_detail(self, soup) -> Optional[str]:
        try:
            container = soup.find('div', class_='people-detail')
            if not container:
                return None
            for li in container.find_all('li'):
                txt = li.get_text(separator=' ', strip=True)
                if '电子邮件' in txt or '电子郵件' in txt or '邮箱' in txt or 'Email' in txt:
                    # extract email address from li
                    m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', txt)
                    if m:
                        return m.group(1).strip()
                    # strip label e.g., '电子邮件：xxx'
                    # find colon and return remainder
                    parts = re.split(r'[:：]\s*', txt, maxsplit=1)
                    if len(parts) == 2:
                        cand = parts[1].strip()
                        if cand:
                            # if contains whitespace, maybe additional info; attempt email regex
                            m2 = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', cand)
                            if m2:
                                return m2.group(1)
                            return cand
            # fallback: search whole people-detail block for email
            if container:
                m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', container.get_text(separator=' ', strip=True))
                if m:
                    return m.group(1)
            return None
        except Exception:
            return None

    def extract_research_people_detail(self, soup) -> str:
        """
        Find the <h3 class="tit"><span>研究方向</span></h3> and take the immediately
        following <div class="people-des mt20"> (or class including 'people-des'), then collect its text.
        Stop when the next h3.tit has a span matching any PEOPLE_STOP_HEADINGS.
        """
        try:
            # find all h3.tit
            for h3 in soup.find_all('h3', class_='tit'):
                span = h3.find('span')
                if not span:
                    continue
                span_text = span.get_text(strip=True)
                if '研究方向' in span_text:
                    # find next sibling div whose class list contains 'people-des'
                    target_div = h3.find_next_sibling(lambda t: isinstance(t, Tag) and t.name == 'div' and ('people-des' in (t.get('class') or [])))
                    collected = []
                    if target_div:
                        collected.append(self.text_of_tag(target_div))
                        for sib in target_div.find_next_siblings():
                            # stop if encounter an h3.tit with stop heading
                            if isinstance(sib, Tag) and sib.name == 'h3' and 'tit' in (sib.get('class') or []):
                                s_span = sib.find('span')
                                s_text = s_span.get_text(strip=True) if s_span else sib.get_text(strip=True)
                                if any(stop in s_text for stop in self.PEOPLE_STOP_HEADINGS):
                                    break
                                else:
                                    break
                            if isinstance(sib, Tag):
                                # if sibling text contains stop headings, break
                                stext = sib.get_text(separator=' ', strip=True)
                                if any(stop in stext for stop in self.PEOPLE_STOP_HEADINGS):
                                    break
                                collected.append(self.text_of_tag(sib))
                    if collected:
                        candidate = '\n\n'.join([c for c in collected if c and len(c.strip()) > 0])
                        candidate = self.clean_research_text(candidate)
                        if candidate and len(candidate) > 5:
                            return candidate
            return ""
        except Exception as e:
            logger.debug("Error in extract_research_people_detail: %s", str(e))
            return ""

    # ---------- Email extraction (generic fallbacks kept) ----------
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
            for p in content_div.find_all('p'):
                text = p.get_text(separator=' ', strip=True)
                if re.search(r'\b(e-?mail|email|邮箱)\b', text, flags=re.IGNORECASE):
                    m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', text)
                    if m:
                        return m.group(1).strip()
            text_blob = content_div.get_text(separator=' ', strip=True)
            m = re.search(r'\b(e-?mail|email|邮箱)\b.*?([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', text_blob, flags=re.IGNORECASE)
            if m:
                return m.group(2).strip()
            return None
        except Exception:
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
                if re.search(r'\b(e-?mail|email|邮箱)\b', text, flags=re.IGNORECASE):
                    m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', text)
                    if m:
                        return m.group(1)
            email = self.extract_email_from_contact_section(soup) or self.extract_email_from_content_div(soup)
            if email:
                return email
            m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', soup.get_text(separator=' ', strip=True))
            if m:
                return m.group(1)
            return None
        except Exception:
            try:
                m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', soup.get_text(separator=' ', strip=True))
                if m:
                    return m.group(1)
            except Exception:
                pass
            return None

    # ---------- Consolidated research extraction (content div) ----------
    def extract_research_from_content_div(self, soup) -> str:
        try:
            content_div = soup.find('div', class_='content')
            if not content_div:
                return ""
            start_variants = [self.normalize_heading_text(s).lower() for s in self.START_HEADING_VARIANTS]
            stop_variants = [self.normalize_heading_text(s).lower() for s in self.STOP_HEADING_VARIANTS]
            misleading_variants = [self.normalize_heading_text(s).lower() for s in self.MISLEADING_HEADINGS]
            for h3 in content_div.find_all('h3'):
                heading_text = self.normalize_heading_text(h3.get_text(strip=True)).lower()
                is_start = any(sv.strip().lower() in heading_text for sv in start_variants)
                if not is_start:
                    continue
                collected_parts: List[str] = []
                for sibling in h3.find_next_siblings():
                    if isinstance(sibling, Tag) and sibling.name and sibling.name.lower() == 'h3':
                        sib_text = self.normalize_heading_text(sibling.get_text(strip=True)).lower()
                        if self.is_messy_heading(sibling):
                            logger.debug("Stopping due to messy heading pattern.")
                            break
                        if any(stop.strip().lower() in sib_text for stop in stop_variants):
                            logger.debug(f"Stopping at stop heading: {sib_text}")
                            break
                        if any(mis.strip().lower() in sib_text for mis in misleading_variants):
                            logger.debug(f"Stopping at misleading heading: {sib_text}")
                            break
                        if re.search(self.YEAR_PATTERN, sib_text) or re.search(self.DOI_PATTERN, sib_text):
                            logger.debug("Stopping at heading containing year or DOI.")
                            break
                        continue
                    text = sibling.get_text(separator=' ', strip=True)
                    if not text:
                        continue
                    if re.search(self.YEAR_PATTERN, text) or re.search(self.DOI_PATTERN, text):
                        logger.debug("Stopping at sibling containing year or DOI.")
                        break
                    if any(stop.strip().lower() in text.lower() for stop in stop_variants + misleading_variants):
                        logger.debug("Stopping because sibling contains a stop/misleading keyword.")
                        break
                    if len(text) >= 6:
                        collected_parts.append(text)
                if collected_parts:
                    research_text = '\n\n'.join(collected_parts)
                    research_text = self.clean_research_text(research_text)
                    if research_text and len(research_text) > 5:
                        logger.info(f"Research extracted (content div start='{h3.get_text()[:60]}'): {len(research_text)} chars")
                        return research_text
            # Fallback: paragraphs/list items
            for p in content_div.find_all(['p', 'div', 'li']):
                txt = p.get_text(strip=True)
                if any(k in txt for k in ['研究方向', '研究兴趣', 'Research Interest', 'Research Interests']):
                    parts = [txt]
                    count = 0
                    for sib in p.find_next_siblings():
                        if count >= 6:
                            break
                        stext = sib.get_text(strip=True)
                        if not stext:
                            continue
                        if any(stop.lower() in stext.lower() for stop in stop_variants + misleading_variants):
                            break
                        if re.search(self.YEAR_PATTERN, stext) or re.search(self.DOI_PATTERN, stext):
                            break
                        parts.append(stext)
                        count += 1
                    candidate = '\n\n'.join(parts)
                    candidate = self.clean_research_text(candidate)
                    if candidate and len(candidate) > 5:
                        logger.info("Research extracted using fallback paragraph search inside content div")
                        return candidate
            return ""
        except Exception as e:
            logger.error(f"Error extracting research from content div: {e}")
            return ""

    # ---------- Template-specific research extraction (kept) ----------
    def extract_research_template1(self, soup) -> str:
        try:
            research_elem = soup.select_one('div.teacher-field.dh > span.field-info.i4 > p')
            if research_elem:
                research_text = research_elem.get_text(strip=True)
                for keyword in ['研究方向：', '研究方向:', '研究兴趣：', '研究兴趣:']:
                    if research_text.startswith(keyword):
                        research_text = research_text[len(keyword):].strip()
                research_text = self.clean_research_text(research_text)
                if research_text and len(research_text) > 5:
                    return research_text
            research_elem = soup.select_one('div.teacher-field.dh > span.field-info.i4')
            if research_elem:
                research_text = research_elem.get_text(strip=True)
                for keyword in ['研究方向：', '研究方向:', '研究兴趣：', '研究兴趣:']:
                    if research_text.startswith(keyword):
                        research_text = research_text[len(keyword):].strip()
                research_text = self.clean_research_text(research_text)
                if research_text and len(research_text) > 5:
                    return research_text
            cd = self.extract_research_from_content_div(soup)
            if cd:
                return cd
            meta_extracted = self.extract_from_meta_description(soup)
            if meta_extracted:
                return meta_extracted
            return ""
        except Exception:
            return ""

    def extract_research_template2(self, soup) -> str:
        try:
            research_content = []
            found_start = False
            for keyword in ['研究兴趣', '研究方向']:
                for elem in soup.find_all(['p', 'h2', 'h3', 'h4', 'strong', 'div']):
                    elem_text = elem.get_text(strip=True)
                    if keyword in elem_text:
                        found_start = True
                        if elem_text != keyword and len(elem_text) > len(keyword) + 5:
                            content = elem_text.replace(keyword, '').strip()
                            if content and not any(stop in content for stop in self.STOP_HEADING_VARIANTS):
                                research_content.append(content)
                        for sibling in elem.find_next_siblings():
                            sibling_text = sibling.get_text(strip=True)
                            if any(stop in sibling_text for stop in self.STOP_HEADING_VARIANTS):
                                break
                            if re.search(self.YEAR_PATTERN, sibling_text) or re.search(self.DOI_PATTERN, sibling_text):
                                break
                            if sibling_text and len(sibling_text) > 5:
                                research_content.append(sibling_text)
                        if research_content:
                            break
                if found_start:
                    break
            if research_content:
                research_text = '\n'.join(research_content)
                research_text = self.clean_research_text(research_text)
                if research_text and len(research_text) > 5:
                    return research_text
            cd = self.extract_research_from_content_div(soup)
            if cd:
                return cd
            meta_extracted = self.extract_from_meta_description(soup)
            if meta_extracted:
                return meta_extracted
            return ""
        except Exception:
            return ""

    # ---------- Meta description extraction ----------
    def extract_from_meta_description(self, soup) -> str:
        try:
            candidates = [
                ('name', 'description'),
                ('property', 'og:description'),
                ('name', 'twitter:description'),
                ('property', 'description')
            ]
            content = ""
            for attr, val in candidates:
                meta = soup.find('meta', attrs={attr: val})
                if meta and meta.get('content'):
                    content = meta.get('content')
                    if content:
                        break
            if not content:
                return ""
            content = html.unescape(content).replace('\xa0', ' ').replace('&nbsp;', ' ')
            pattern = re.compile(r'(?:研究方向|研究兴趣|研究领域)[:：]\s*([^；;。．.，,、/]+)', flags=re.UNICODE)
            m = pattern.search(content)
            if m:
                extracted = m.group(1).strip()
                extracted = self.clean_research_text(extracted)
                if extracted:
                    return extracted
            pattern2 = re.compile(r'(?:研究方向|研究兴趣|研究领域)[:：]\s*(.+)$', flags=re.UNICODE)
            m2 = pattern2.search(content)
            if m2:
                tail = m2.group(1).strip()
                tail = re.split(r'(专业|学历|联系方式|；|;|。|\.|，|,|、)', tail)[0].strip()
                tail = self.clean_research_text(tail)
                if tail:
                    return tail
            return ""
        except Exception:
            return ""

    # ---------- Cleaning ----------
    def clean_research_text(self, text: str) -> str:
        if not text:
            return ""
        text = html.unescape(text)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;|\xa0', ' ', text)
        text = re.sub(r'^\s*\b(19|20)\d{2}\b\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*\b(19|20)\d{2}\b\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'(doi|DOI)[\s:]*10\.\d{4,}[^\s]*', '', text)
        text = re.sub(r'https?://[^\s]+', '', text)
        text = re.sub(r'```[\s\S]*?```', '', text, flags=re.DOTALL)
        for keyword in self.MISLEADING_CONTENT:
            if keyword in ['doi', 'DOI', 'http://', 'https://']:
                continue
            lines = text.split('\n')
            lines = [line for line in lines if keyword not in line]
            text = '\n'.join(lines)
        text = re.sub(r'\b(19|20)\d{2}年\d{1,2}月', '', text)
        text = re.sub(r'\bVol\.\s*\d+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bpp\.\s*\d+-\d+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'第\d+期', '', text)
        text = re.sub(r'第\d+卷', '', text)
        text = re.sub(r'IF[=:]\s*[\d.]+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^[\d]+\.\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = '\n'.join([line.strip() for line in text.splitlines() if line.strip()])
        text = text.strip()
        if getattr(self.args, 'truncate', 0) and self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        return text

    # ---------- Driver ----------
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
            logger.error("Failed to start Chrome WebDriver via webdriver-manager: %s", str(e))
            logger.error("If you are on a headless server, ensure Chrome/Chromium and a compatible chromedriver are installed.")
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

    # ---------- Main scraping ----------
    def scrape_profile(self, url: str) -> Optional[Dict[str, str]]:
        normalized_url = url.strip()
        if normalized_url in self.processed_urls:
            logger.info(f"Skipping duplicate URL: {url}")
            return None
        logger.info(f"Processing: {url}")
        for attempt in range(self.args.retries + 1):
            try:
                self.driver.get(url)
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(1.0)
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                template = self.detect_template_type(soup)
                if self.args.debug:
                    logger.debug(f"Template detected: {template}")
                name = "Unknown"
                email = None
                research = ""

                # New templates priority
                if template == 'NASPOOL':
                    # Source 1 style
                    name = self.extract_name_naspool(soup) or self.extract_name_from_title(soup) or "Unknown"
                    email = self.extract_email_naspool(soup) or 'Not found'
                    research = self.extract_research_naspool(soup) or "Not found"
                elif template == 'PEOPLE_DETAIL':
                    # Sources 2 & 3 style
                    name = self.extract_name_people_detail(soup) or self.extract_name_from_title(soup) or "Unknown"
                    email = self.extract_email_people_detail(soup) or self.extract_email_template2(soup) or 'Not found'
                    research = self.extract_research_people_detail(soup) or self.extract_research_template2(soup) or "Not found"
                elif template == 'TEMPLATE_1':
                    name = self.extract_name_template1(soup)
                    email = self.extract_email_template1(soup)
                    research = self.extract_research_template1(soup)
                elif template == 'TEMPLATE_2':
                    name = self.extract_name_template2(soup)
                    email = self.extract_email_template2(soup)
                    research = self.extract_research_template2(soup)
                elif template == 'TEMPLATE_CONTENT_DIV':
                    title_name = self.extract_name_from_title(soup)
                    name = title_name or self.extract_name_template1(soup) or "Unknown"
                    email = self.extract_email_from_contact_section(soup) or self.extract_email_from_content_div(soup) or 'Not found'
                    research = self.extract_research_from_content_div(soup) or self.extract_from_meta_description(soup) or "Not found"
                else:
                    name = self.extract_name_template1(soup) or self.extract_name_template2(soup) or self.extract_name_from_title(soup) or "Unknown"
                    email = self.extract_email_template1(soup) or self.extract_email_template2(soup) or 'Not found'
                    research = self.extract_research_template1(soup) or self.extract_research_template2(soup) or self.extract_research_from_content_div(soup) or self.extract_from_meta_description(soup) or "Not found"

                if not name or name == "Unknown":
                    name = "Unknown"
                if not email:
                    email = "Not found"
                if not research or len(research) < 5:
                    research = "Not found"

                self.processed_urls.add(normalized_url)
                logger.info(f"Extraction -> Name: {name}, Email: {email}, Research: {research[:120]}{'...' if len(research)>120 else ''}")
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
                    return {
                        'name': 'Unknown',
                        'email': 'Not found',
                        'research_interest': 'Not found',
                        'profile_link': url
                    }
                time.sleep(2)
        return None

    # ---------- Output ----------
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
                    logger.info(f"Processed {processed_count}/{len(urls)}: {profile['name']} - {profile['email']}")
                if i < len(urls) - 1:
                    self.random_delay()
            if self.args.json_output and profiles_list:
                self.write_json_profile(profiles_list, output_file)
                logger.info(f"Saved JSON output to {output_file.with_suffix('.json')}")
        finally:
            self.close_driver()
        logger.info(f"Completed! Processed {processed_count} profiles")
        logger.info(f"Results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(description='Faculty Profile Scraper with Dual Template + NASPOOL/People support')
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
