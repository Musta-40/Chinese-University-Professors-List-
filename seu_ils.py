#!/usr/bin/env python3
"""
Faculty Research-Interest Scraper (multi-site, XJTU/SEU-friendly)
- Tries requests + BeautifulSoup first; falls back to Selenium when page appears dynamic or extraction fails.
- Extracts: name, preferred email (favoring institutional domains), research direction (only the text after '研究方向：' or variants).
- Outputs simple text file with blocks separated by '---'
- New: added --allow-duplicate-email to avoid skipping profiles that share the same email.
"""

import argparse
import logging
import random
import re
import time
from pathlib import Path
from typing import Dict, Optional, Set, List

import requests
from bs4 import BeautifulSoup, Tag, NavigableString

# Optional Selenium fallback
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Keywords for research section (common variants)
RESEARCH_KEYWORDS = [
    '研究方向', '研究领域', '主要研究方向', '研究兴趣', '研究内容', '科研方向'
]

# Stop markers that usually denote end of research section (we stop extraction before these)
END_MARKERS = [
    '代表性', '论文', '个人简介', '教育背景', '工作经历', '联系方式'
]

# Email preference order (default favors seu.edu.cn then other edu.*)
DEFAULT_EMAIL_PREF = ['seu.edu.cn', '.edu.cn', '.edu']

EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+', flags=re.I)


def choose_preferred_email(emails: List[str], preferred_domains: List[str]) -> Optional[str]:
    if not emails:
        return None
    # prefer in-order based on domain list
    for dom in preferred_domains:
        for e in emails:
            if dom.lower() in e.lower():
                return e
    # if none matched, return first
    return emails[0]


def text_after_keyword_in_text(full_text: str, keyword: str) -> Optional[str]:
    """
    Find first occurrence of keyword and return text after the first colon (： or :)
    up until an end marker or truncation.
    """
    idx = full_text.find(keyword)
    if idx == -1:
        return None
    tail = full_text[idx + len(keyword):]
    # remove leading punctuation/spaces
    tail = tail.lstrip('：: \t\n\u3000')
    if not tail:
        return None
    # cut at any end marker if present
    for m in END_MARKERS:
        mpos = tail.find(m)
        if mpos != -1:
            tail = tail[:mpos]
    # further trim trailing punctuation/newlines and excessive whitespace
    tail = re.sub(r'\s+', ' ', tail).strip()
    return tail or None


class FacultyProfileScraper:
    def __init__(self, args):
        self.args = args
        self.processed_urls: Set[str] = set()
        self.processed_emails: Set[str] = set()
        self.driver = None

    # ---------------- Selenium setup/teardown ----------------
    def setup_selenium(self):
        if self.driver:
            return
        options = Options()
        if self.args.headless:
            # compatibility: use --headless=new if available, else --headless
            try:
                options.add_argument('--headless=new')
            except Exception:
                options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64)')
        options.add_argument('--disable-gpu')
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(8)

    def close_selenium(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    # ---------------- Utilities ----------------
    def random_delay(self):
        time.sleep(random.uniform(self.args.delay_min, self.args.delay_max))

    # ---------------- Extraction helpers ----------------
    def extract_emails_from_text(self, text: str) -> List[str]:
        return EMAIL_RE.findall(text or '')

    def extract_name(self, soup: BeautifulSoup) -> str:
        # Title -> h1/h2 -> fallbacks
        title = soup.find('title')
        if title and title.string:
            t = title.get_text().strip()
            t = re.sub(r'(个人主页|教授|博士生导师|主页|—.*|_-).*', '', t).strip()
            if 2 <= len(t) <= 40:
                return t
        for tag in ('h1', 'h2'):
            el = soup.find(tag)
            if el:
                name = el.get_text().strip()
                name = re.sub(r'(教授|博士生导师|个人简介).*', '', name).strip()
                if name:
                    return name
        # fallback: look for big bold near top
        strongs = soup.find_all(['strong', 'b'])
        for s in strongs[:8]:
            txt = s.get_text().strip()
            if 1 < len(txt) < 40 and len(txt.split()) <= 4:
                return txt
        return "Unknown"

    def extract_email(self, soup: BeautifulSoup) -> Optional[str]:
        # Try contact lines first (look for 'E-mail' or '邮箱' words)
        text = soup.get_text(separator='\n')
        emails = self.extract_emails_from_text(text)
        # prefer institutional domains
        preferred = choose_preferred_email(emails, self.args.preferred_email_domains)
        return preferred

    def element_text_stripped(self, elem: Tag) -> str:
        return re.sub(r'\s+', ' ', elem.get_text(separator=' ', strip=True)).strip()

    def extract_research_direction(self, soup: BeautifulSoup) -> str:
        """
        Multiple strategies (in order):
        1) Find an element (p/div/td/span) containing a research keyword and a colon, return text after colon.
        2) If label and value are split across sibling tags (e.g. <strong>研究方向：</strong><span>...<span>), detect label element and collect subsequent sibling text.
        3) Regex on raw HTML as last resort for patterns like '研究方向：</span>...<span>VALUE</span>'
        """
        # Strategy 1: direct text-containing nodes
        for tagname in ['p', 'div', 'td', 'span', 'li']:
            for elem in soup.find_all(tagname):
                txt = self.element_text_stripped(elem)
                if not txt:
                    continue
                for kw in RESEARCH_KEYWORDS:
                    if kw in txt:
                        # If colon present in the same text, extract after colon
                        if '：' in txt or ':' in txt:
                            candidate = text_after_keyword_in_text(txt, kw)
                            if candidate:
                                return candidate
                        # else maybe the label is in this element but value is in sibling or child strong/span
                        # Check children that follow for content
                        content_parts = []
                        saw_kw = False
                        for child in elem.children:
                            child_text = ''
                            if isinstance(child, NavigableString):
                                child_text = str(child).strip()
                            elif isinstance(child, Tag):
                                child_text = self.element_text_stripped(child)
                            if kw in child_text:
                                saw_kw = True
                                after = text_after_keyword_in_text(child_text, kw)
                                if after:
                                    return after
                                continue
                            if saw_kw and child_text:
                                content_parts.append(child_text)
                                if any(m in child_text for m in END_MARKERS):
                                    break
                        if content_parts:
                            candidate = ' '.join(content_parts).strip()
                            candidate = re.sub(r'\s+', ' ', candidate)
                            for m in END_MARKERS:
                                if m in candidate:
                                    candidate = candidate.split(m)[0].strip()
                            if candidate:
                                return candidate

                        # siblings: if this elem contains kw but not colon, collect next siblings
                        if kw in txt and (':' not in txt and '：' not in txt):
                            sib_texts = []
                            for sib in elem.next_siblings:
                                if isinstance(sib, NavigableString):
                                    s = str(sib).strip()
                                elif isinstance(sib, Tag):
                                    s = self.element_text_stripped(sib)
                                else:
                                    s = ''
                                if not s:
                                    continue
                                if any(m in s for m in END_MARKERS):
                                    break
                                sib_texts.append(s)
                                if len(' '.join(sib_texts)) > 300:
                                    break
                            if sib_texts:
                                candidate = ' '.join(sib_texts).strip()
                                candidate = re.sub(r'^[：:\s]+', '', candidate)
                                for m in END_MARKERS:
                                    if m in candidate:
                                        candidate = candidate.split(m)[0].strip()
                                if candidate:
                                    return candidate

        # Strategy 2: raw HTML regex fallback (handles patterns like: 研究方向：</span>...<span>VALUE</span></p>)
        raw = str(soup)
        for kw in RESEARCH_KEYWORDS:
            pattern = re.compile(
                re.escape(kw) + r'\s*[：:]\s*(.*?)</p>',
                flags=re.S
            )
            m = pattern.search(raw)
            if m:
                candidate_html = m.group(1)
                candidate_text = re.sub(r'<[^>]+>', '', candidate_html)
                candidate_text = re.sub(r'\s+', ' ', candidate_text).strip()
                for mm in END_MARKERS:
                    if mm in candidate_text:
                        candidate_text = candidate_text.split(mm)[0].strip()
                if candidate_text:
                    return candidate_text

        # last: fail gracefully
        return ""

    # ---------------- Fetching ----------------
    def fetch_with_requests(self, url: str) -> Optional[str]:
        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'
            }
            resp = requests.get(url, headers=headers, timeout=self.args.timeout)
            if resp.status_code == 200:
                resp.encoding = resp.apparent_encoding or 'utf-8'
                return resp.text
            logger.warning(f"Requests GET {url} returned status {resp.status_code}")
            return None
        except Exception as e:
            logger.warning(f"Requests error for {url}: {e}")
            return None

    def fetch_with_selenium(self, url: str) -> Optional[str]:
        try:
            if not self.driver:
                self.setup_selenium()
            self.driver.get(url)
            try:
                WebDriverWait(self.driver, 6).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except Exception:
                pass
            time.sleep(1.0)
            return self.driver.page_source
        except Exception as e:
            logger.warning(f"Selenium error for {url}: {e}")
            return None

    # ---------------- Per-profile scrape ----------------
    def scrape_profile(self, url: str) -> Optional[Dict[str, str]]:
        normalized_url = url.strip()
        if not normalized_url:
            return None
        if normalized_url in self.processed_urls:
            logger.info(f"Skipping duplicate URL: {normalized_url}")
            return None
        logger.info(f"Processing: {normalized_url}")

        # Try requests first unless user forces selenium
        html = None
        if not self.args.force_selenium:
            html = self.fetch_with_requests(normalized_url)

        if not html and self.args.use_selenium_if_needed:
            html = self.fetch_with_selenium(normalized_url)

        if not html:
            html = self.fetch_with_selenium(normalized_url)

        if not html:
            logger.error(f"Failed to fetch {normalized_url}")
            return {
                'name': 'Unknown',
                'email': '',
                'research_interest': '<FAILED: fetch>',
                'profile_link': normalized_url
            }

        soup = BeautifulSoup(html, 'html.parser')
        for s in soup(['script', 'style']):
            s.decompose()

        name = self.extract_name(soup)
        email = self.extract_email(soup) or ''

        # New behavior: optionally allow duplicate emails
        if email and (email in self.processed_emails):
            if not getattr(self.args, 'allow_duplicate_email', False):
                logger.info(f"Skipping duplicate email: {email}")
                return None
            else:
                logger.info(f"Duplicate email allowed, continuing for: {email}")

        research = self.extract_research_direction(soup)
        if not research:
            research = "Not found"

        # Mark as processed
        self.processed_urls.add(normalized_url)
        if email:
            self.processed_emails.add(email)

        # respect truncation if requested
        if self.args.truncate > 0 and len(research) > self.args.truncate:
            research = research[:self.args.truncate] + ' [...]'

        return {
            'name': name,
            'email': email,
            'research_interest': research,
            'profile_link': normalized_url
        }

    def write_profile(self, profile: Dict[str, str], output_file: Path):
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"Name: {profile['name']}\n")
            f.write(f"Email: {profile['email']}\n")
            f.write(f"Research interest: {profile['research_interest']}\n")
            f.write(f"Profile link: {profile['profile_link']}\n")
            f.write("---\n\n")

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

        try:
            processed_count = 0
            for i, url in enumerate(urls):
                if self.args.max_profiles > 0 and processed_count >= self.args.max_profiles:
                    logger.info("Reached maximum profile limit.")
                    break

                profile = None
                for attempt in range(self.args.retries + 1):
                    profile = self.scrape_profile(url)
                    if profile is not None:
                        break
                    logger.info(f"Retrying ({attempt+1}) for {url}")
                    time.sleep(2)

                if profile:
                    self.write_profile(profile, output_file)
                    processed_count += 1
                    logger.info(f"Processed {processed_count}/{len(urls)}: {profile['name']}")

                # delay between requests
                if i < len(urls) - 1:
                    self.random_delay()

        finally:
            self.close_selenium()

        logger.info(f"Completed. Processed {processed_count} profiles.")


def build_argparser():
    parser = argparse.ArgumentParser(description='Scrape faculty research directions (multi-site)')
    parser.add_argument('--input-file', default='urls.txt', help='Input file with one URL per line')
    parser.add_argument('--output-file', default='output.txt', help='Output file')
    parser.add_argument('--headless', action='store_true', help='Run selenium headless (if used)')
    parser.add_argument('--delay-min', type=float, default=1.0, help='Min delay between requests')
    parser.add_argument('--delay-max', type=float, default=3.0, help='Max delay between requests')
    parser.add_argument('--max-profiles', type=int, default=0, help='Max profiles to process (0 = unlimited)')
    parser.add_argument('--retries', type=int, default=2, help='Retries for failed profiles')
    parser.add_argument('--truncate', type=int, default=4000, help='Truncate research interest length (0 = no trunc)')
    parser.add_argument('--append', action='store_true', help='Append to output file instead of overwriting')
    parser.add_argument('--timeout', type=int, default=20, help='HTTP request timeout seconds')
    parser.add_argument('--force-selenium', action='store_true', help='Always use Selenium instead of requests')
    parser.add_argument('--use-selenium-if-needed', action='store_true', default=True,
                        help='Fall back to Selenium when requests fails (default: True)')
    parser.add_argument('--preferred-email-domains', type=str, default=','.join(DEFAULT_EMAIL_PREF),
                        help='Comma-separated preferred email domains (in order). e.g. "seu.edu.cn,.edu.cn,.edu"')
    parser.add_argument('--allow-duplicate-email', action='store_true',
                        help='If set, do NOT skip profiles with emails already seen (default: False).')
    return parser


def main():
    args = build_argparser().parse_args()
    # parse preferred email domains string to list
    args.preferred_email_domains = [d.strip() for d in (args.preferred_email_domains or '').split(',') if d.strip()]
    # convenience: always include common edu fallback if not present
    if '.edu.cn' not in args.preferred_email_domains:
        args.preferred_email_domains.append('.edu.cn')
    scraper = FacultyProfileScraper(args)
    scraper.run()


if __name__ == '__main__':
    main()
