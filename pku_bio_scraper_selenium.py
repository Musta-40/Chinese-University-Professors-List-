#!/usr/bin/env python3
"""
PKU Biology faculty scraper using Selenium to render JS-driven pages.
Extracts: name, email, research (research interests/field), profile_url
Outputs: pku_bio_faculty.csv
"""

import time
import re
import csv
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --------- CONFIG ----------
START_URL = "https://www.bio.pku.edu.cn/homes/Index/news_szll_zy/16/16.html"
BASE_URL = "https://www.bio.pku.edu.cn"
DELAY_BETWEEN_PROFILE = 1.0   # seconds
MAX_PROFILES = None           # set to int for quick test (e.g., 10)
CHROME_DRIVER_PATH = None     # set to path if chromedriver not on PATH
# ---------------------------


def setup_driver(headless=True):
    chrome_opts = Options()
    if headless:
        chrome_opts.add_argument("--headless=new")
    chrome_opts.add_argument("--no-sandbox")
    chrome_opts.add_argument("--disable-dev-shm-usage")
    chrome_opts.add_argument("--disable-gpu")
    chrome_opts.add_argument("--window-size=1920,1200")
    chrome_opts.add_argument("user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                             "(KHTML, like Gecko) Chrome/120.0 Safari/537.36")
    if CHROME_DRIVER_PATH:
        service = Service(CHROME_DRIVER_PATH)
    else:
        service = Service()  # relies on chromedriver being on PATH
    driver = webdriver.Chrome(service=service, options=chrome_opts)
    driver.set_page_load_timeout(30)
    return driver


# conservative filter for profile hrefs (heuristics)
def is_likely_profile_href(href: str):
    if not href:
        return False
    href = href.strip()
    # ignore anchors and JS
    if href.startswith("javascript:") or href.startswith("#"):
        return False
    # must be an html page on the same site OR contain likely keywords
    if href.startswith("http") and "bio.pku.edu.cn" not in href:
        return False
    # heuristics: many PKU profile pages are under /homes/ and end with .html
    if "/homes/" in href or re.search(r"/\w+/\w+/\d+/\d+\.html", href):
        return True
    # also allow relative html links
    if href.endswith(".html"):
        return True
    return False


def extract_research_and_email(html_text: str):
    """
    Attempts structured extraction:
      1) find headings like '研究方向', '研究兴趣', '研究领域', '科研方向'
      2) if not found, regex search for long '研究...' sentences
      3) email via regex
    """
    research = ""
    email = ""

    # email
    m = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", html_text)
    if m:
        email = m.group(0).strip()

    # research headings (Chinese and English)
    soup = BeautifulSoup(html_text, "html.parser")
    headings = ["研究方向", "研究兴趣", "研究领域", "科研方向", "Research interests", "Research field"]
    for hd in headings:
        node = soup.find(text=re.compile(re.escape(hd)))
        if node:
            # try parent -> subsequent sibling paragraphs
            parent = node.parent
            # remove heading text then read following siblings
            content = parent.get_text(" ", strip=True)
            content = re.sub(rf".*{re.escape(hd)}[:：]?\s*", "", content)
            if content and len(content) > 6:
                research = content.strip()
                break
            # fallback: gather text from next siblings
            pieces = []
            for sib in parent.find_next_siblings(limit=6):
                t = sib.get_text(" ", strip=True)
                if not t:
                    continue
                # stop if next heading-like text occurs
                if re.search(r'(教育背景|联系方式|代表性成果|获奖|教学)', t):
                    break
                pieces.append(t)
            if pieces:
                research = " ".join(pieces).strip()
                break

    # fallback: catch a sentence containing the character '研究' and of reasonable length
    if not research:
        m2 = re.search(r'([^.。\n]{10,300}研究[^.。\n]{0,200})', soup.get_text(" ", strip=True))
        if m2:
            research = m2.group(1).strip()

    # final cleanup
    research = re.sub(r'\s{2,}', ' ', research).strip()
    return research, email


def collect_profile_links(driver):
    """Render the main page and collect candidate profile links."""
    driver.get(START_URL)
    # Wait for at least one anchor to appear
    try:
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "a")))
    except Exception:
        # still continue - sometimes waiting fails but content is present
        pass

    time.sleep(1)  # allow any late JS
    page_html = driver.page_source
    soup = BeautifulSoup(page_html, "html.parser")

    # Attempt several container selectors, concatenating results
    candidate_hrefs = set()
    container_selectors = [
        "div.container", "div.content", "div#main", "div.wrap", "div.left", "div.right",
        "div.article", "div#content", "ul li", "div.list", "div.news_list"
    ]
    for sel in container_selectors:
        for a in soup.select(f"{sel} a"):
            href = a.get("href")
            if href and is_likely_profile_href(href):
                full = urljoin(BASE_URL, href)
                text = a.get_text(" ", strip=True)
                # simple heuristics: link text should look like a person's name (not empty)
                if text and len(text) <= 60:
                    candidate_hrefs.add((full, text))

    # As fallback: search all anchors on the page
    if not candidate_hrefs:
        for a in soup.find_all("a"):
            href = a.get("href")
            if href and is_likely_profile_href(href):
                full = urljoin(BASE_URL, href)
                text = a.get_text(" ", strip=True)
                if text:
                    candidate_hrefs.add((full, text))

    # return list preserving insertion order
    return list(candidate_hrefs)


def scrape_all():
    driver = setup_driver(headless=True)
    try:
        profiles = collect_profile_links(driver)
        print(f"[INFO] Candidate profiles found: {len(profiles)}")
        results = []
        count = 0
        for href, link_text in profiles:
            if MAX_PROFILES and count >= MAX_PROFILES:
                break
            print(f"[INFO] Visiting profile {count+1}: {href}  (link text: {link_text})")
            try:
                driver.get(href)
                WebDriverWait(driver, 8).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(0.6)  # allow dynamic content
                page_html = driver.page_source
            except Exception as e:
                print(f"[WARN] Could not load {href}: {e}")
                page_html = ""

            research, email = ("", "")
            if page_html:
                research, email = extract_research_and_email(page_html)
            # Best-guess name: use link text if plausible, else try page title or h1
            name = link_text.strip()
            if not name or len(name) > 80:
                soup = BeautifulSoup(page_html, "html.parser")
                h1 = soup.find(["h1", "h2"])
                if h1:
                    name = h1.get_text(" ", strip=True)

            results.append({
                "name": name,
                "email": email,
                "research": research,
                "profile_url": href
            })
            count += 1
            time.sleep(DELAY_BETWEEN_PROFILE)

        # Save CSV
        keys = ["name", "email", "research", "profile_url"]
        with open("pku_bio_faculty.csv", "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(results)
        print(f"[INFO] Done. Saved {len(results)} records to pku_bio_faculty.csv")

    finally:
        driver.quit()


if __name__ == "__main__":
    scrape_all()
