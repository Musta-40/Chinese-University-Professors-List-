"""
pkusz_faculty_scraper.py

Scrapes faculty name, email and research interest from:
https://scbb.pkusz.edu.cn/szdw.htm
"""

import re
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE = "https://scbb.pkusz.edu.cn"
INDEX_URL = "https://scbb.pkusz.edu.cn/szdw.htm"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120 Safari/537.36",
    "Accept-Language": "zh-CN,zh;q=0.9"
}

EMAIL_RE = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+', flags=re.I)
OBFUSCATED_AT = re.compile(r'\[?\s*at\s*\]?|@|（at）|\\\[at\\\]| at ', flags=re.I)
OBFUSCATED_DOT = re.compile(r'\[?\s*dot\s*\]?|\.|（dot）| dot ', flags=re.I)


def make_session():
    s = requests.Session()
    retries = Retry(total=3, backoff_factor=0.6, status_forcelist=(429, 500, 502, 503, 504))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    s.headers.update(HEADERS)
    return s


def normalize_email(raw: str) -> str:
    """Try to clean common obfuscations like 'cy[at]pku dot edu dot cn'."""
    if not raw:
        return ""
    txt = raw.strip()
    # replace common obfuscations
    txt = re.sub(r'\[dot\]|\(dot\)|\s+dot\s+| dot ', '.', txt, flags=re.I)
    txt = re.sub(r'\[at\]|\(at\)|\s+at\s+| at ', '@', txt, flags=re.I)
    # also replace spaced dots or at signs
    txt = txt.replace(' ', '')
    # search for a valid email pattern after normalization
    m = EMAIL_RE.search(txt)
    return m.group(0) if m else ""


class PKUSZFacultyScraper:
    def __init__(self, index_url=INDEX_URL, base=BASE, max_workers=6):
        self.index_url = index_url
        self.base = base
        self.max_workers = max_workers
        self.session = make_session()
        self.results = []

    def fetch_index(self):
        r = self.session.get(self.index_url, timeout=20)
        r.encoding = r.apparent_encoding or 'utf-8'
        return r.text

    def parse_index(self, html):
        """Parse index page and return list of basic records (name, profile_url, email if present)."""
        soup = BeautifulSoup(html, "html.parser")
        records = []
        # Each faculty item is an li.teacher-list
        for li in soup.select("li.teacher-list"):
            try:
                # name & profile link are in li > ul > li.title > a
                a = li.select_one("li.title a")
                if not a:
                    # fallback: first anchor
                    a = li.find("a")
                if not a:
                    continue
                name = a.get_text(strip=True)
                href = a.get("href", "").strip()
                profile_url = urljoin(self.base + "/", href)
                # the list item text includes lines like "邮箱：..."; search inside li text first
                li_text = li.get_text(" ", strip=True)
                # try to find an email in li_text
                email_m = EMAIL_RE.search(li_text)
                if email_m:
                    email = email_m.group(0)
                else:
                    # sometimes obfuscated like 'cy[at]pku dot edu dot cn'
                    email = normalize_email(li_text)
                # strip stray punctuation
                email = email.strip()
                records.append({
                    "Name": name,
                    "Profile": profile_url,
                    "Email": email,
                    "Research": ""  # to be filled by profile fetch
                })
            except Exception:
                continue
        return records

    def parse_profile(self, html, url):
        """Extract research interest from profile page HTML."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)

        # 1) Try to find explicit labeled nodes: '研究兴趣', '研究方向'
        research = ""
        cand = soup.find(text=re.compile(r'(研究兴趣|研究方向|研究领域|研究方向与研究兴趣)'))
        if cand:
            # cand.parent may contain the label; look for the next siblings or following <p>/<div>
            parent = cand.parent
            # Often the label is followed by sibling paragraphs or the actual text inside same parent
            # collect text from parent and next siblings until next heading-like text
            pieces = []
            # Check the parent itself (label removed)
            parent_text = parent.get_text(" ", strip=True)
            parent_text = re.sub(r'.*(研究兴趣|研究方向)[:：]?\s*', '', parent_text)
            if parent_text:
                pieces.append(parent_text)
            # then next siblings
            for sib in parent.find_next_siblings():
                s_txt = sib.get_text(" ", strip=True)
                if not s_txt:
                    continue
                # stop if we hit contact or education headings
                if re.search(r'(教育背景|代表性|联系方式|招生|联系)', s_txt):
                    break
                pieces.append(s_txt)
                # limit length
                if len(" ".join(pieces)) > 1000:
                    break
            research = "\n".join(pieces).strip()

        # 2) Fallback: search for blocks of Chinese text with keywords in whole page text
        if not research:
            # pattern around keywords (grab 200 chars after the keyword)
            m = re.search(r'(研究兴趣|研究方向|研究领域|研究方向与研究兴趣)[:：]?\s*([\s\S]{1,800}?)((?:教育背景|代表性|联系方式|招生)|$)', text)
            if m:
                research = m.group(2).strip()

        # 3) Final fallback: no label but maybe there's a section with '研究' word - extract nearby sentence
        if not research:
            m2 = re.search(r'((?:[^\n。]{10,200}研究[^\n。]{0,200}))', text)
            if m2:
                research = m2.group(1).strip()

        # sanitize whitespace
        research = re.sub(r'\s{2,}', ' ', research).strip()
        return research

    def fetch_profile_and_extract(self, record):
        """Fetch profile URL and update research + possibly email if missing."""
        url = record["Profile"]
        try:
            s = make_session()
            r = s.get(url, timeout=20)
            r.encoding = r.apparent_encoding or 'utf-8'
            html = r.text
            # extract research
            research = self.parse_profile(html, url)
            record["Research"] = research
            # if email missing, try to find one on profile page
            if not record.get("Email"):
                m = EMAIL_RE.search(html)
                if m:
                    record["Email"] = m.group(0)
                else:
                    # try deobfuscation attempt
                    record["Email"] = normalize_email(html)
        except Exception as e:
            record["Research"] = record.get("Research", "")  # leave as-is
            record["Error"] = str(e)
        return record

    def scrape(self):
        # 1) index fetch
        index_html = self.fetch_index()
        records = self.parse_index(index_html)
        if not records:
            print("No records found on index. Please inspect saved index or check network/headers.")
            return []
        print(f"Found {len(records)} entries on index. Fetching profiles (parallel={self.max_workers})...")
        # 2) concurrent profile fetch
        updated = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as exe:
            future_to_rec = {exe.submit(self.fetch_profile_and_extract, rec): rec for rec in records}
            for fut in as_completed(future_to_rec):
                rec = fut.result()
                updated.append(rec)
                nm = rec.get("Name") or rec.get("Profile")
                print("Parsed:", nm)
        self.results = updated
        return updated

    def dump_to_csv(self, filename="pkusz_faculty.csv"):
        if not self.results:
            print("No results to save.")
            return
        df = pd.DataFrame(self.results)
        # ensure consistent column order
        cols = ["Name", "Email", "Research", "Profile"]
        for c in cols:
            if c not in df.columns:
                df[c] = ""
        df = df[cols]
        df.to_csv(filename, index=False, encoding="utf-8-sig")
        print("Saved", filename)


if __name__ == "__main__":
    scraper = PKUSZFacultyScraper(max_workers=6)
    results = scraper.scrape()
    scraper.dump_to_csv("pkusz_faculty.csv")
