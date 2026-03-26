import requests
from bs4 import BeautifulSoup
import csv
import re
import time

BASE_URL = "https://scbb.pkusz.edu.cn/"

class FacultyScraper:
    def __init__(self, start_url, delay=1):
        self.start_url = start_url
        self.delay = delay
        self.visited = set()
        self.data = []

    def fetch(self, url):
        """Fetch HTML content with error handling."""
        try:
            resp = requests.get(url, timeout=15)
            resp.encoding = "utf-8"
            if resp.status_code == 200:
                return resp.text
        except Exception as e:
            print(f"[ERROR] Failed to fetch {url}: {e}")
        return ""

    def parse_faculty_list(self, html):
        """Extract faculty list from department page."""
        soup = BeautifulSoup(html, "html.parser")
        teachers = []
        for li in soup.select("li.teacher-list"):
            name_tag = li.select_one("li.title a")
            email_tag = li.find(text=re.compile(r"@"))
            profile_url = None
            if name_tag and name_tag.get("href"):
                profile_url = name_tag["href"]
                if not profile_url.startswith("http"):
                    profile_url = BASE_URL + profile_url.lstrip("/")
            teachers.append({
                "name": name_tag.get_text(strip=True) if name_tag else "",
                "email": email_tag.strip() if email_tag else "",
                "profile_url": profile_url
            })
        return teachers

    def parse_profile(self, html, url):
        """Extract research interest more fully from profile page."""
        soup = BeautifulSoup(html, "html.parser")
        text = soup.get_text(" ", strip=True)
        research = ""

        # 1) Look for labeled nodes like '研究兴趣' / '研究方向'
        cand = soup.find(text=re.compile(r'(研究兴趣|研究方向|研究领域|研究方向与研究兴趣)'))
        if cand:
            parent = cand.parent
            pieces = []

            # Clean parent text
            parent_text = parent.get_text(" ", strip=True)
            parent_text = re.sub(r'.*(研究兴趣|研究方向)[:：]?\s*', '', parent_text)
            if parent_text:
                pieces.append(parent_text)

            # Collect siblings until next heading-like node
            for sib in parent.find_next_siblings():
                s_txt = sib.get_text(" ", strip=True)
                if not s_txt:
                    continue
                # Stop at typical headings
                if re.search(r'(教育背景|代表性成果|联系方式|招生信息|获奖情况)', s_txt):
                    break
                pieces.append(s_txt)

            research = "\n".join(pieces).strip()

        # 2) Fallback: grab larger chunk from raw text
        if not research:
            m = re.search(
                r'(研究兴趣|研究方向|研究领域)[:：]?\s*([\s\S]{1,1500}?)(教育背景|联系方式|代表性成果|$)',
                text
            )
            if m:
                research = m.group(2).strip()

        # 3) Final fallback: just find any sentence with '研究'
        if not research:
            m2 = re.search(r'([^.。\n]{15,200}研究[^.。\n]{0,200})', text)
            if m2:
                research = m2.group(1).strip()

        research = re.sub(r'\s{2,}', ' ', research).strip()
        return research

    def scrape(self):
        """Scrape all departments and faculty profiles."""
        print("[INFO] Starting scrape...")
        html = self.fetch(self.start_url)
        if not html:
            print("[ERROR] Could not fetch start page.")
            return

        soup = BeautifulSoup(html, "html.parser")

        # Find department links under sidebar
        dept_links = [a["href"] for a in soup.select(".sidebar a") if a.get("href")]
        dept_links = [BASE_URL + l.strip("/") for l in dept_links if not l.startswith("http")]

        print(f"[INFO] Found {len(dept_links)} department links")

        for dept_url in dept_links:
            print(f"[INFO] Scraping department: {dept_url}")
            dept_html = self.fetch(dept_url)
            if not dept_html:
                continue

            faculty_list = self.parse_faculty_list(dept_html)
            print(f"[INFO] Found {len(faculty_list)} faculty in this dept")

            for f in faculty_list:
                research = ""
                if f["profile_url"] and f["profile_url"] not in self.visited:
                    self.visited.add(f["profile_url"])
                    profile_html = self.fetch(f["profile_url"])
                    if profile_html:
                        research = self.parse_profile(profile_html, f["profile_url"])
                        time.sleep(self.delay)
                self.data.append({
                    "name": f["name"],
                    "email": f["email"],
                    "research": research,
                    "profile_url": f["profile_url"]
                })

    def save_csv(self, filename="faculty.csv"):
        """Save scraped data to CSV."""
        keys = ["name", "email", "research", "profile_url"]
        with open(filename, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(self.data)
        print(f"[INFO] Saved {len(self.data)} records to {filename}")


if __name__ == "__main__":
    start_url = "https://scbb.pkusz.edu.cn/szdw.htm"
    scraper = FacultyScraper(start_url)
    scraper.scrape()
    scraper.save_csv()
