#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
University faculty profile scraper (name, email, research interest only)

Features:
- Prioritized research-section extraction order:
    1) 研究方向
    2) 研究领域
    3) 研究兴趣
    4) 招生方向
  (capturing ALL matches among these)
- Fallbacks:
    A) 出版信息 -> 发表论文
    B) 科研活动 or 科研项目
- Extracts name and email from <div class="bp-enty"> where available
- Robust email de-obfuscation ( " at " / "(at)" / "[at]" -> @ )
- Safe regex usage and defensive parsing
- CLI options: input-file (urls), output-file, headless, delays, retries, json-output, debug
"""
from __future__ import annotations
import argparse
import json
import logging
import random
import re
import time
import html
from pathlib import Path
from typing import Dict, List, Optional, Set

from bs4 import BeautifulSoup, Tag, NavigableString
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# ---------------- logging ----------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("faculty-scraper")


# ---------------- utilities ----------------
def normalize_text(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r'\s+', ' ', s).strip()


def text_of_tag(tag: Tag) -> str:
    """Extract tag text while preserving some block boundaries."""
    if not tag:
        return ""
    parts: List[str] = []
    for node in tag.descendants:
        if isinstance(node, NavigableString):
            parts.append(str(node))
        elif isinstance(node, Tag) and node.name in ('li', 'p', 'div', 'br'):
            parts.append('\n')
    text = ''.join(parts)
    text = html.unescape(text)
    text = re.sub(r'\s+\n\s+', '\n', text)
    text = re.sub(r'\n{2,}', '\n\n', text)
    return text.strip()


def deobfuscate_email(s: str) -> str:
    if not s:
        return s
    s = s.strip()
    s = s.replace('(at)', '@').replace('[at]', '@').replace(' at ', '@').replace(' AT ', '@')
    s = re.sub(r'\s+', '', s)
    m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', s)
    return m.group(1) if m else s


# ---------------- Scraper class ----------------
class FacultyResearchScraper:
    PRIORITY_KEYWORDS = ['研究方向', '研究领域', '研究兴趣', '招生方向']
    FALLBACK_PUBLICATIONS = ('出版信息', '发表论文')
    FALLBACK_PROJECTS = ['科研活动', '科研项目']

    STOP_HEADING_SIGNATURES = [
        '代表论文', '代表论著', '教育及工作经历', '近五年承担项目', '近五年代表性论文',
        '获奖及荣誉', '工作经历', '个人简历'
    ]

    def __init__(self, args):
        self.args = args
        self.driver: Optional[webdriver.Chrome] = None
        self.processed_urls: Set[str] = set()

    # ---------- driver ----------
    def setup_driver(self):
        options = Options()
        if self.args.headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
        options.add_argument('--lang=zh-CN')
        try:
            driver_path = ChromeDriverManager().install()
            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.implicitly_wait(8)
        except Exception as e:
            logger.error("Failed to start Chrome WebDriver: %s", e)
            raise

    def close_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass

    def random_delay(self):
        time.sleep(random.uniform(self.args.delay_min, self.args.delay_max))

    # ---------- page-level detection and extraction ----------
    def load_soup(self, url: str) -> BeautifulSoup:
        assert self.driver is not None
        self.driver.get(url)
        WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        # small pause so JS can render if necessary
        time.sleep(0.6)
        html_src = self.driver.page_source
        return BeautifulSoup(html_src, 'html.parser')

    # ------- name & email: bp-enty style (common in your samples) -------
    def extract_name_email_bp_enty(self, soup: BeautifulSoup) -> (Optional[str], Optional[str]):
        """
        Many samples have:
            <div class="bp-enty">
                <b>NAME&nbsp;&nbsp;男&nbsp;&nbsp;职称...</b>
                ... (lines include '电子邮件： email<br>')
        """
        name = None
        email = None
        enty = soup.find('div', class_='bp-enty')
        if enty:
            # find <b> child with name
            b = enty.find('b')
            if b:
                raw = b.get_text(separator=' ', strip=True)
                # split on non-breaking or multiple spaces and take first token(s) before gender/position
                # split by common separators
                parts = re.split(r'\s{2,}|&nbsp;| |\u00A0|\s*\u3000\s*|\s+', raw)
                if parts:
                    candidate = parts[0].strip()
                    if candidate:
                        name = candidate
            # email line: search text inside enty for '电子邮件'
            enty_text = enty.get_text(separator='\n', strip=True)
            # try to find an email pattern following 电子邮件
            m = re.search(r'电子邮件[:：]?\s*([A-Za-z0-9._%+\-\s@\[\]\(\)]+)', enty_text)
            if m:
                cand = m.group(1).strip()
                cand = deobfuscate_email(cand)
                # extract actual email substring if extra text present
                m2 = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', cand)
                if m2:
                    email = m2.group(1)
                else:
                    email = cand
        return name, email

    # ------- generic helper: find m-itme sections and extract adjacent mib-c -------
    def find_sections_by_keywords(self, soup: BeautifulSoup, keywords: List[str]) -> List[str]:
        """
        Returns list of strings extracted for each matched keyword section:
        - look for <div class="m-itme"> containing a <span> or heading with keyword,
          then take the immediately following <div class="mib-c"> content.
        - also searches for heading tags containing the keyword and uses next sibling .mib-c or next block.
        """
        found_blocks: List[str] = []

        # method A: m-itme pattern
        for mit in soup.find_all('div', class_=re.compile(r'\bm-itme\b|\bmi-box\b|\bmi_box\b', flags=re.I)):
            # look for child span/h*/b containing any keyword
            title_holder = None
            for child in mit.find_all(recursive=False):
                # direct children might include span, h3 etc.
                if isinstance(child, Tag):
                    ctext = normalize_text(child.get_text(strip=True))
                    for kw in keywords:
                        if kw in ctext:
                            title_holder = child
                            break
                if title_holder:
                    break
            if title_holder:
                # try immediate following .mib-c
                sib = title_holder.find_next_sibling()
                if sib and isinstance(sib, Tag) and 'mib-c' in ' '.join(sib.get('class') or []):
                    extracted = text_of_tag(sib)
                    if extracted:
                        found_blocks.append(extracted)
                        continue
                # fallback: find a .mib-c within mit
                inner = mit.find('div', class_=re.compile(r'\bmib-c\b', flags=re.I))
                if inner:
                    extracted = text_of_tag(inner)
                    if extracted:
                        found_blocks.append(extracted)
                        continue

        # method B: headings scan (h3/h4/h5) anywhere
        for heading_tag in ('h1', 'h2', 'h3', 'h4', 'h5'):
            for h in soup.find_all(heading_tag):
                htext = normalize_text(h.get_text(strip=True))
                for kw in keywords:
                    if kw in htext:
                        # candidate content: next sibling(s) until another heading of same or higher level or stop marker
                        collected = []
                        for sib in h.find_next_siblings():
                            if isinstance(sib, Tag) and sib.name in ('h1', 'h2', 'h3', 'h4', 'h5'):
                                break
                            # stop if a stop signature appears in sibling text
                            s_txt = normalize_text(sib.get_text(separator=' ', strip=True))
                            if any(sig in s_txt for sig in self.STOP_HEADING_SIGNATURES):
                                break
                            if isinstance(sib, Tag):
                                t = text_of_tag(sib)
                                if t:
                                    collected.append(t)
                        candidate = '\n\n'.join([c for c in collected if c.strip()])
                        if candidate:
                            found_blocks.append(candidate)
                        else:
                            # try sibling with class mib-c
                            next_mib = h.find_next(lambda t: isinstance(t, Tag) and 'mib-c' in ' '.join(t.get('class') or []))
                            if next_mib:
                                t = text_of_tag(next_mib)
                                if t:
                                    found_blocks.append(t)
        # Deduplicate preserving order
        deduped: List[str] = []
        for b in found_blocks:
            cleaned = self.clean_research_text(b)
            if cleaned and cleaned not in deduped:
                deduped.append(cleaned)
        return deduped

    # ------- fallback searches -------
    def extract_publication_section(self, soup: BeautifulSoup) -> Optional[str]:
        # look for h3/span containing '出版信息', then look for h5 '发表论文' under it
        for h3 in soup.find_all(['h2', 'h3']):
            if '出版信息' in normalize_text(h3.get_text()):
                # search for following h5 with 发表论文
                for sib in h3.find_next_siblings():
                    if isinstance(sib, Tag) and sib.name == 'h5' and '发表论文' in normalize_text(sib.get_text()):
                        # collect content until next h5/h3 or stop signature
                        collected = []
                        for s2 in sib.find_next_siblings():
                            if isinstance(s2, Tag) and s2.name in ('h3', 'h5', 'h4', 'h2'):
                                break
                            t = text_of_tag(s2)
                            if t:
                                if any(sig in t for sig in self.STOP_HEADING_SIGNATURES):
                                    break
                                collected.append(t)
                        candidate = '\n\n'.join([c for c in collected if c.strip()])
                        return self.clean_research_text(candidate) if candidate else None
                # if no explicit h5, maybe publications listed directly inside a .mib-c following h3
                next_mib = h3.find_next(lambda t: isinstance(t, Tag) and 'mib-c' in ' '.join(t.get('class') or []))
                if next_mib:
                    return self.clean_research_text(text_of_tag(next_mib))
        return None

    def extract_projects_section(self, soup: BeautifulSoup) -> Optional[str]:
        # search for '科研活动' or '科研项目'
        for tag in soup.find_all(['h2', 'h3', 'h4', 'h5']):
            t = normalize_text(tag.get_text())
            if any(k in t for k in self.FALLBACK_PROJECTS):
                # collect siblings until next header or stop signature
                collected = []
                for sib in tag.find_next_siblings():
                    if isinstance(sib, Tag) and sib.name in ('h2', 'h3', 'h4', 'h5'):
                        break
                    stext = text_of_tag(sib)
                    if stext:
                        if any(sig in stext for sig in self.STOP_HEADING_SIGNATURES):
                            break
                        collected.append(stext)
                candidate = '\n\n'.join([c for c in collected if c.strip()])
                return self.clean_research_text(candidate) if candidate else None
        return None

    # ------- clean research text -------
    def clean_research_text(self, text: str) -> str:
        if not text:
            return ""
        t = html.unescape(text)
        t = re.sub(r'<[^>]+>', ' ', t)
        t = re.sub(r'\xa0|&nbsp;', ' ', t)
        t = re.sub(r'\s+\n\s+', '\n', t)
        t = re.sub(r'\n{3,}', '\n\n', t)
        t = '\n'.join([ln.strip() for ln in t.splitlines() if ln.strip()])
        t = t.strip()
        if self.args.truncate and self.args.truncate > 0 and len(t) > self.args.truncate:
            t = t[:self.args.truncate] + '...'
        return t

    # ------- main page scrape -------
    def scrape_profile(self, url: str) -> Dict[str, str]:
        result = {'name': 'Unknown', 'email': 'Not found', 'research_interest': 'Not found', 'profile_link': url}
        if url.strip() in self.processed_urls:
            logger.info("Skipping duplicate URL: %s", url)
            return result
        logger.info("Processing: %s", url)
        for attempt in range(self.args.retries + 1):
            try:
                soup = self.load_soup(url)
                # 1) name & email from bp-enty (most reliable for your dataset)
                name, email = self.extract_name_email_bp_enty(soup)
                if name:
                    result['name'] = name
                if email:
                    result['email'] = email

                # 2) research extraction by priority keywords (collect all matches)
                collected_blocks: List[str] = []
                # attempt to find sections (m-itme / headings etc.) for each priority key in order
                # but we want ALL (so we won't stop at first)
                for kw in self.PRIORITY_KEYWORDS:
                    blocks = self.find_sections_by_keywords(soup, [kw])
                    # blocks may contain multiple occurrences for same kw (e.g., research + 招生信息)
                    for b in blocks:
                        if b and b not in collected_blocks:
                            collected_blocks.append(b)
                # If we have something from priority, join them (preserve order)
                research_text = ""
                if collected_blocks:
                    research_text = '\n\n---\n\n'.join(collected_blocks)
                    research_text = self.clean_research_text(research_text)
                else:
                    # Fallback A: 出版信息 -> 发表论文
                    pub = self.extract_publication_section(soup)
                    if pub:
                        research_text = pub
                    else:
                        # Fallback B: 科研活动 / 科研项目
                        proj = self.extract_projects_section(soup)
                        if proj:
                            research_text = proj
                if research_text:
                    result['research_interest'] = research_text
                # final email deobfuscation / safe-check
                if result['email'] and ' at ' in result['email']:
                    result['email'] = deobfuscate_email(result['email'])
                # if still no email, try a global regex search as last resort
                if (not result['email'] or result['email'] == 'Not found') and soup:
                    m = re.search(r'([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', soup.get_text(separator=' ', strip=True))
                    if m:
                        result['email'] = m.group(1)
                # mark processed and return
                self.processed_urls.add(url.strip())
                logger.info("Extracted: name=%s email=%s research_len=%d", result['name'], result['email'], len(result['research_interest'] or ""))
                return result
            except Exception as e:
                logger.warning("Attempt %d failed for %s : %s", attempt + 1, url, str(e))
                if attempt == self.args.retries:
                    # return partial result (name/email may be unknown)
                    self.processed_urls.add(url.strip())
                    return result
                time.sleep(1.5)
        return result

    # ------- output helpers -------
    def write_profile_txt(self, profile: Dict[str, str], out_path: Path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, 'a', encoding='utf-8') as f:
            f.write(f"Name: {profile['name']}\n")
            f.write(f"Email: {profile['email']}\n")
            f.write(f"Research interest: {profile['research_interest']}\n")
            f.write(f"Profile link: {profile['profile_link']}\n")
            f.write("---\n\n")

    def write_profiles_json(self, profiles: List[Dict], out_path: Path):
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path.with_suffix('.json'), 'w', encoding='utf-8') as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)

    def run(self):
        infile = Path(self.args.input_file)
        if not infile.exists():
            logger.error("Input file not found: %s", infile)
            return
        urls = [line.strip() for line in infile.read_text(encoding='utf-8').splitlines() if line.strip()]
        logger.info("Found %d URLs", len(urls))
        out_path = Path(self.args.output_file)

        # prepare output (overwrite unless append)
        if out_path.exists() and not self.args.append:
            out_path.unlink()

        # start driver
        self.setup_driver()

        profiles: List[Dict] = []
        try:
            processed = 0
            for i, url in enumerate(urls):
                if self.args.max_profiles > 0 and processed >= self.args.max_profiles:
                    logger.info("Reached max_profiles: %d", self.args.max_profiles)
                    break
                profile = self.scrape_profile(url)
                if profile:
                    self.write_profile_txt(profile, out_path)
                    profiles.append(profile)
                    processed += 1
                if i < len(urls) - 1:
                    self.random_delay()
            # json output
            if self.args.json_output and profiles:
                self.write_profiles_json(profiles, out_path)
                logger.info("Saved JSON to %s", out_path.with_suffix('.json'))
        finally:
            self.close_driver()
        logger.info("Done. Processed %d profiles. Results: %s", len(profiles), out_path)


# ---------------- CLI ----------------
def main():
    parser = argparse.ArgumentParser(description="Faculty profile scraper (name, email, research only)")
    parser.add_argument('--input-file', default='urls.txt', help='one URL per line')
    parser.add_argument('--output-file', default='output.txt', help='text output file')
    parser.add_argument('--headless', action='store_true', help='run headless')
    parser.add_argument('--delay-min', type=float, default=1.0, help='min delay between pages (s)')
    parser.add_argument('--delay-max', type=float, default=2.5, help='max delay between pages (s)')
    parser.add_argument('--max-profiles', type=int, default=0, help='max profiles (0 = unlimited)')
    parser.add_argument('--retries', type=int, default=2, help='retries per page')
    parser.add_argument('--truncate', type=int, default=4000, help='truncate research text (0 = no limit)')
    parser.add_argument('--append', action='store_true', help='append to output file')
    parser.add_argument('--json-output', action='store_true', help='also save JSON output')
    parser.add_argument('--debug', action='store_true', help='debug logging')
    args = parser.parse_args()
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    scraper = FacultyResearchScraper(args)
    scraper.run()


if __name__ = c= '__main__':
    main()
