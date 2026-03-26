#!/usr/bin/env python3
"""
Faculty profile batch scraper - prioritizes ID-based DOM extraction for the
Institute template (IDs: #xm, #dzyj, #yjfx, #bz3). Falls back to JS-variable
extraction when IDs are absent.

Output format (text file):
Name:
Email:
Research Interest:
Profile Link:
--------
"""

from typing import Optional, List, Dict
import re
import html
import time
import random
import logging
import requests
from bs4 import BeautifulSoup

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
logger = logging.getLogger("faculty-scraper")

# -----------------------------
# JS string capture helpers
# -----------------------------
_JS_STR_DOUBLE_RE = r'"((?:[^"\\]|\\.)*)"'
_JS_STR_SINGLE_RE = r"'((?:[^'\\]|\\.)*)'"
_JS_VAR_TEMPLATE = r'(?:\b(?:var|let|const)\b\s*)?{varname}\s*=\s*(?:' + _JS_STR_DOUBLE_RE + r'|' + _JS_STR_SINGLE_RE + r')'


def _unescape_js_string(s: Optional[str]) -> str:
    """Unescape common JS escapes and HTML entities into readable text."""
    if not s:
        return ''
    s = s.replace(r'\\', '\\')
    s = s.replace(r'\"', '"')
    s = s.replace(r"\'", "'")
    s = s.replace(r'\/', '/')
    s = s.replace(r'\n', '\n')
    s = s.replace(r'\r', '')
    s = s.replace(r'\t', '\t')
    s = s.strip()
    return html.unescape(s)


def _extract_first_js_var(html_text: str, var_candidates: List[str]) -> Optional[str]:
    """
    Try a list of JS variable names; return the first matched unescaped string,
    or None if not found.
    """
    if not html_text:
        return None
    for var in var_candidates:
        pattern = _JS_VAR_TEMPLATE.format(varname=re.escape(var))
        m = re.search(pattern, html_text, re.DOTALL | re.IGNORECASE)
        if m:
            # m.group(1) -> double-quoted, group(2) -> single-quoted
            raw = m.group(1) if m.group(1) is not None else m.group(2)
            if raw is None:
                continue
            return _unescape_js_string(raw)
    return None


# -----------------------------
# DOM cleaning helpers
# -----------------------------
def _clean_text_from_element(elem: Optional[BeautifulSoup], separator: str = ' ', multi_line: bool = False) -> str:
    """
    Safely get text from BeautifulSoup element. Uses separator between nested tags.
      - If elem is None -> return empty string.
      - If multi_line is True -> use '\n' to preserve paragraphs, else use separator.
    """
    if not elem:
        return ''
    sep = '\n' if multi_line else separator
    txt = elem.get_text(separator=sep, strip=True)
    if not txt or txt.strip() == '&nbsp;':
        return ''
    # Normalize multiple blank lines
    if multi_line:
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        return '\n'.join(lines)
    return ' '.join(txt.split())


def _normalize_email(candidate: Optional[str]) -> str:
    """Fix @@ obfuscation and extract first email-like token if present."""
    if not candidate:
        return ''
    s = candidate.strip().replace('@@', '@')
    # find first typical email pattern
    m = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', s)
    return m.group(0) if m else s


def _normalize_field(value: Optional[str]) -> str:
    """Map None or placeholders like &nbsp; to empty string, else trimmed value."""
    if value is None:
        return ''
    v = value.strip()
    if not v or v == '&nbsp;':
        return ''
    return v


# -----------------------------
# Main scraper (accepts raw HTML string)
# -----------------------------
def scrape_faculty_profile(html_source: str) -> Dict[str, str]:
    """
    Parse the provided raw HTML string and return a dict:
      { "name", "email", "research_areas", "research_interests" }

    Priority:
      1) Use DOM IDs (#xm, #dzyj, #yjfx, #bz3) when present.
      2) If any missing, fallback to JS variable extraction using safe regex patterns.

    Notes:
      - Research interest output returns cleaned text (for #bz3 we flatten nested tags).
      - Research Areas (#yjfx) returned as a short phrase (single-line).
      - Missing or placeholder values -> '' (empty string).
    """
    result = {
        "name": "",
        "email": "",
        "research_areas": "",
        "research_interests": ""
    }

    if not isinstance(html_source, str) or not html_source.strip():
        return result

    # Parse DOM first (ID-based extraction)
    soup = BeautifulSoup(html_source, 'html.parser')

    # 1) Name (#xm)
    name_el = soup.find(id='xm')
    name = _clean_text_from_element(name_el, separator=' ', multi_line=False)
    name = _normalize_field(name)

    # 2) Email (#dzyj)
    email_el = soup.find(id='dzyj')
    email = _clean_text_from_element(email_el, separator=' ', multi_line=False)
    email = _normalize_email(_normalize_field(email))

    # 3) Research Direction / Areas (#yjfx)
    yjfx_el = soup.find(id='yjfx')
    research_areas = _clean_text_from_element(yjfx_el, separator=' ', multi_line=False)
    research_areas = _normalize_field(research_areas)

    # 4) Research Work / Interests (#bz3) - detailed
    bz3_el = soup.find(id='bz3')
    # Use single-line flattening for nested <p> per your instruction.
    # If you prefer paragraphs preserved, set multi_line=True.
    research_interests = _clean_text_from_element(bz3_el, separator=' ', multi_line=False)
    research_interests = _normalize_field(research_interests)

    # If any required field is missing, fallback to JS-variable extraction (inline script patterns)
    # Candidate JS var names observed in previous examples:
    if not name:
        name_js = _extract_first_js_var(html_source, ["en_xm", "xm_en", "xm", "name"])
        name = _normalize_field(name_js)
    if not email:
        email_js = _extract_first_js_var(html_source, ["dzyj", "en_dzyj", "email", "mail"])
        email = _normalize_email(_normalize_field(email_js))
    if not research_areas:
        yjfx_js = _extract_first_js_var(html_source, ["en_yjfx", "enyjfx", "yjfx"])
        research_areas = _normalize_field(yjfx_js)
    if not research_interests:
        bz3_js = _extract_first_js_var(html_source, ["qtbz3", "bz3", "en_bz3", "en_qtbz3"])
        # bz3_js may contain HTML fragments -> clean them
        if bz3_js:
            research_interests = _clean_text_from_element(BeautifulSoup(bz3_js, 'html.parser'), separator=' ', multi_line=False)
            research_interests = _normalize_field(research_interests)

    # As a safety: do not extract content from misleading sections.
    # If research_interests contains headings like 'Publications' or 'Main Achievements', strip them off.
    # We'll attempt a simple guard: drop content after those words if they appear.
    for stop_kw in ['Main Achievements', 'Publications', 'Personal Profile', 'Research Unit']:
        if stop_kw.lower() in research_interests.lower():
            # truncate at the stop keyword (case-insensitive)
            idx = research_interests.lower().find(stop_kw.lower())
            research_interests = research_interests[:idx].strip()
            break

    result['name'] = name or ''
    result['email'] = email or ''
    result['research_areas'] = research_areas or ''
    result['research_interests'] = research_interests or ''

    return result


# -----------------------------
# Fetch helper & batch writer
# -----------------------------
def fetch_html(url: str, timeout: int = 12) -> Optional[str]:
    """Fetch HTML using requests, return text or None on error."""
    try:
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (compatible; FacultyScraper/1.0)"}, timeout=timeout)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as e:
        logger.warning("Failed to fetch %s : %s", url, e)
        return None


def process_urls_and_write_text(urls: List[str], output_file: str, delay: float = 1.0) -> None:
    """
    Fetch each URL, extract required fields, and write to output_file in the exact format:
      Name:
      Email:
      Research Interest:
      Profile Link:
      --------
    Research Interest prefers 'research_interests' (detailed). If empty, uses research_areas.
    """
    with open(output_file, 'w', encoding='utf-8') as fout:
        total = len(urls)
        for i, url in enumerate(urls, start=1):
            logger.info("[%d/%d] Processing: %s", i, total, url)
            html_text = fetch_html(url)
            if html_text is None:
                # write empty fields but include profile link
                fout.write("Name:\n")
                fout.write("Email:\n")
                fout.write("Research Interest:\n")
                fout.write(f"Profile Link: {url}\n")
                fout.write("--------\n")
            else:
                data = scrape_faculty_profile(html_text)
                # Choose detailed research_interests if available, else research_areas
                research_out = data.get('research_interests') or data.get('research_areas') or ''
                # Write fields; empty strings produce blank lines as requested
                fout.write(f"Name: {data.get('name','')}\n")
                fout.write(f"Email: {data.get('email','')}\n")
                # If research_out is multiline, write on next line for readability
                if '\n' in research_out:
                    fout.write("Research Interest:\n")
                    fout.write(f"{research_out}\n")
                else:
                    fout.write(f"Research Interest: {research_out}\n")
                fout.write(f"Profile Link: {url}\n")
                fout.write("--------\n")

            # Polite delay with jitter
            if i < total:
                time.sleep(delay + random.random() * 0.4)

    logger.info("Finished writing output to %s", output_file)


def read_urls_from_file(filename: str) -> List[str]:
    urls: List[str] = []
    try:
        with open(filename, 'r', encoding='utf-8') as fh:
            for line in fh:
                u = line.strip()
                if u and not u.startswith('#'):
                    urls.append(u)
    except FileNotFoundError:
        logger.error("URLs file not found: %s", filename)
    return urls


# -----------------------------
# CLI entry
# -----------------------------
if __name__ == "__main__":
    URLS_FILE = "urls.txt"          # one profile URL per line
    OUTPUT_FILE = "faculty_profiles.txt"
    DELAY_SECONDS = 1.0

    urls_list = read_urls_from_file(URLS_FILE)
    if not urls_list:
        logger.error("No URLs found in %s. Please add one URL per line.", URLS_FILE)
    else:
        logger.info("Starting scraping of %d URLs", len(urls_list))
        process_urls_and_write_text(urls_list, OUTPUT_FILE, delay=DELAY_SECONDS)
        logger.info("Scraping complete. Output file: %s", OUTPUT_FILE)
