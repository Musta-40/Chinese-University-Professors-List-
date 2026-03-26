#!/usr/bin/env python3
"""
Faculty Profile Research Interest Extractor
Extracts research interests from faculty profile pages while excluding publications, CV items, etc.

Features:
- Selenium primary extraction with requests/BeautifulSoup fallback
- Multilingual research heading detection (Chinese + English)
- Strict stop/cut-off for publications, CV, education, projects, etc.
- Heuristics when no explicit heading exists
- Robust name and email extraction with institutional preference
- Polite scraping: randomized delay, optional robots.txt check
- Dedup by URL and institutional email, deterministic processing in input order
- Immediate, append-to-disk output for resilience

Python 3.9+
"""

import re
import time
import random
import logging
import argparse
import html
from pathlib import Path
from typing import Optional, Dict, List
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager

import requests
from bs4 import BeautifulSoup, Tag, NavigableString

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ResearchInterestExtractor:
    """Main extractor class for faculty research interests"""

    # Research interest keywords (case-insensitive)
    RESEARCH_KEYWORDS_CN = [
        '研究方向', '研究兴趣', '主要研究方向', '研究方向与内容', '研究领域'
    ]

    RESEARCH_KEYWORDS_EN = [
        'research focus', 'research interests', 'research interest',
        'research area', 'research areas', 'research direction',
        'research directions', 'research field', 'research fields'
    ]

    # Publication/CV/stop keywords — when encountered, stop extraction
    STOP_KEYWORDS_CN = [
        '论文', '发表', '代表性论文', '近五年', '主要成果', '出版', '著作',
        '项目', '研究生导师', '教育背景', '工作经历', '简历', '个人简历',
        '学历', '获奖', '专利', '课程', '教学', '学术兼职', '社会服务',
        '科研项目', '招生', '招生信息', '指导学生'
    ]

    STOP_KEYWORDS_EN = [
        'paper', 'papers', 'publication', 'publications', 'representative papers',
        'selected publications', 'education', 'work experience', 'cv', 'resume',
        'books', 'projects', 'supervision', 'biography', 'awards', 'honors',
        'teaching', 'courses', 'professional experience', 'employment',
        'academic positions', 'bibliography', 'grants', 'funding', 'patents'
    ]

    GENERIC_HEADINGS = {
        'home', 'news', 'lectures', 'faculty', 'college', 'research',
        'international', 'join us', 'contact', 'administration',
        'professor', 'associate professor', 'assistant professor',
        'teacher', 'staff', 'people', 'profile'
    }

    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls = set()
        self.processed_emails = set()
        self.setup_driver()

    # ----------------------------- Setup -----------------------------

    def setup_driver(self):
        """Initialize Selenium WebDriver"""
        try:
            options = Options()
            if self.args.headless:
                options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-blink-features=AutomationControlled')
            options.add_experimental_option("excludeSwitches", ["enable-automation"])
            options.add_experimental_option('useAutomationExtension', False)
            options.add_argument('--lang=en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7')
            options.add_argument(
                'user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/120.0.0.0 Safari/537.36'
            )

            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.implicitly_wait(10)
            logger.info("WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise

    # ----------------------------- Helpers -----------------------------

    def normalize_url(self, url: str) -> str:
        """Normalize URL for deduplication (lowercase, strip whitespace/fragment)"""
        u = url.strip()
        if not u:
            return ''
        parsed = urlparse(u)
        norm = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        if parsed.query:
            norm += f"?{parsed.query}"
        return norm.lower().rstrip('/')

    def get_base_domain(self, hostname: str) -> str:
        """
        Heuristic to get base domain without adding a dependency.
        For .cn and other multi-label TLDs, keep last 3 labels; otherwise last 2.
        """
        if not hostname:
            return ''
        parts = hostname.split('.')
        if len(parts) <= 2:
            return hostname.lower()
        multi_level_suffixes = {'com.cn', 'edu.cn', 'gov.cn', 'ac.cn', 'org.cn', 'net.cn'}
        last_two = '.'.join(parts[-2:]).lower()
        last_three = '.'.join(parts[-3:]).lower()
        if last_two in multi_level_suffixes:
            return '.'.join(parts[-3:]).lower()
        if last_three in multi_level_suffixes:
            return last_three
        return last_two

    def is_institutional_email(self, email: str, site_domain: str) -> bool:
        """Check if email looks institutional or matches the site base domain."""
        email_l = email.lower()
        return (
            (site_domain and email_l.endswith(site_domain)) or
            ('.edu' in email_l) or
            ('.ac.' in email_l) or
            ('university' in email_l) or
            ('college' in email_l) or
            (email_l.endswith('.edu.cn') or email_l.endswith('.ac.cn'))
        )

    def check_robots_txt(self, url: str) -> bool:
        """Check if URL is allowed by robots.txt"""
        if not self.args.check_robots:
            return True
        try:
            parsed_url = urlparse(url)
            robots_url = f"{parsed_url.scheme}://{parsed_url.netloc}/robots.txt"
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.read()
            is_allowed = rp.can_fetch("*", url)
            if not is_allowed:
                logger.warning(f"URL blocked by robots.txt: {url}")
            return is_allowed
        except Exception as e:
            logger.debug(f"Could not check robots.txt: {e}")
            return True  # Allow if can't check

    def get_main_container(self, soup: BeautifulSoup) -> Tag:
        """Attempt to find the main content container to avoid headers/footers."""
        candidates = soup.select(
            '#vsb_content, .v_news_content, .nr, .content, #content, '
            '.main, #main, .article, #article, .profile, #profile, '
            '[class*="content"], [id*="content"], [class*="main"], [id*="main"], '
            '[class*="article"], [id*="article"], [class*="profile"], [id*="profile"], '
            '[class*="detail"], [id*="detail"]'
        )

        def score_container(tag: Tag) -> int:
            text = tag.get_text(" ", strip=True)
            score = len(text)
            low = text.lower()
            if any(k in low for k in ['research', '研究', '方向', '领域']):
                score += 5000
            return score

        if candidates:
            try:
                return max(candidates, key=score_container)
            except Exception:
                return candidates[0]
        return soup.body or soup

    # ----------------------------- Extraction -----------------------------

    def extract_with_selenium(self, url: str) -> Dict:
        """Extract profile data using Selenium"""
        try:
            if not self.check_robots_txt(url):
                return {'error': 'Blocked by robots.txt', 'profile_link': url}

            self.driver.get(url)

            # Wait for body presence (explicit wait)
            WebDriverWait(self.driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )

            soup = BeautifulSoup(self.driver.page_source, 'lxml')
            return self.extract_from_soup(soup, url)

        except TimeoutException:
            logger.error(f"Timeout loading {url}")
            return {'error': 'Timeout', 'profile_link': url}
        except WebDriverException as e:
            logger.error(f"WebDriver error for {url}: {e}")
            return {'error': f'WebDriver error: {str(e)[:200]}', 'profile_link': url}
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {e}")
            return {'error': f'Unexpected error: {str(e)[:200]}', 'profile_link': url}

    def extract_with_requests(self, url: str) -> Dict:
        """Fallback extraction using requests and BeautifulSoup"""
        try:
            headers = {
                'User-Agent': (
                    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                    'AppleWebKit/537.36 (KHTML, like Gecko) '
                    'Chrome/120.0.0.0 Safari/537.36'
                )
            }

            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            if not response.encoding or response.encoding.lower() == 'iso-8859-1':
                response.encoding = response.apparent_encoding or 'utf-8'

            soup = BeautifulSoup(response.text, 'lxml')
            return self.extract_from_soup(soup, url)

        except requests.RequestException as e:
            logger.error(f"Request failed for {url}: {e}")
            return {'error': f'Request failed: {str(e)[:200]}', 'profile_link': url}
        except Exception as e:
            logger.error(f"Unexpected error for {url}: {e}")
            return {'error': f'Unexpected error: {str(e)[:200]}', 'profile_link': url}

    def extract_from_soup(self, soup: BeautifulSoup, url: str) -> Dict:
        """Extract profile data from BeautifulSoup object"""
        container = self.get_main_container(soup)
        name = self.extract_name(container, soup)
        email = self.extract_email(container, soup, url)
        research_interest = self.extract_research_interest(container)

        # Clean and truncate
        research_interest = self.clean_text(research_interest)
        research_interest = self.trim_publication_trailing(research_interest)
        if self.args.truncate and len(research_interest) > self.args.truncate:
            research_interest = research_interest[: self.args.truncate].rstrip() + ' [...]'

        return {
            'name': name,
            'email': email,
            'research_interest': research_interest,
            'profile_link': url
        }

    # ----------------------------- Name & Email -----------------------------

    def extract_name(self, container: Tag, soup: BeautifulSoup) -> str:
        """Extract faculty name from page with safe heuristics"""

        def text_clean(t: str) -> str:
            return re.sub(r'\s+', ' ', t or '').strip()

        candidates: List[tuple[int, str]] = []

        # 1) Meta pageTitle
        meta_title = soup.find('meta', {'name': 'pageTitle'})
        if meta_title and meta_title.get('content'):
            t = text_clean(meta_title['content'])
            if t:
                candidates.append((80, t))

        # 2) Title tag
        title_tag = soup.find('title')
        if title_tag:
            tt = text_clean(title_tag.get_text())
            for sep in ['-', '|', '—', '·']:
                if sep in tt:
                    t = text_clean(tt.split(sep)[0])
                    if t:
                        candidates.append((70, t))
                    break
            else:
                if tt:
                    candidates.append((60, tt))

        # 3) h1/h2 inside main container (prefer)
        for tag in container.find_all(['h1', 'h2'], limit=10):
            t = text_clean(tag.get_text())
            low = t.lower()
            if not t or len(t) > 80:
                continue
            if low in self.GENERIC_HEADINGS:
                continue
            if any(k in low for k in (self.RESEARCH_KEYWORDS_EN + self.RESEARCH_KEYWORDS_CN)):
                continue
            if re.search(r'\d{2,}', t):
                continue
            if low in {'professor', 'associate professor', 'assistant professor'}:
                continue
            if low in {'contact', 'biography', 'resume', 'cv'}:
                continue
            # Avoid odd characters (fixes your earlier syntax issue)
            if any(ch in t for ch in '<>{}[]|'):
                continue
            score = 90 if tag.name == 'h1' else 85
            candidates.append((score, t))

        # 4) Common name class hints
        for sel in ['.name', '.teacher_name', '.profile-name', '.faculty-name', '.title']:
            for tag in container.select(sel):
                t = text_clean(tag.get_text())
                if t and 2 <= len(t) <= 80:
                    low = t.lower()
                    if low not in self.GENERIC_HEADINGS and not re.search(r'\d{2,}', t):
                        candidates.append((65, t))

        if candidates:
            best_by_text: Dict[str, int] = {}
            for score, t in candidates:
                if t not in best_by_text or score > best_by_text[t]:
                    best_by_text[t] = score
            best = sorted(best_by_text.items(), key=lambda x: (-x[1], len(x[0])))[0][0]
            if not any(ch in best for ch in '<>{}[]|'):
                return best[:100]

        return ''

    def extract_email(self, container: Tag, soup: BeautifulSoup, url: str) -> str:
        """Extract email address; prefer institutional and page-specific emails"""
        page_text = container.get_text(" ", strip=True) + " " + soup.get_text(" ", strip=True)
        page_text = html.unescape(page_text)

        # 1) Look for explicit "Email:" labeled addresses
        labeled = re.findall(r'(?i)(?:e-?mail)\s*[:：]\s*([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', page_text)
        all_emails = set(labeled)

        # 2) General email regex across the page
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b'
        all_emails.update(re.findall(email_pattern, page_text))

        if not all_emails:
            return ''

        site_domain = self.get_base_domain(urlparse(url).netloc)

        def score_email(e: str) -> int:
            el = e.lower()
            score = 0
            if self.is_institutional_email(el, site_domain):
                score += 50
            if e in labeled:
                score += 10
            return score

        best = sorted(all_emails, key=lambda e: (-score_email(e), len(e)))[0]
        return best

    # ----------------------------- Research extraction -----------------------------

    def contains_stop_keywords(self, text: str) -> bool:
        """Check if text contains stop keywords or publication-like patterns"""
        if not text:
            return False
        text_lower = text.lower()

        # Keywords
        for keyword in self.STOP_KEYWORDS_CN + self.STOP_KEYWORDS_EN:
            if keyword.lower() in text_lower:
                return True

        # Too many years -> likely publications
        years = re.findall(r'\b(19|20)\d{2}\b', text_lower)
        if len(years) >= 3:
            return True

        # DOI patterns
        if re.search(r'\bdoi:\s*10\.\d+/\S+', text_lower):
            return True

        # Journal/conference indicators
        journal_indicators = ['journal', 'conference', 'proceedings', 'vol.', 'pp.', 'isbn', 'issn']
        if any(ind in text_lower for ind in journal_indicators):
            return True

        # Lines starting with [1], 1), or year bullets
        if re.search(r'^\s*(```math
\d+```|\d+KATEX_INLINE_CLOSE|KATEX_INLINE_OPEN?20\d{2}KATEX_INLINE_CLOSE?[\.\s:，、])', text_lower, flags=re.M):
            return True

        return False

    def is_heading(self, tag: Tag) -> bool:
        return isinstance(tag, Tag) and tag.name in ['h1', 'h2', 'h3', 'h4', 'h5']

    def tag_text(self, tag: Tag) -> str:
        if not tag:
            return ''
        return tag.get_text(" ", strip=True)

    def extract_research_interest(self, container: Tag) -> str:
        """Extract research interest text from page (container)"""
        txt = self.extract_by_heading(container)
        if txt:
            return txt
        return self.extract_by_heuristic(container)

    def matched_research_heading(self, tag: Tag) -> Optional[Tag]:
        """
        If tag or its text matches a research heading keyword, return the block-level anchor
        (the tag itself if heading/p/div, else its parent p/div). Otherwise None.
        """
        if not isinstance(tag, Tag):
            return None

        all_keywords = [k.lower() for k in (self.RESEARCH_KEYWORDS_CN + self.RESEARCH_KEYWORDS_EN)]
        text = self.tag_text(tag).lower()

        if any(k in text for k in all_keywords):
            if tag.name in ['h1', 'h2', 'h3', 'h4', 'p', 'div', 'section', 'dt', 'th']:
                return tag
            parent = tag.find_parent(['p', 'div', 'section'])
            if parent:
                return parent
            return tag
        return None

    def collect_text_until_stop(self, start_anchor: Tag, max_chars: int = 4000) -> str:
        """
        Walk sibling elements after start_anchor, collecting text until a stop condition:
        - Next heading of similar/higher level
        - Element text contains stop keywords
        - Bulleted publication-like list
        """
        collected: List[str] = []
        total = 0

        for sib in start_anchor.next_siblings:
            if isinstance(sib, NavigableString):
                continue
            if not isinstance(sib, Tag):
                continue

            if self.is_heading(sib):
                break

            if sib.name in ['p', 'div', 'section']:
                text = self.tag_text(sib)
                if not text:
                    continue
                if self.contains_stop_keywords(text):
                    break
                if re.search(r'(?i)\b(tel|phone|fax|office|homepage|website)\b', text):
                    continue
                collected.append(text)
                total += len(text)

            elif sib.name in ['ul', 'ol']:
                items = []
                pub_like = False
                for li in sib.find_all('li', recursive=False):
                    li_text = self.tag_text(li)
                    if not li_text:
                        continue
                    if self.contains_stop_keywords(li_text):
                        pub_like = True
                        break
                    if re.match(r'^\s*(```math
\d+```|\d+KATEX_INLINE_CLOSE|KATEX_INLINE_OPEN?20\d{2}KATEX_INLINE_CLOSE?[\.\s:，、])', li_text):
                        pub_like = True
                        break
                    items.append(li_text)
                if pub_like:
                    break
                if items:
                    block = '; '.join(items)
                    collected.append(block)
                    total += len(block)

            if total >= max_chars:
                break

        return ' '.join(collected).strip()

    def extract_by_heading(self, container: Tag) -> str:
        """Extract research interest by finding relevant headings and collecting following blocks"""
        search_tags = ['h1', 'h2', 'h3', 'h4', 'p', 'div', 'strong', 'b', 'span', 'dt', 'th']
        candidates: List[Tag] = []

        for tag in container.find_all(search_tags):
            anchor = self.matched_research_heading(tag)
            if anchor:
                candidates.append(anchor)

        for anchor in candidates:
            text = self.collect_text_until_stop(anchor, max_chars=5000)
            if text and len(text) > 30 and not self.contains_stop_keywords(text):
                return text

        return ''

    def extract_by_heuristic(self, container: Tag) -> str:
        """
        Fallback: search for paragraphs containing research-related keywords and build a nearby block.
        Choose the earliest plausible block.
        """
        research_keywords = ['研究', 'research', 'interest', 'interests', 'focus', '方向', '领域']
        paragraphs = container.find_all(['p', 'div'])

        for idx, para in enumerate(paragraphs):
            t = self.tag_text(para)
            tl = t.lower()
            if not t or len(t) < 40:
                continue
            if any(k in tl for k in research_keywords) and not self.contains_stop_keywords(t):
                block_parts = [t]
                forward = 0
                for next_tag in para.next_siblings:
                    if isinstance(next_tag, NavigableString):
                        continue
                    if not isinstance(next_tag, Tag):
                        continue
                    if self.is_heading(next_tag):
                        break
                    if next_tag.name not in ['p', 'div', 'ul', 'ol']:
                        continue
                    nt = self.tag_text(next_tag)
                    if not nt:
                        continue
                    if self.contains_stop_keywords(nt):
                        break
                    block_parts.append(nt)
                    forward += 1
                    if forward >= 4:
                        break

                text = ' '.join(block_parts).strip()
                if text and len(text) > 40 and not self.contains_stop_keywords(text):
                    return text

        return ''

    # ----------------------------- Cleaning -----------------------------

    def clean_text(self, text: str) -> str:
        """Clean extracted text: normalize whitespace and remove leftover labels."""
        if not text:
            return ''
        text = html.unescape(text)
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'(?i)^\s*(research interests?|research focus|研究方向[与及]*内容?|研究兴趣|研究领域)\s*[:：-]\s*', '', text)
        return text

    def trim_publication_trailing(self, text: str) -> str:
        """
        If any stop keyword appears later in the text (due to imperfect DOM boundaries),
        trim from the first occurrence onward.
        """
        if not text:
            return text

        all_stops = [re.escape(k.lower()) for k in (self.STOP_KEYWORDS_CN + self.STOP_KEYWORDS_EN)]
        pattern = re.compile('|'.join(all_stops), flags=re.I)
        m = pattern.search(text)
        if m:
            text = text[:m.start()].rstrip()

        lines = re.split(r'(?<=[。！？.!?;；])\s+', text)
        kept: List[str] = []
        for line in lines:
            if self.contains_stop_keywords(line):
                break
            kept.append(line)
        return ' '.join(kept).strip()

    # ----------------------------- Orchestration -----------------------------

    def process_profile(self, url: str) -> Optional[Dict]:
        """Process a single profile URL with retries and fallback"""
        norm_url = self.normalize_url(url)
        if not norm_url:
            logger.warning("Skipping empty/invalid URL line")
            return None

        if norm_url in self.processed_urls:
            logger.info(f"Skipping duplicate URL: {url}")
            return None

        logger.info(f"Processing: {url}")

        # Polite delay between requests
        delay = random.uniform(self.args.delay_min, self.args.delay_max)
        time.sleep(delay)

        attempts: List[Dict] = []

        # Attempt 1: Selenium
        res = self.extract_with_selenium(url)
        if 'error' not in res:
            result = res
        else:
            attempts.append(res)
            # Attempt 2: requests fallback
            res2 = self.extract_with_requests(url)
            if 'error' not in res2:
                result = res2
            else:
                attempts.append(res2)
                # Extra retries if requested
                for _ in range(max(0, self.args.retries)):
                    time.sleep(random.uniform(self.args.delay_min, self.args.delay_max))
                    res3 = self.extract_with_selenium(url)
                    if 'error' not in res3:
                        result = res3
                        break
                    attempts.append(res3)
                else:
                    last_err = attempts[-1].get('error', 'Failed')
                    return {'error': last_err, 'profile_link': url}

        # Dedup by institutional email
        email = (result.get('email') or '').strip().lower()
        site_domain = self.get_base_domain(urlparse(url).netloc)
        if email and self.is_institutional_email(email, site_domain):
            if email in self.processed_emails:
                logger.info(f"Skipping duplicate institutional email: {email} ({url})")
                return None
            self.processed_emails.add(email)

        self.processed_urls.add(norm_url)
        return result

    def format_output(self, data: Dict) -> str:
        """Format extracted data for output"""
        if 'error' in data:
            return (
                f"Name: \n"
                f"Email: \n"
                f"Research interest: <FAILED: {data['error']}>\n"
                f"Profile link: {data.get('profile_link', '')}\n"
                f"---\n"
            )
        return (
            f"Name: {data.get('name', '')}\n"
            f"Email: {data.get('email', '')}\n"
            f"Research interest: {data.get('research_interest', '')}\n"
            f"Profile link: {data.get('profile_link', '')}\n"
            f"---\n"
        )

    def run(self):
        """Main execution method"""
        input_path = Path(self.args.input_file)
        if not input_path.exists():
            logger.error(f"Input file not found: {input_path}")
            return

        with open(input_path, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]

        if not urls:
            logger.error("No URLs found in input file")
            return

        logger.info(f"Found {len(urls)} URLs to process")

        output_path = Path(self.args.output_file)
        processed_count = 0

        try:
            with open(output_path, 'w', encoding='utf-8') as out_file:
                for i, url in enumerate(urls):
                    if self.args.max_profiles and processed_count >= self.args.max_profiles:
                        logger.info(f"Reached maximum profile limit: {self.args.max_profiles}")
                        break

                    logger.info(f"Processing {i + 1}/{len(urls)}: {url}")

                    try:
                        result = self.process_profile(url)
                        if result:
                            # Ensure profile link is the input URL
                            result['profile_link'] = url
                            output = self.format_output(result)
                            out_file.write(output + '\n')  # One blank line between blocks
                            out_file.flush()  # Immediate write
                            if 'error' not in result:
                                processed_count += 1
                                logger.info(f"Successfully processed: {url}")
                            else:
                                logger.warning(f"Failed for {url}: {result.get('error')}")
                    except Exception as e:
                        logger.error(f"Failed to process {url}: {e}")
                        error_output = self.format_output({
                            'error': str(e)[:200],
                            'profile_link': url
                        })
                        out_file.write(error_output + '\n')
                        out_file.flush()
        finally:
            if self.driver:
                self.driver.quit()
                logger.info("WebDriver closed")

        logger.info(f"Processing complete. Processed {processed_count} profiles.")
        logger.info(f"Output written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Extract research interests from faculty profile pages'
    )
    parser.add_argument(
        '--input-file',
        default='urls.txt',
        help='Input file with URLs (one per line)'
    )
    parser.add_argument(
        '--output-file',
        default='output.txt',
        help='Output file for extracted data'
    )
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode'
    )
    parser.add_argument(
        '--delay-min',
        type=float,
        default=0.5,
        help='Minimum delay between requests (seconds)'
    )
    parser.add_argument(
        '--delay-max',
        type=float,
        default=2.0,
        help='Maximum delay between requests (seconds)'
    )
    parser.add_argument(
        '--max-profiles',
        type=int,
        default=None,
        help='Maximum number of profiles to process'
    )
    parser.add_argument(
        '--retries',
        type=int,
        default=1,
        help='Number of extra retries after initial Selenium+requests attempts'
    )
    parser.add_argument(
        '--truncate',
        type=int,
        default=4000,
        help='Maximum characters for research interest (0 = no limit)'
    )
    parser.add_argument(
        '--check-robots',
        action='store_true',
        help='Check robots.txt before scraping'
    )

    args = parser.parse_args()

    if args.delay_min < 0 or args.delay_max < args.delay_min:
        parser.error("Invalid delay values: ensure 0 <= --delay-min <= --delay-max")

    if args.truncate < 0:
        parser.error("Truncate value must be non-negative")

    extractor = ResearchInterestExtractor(args)
    extractor.run()


if __name__ == '__main__':
    main()