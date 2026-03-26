#!/usr/bin/env python3
"""
biox_scraper.py

Scrape faculty list from https://biox.ustc.edu.cn/js/list.htm and follow each faculty profile to
extract: name, profile_url, email, research_interests.

Outputs: faculty.csv and faculty.json

Heuristics:
 - List page: follow links that include '/page.htm'
 - Profile page: name from <h2 class="tits"> (fallback: <title>)
 - Research text: content inside div.wp_articlecontent (skip first <p> if it looks like background)
 - Email detection: normal emails (xxx@domain) and obfuscated [at] forms
"""

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
import re
import time
import csv
import json

BASE = "https://biox.ustc.edu.cn"
START = urljoin(BASE, "/js/list.htm")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BioxScraper/1.0; +https://example.local/)"
}
SLEEP = 0.5  # polite pause between requests

# patterns
EMAIL_RE = re.compile(r'[\w.+-]+@[\w\.-]+\.[a-zA-Z]{2,}', re.I)
AT_OBFUSCATED_RE = re.compile(r'([\w.+-]+)\s*(?:\[at\]|@)\s*([\w\.-]+\.[a-zA-Z]{2,})', re.I)

# Chinese-words that usually indicate an education/background paragraph:
BACKGROUND_KEYWORDS = [
    "本科", "硕士", "博士", "毕业", "工作", "任职", "导师", "教授", "学位", "就职", "研究生导师", "现任"
]

# research-keywords that often label research direction sections
RESEARCH_KEYWORDS = ["研究方向", "研究兴趣", "研究内容", "主要研究方向", "研究领域", "研究方向与兴趣"]

def fetch(url):
    r = requests.get(url, headers=HEADERS, timeout=20)
    r.raise_for_status()
    r.encoding = r.apparent_encoding
    return r.text

def find_faculty_links(list_html):
    soup = BeautifulSoup(list_html, "html.parser")
    links = set()
    # Primary heuristic: follow anchors whose href contains '/page.htm'
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if "/page.htm" in href:
            full = urljoin(BASE, href)
            links.add(full)
    # preserve order: convert to list
    return sorted(links)

def clean_text(s):
    # normalize whitespace and remove excessive newlines
    return re.sub(r'\s+\n', '\n', re.sub(r'[ \t\r]+', ' ', s)).strip()

def extract_emails(text):
    emails = set()
    # find normal emails
    for m in EMAIL_RE.findall(text):
        emails.add(m)
    # find obfuscated patterns like 'name[at]ustc.edu.cn' or 'name [at] ustc.edu.cn'
    for m in AT_OBFUSCATED_RE.findall(text):
        cand = f"{m[0]}@{m[1]}"
        emails.add(cand)
    return sorted(emails)

def looks_like_background(paragraph_text):
    # returns True if paragraph contains education/work keywords
    for kw in BACKGROUND_KEYWORDS:
        if kw in paragraph_text:
            return True
    return False

def extract_research_from_profile(html):
    soup = BeautifulSoup(html, "html.parser")

    # 1) name
    name_tag = soup.find("h2", class_="tits")
    name = name_tag.get_text(strip=True) if name_tag else (soup.title.string.strip() if soup.title else "")

    # 2) article content area
    article_div = soup.find("div", class_="wp_articlecontent")
    content_text = ""
    if article_div:
        # get paragraphs
        paragraphs = []
        for p in article_div.find_all(["p", "div"], recursive=False):
            text = p.get_text(separator=" ", strip=True)
            if text:
                paragraphs.append(text)

        # fallback: if no direct child <p>, use all text inside article_div
        if not paragraphs:
            paragraphs = [article_div.get_text(separator=" ", strip=True)]

        # If first paragraph looks like background (education/work), skip it
        if len(paragraphs) >= 1 and looks_like_background(paragraphs[0]):
            candidate_paragraphs = paragraphs[1:]
        else:
            candidate_paragraphs = paragraphs

        # If research keywords appear somewhere, try to extract the sentences/paragraphs containing them
        joined = "\n".join(candidate_paragraphs)
        found_research_sections = []
        for kw in RESEARCH_KEYWORDS:
            if kw in joined:
                # collect lines that contain the keyword (and few lines after it)
                for line in joined.splitlines():
                    if kw in line:
                        found_research_sections.append(line.strip())
                # if we found keyword-based lines, prefer them
        if found_research_sections:
            content_text = "\n".join(found_research_sections)
        else:
            # Otherwise, use the candidate paragraphs but remove lines that clearly look like publications or lists of papers
            cleaned_lines = []
            for para in candidate_paragraphs:
                # skip paragraphs that look like "近五年5篇代表性论文" or long lists with DOI numbers
                if re.search(r'代表性论文|近五年|论文|doi|DOI|\d{4}年', para):
                    continue
                cleaned_lines.append(para)
            content_text = "\n\n".join(cleaned_lines).strip()
    else:
        # fallback: whole page text
        page_text = soup.get_text(separator="\n", strip=True)
        content_text = page_text

    content_text = clean_text(content_text)
    return name, content_text

def scrape_all():
    print("Fetching list page:", START)
    list_html = fetch(START)
    links = find_faculty_links(list_html)
    print(f"Found {len(links)} profile links (heuristic: '/page.htm').")

    results = []
    for idx, link in enumerate(links, 1):
        try:
            print(f"[{idx}/{len(links)}] Fetching: {link}")
            html = fetch(link)
            name, research_text = extract_research_from_profile(html)

            # emails: check both page HTML and visible text
            emails = set(extract_emails(html))
            emails.update(extract_emails(research_text))

            # if no email found yet, also search visible text inside page
            visible_text = BeautifulSoup(html, "html.parser").get_text(separator=" ", strip=True)
            emails.update(extract_emails(visible_text))

            record = {
                "name": name,
                "profile_url": link,
                "emails": list(sorted(emails)),
                "research_interests": research_text
            }
            results.append(record)
        except Exception as e:
            print(f"ERROR fetching {link}: {e}")
        time.sleep(SLEEP)

    # save CSV
    csv_cols = ["name", "profile_url", "emails", "research_interests"]
    with open("faculty.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_cols)
        writer.writeheader()
        for r in results:
            # join emails into semicolon-separated string for CSV
            row = {
                "name": r["name"],
                "profile_url": r["profile_url"],
                "emails": ";".join(r["emails"]),
                "research_interests": r["research_interests"]
            }
            writer.writerow(row)

    # save JSON
    with open("faculty.json", "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print("Done. Results written to faculty.csv and faculty.json")
    return results

if __name__ == "__main__":
    scrape_all()
