#!/usr/bin/env python3
"""
faculty_profile_extractor.py

Purpose
-------
Extracts structured profile information from university faculty profile pages (English/Chinese).
It focuses on: name, emails, research interest/direction/field, research projects, and publications.

Key features
------------
- Works with static pages (requests + BeautifulSoup) and optionally with dynamic pages (Selenium Chrome) using --render flag.
- Robust heading-based extraction using START / STOP keyword lists (English + Chinese).
- Sections are returned as raw text and also post-processed into fields: research_interests, research_projects, publications, research_fields.
- Emits JSONL output (one JSON object per URL) and saves raw HTML for later debugging.
- Adds a simple confidence score for each extracted field.

Usage
-----
python faculty_profile_extractor.py --input urls.txt --output results.jsonl --savedir ./pages --render

Requirements
------------
- Python 3.8+
- pip install requests beautifulsoup4 lxml tqdm
- If using --render: selenium and a ChromeDriver compatible with your Chrome version
  pip install selenium

Notes
-----
This extractor is conservative: it uses heading matching to find content. If no heading is found it will try heuristics but mark low confidence.
The "raw_sections" field contains a mapping heading -> extracted text and is useful for later AI-based cleaning.

"""

from __future__ import annotations
import argparse
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import requests
from bs4 import BeautifulSoup, Tag
from tqdm import tqdm

# Optional selenium (only if user passes --render)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    SELENIUM_AVAILABLE = True
except Exception:
    SELENIUM_AVAILABLE = False

# ---------------------------------------------
# Configurable keyword sets (English + Chinese)
# ---------------------------------------------
START_KEYWORDS = [
    # English
    r"research direction",
    r"research directions",
    r"research interest",
    r"research interests",
    r"research area",
    r"research areas",
    r"research field",
    r"research fields",
    r"research",
    r"research focus",
    # Chinese
    r"研究方向",
    r"研究兴趣",
    r"研究领域",
    r"主要研究方向",
]

STOP_KEYWORDS = [
    # English
    r"thesis",
    r"articles published",
    r"publications",
    r"scientific research project",
    r"scientific research projects",
    r"projects",
    r"education",
    r"abroad study",
    r"participation in the academic community",
    r"contact",
    r"email",
    r"phone",
    r"research foundation",
    r"research project",
    r"resume",
    r"cv",
    # Chinese
    r"论文",
    r"科研项目",
    r"研究基金",
    r"教育经历",
    r"获奖",
    r"联系方式",
    r"邮箱",
    r"电话",
]

# Misleading keywords that contain the word "research" but are not the personal research interests
MISLEADING_KEYWORDS = [
    r"research foundation",
    r"research project",
    r"participation in the academic community",
    r"abroad study",
]

# Compile regexes
START_RE = re.compile("|".join(f"(?:{k})" for k in START_KEYWORDS), flags=re.I)
STOP_RE = re.compile("|".join(f"(?:{k})" for k in STOP_KEYWORDS), flags=re.I)
MISLEADING_RE = re.compile("|".join(f"(?:{k})" for k in MISLEADING_KEYWORDS), flags=re.I)

EMAIL_RE = re.compile(r"[\w\.-]+@[\w\.-]+\.[a-zA-Z]{2,}")
YEAR_RE = re.compile(r"\b(19|20)\d{2}\b")

# ------------------------------------------------------------------
# Helpers: fetching, cleaning text, heuristics for publications, headings
# ------------------------------------------------------------------

def fetch_page(url: str, timeout: int = 20, render: bool = False, driver: Optional[object] = None) -> Tuple[str, str]:
    """Fetch a page and return (final_url, html). If render=True, requires selenium driver."""
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"
    }
    if render:
        if not SELENIUM_AVAILABLE or driver is None:
            raise RuntimeError("Selenium rendering requested but selenium is not available or driver not provided")
        driver.get(url)
        time.sleep(1.0)
        return driver.current_url, driver.page_source
    else:
        resp = requests.get(url, headers=headers, timeout=timeout)
        resp.encoding = resp.apparent_encoding or resp.encoding
        resp.raise_for_status()
        return resp.url, resp.text


def clean_text(s: str) -> str:
    """Normalize whitespace and remove non-printable characters."""
    if not s:
        return ""
    text = re.sub(r"\s+", " ", s).strip()
    return text


def find_name(soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
    """Try several heuristics to find full name and the selector/source.

    Returns (name, source_description)
    """
    # Common place in sample: <div class="news_detail"> <h3 align="center">Name</h3>
    h3 = soup.select_one("div.news_detail > h3, h3[align='center'], .news_detail h3")
    if h3 and h3.get_text(strip=True):
        return clean_text(h3.get_text()), "div.news_detail > h3"

    # Fallback: first H1..H3 on page
    for tag in ("h1", "h2", "h3"):
        el = soup.find(tag)
        if el and el.get_text(strip=True):
            return clean_text(el.get_text()), f"{tag}"

    # Fallback: title tag
    if soup.title and soup.title.string:
        title_text = clean_text(soup.title.string)
        # often title contains dash or pipe, try the left-most token
        parts = re.split(r"[-|—:\|]", title_text)
        if parts:
            candidate = parts[0].strip()
            if len(candidate) <= 60 and len(candidate.split()) <= 6:
                return candidate, "title"

    return None, None


def extract_emails(soup: BeautifulSoup) -> List[str]:
    text = soup.get_text(separator=" \n ")
    emails = set(re.findall(EMAIL_RE, text))
    # also check for mailto links
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        if href.startswith("mailto:"):
            m = re.search(EMAIL_RE, href)
            if m:
                emails.add(m.group(0))
    return sorted(emails)


def is_publication_paragraph(text: str) -> bool:
    """Heuristic: paragraphs containing a year and either journal indicators or IF: are likely publications."""
    if not text:
        return False
    if YEAR_RE.search(text) and ("IF" in text or "Journal" in text or "," in text and len(text) > 60):
        return True
    # Chinese heuristics: presence of '期', '卷', '号' plus a year
    if YEAR_RE.search(text) and any(x in text for x in ["期", "卷", "号"]):
        return True
    return False


def gather_section_from_start(start_node: Tag, stop_re: re.Pattern, max_nodes: int = 12) -> str:
    """Collect textual content from siblings after start_node until a stop condition is met."""
    contents: List[str] = []
    node = start_node.next_sibling
    nodes_taken = 0
    while node and nodes_taken < max_nodes:
        # Node might be a NavigableString or Tag
        if isinstance(node, Tag):
            text = node.get_text(separator=" ", strip=True)
            if not text:
                node = node.next_sibling
                continue
            # Stop if this node matches stop keywords or is clearly a heading
            if stop_re.search(text) or re.match(r"^\s*\\d+\.", text):
                break
            # If node itself contains a heading-like tag, break
            if node.name and node.name.lower() in ["h1", "h2", "h3", "h4", "strong", "b"]:
                # but allow strong inside p to be part of same section
                if node.name in ("strong", "b") and node.parent and node.parent.name == "p":
                    # treat <p><strong>Heading</strong></p> specially: skip text which is just heading
                    if node.get_text(strip=True) and len(node.get_text(strip=True)) < 80 and not stop_re.search(node.get_text()):
                        pass
                    else:
                        break
                else:
                    break

            contents.append(text)
            nodes_taken += 1
        else:
            # string node
            node_text = str(node).strip()
            if node_text:
                if stop_re.search(node_text):
                    break
                contents.append(node_text)
                nodes_taken += 1
        node = node.next_sibling
    return clean_text(" \n ".join(contents))


def extract_headed_sections(soup: BeautifulSoup) -> Dict[str, str]:
    """Find headings (h1-h6, strong in p, bold tokens) and collect their following paragraphs as sections."""
    sections: Dict[str, str] = {}

    # Candidate heading tags
    candidates = []
    # h1-h6
    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        candidates.append(h)
    # <p><strong>Heading</strong></p>
    for p in soup.find_all("p"):
        strong = p.find(["strong", "b"])
        if strong and strong.get_text(strip=True) and len(strong.get_text(strip=True)) < 100:
            candidates.append(strong)

    # also include <dt> tags
    for dt in soup.find_all("dt"):
        candidates.append(dt)

    # De-duplicate by id
    seen = set()
    for node in candidates:
        key = (node.name, node.get_text(strip=True)[:120])
        if key in seen:
            continue
        seen.add(key)
        heading_text = clean_text(node.get_text())
        if not heading_text:
            continue
        # Gather its section
        section_text = gather_section_from_start(node, STOP_RE)
        if section_text:
            sections[heading_text] = section_text

    return sections


def classify_sections(sections: Dict[str, str]) -> Dict[str, object]:
    """Based on headings and heuristics, map raw sections into target fields."""
    res = {
        "research_interests": [],
        "research_projects": [],
        "publications": [],
        "research_fields": [],
        "raw_sections": sections,
    }

    for heading, text in sections.items():
        key = heading.lower()
        # match start keywords
        if START_RE.search(key) and not MISLEADING_RE.search(key):
            res["research_interests"].append(text)
            continue
        # publications
        if re.search(r"publication|thesis|articles|论文|发表", key, flags=re.I) or is_publication_paragraph(text):
            # split by lines into list items
            pubs = [clean_text(x) for x in re.split(r"\n+|\d+\.\s+", text) if x.strip()]
            res["publications"].extend(pubs)
            continue
        # projects
        if re.search(r"project|projects|科研项目|研究项目", key, flags=re.I):
            items = [clean_text(x) for x in re.split(r"\n+|;|,|\.|\t", text) if x.strip()]
            res["research_projects"].extend(items)
            continue
        # research field heuristic
        if re.search(r"field|领域|area|方向", key, flags=re.I):
            res["research_fields"].append(text)
            continue
    # Post-process: flatten and deduplicate
    for fld in ("research_interests", "research_projects", "research_fields"):
        joined = " \n ".join(res[fld])
        # split on ; or \n to create short entries
        parts = [clean_text(x) for x in re.split(r";|\n|,|/", joined) if x.strip()]
        # deduplicate preserving order
        seen = set()
        final = []
        for p in parts:
            if p not in seen:
                seen.add(p)
                final.append(p)
        res[fld] = final

    # Publications already list-like
    # Simple confidence scores
    res["_confidence"] = {
        "research_interests": 0.9 if res["research_interests"] else 0.2,
        "research_projects": 0.9 if res["research_projects"] else 0.2,
        "publications": 0.9 if res["publications"] else 0.1,
        "research_fields": 0.8 if res["research_fields"] else 0.2,
    }
    return res

# ---------------------
# Main extractor per URL
# ---------------------

def extract_profile(url: str, render: bool = False, driver: Optional[object] = None) -> Dict[str, object]:
    record: Dict[str, object] = {"url": url}
    try:
        final_url, html = fetch_page(url, render=render, driver=driver)
        record["fetched_url"] = final_url
        record["raw_html_path"] = None
        soup = BeautifulSoup(html, "lxml")

        name, name_source = find_name(soup)
        record["name"] = name
        record["name_source"] = name_source

        emails = extract_emails(soup)
        record["emails"] = emails

        # Extract headed sections
        sections = extract_headed_sections(soup)

        # As a special-case, if the page contains a small "Research Direction" strong tag as in sample,
        # try also direct search for nodes whose text equals start keyword
        if not any(START_RE.search(k) for k in sections.keys()):
            # find elements whose text exactly matches start keywords and then collect
            for tag in soup.find_all(text=True):
                txt = clean_text(tag)
                if not txt:
                    continue
                if START_RE.search(txt) and not MISLEADING_RE.search(txt):
                    parent = tag.parent
                    # If tag is inside <strong> within <p>, prefer parent
                    if parent and isinstance(parent, Tag):
                        sec = gather_section_from_start(parent, STOP_RE)
                        if sec:
                            sections[txt] = sec

        classified = classify_sections(sections)

        record.update(classified)

        # Save raw html for debugging (optional)
        # Caller can specify saving directory; here we leave path assignment to caller
        record["_ok"] = True
    except Exception as e:
        logging.exception(f"Failed to extract {url}: {e}")
        record["_ok"] = False
        record["error"] = str(e)
    return record

# -----------------
# Command-line tool
# -----------------

def make_selenium_driver(headless: bool = True, window_size: str = "1200,800"):
    if not SELENIUM_AVAILABLE:
        raise RuntimeError("selenium not installed")
    opts = Options()
    if headless:
        opts.add_argument("--headless=new")
    opts.add_argument(f"--window-size={window_size}")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    driver = webdriver.Chrome(options=opts)
    return driver


def main():
    parser = argparse.ArgumentParser(description="Faculty profile extractor (heading-based)")
    parser.add_argument("--input", required=True, help="Text file with one URL per line")
    parser.add_argument("--output", required=True, help="JSONL output file (one JSON object per line)")
    parser.add_argument("--savedir", required=False, default=None, help="Directory to save raw HTML pages")
    parser.add_argument("--render", action="store_true", help="Use Selenium to render pages (for JS-heavy sites)")
    parser.add_argument("--headless", action="store_true", default=True, help="If --render, run headless")
    parser.add_argument("--delay", type=float, default=0.3, help="Delay between requests (seconds)")
    args = parser.parse_args()

    savedir = Path(args.savedir) if args.savedir else None
    if savedir:
        savedir.mkdir(parents=True, exist_ok=True)

    driver = None
    if args.render:
        driver = make_selenium_driver(headless=args.headless)

    urls = [line.strip() for line in open(args.input, "r", encoding="utf-8") if line.strip()]
    out_fp = open(args.output, "w", encoding="utf-8")

    try:
        for url in tqdm(urls, desc="Processing URLs"):
            rec = extract_profile(url, render=args.render, driver=driver)
            # Optionally save raw html
            if savedir and rec.get("_ok") and rec.get("fetched_url") and 'raw_html_path' in rec:
                # write the html to a file named by safe index
                idx = len(list(savedir.glob("*.html"))) + 1
                fname = savedir / f"page_{idx}.html"
                # fetch again quickly without rendering to save HTML; or reuse last fetch
                try:
                    _, html = fetch_page(rec.get("fetched_url"), render=False)
                    fname.write_text(html, encoding="utf-8")
                    rec["raw_html_path"] = str(fname)
                except Exception:
                    rec["raw_html_path"] = None

            out_fp.write(json.dumps(rec, ensure_ascii=False) + "\n")
            out_fp.flush()
            time.sleep(args.delay)
    finally:
        out_fp.close()
        if driver:
            driver.quit()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    main()
