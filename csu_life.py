#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Scrape faculty profile pages and extract ONLY research interests.

Output format per profile (appended immediately, UTF-8):
Name: <name>
Email: <email>
Research interest: <cleaned research interest text or <FAILED: reason>>
Profile link: <input URL>
---

Separated by one blank line between blocks.

Features:
- Selenium (explicit waits) + requests/BeautifulSoup fallback
- Robust heading-based extraction for research interests
- Strict publication/CV cut-off rules (Chinese/English + heuristics)
- Dedup by normalized URL and by institutional email
- Random delay between profiles (polite), configurable retries
- Optional robots.txt check
"""

import argparse
import logging
import os
import random
import re
import sys
import time
from typing import Optional, Tuple, List, Set, Dict
from urllib.parse import urlparse, urlunparse, urlencode, parse_qsl

import requests
from bs4 import BeautifulSoup, Tag, NavigableString
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import urllib.robotparser as robotparser

# Selenium imports
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException


DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/127.0.0.0 Safari/537.36"
)

EMAIL_REGEX = re.compile(r"[\w\.-]+@[\w\.-]+\.\w+", re.I)

RESEARCH_HEADINGS = [
    # Chinese
    "研究方向", "研究兴趣", "主要研究方向", "研究方向与内容", "研究领域",
    # English
    "Research focus", "Research interests", "Research interest",
    "Research areas", "Research area", "Research direction", "Research directions",
]
RESEARCH_HEADINGS_RE = re.compile("|".join([re.escape(x) for x in RESEARCH_HEADINGS]), re.I)

# Publication/CV cut-off words (strict)
STOP_KEYWORDS = [
    # Chinese (as specified)
    "论文", "发表", "代表性论文", "近五年", "主要成果", "出版", "著作", "项目",
    "研究生导师", "教育背景", "工作经历", "简历", "个人简历",
    # Common extras to be safe
    "科研项目", "承担项目", "教学", "课程", "获奖", "荣誉", "奖励", "社会服务",
    "学术兼职", "代表性著作", "专著", "专利", "会议", "期刊",
    # English (as specified)
    "paper", "publication", "publications", "representative papers",
    "selected publications", "education", "work experience", "cv", "resume",
    "books", "projects", "supervision",
    # Extras
    "awards", "honors", "service", "teaching", "grants", "funding",
]
STOP_RE = re.compile("|".join([re.escape(x) for x in STOP_KEYWORDS]), re.I)

# Heuristics for detecting publication-like lines/blocks
DOI_RE = re.compile(r"\bdoi[:\s]*10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.I)
YEAR_LINE_RE = re.compile(r"^\s*(19|20)\d{2}([—\-–/年\.]|[KATEX_INLINE_CLOSE```]|\s)", re.U)
BIB_MARK_RE = re.compile(r"^\s*(```math
\d+```|\d+\.\s+|（\d+）|KATEX_INLINE_OPEN\d+KATEX_INLINE_CLOSE)")
JOURNAL_CUES_RE = re.compile(r"\b(Vol\.|No\.|pp\.|Proc\.|Proceedings|Conference|Journal|IEEE|ACM|Springer|Elsevier|arXiv)\b", re.I)

# Main content selectors often used by CSU and similar sites
MAIN_SELECTORS = [
    "#vsb_content", ".v_news_content", "#vsb_content_2",
    ".article", ".article-content", ".news_content", ".content", "#content",
    ".main", ".detail", ".TRS_Editor"
]

# For Selenium waiting
WAIT_SELECTORS = [
    "body", "#vsb_content", ".v_news_content", "#vsb_content_2",
    ".article", ".content"
]

# Prefer institutional emails (.edu.cn first, then .edu)
EMAIL_DOMAIN_PREFERENCE = [
    ".csu.edu.cn", ".edu.cn", ".edu"
]

def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        stream=sys.stderr,
    )

def normalize_url(url: str) -> str:
    try:
        p = urlparse(url.strip())
        # Sort query params for deterministic normalization
        q = urlencode(sorted(parse_qsl(p.query, keep_blank_values=True)))
        path = p.path.rstrip("/") or p.path
        norm = p._replace(fragment="", query=q, path=path)
        return urlunparse(norm)
    except Exception:
        return url.strip()

def create_requests_session(retries: int, user_agent: str) -> requests.Session:
    s = requests.Session()
    retry = Retry(
        total=retries,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "HEAD"]
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    s.headers.update({
        "User-Agent": user_agent,
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
    })
    return s

def build_driver(headless: bool, user_agent: str) -> webdriver.Chrome:
    options = Options()
    if headless:
        options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument(f"user-agent={user_agent}")
    options.add_argument("--window-size=1280,1200")
    # Less noisy logs
    options.add_experimental_option("excludeSwitches", ["enable-logging"])
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def fetch_html_requests(session: requests.Session, url: str, timeout: int = 20) -> Optional[str]:
    try:
        resp = session.get(url, timeout=timeout)
        if resp.status_code != 200:
            logging.warning("HTTP %s for %s", resp.status_code, url)
            return None
        if not resp.encoding:
            resp.encoding = resp.apparent_encoding or "utf-8"
        return resp.text
    except Exception as e:
        logging.warning("Requests error for %s: %s", url, e)
        return None

def wait_for_content(driver: webdriver.Chrome, timeout: int = 15):
    # Wait for document ready
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )
    # Try to wait for any main selector if present
    end_time = time.time() + timeout
    while time.time() < end_time:
        for sel in WAIT_SELECTORS:
            try:
                if driver.find_elements(By.CSS_SELECTOR, sel):
                    return
            except Exception:
                pass
        time.sleep(0.3)

def fetch_html_selenium(driver: webdriver.Chrome, url: str, timeout: int = 15) -> Optional[str]:
    try:
        driver.get(url)
        wait_for_content(driver, timeout)
        return driver.page_source
    except (TimeoutException, WebDriverException) as e:
        logging.warning("Selenium error for %s: %s", url, e)
        return None

def get_main_content(soup: BeautifulSoup) -> Tag:
    for sel in MAIN_SELECTORS:
        el = soup.select_one(sel)
        if el:
            return el
    return soup.body or soup

def clean_text(s: str) -> str:
    if not s:
        return ""
    s = s.replace("\xa0", " ").replace("\r", "\n")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()

def heading_rank(tag: Tag) -> int:
    # Lower is higher priority (h1=1). Non-heading strong/b treated as 5, others 10
    if not isinstance(tag, Tag):
        return 10
    if tag.name and tag.name.lower() in ["h1", "h2", "h3", "h4", "h5", "h6"]:
        return int(tag.name[1]) if tag.name[1].isdigit() else 10
    if tag.name and tag.name.lower() in ["strong", "b"]:
        return 5
    return 10

def is_publication_like(text: str) -> bool:
    if not text:
        return False
    t = text.strip()
    if STOP_RE.search(t):
        return True
    if DOI_RE.search(t):
        return True
    if JOURNAL_CUES_RE.search(t):
        return True
    if YEAR_LINE_RE.search(t):
        return True
    if BIB_MARK_RE.search(t):
        return True
    # Heuristic: too many separators/commas and et al.
    if "et al" in t.lower():
        return True
    if t.count(",") >= 3 and re.search(r"\b[A-Z][a-z]{2,}\b", t):
        return True
    return False

def extract_name(soup: BeautifulSoup, main: Tag) -> str:
    # 1) label “姓名：”
    text = (main or soup).get_text("\n", strip=True)
    m = re.search(r"(?:姓名|Name)\s*[:：]\s*([^\s，,;；|/()\n]{2,30})", text)
    if m:
        return m.group(1).strip()

    # 2) Top-level headers
    for tag in soup.select("h1, h2"):
        t = clean_text(tag.get_text(" ", strip=True))
        if not t:
            continue
        # Often page titles contain the name at the beginning
        m2 = re.match(r"^\s*([\u4e00-\u9fa5·]{2,8})", t)
        if m2:
            return m2.group(1)
        m3 = re.match(r"^\s*([A-Z][A-Za-z.\-]*(?:\s+[A-Z][A-Za-z.\-]*){0,3})", t)
        if m3:
            return m3.group(1).strip()

    # 3) Fallback to document title
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    if title:
        base = re.split(r"[-_—|｜]", title)[0].strip()
        base = re.sub(r"中南大学.*$", "", base).strip() or base
        if 2 <= len(base) <= 40:
            return base
    return ""

def prefer_email(emails: List[str]) -> str:
    if not emails:
        return ""
    # Rank by domain preference
    def rank(e: str) -> Tuple[int, int]:
        dom = e.split("@")[-1].lower()
        for i, suf in enumerate(EMAIL_DOMAIN_PREFERENCE):
            if dom.endswith(suf):
                return (i, len(dom))
        return (len(EMAIL_DOMAIN_PREFERENCE) + 1, len(dom))
    emails_sorted = sorted(set(emails), key=rank)
    return emails_sorted[0]

def extract_email(soup: BeautifulSoup, main: Tag) -> str:
    # mailto first
    a = soup.select_one('a[href^="mailto:"]')
    if a:
        href = a.get("href", "")
        mail = href.split(":", 1)[1].strip() if ":" in href else href.strip()
        if EMAIL_REGEX.search(mail):
            return mail
    # else scan text
    text = (main or soup).get_text("\n", strip=True)
    emails = EMAIL_REGEX.findall(text)
    if not emails:
        return ""
    return prefer_email(emails)

def looks_like_research_heading(tag: Tag) -> bool:
    if not isinstance(tag, Tag):
        return False
    if tag.name and tag.name.lower() in ["h1","h2","h3","h4","strong","b","div","span","p"]:
        txt = tag.get_text(" ", strip=True)
        if txt and RESEARCH_HEADINGS_RE.search(txt):
            return True
    return False

def collect_after_heading(heading: Tag, limit_chars: int = 6000) -> str:
    # If heading is <strong>/<b> inside <p>, promote start to that parent <p>
    start = heading
    if heading.name in ("strong", "b") and heading.parent:
        start = heading.parent

    texts: List[str] = []
    start_rank = heading_rank(heading)
    node = start.next_sibling
    nodes = 0
    consecutive_pub_like = 0

    while node and nodes < 120:
        nodes += 1
        if isinstance(node, NavigableString):
            s = clean_text(str(node))
            if s:
                if is_publication_like(s):
                    break
                texts.append(s)
        elif isinstance(node, Tag):
            # Stop at next heading of similar or higher level
            if node.name and re.match(r"h[1-6]", node.name, re.I):
                # If next heading is also research-heading, allow once to include immediate block; else stop
                if looks_like_research_heading(node):
                    # include nothing here; just skip to its next sibling and continue (avoid duplicate heading text)
                    node = node.next_sibling
                    continue
                break

            node_text = clean_text(node.get_text("\n", strip=True))
            if not node_text:
                node = node.next_sibling
                continue

            # Hard stop if block contains stop keywords or looks publication-like
            if STOP_RE.search(node_text):
                break

            # If this whole block looks like publications, stop
            if is_publication_like(node_text):
                consecutive_pub_like += 1
                if consecutive_pub_like >= 1:
                    break
            else:
                consecutive_pub_like = 0

            if node.name in ("ul", "ol"):
                li_texts = []
                pub_like_count = 0
                for li in node.find_all("li", recursive=False):
                    t = clean_text(li.get_text(" ", strip=True))
                    if not t:
                        continue
                    if is_publication_like(t):
                        pub_like_count += 1
                        # If list is publication-like, stop entirely
                        if pub_like_count >= 1:
                            li_texts = []
                            break
                        else:
                            continue
                    li_texts.append("• " + t)
                if not li_texts:
                    # looks like publication list or empty — stop
                    break
                texts.extend(li_texts)
            else:
                # Regular paragraph/div
                # Keep only sentences that mention research-related words when mixed content
                if RESEARCH_HEADINGS_RE.search(node_text) or re.search(r"(研究|research|focus|interest|方向|领域)", node_text, re.I):
                    texts.append(node_text)
                else:
                    # Avoid dragging unrelated biography/work/education content
                    # Keep short if adjacent to heading and clearly topical
                    if len(node_text) <= 300 and not STOP_RE.search(node_text):
                        texts.append(node_text)

        # Stop if too long
        if sum(len(x) for x in texts) >= limit_chars:
            break
        node = node.next_sibling

    # Cleanup: remove any trailing lines that look publication-like
    lines = []
    for t in "\n".join(texts).splitlines():
        t = t.strip()
        if not t:
            continue
        if is_publication_like(t):
            break
        lines.append(t)
    return clean_text("\n".join(lines))

def find_research_interest(main: Tag) -> str:
    # 1) Heading-first strategy
    candidates: List[Tag] = []
    for tag in main.find_all(True):
        if tag.name in ("script", "style", "noscript"):
            continue
        if looks_like_research_heading(tag):
            candidates.append(tag)
    for cand in candidates:
        s = collect_after_heading(cand)
        s = clean_text(s)
        if s and len(s) >= 10:
            return s

    # 2) Fallback: paragraph window near keywords
    paras = [p for p in main.find_all(["p", "div", "li"]) if clean_text(p.get_text(" ", strip=True))]
    # pick first paragraph that contains research-ish keywords
    idx = -1
    for i, p in enumerate(paras):
        t = clean_text(p.get_text(" ", strip=True))
        if re.search(r"(研究|research|interest|focus|方向|领域)", t, re.I):
            idx = i
            break
    if idx != -1:
        win = paras[max(0, idx-1): idx+4]  # ±3 window total
        pieces = []
        for el in win:
            t = clean_text(el.get_text(" ", strip=True))
            if not t:
                continue
            if STOP_RE.search(t) or is_publication_like(t):
                break
            pieces.append(t)
        s = clean_text("\n".join(pieces))
        if s:
            # Final safety filter: trim anything after stop cues
            s_lines = []
            for ln in s.splitlines():
                if is_publication_like(ln):
                    break
                s_lines.append(ln.strip())
            return clean_text("\n".join(s_lines))

    return ""

def extract_from_html(html: str, url: str) -> Tuple[str, str, str]:
    soup = BeautifulSoup(html, "lxml")
    main = get_main_content(soup)
    name = extract_name(soup, main)
    email = extract_email(soup, main)
    ri = find_research_interest(main)
    return name, email, ri

def check_robots(url: str, user_agent: str) -> bool:
    try:
        p = urlparse(url)
        robots_url = f"{p.scheme}://{p.netloc}/robots.txt"
        rp = robotparser.RobotFileParser()
        rp.set_url(robots_url)
        rp.read()
        path = p.path or "/"
        if p.query:
            path = path + "?" + p.query
        return rp.can_fetch(user_agent, path)
    except Exception:
        # If robots cannot be fetched, default to allow (unless flag says otherwise)
        return True

def append_block(output_file: str, name: str, email: str, research: str, url: str):
    with open(output_file, "a", encoding="utf-8") as f:
        f.write(f"Name: {name}\n")
        f.write(f"Email: {email}\n")
        f.write(f"Research interest: {research}\n")
        f.write(f"Profile link: {url}\n")
        f.write("---\n\n")
        f.flush()

def process_profile(
    url: str,
    args,
    session: requests.Session,
    driver: Optional[webdriver.Chrome],
) -> Tuple[str, str, str, str]:
    """
    Returns (name, email, research, reason_if_failed_or_empty_string)
    reason_if_failed used only when research == "" to craft FAILED message.
    """
    reason = ""
    html = None
    use_requests_first = not args.selenium_first

    def try_requests():
        return fetch_html_requests(session, url, timeout=25)

    def try_selenium():
        nonlocal driver
        if driver is None:
            try:
                driver = build_driver(headless=args.headless, user_agent=args.user_agent)
            except Exception as e:
                logging.error("Failed to initialize Selenium driver: %s", e)
                return None
        return fetch_html_selenium(driver, url, timeout=20)

    # Fetch
    html_attempts: List[Tuple[str, Optional[str]]] = []
    for attempt in range(args.retries + 1):
        if use_requests_first:
            html = try_requests()
            html_attempts.append(("requests", html))
            if html:
                break
            # fallback selenium
            html = try_selenium()
            html_attempts.append(("selenium", html))
            if html:
                break
        else:
            html = try_selenium()
            html_attempts.append(("selenium", html))
            if html:
                break
            # fallback requests
            html = try_requests()
            html_attempts.append(("requests", html))
            if html:
                break

    if not html:
        return "", "", "", "page load failed"

    name, email, ri = extract_from_html(html, url)
    # If research interest empty or very short, try the other fetch method (one more time)
    if (not ri or len(ri) < 10) and len(html_attempts) >= 1:
        tried_by = [m for m, h in html_attempts if h]
        if "requests" in tried_by and "selenium" not in tried_by:
            html2 = try_selenium()
            if html2:
                name2, email2, ri2 = extract_from_html(html2, url)
                # Prefer non-empty research interest
                if ri2 and len(ri2) > len(ri):
                    name, email, ri = (name2 or name), (email2 or email), ri2
        elif "selenium" in tried_by and "requests" not in tried_by:
            html2 = try_requests()
            if html2:
                name2, email2, ri2 = extract_from_html(html2, url)
                if ri2 and len(ri2) > len(ri):
                    name, email, ri = (name2 or name), (email2 or email), ri2

    # Final cleaning and enforcement:
    if ri:
        # Trim after any stop keyword that slipped
        parts: List[str] = []
        for line in ri.splitlines():
            if is_publication_like(line):
                break
            parts.append(line.strip())
        ri = clean_text("\n".join(parts))
        # Truncate
        if args.truncate and len(ri) > args.truncate:
            ri = ri[:args.truncate].rstrip() + " [...]"

    return name, email, ri, "" if ri else "no research-interest text found"

def main():
    setup_logging()
    parser = argparse.ArgumentParser(description="Extract only research interests from faculty profile pages.")
    parser.add_argument("--input-file", required=True, help="UTF-8 text file with one profile URL per line.")
    parser.add_argument("--output-file", default="output.txt", help="Output text file (UTF-8). Default: output.txt")
    parser.add_argument("--headless", action="store_true", help="Run browser in headless mode (Selenium).")
    parser.add_argument("--selenium-first", action="store_true", help="Use Selenium first, then requests as fallback.")
    parser.add_argument("--delay-min", type=float, default=0.5, help="Min delay between profiles (seconds).")
    parser.add_argument("--delay-max", type=float, default=2.0, help="Max delay between profiles (seconds).")
    parser.add_argument("--max-profiles", type=int, default=0, help="Process at most N profiles (0 = all).")
    parser.add_argument("--retries", type=int, default=1, help="Retries per URL (per fetch method).")
    parser.add_argument("--truncate", type=int, default=4000, help="Max chars for research interest (0 = no limit).")
    parser.add_argument("--respect-robots", action="store_true", help="Check robots.txt and skip disallowed URLs.")
    parser.add_argument("--user-agent", default=DEFAULT_UA, help="User-Agent string.")
    args = parser.parse_args()

    # Read URLs
    with open(args.input_file, "r", encoding="utf-8") as f:
        raw_urls = [ln.strip() for ln in f if ln.strip()]

    # Dedup by normalized URL (keep input order deterministically)
    seen_norm: Set[str] = set()
    urls: List[str] = []
    for u in raw_urls:
        nu = normalize_url(u)
        if nu in seen_norm:
            logging.info("Duplicate URL (normalized) skipped: %s", u)
            continue
        seen_norm.add(nu)
        urls.append(u)

    if args.max_profiles and args.max_profiles > 0:
        urls = urls[:args.max_profiles]

    # Prepare output file (truncate)
    with open(args.output_file, "w", encoding="utf-8") as f:
        f.write("")  # clear

    session = create_requests_session(args.retries, args.user_agent)
    driver: Optional[webdriver.Chrome] = None

    # Dedup by email
    seen_emails: Set[str] = set()

    processed = 0
    for idx, url in enumerate(urls, 1):
        url_norm = normalize_url(url)
        logging.info("(%d/%d) Processing: %s", idx, len(urls), url)

        if args.respect_robots and not check_robots(url, args.user_agent):
            logging.warning("Blocked by robots.txt, skipping: %s", url)
            append_block(args.output_file, "", "", "<FAILED: robots.txt disallows>", url)
            continue

        # Polite delay
        delay = random.uniform(max(0, args.delay_min), max(args.delay_min, args.delay_max))
        time.sleep(delay)

        try:
            name, email, ri, fail_reason = process_profile(url, args, session, driver)
        except Exception as e:
            logging.exception("Unhandled error on %s: %s", url, e)
            append_block(args.output_file, "", "", f"<FAILED: {e}>", url)
            continue

        # Dedup by institutional email (skip if already seen and institutional)
        if email:
            e_low = email.lower()
            if any(e_low.endswith(suf) for suf in EMAIL_DOMAIN_PREFERENCE):
                if e_low in seen_emails:
                    logging.info("Duplicate institutional email detected; skipping profile: %s (%s)", url, email)
                    continue
                seen_emails.add(e_low)

        if not ri:
            ri_out = f"<FAILED: {fail_reason}>"
        else:
            ri_out = ri

        append_block(args.output_file, name or "", email or "", ri_out, url)
        processed += 1

    # Cleanup Selenium
    if driver is not None:
        try:
            driver.quit()
        except Exception:
            pass

    logging.info("Done. Wrote %d profile blocks to %s", processed, args.output_file)

if __name__ == "__main__":
    main()