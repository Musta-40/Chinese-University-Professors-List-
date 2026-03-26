import csv
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class FacultyScraper:
    def __init__(self, start_url, delay=1.0):
        self.start_url = start_url
        self.delay = delay
        self.visited = set()  # URLs we've fetched
        self.added = set()    # Profile URLs we've added to CSV data
        self.data = []

        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/115.0 Safari/537.36"
            ),
            "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
        })

        retries = Retry(
            total=3,
            backoff_factor=0.5,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "HEAD"],
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def fetch(self, url):
        """Fetch HTML content with robust error handling and encoding detection."""
        try:
            resp = self.session.get(url, timeout=20)
            if resp.status_code == 200:
                # Respect server charset; otherwise fall back to chardet-based guess
                ct = resp.headers.get("Content-Type", "").lower()
                if "charset=" not in ct and not resp.encoding:
                    resp.encoding = resp.apparent_encoding
                return resp.text
            else:
                print(f"[WARN] Non-200 status for {url}: {resp.status_code}")
        except requests.RequestException as e:
            print(f"[ERROR] HTTP error fetching {url}: {e}")
        except Exception as e:
            print(f"[ERROR] Failed to fetch {url}: {e}")
        return ""

    def extract_email_from_html(self, html):
        """Try to find an email in a profile page."""
        soup = BeautifulSoup(html, "html.parser")

        # mailto link
        a_mail = soup.select_one('a[href^="mailto:"]')
        if a_mail:
            href = a_mail.get("href", "")
            return href.replace("mailto:", "").strip()

        # Plain email
        text = soup.get_text(" ", strip=True)
        m = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        if m:
            return m.group(0)

        # Lightly obfuscated formats like "name at domain dot com"
        m2 = re.search(
            r'([\w\.-]+)\s*(?:@| at )\s*([\w\.-]+)\s*(?:\.| dot )\s*([a-z]{2,})',
            text, re.I
        )
        if m2:
            return f"{m2.group(1)}@{m2.group(2)}.{m2.group(3)}"

        return ""

    def parse_faculty_list(self, html, base_url):
        """Extract faculty name, email (if present), and profile URL from a department/list page."""
        soup = BeautifulSoup(html, "html.parser")
        teachers = []

        # Try several common list/card patterns seen on university sites
        selectors = [
            "ul.teacher-list li",
            ".teacher-list li",
            "ul.wp_article_list li",
            ".wp_article_list li",
            ".article-list li",
            "ul.list li",
            ".list li",
            ".news_list li",
        ]
        rows = []
        for sel in selectors:
            found = soup.select(sel)
            if found:
                rows.extend(found)

        if not rows:
            # Fallback to any li; we'll filter at anchor level
            rows = soup.select("li")

        for li in rows:
            # Heuristic: pick a sensible anchor
            a = None
            for candidate in li.select(".title a[href], a[href]"):
                text = candidate.get_text(strip=True)
                href = candidate.get("href", "").strip()
                if not href or href.startswith(("javascript:", "#")):
                    continue
                if text and text not in ("更多", "更多>>", "more", "More"):
                    a = candidate
                    break
            if not a:
                continue

            name = a.get_text(strip=True)
            if not name:
                continue

            href = a.get("href", "").strip()
            profile_url = urljoin(base_url, href) if href else ""
            if not profile_url:
                continue

            # Extract email from the list item if present
            email = ""
            li_text = li.get_text(" ", strip=True)
            m = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", li_text)
            if m:
                email = m.group(0)

            teachers.append({
                "name": name,
                "email": email,
                "profile_url": profile_url,
            })

        return teachers

    def parse_profile(self, html, url):
        """Extract 'research interests/areas' from a profile page using multiple strategies."""
        soup = BeautifulSoup(html, "html.parser")
        research = ""

        heading_patterns = re.compile(
            r"(研究(?:兴趣|方向|领域)|Research\s+(?:Interests?|Areas?))",
            re.IGNORECASE
        )

        def collect_until_next_heading(start_tag):
            """Collect text from siblings after start_tag until the next heading."""
            content = []
            current = start_tag.find_next_sibling()
            while current and getattr(current, "name", None) not in (
                "h1", "h2", "h3", "h4", "h5", "h6", "dt"
            ):
                if hasattr(current, "get_text"):
                    text = current.get_text(" ", strip=True)
                    if text:
                        content.append(text)
                current = current.find_next_sibling()
            return "\n".join(content).strip()

        # Strategy 1: headings that explicitly match "研究兴趣/方向/领域" or "Research Interests/Areas"
        for tag in soup.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "dt", "strong", "b"]):
            if heading_patterns.search(tag.get_text(" ", strip=True) or ""):
                # First try: paragraphs/divs directly inside the same container
                container = tag.parent if tag.parent else tag
                paragraphs = container.find_all(["p", "div"], recursive=False)
                text_blocks = [
                    p.get_text(" ", strip=True)
                    for p in paragraphs
                    if p.get_text(" ", strip=True)
                ]
                if text_blocks:
                    research = "\n".join(text_blocks).strip()
                    if research:
                        break

                # Fallback: collect following siblings until next heading
                research = collect_until_next_heading(tag)
                if research:
                    break

        # Strategy 2: raw text search bounded by next section keyword
        if not research:
            raw = soup.get_text("\n", strip=True)
            m = re.search(
                r"(?:研究(?:兴趣|方向|领域)|Research\s+(?:Interests?|Areas?))[:：]?\s*"
                r"([\s\S]{10,2000}?)"
                r"(?=\n(?:教育背景|联系方式|工作经历|个人简介|承担项目|科研项目|代表性?论文|荣誉|获奖|学术服务|课程|出版|Publications|Education|Contact|Experience|Biography|Projects|Awards)|$)",
                raw,
                re.IGNORECASE
            )
            if m:
                research = m.group(1).strip()

        # Cleanup spacing
        research = re.sub(r"[ \t\u00A0]+", " ", research).strip()
        research = re.sub(r"\n{3,}", "\n\n", research)

        return research

    def scrape(self):
        """Scrape all departments and faculty profiles with proper URL handling."""
        print("[INFO] Starting scrape...")
        html = self.fetch(self.start_url)
        if not html:
            print("[ERROR] Could not fetch start page.")
            return

        soup = BeautifulSoup(html, "html.parser")

        # Collect potential department/category links
        dept_links = set()
        selectors = [
            ".sidebar a[href]",
            ".left_nav a[href]",
            ".list-left a[href]",
            ".wp_listcolumn a[href]",
            ".wp_nav a[href]",
            ".column_left a[href]",
            "#sidebar a[href]",
        ]
        for sel in selectors:
            for a in soup.select(sel):
                href = a.get("href", "").strip()
                if not href or href.startswith(("javascript:", "#")):
                    continue
                abs_url = urljoin(self.start_url, href)
                # Keep links within the same host
                if urlparse(abs_url).netloc == urlparse(self.start_url).netloc:
                    dept_links.add(abs_url)

        print(f"[INFO] Found {len(dept_links)} department links")
        if not dept_links:
            print("[WARN] Using fallback department extraction (start page only)")
            dept_links = {self.start_url}

        for dept_url in sorted(dept_links):
            print(f"[INFO] Scraping department: {dept_url}")
            dept_html = self.fetch(dept_url)
            if not dept_html:
                continue

            faculty_list = self.parse_faculty_list(dept_html, dept_url)
            print(f"[INFO] Found {len(faculty_list)} faculty on this page")

            for i, faculty in enumerate(faculty_list, 1):
                name = faculty.get("name", "").strip()
                email = faculty.get("email", "").strip()
                profile_url = faculty.get("profile_url", "").strip()

                # Skip duplicates by profile_url
                if profile_url and profile_url in self.added:
                    print(f"  [{i}/{len(faculty_list)}] Skipping duplicate: {name}")
                    continue

                print(f"  [{i}/{len(faculty_list)}] Processing: {name}")
                research = ""

                if profile_url:
                    if profile_url not in self.visited:
                        self.visited.add(profile_url)
                        profile_html = self.fetch(profile_url)
                        if profile_html:
                            research = self.parse_profile(profile_html, profile_url)
                            if not email:
                                email = self.extract_email_from_html(profile_html)
                        else:
                            print(f"[WARN] Empty profile page: {profile_url}")
                        time.sleep(self.delay)  # be polite
                    else:
                        print(f"    Already visited profile: {profile_url}")

                # Record result once per unique profile URL (or by name if no URL)
                key = profile_url or f"{name}|{email}"
                if key in self.added:
                    continue
                self.added.add(key)

                self.data.append({
                    "name": name,
                    "email": email,
                    "research": research,
                    "profile_url": profile_url,
                })

    def save_csv(self, filename="faculty.csv"):
        """Save scraped data to CSV with error handling."""
        keys = ["name", "email", "research", "profile_url"]
        try:
            with open(filename, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(self.data)
            print(f"[SUCCESS] Saved {len(self.data)} records to {filename}")
        except Exception as e:
            print(f"[ERROR] Failed to save CSV: {e}")


if __name__ == "__main__":
    start_url = "https://scbb.pkusz.edu.cn/szdw.htm"
    scraper = FacultyScraper(start_url, delay=1.5)
    scraper.scrape()
    scraper.save_csv()