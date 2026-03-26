#!/usr/bin/env python3
"""
Batch scrape faculty profiles (JS-variable inline pages) and write
results to a plain text file in the requested format:

Name:
Email:
Research Interest:
Profile Link:
--------

Requires:
    pip install requests beautifulsoup4

Usage:
    1) Put one profile URL per line in urls.txt (or change URLS_FILE variable).
    2) python scrape_and_save.py
"""

import re
import html
import logging
import time
import random
from typing import Optional, List, Dict
from bs4 import BeautifulSoup
import requests

# ---------------------------
# Logging
# ---------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("faculty-scraper")

# ---------------------------
# Small JS-string utilities
# ---------------------------
_JS_STR_DOUBLE_RE = r'"((?:[^"\\]|\\.)*)"'
_JS_STR_SINGLE_RE = r"'((?:[^'\\]|\\.)*)'"
_JS_VAR_TEMPLATE = r'(?:\b(?:var|let|const)\b\s*)?{varname}\s*=\s*(?:' + _JS_STR_DOUBLE_RE + r'|' + _JS_STR_SINGLE_RE + r')'


def _unescape_js_string(s: str) -> str:
    """Unescape common JS escapes and HTML entities."""
    if s is None:
        return ''
    s = s.replace(r'\\', '\\')
    s = s.replace(r'\"', '"')
    s = s.replace(r"\'", "'")
    s = s.replace(r'\/', '/')
    s = s.replace(r'\n', '\n')
    s = s.replace(r'\r', '')
    s = s.replace(r'\t', '\t')
    s = s.strip()
    s = html.unescape(s)
    return s


def _extract_first_js_var(html_text: str, var_candidates: List[str]) -> Optional[str]:
    """Try candidate JS var names; return the unescaped string or None."""
    if not html_text:
        return None
    for var in var_candidates:
        pattern = _JS_VAR_TEMPLATE.format(varname=re.escape(var))
        m = re.search(pattern, html_text, re.DOTALL | re.IGNORECASE)
        if m:
            raw = m.group(1) if m.group(1) is not None else m.group(2)
            if raw is None:
                continue
            return _unescape_js_string(raw)
    return None


def _clean_html_fragment_to_text(fragment: str) -> str:
    """Convert HTML fragment into readable text preserving paragraph breaks."""
    if not fragment:
        return ''
    soup = BeautifulSoup(fragment, 'html.parser')
    text = soup.get_text(separator='\n', strip=True)
    text = '\n'.join(line.strip() for line in text.splitlines() if line.strip())
    return text


def _normalize_field(value: Optional[str]) -> str:
    """Return empty string for None / placeholder / whitespace-only; otherwise trimmed string."""
    if value is None:
        return ''
    v = value.strip()
    if not v or v == '&nbsp;':
        return ''
    return v


# ---------------------------
# Core scraping function (as requested)
# ---------------------------
def scrape_faculty_profile(html: str) -> Dict[str, str]:
    """
    Extract name, email, research_areas, research_interests from a raw HTML string
    where values are set via inline JavaScript variables such as:
        var en_xm="WANG Hongyan";
        var dzyj="someone@@domain.ac.cn";
        var en_yjfx="Research Areas...";
        var qtbz3="<div>Research Interests...</div>";
    Returns dict with keys: name, email, research_areas, research_interests (all strings).
    """
    result = {"name": "", "email": "", "research_areas": "", "research_interests": ""}

    if not isinstance(html, str) or not html.strip():
        return result

    try:
        name_candidates = ["en_xm", "xm_en", "name", "enName"]
        email_candidates = ["dzyj", "en_dzyj", "email", "mail"]
        research_areas_candidates = ["en_yjfx", "enyjfx", "yjfx", "research_areas"]
        research_interests_candidates = ["qtbz3", "en_qtbz3", "research_interests", "en_yj"]

        raw_name = _extract_first_js_var(html, name_candidates)
        raw_email = _extract_first_js_var(html, email_candidates)
        raw_research_areas = _extract_first_js_var(html, research_areas_candidates)
        raw_research_interests = _extract_first_js_var(html, research_interests_candidates)

        name = _normalize_field(raw_name)
        email = _normalize_field(raw_email)
        research_areas = _normalize_field(raw_research_areas)
        research_interests_raw = _normalize_field(raw_research_interests)

        # Email: convert obfuscation @@ -> @ and canonicalize
        if email:
            email = email.replace('@@', '@').strip()
            m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email)
            email = m.group(0) if m else email

        # Clean research_interests (HTML fragment -> text)
        research_interests = ''
        if research_interests_raw:
            research_interests = _clean_html_fragment_to_text(research_interests_raw)

        # Clean research_areas (small HTML or text -> one line)
        if research_areas:
            research_areas = _clean_html_fragment_to_text(research_areas).replace('\n', ' ').strip()

        result["name"] = name or ""
        result["email"] = email or ""
        result["research_areas"] = research_areas or ""
        result["research_interests"] = research_interests or ""

        return result

    except Exception as e:
        logger.exception("Error while parsing profile HTML: %s", e)
        return result


# ---------------------------
# Fetch helper
# ---------------------------
def fetch_html(url: str, timeout: int = 12) -> Optional[str]:
    """Fetch a URL with requests; return text or None on error."""
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; FacultyScraper/1.0)"}, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        logger.warning("Failed to fetch %s : %s", url, e)
        return None


# ---------------------------
# Batch runner and writer
# ---------------------------
def process_urls_and_write_text(urls: List[str], output_file: str, delay: float = 1.0):
    """
    Process list of profile URLs and write results to 'output_file' in the required format:
    Name:
    Email:
    Research Interest:
    Profile Link: 
    --------
    """
    with open(output_file, 'w', encoding='utf-8') as fout:
        total = len(urls)
        for idx, url in enumerate(urls, start=1):
            logger.info("[%d/%d] Fetching: %s", idx, total, url)
            html = fetch_html(url)
            if html is None:
                logger.info("  -> Skipping due to fetch error.")
                # Still write an entry with empty fields and the profile link (or omit? user asked to include link)
                fout.write("Name:\n")
                fout.write("Email:\n")
                fout.write("Research Interest:\n")
                fout.write(f"Profile Link: {url}\n")
                fout.write("--------\n")
            else:
                data = scrape_faculty_profile(html)
                # For output, prefer research_interests (detailed); if empty, fall back to research_areas
                research_out = data.get("research_interests") or data.get("research_areas") or ""
                # Normalize multi-line research output to single paragraphs while preserving moderate line breaks
                if research_out:
                    # collapse repeated blank lines and trim edges
                    lines = [ln.strip() for ln in research_out.splitlines() if ln.strip()]
                    research_out = "\n".join(lines)

                fout.write(f"Name: {data.get('name','')}\n")
                fout.write(f"Email: {data.get('email','')}\n")
                fout.write("Research Interest: ")
                # If research_out is multiline, write it on next line for readability
                if '\n' in research_out:
                    fout.write("\n")
                    fout.write(f"{research_out}\n")
                else:
                    fout.write(f"{research_out}\n")
                fout.write(f"Profile Link: {url}\n")
                fout.write("--------\n")

            # polite delay with small jitter
            if idx < total:
                time.sleep(delay + random.random() * 0.5)

    logger.info("Wrote output to %s", output_file)


# ---------------------------
# CLI behaviour (simple)
# ---------------------------
def read_urls_from_file(filename: str) -> List[str]:
    urls = []
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            for line in f:
                u = line.strip()
                if u and not u.startswith('#'):
                    urls.append(u)
    except FileNotFoundError:
        logger.error("URLs file not found: %s", filename)
    return urls


if __name__ == "__main__":
    URLS_FILE = "urls.txt"            # one URL per line
    OUTPUT_FILE = "faculty_profiles.txt"
    DELAY_SECONDS = 1.0               # base delay between requests

    urls = read_urls_from_file(URLS_FILE)
    if not urls:
        logger.error("No URLs to process. Please create '%s' with profile URLs (one per line).", URLS_FILE)
    else:
        logger.info("Starting processing of %d URLs", len(urls))
        process_urls_and_write_text(urls, OUTPUT_FILE, delay=DELAY_SECONDS)
        logger.info("Finished. Output: %s", OUTPUT_FILE)
