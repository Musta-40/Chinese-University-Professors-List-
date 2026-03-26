#!/usr/bin/env python3
"""
Faculty profile scraper - extended to support JS-variable heavy pages
(example: pages that set `var en_xm="..."; var dzyj="..."; var en_yjfx="<div>...</div>";`)
Usage: put URLs (one per line) in urls.txt and run the script.
"""
import requests
from bs4 import BeautifulSoup
import re
import time
from typing import Dict, Optional, List
import html


class FacultyProfileScraper:
    def __init__(self, use_selenium: bool = False):
        self.use_selenium = use_selenium
        self.driver = None

        if use_selenium:
            from selenium import webdriver
            from selenium.webdriver.chrome.options import Options
            chrome_options = Options()
            chrome_options.add_argument('--headless')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            self.driver = webdriver.Chrome(options=chrome_options)

    # ---------------------------
    # Utility helpers
    # ---------------------------
    def _unescape_js_string(self, s: str) -> str:
        """
        Convert common JS escaped sequences into readable text and unescape HTML entities.
        We do not use .encode().decode('unicode_escape') to avoid accidental decoding errors.
        """
        if s is None:
            return s
        # Replace common JS escapes
        s = s.replace(r'\"', '"')
        s = s.replace(r"\'", "'")
        s = s.replace(r'\/', '/')
        s = s.replace(r'\n', '\n')
        s = s.replace(r'\r', '')
        s = s.replace(r'\t', ' ')
        # Remove stray leading/trailing whitespace introduced by JS quoting
        s = s.strip()
        # Unescape HTML entities (&nbsp;, &amp;, etc.)
        s = html.unescape(s)
        return s

    def _extract_js_var(self, html_content: str, varnames: List[str]) -> Optional[str]:
        """
        Try multiple candidate JS variable names and return the first matched value.
        Pattern captures a double-quoted JS string allowing escaped quotes: "((?:[^"\\]|\\.)*)"
        """
        for var in varnames:
            # Build safe regex: allow whitespace and optional semicolon after the JS assignment
            pattern = rf'var\s+{re.escape(var)}\s*=\s*"((?:[^"\\]|\\.)*)"'
            m = re.search(pattern, html_content, re.DOTALL)
            if m:
                raw = m.group(1)
                return self._unescape_js_string(raw)
        return None

    def clean_html_text(self, html_string: str) -> str:
        """
        Clean HTML string and extract text properly (keeps structure on new lines).
        """
        if not html_string:
            return ''
        # After unescaping we may still have HTML fragments; parse them
        soup = BeautifulSoup(html_string, 'html.parser')

        # Prefer extracting from paragraphs/divs/lists first
        parts = []
        for el in soup.find_all(['p', 'div', 'li']):
            text = el.get_text(separator=' ', strip=True)
            if text:
                parts.append(text)

        if not parts:
            # Fallback to whole text
            full = soup.get_text(separator='\n', strip=True)
            parts = [line.strip() for line in full.splitlines() if line.strip()]

        return '\n'.join(parts)

    # ---------------------------
    # Extraction for JS-heavy pages
    # ---------------------------
    def scrape_from_javascript(self, html_content: str) -> Dict[str, Optional[str]]:
        """
        Extract data from common JS variables present on the page.
        Tries multiple candidate variable names for name, email and research.
        """
        data = {'name': None, 'email': None, 'research': None}

        # Candidate variable names observed across target sites (extend if needed)
        name_candidates = ['en_xm', 'xm_en', 'xm', 'name', 'enName', 'xmName']
        email_candidates = ['dzyj', 'en_dzyj', 'email', 'mail', 'en_email']
        research_candidates = ['en_yjfx', 'enyjfx', 'yjfx', 'research', 'en_research', 'en_yj']

        # 1) Try extracting via JS variables
        name_val = self._extract_js_var(html_content, name_candidates)
        if name_val:
            data['name'] = name_val.strip()

        email_val = self._extract_js_var(html_content, email_candidates)
        if email_val:
            data['email'] = email_val.strip()

        research_val = self._extract_js_var(html_content, research_candidates)
        if research_val:
            # research_val often contains HTML fragments — clean them to readable text
            data['research'] = self.clean_html_text(research_val)

        # 2) If any field is missing, fallback to DOM elements with common IDs (if the script used them)
        if not (data['name'] and data['email'] and data['research']):
            soup = BeautifulSoup(html_content, 'html.parser')
            # name
            if not data['name']:
                el = soup.find(id='name') or soup.find(class_='ryname_l') or soup.find('h1')
                if el:
                    txt = el.get_text(separator=' ', strip=True)
                    if txt:
                        data['name'] = txt
            # email
            if not data['email']:
                # Try element with id 'dzyj' or direct email regex in page
                el = soup.find(id='dzyj')
                if el:
                    txt = el.get_text(separator=' ', strip=True)
                    if txt:
                        data['email'] = txt
                else:
                    # scan page text for an email address
                    email_search = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', soup.get_text(separator=' '))
                    if email_search:
                        data['email'] = email_search.group(0)
            # research
            if not data['research']:
                el = soup.find(id='yjfx')
                if el:
                    # it might be empty if JS would fill it; but if present, extract
                    text = el.get_text(separator='\n', strip=True)
                    if text:
                        data['research'] = text
                else:
                    # try to find a section header like 'Research Direction' and take the following block
                    header = soup.find(lambda tag: tag.name in ['h3', 'h4', 'h5', 'b'] and re.search(r'Research|Research Direction|Research Direction', tag.get_text(), re.I))
                    if header:
                        # take sibling/parent text if available
                        candidate = header.find_next_sibling()
                        if candidate:
                            data['research'] = candidate.get_text(separator='\n', strip=True)

        # Final clean-up: ensure research is not short nonsense
        if data['research']:
            if data['research'].strip() in ('', '&nbsp;', 'N/A') or len(data['research'].strip()) < 6:
                data['research'] = None

        return data

    # ---------------------------
    # Selenium scraping (unchanged)
    # ---------------------------
    def scrape_with_selenium(self, url: str) -> Dict[str, Optional[str]]:
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException

        data = {'name': None, 'email': None, 'research': None}
        try:
            self.driver.get(url)
            time.sleep(2)
            wait = WebDriverWait(self.driver, 10)

            try:
                name_element = wait.until(EC.presence_of_element_located((By.ID, "name")))
                data['name'] = name_element.text.strip()
            except TimeoutException:
                pass

            try:
                email_element = self.driver.find_element(By.ID, "dzyj")
                data['email'] = email_element.text.strip()
            except Exception:
                pass

            try:
                research_element = self.driver.find_element(By.ID, "yjfx")
                raw = research_element.get_attribute('innerHTML') or research_element.text
                data['research'] = self.clean_html_text(raw)
            except Exception:
                pass
        except Exception as e:
            print(f"Error scraping with Selenium: {e}")
        return data

    # ---------------------------
    # Main scraping orchestration
    # ---------------------------
    def scrape(self, url: str) -> Dict[str, Optional[str]]:
        if self.use_selenium:
            return self.scrape_with_selenium(url)

        try:
            resp = requests.get(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
                timeout=12
            )
            if resp.status_code != 200:
                print(f"Failed to fetch {url}: status {resp.status_code}")
                return {'name': None, 'email': None, 'research': None}

            html_content = resp.text

            # Primary path: JS variables (fast and reliable for your "106" pages)
            data = self.scrape_from_javascript(html_content)

            # As a final fallback, if all fields are None, try simple DOM heuristics
            if not any([data['name'], data['email'], data['research']]):
                soup = BeautifulSoup(html_content, 'html.parser')
                # name heuristics
                if not data['name']:
                    h = soup.find(['h1', 'h2', 'h3'])
                    if h:
                        data['name'] = h.get_text(strip=True)
                # email heuristics
                if not data['email']:
                    email_search = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', soup.get_text(separator=' '))
                    if email_search:
                        data['email'] = email_search.group(0)
                # research heuristics: look for "Research" section
                if not data['research']:
                    sec = soup.find(lambda tag: tag.name in ['h3', 'h4', 'h5'] and re.search(r'Research|Research Direction|Research Interests', tag.get_text(), re.I))
                    if sec:
                        # gather following siblings up to next heading
                        pieces = []
                        sib = sec.find_next_sibling()
                        while sib and sib.name not in ['h1', 'h2', 'h3', 'h4', 'h5']:
                            pieces.append(sib.get_text(separator=' ', strip=True))
                            sib = sib.find_next_sibling()
                        data['research'] = '\n'.join([p for p in pieces if p.strip()]) if pieces else None

            return data

        except requests.RequestException as e:
            print(f"Request error for {url}: {e}")
            return {'name': None, 'email': None, 'research': None}

    # ---------------------------
    # File I/O & utility wrappers (unchanged; keep your existing methods)
    # ---------------------------
    def read_urls_from_file(self, filename: str) -> List[str]:
        urls = []
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                for line in f:
                    url = line.strip()
                    if url and not url.startswith('#'):
                        urls.append(url)
            print(f"Loaded {len(urls)} URLs from {filename}")
        except FileNotFoundError:
            print(f"Error: File '{filename}' not found")
        except Exception as e:
            print(f"Error reading file: {e}")
        return urls

    def scrape_multiple_urls(self, urls: list, delay: float = 1.0) -> list:
        results = []
        total = len(urls)
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{total}] Scraping: {url}")
            data = self.scrape(url)
            data['url'] = url
            results.append(data)
            if data.get('name'):
                print(f"  ✓ Found: {data['name']}")
                if data.get('research'):
                    preview = data['research'][:80] + "..." if len(data['research']) > 80 else data['research']
                    print(f"    Research: {preview}")
            else:
                print("  ✗ No data found")
            if i < total:
                time.sleep(delay)
        return results

    def save_to_txt(self, data: list, filename: str = 'faculty_data.txt'):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("="*80 + "\n")
                f.write("FACULTY PROFILES - SCRAPED DATA\n")
                f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Profiles: {len(data)}\n")
                f.write("="*80 + "\n\n")
                successful_count = 0
                for i, profile in enumerate(data, 1):
                    if not profile.get('name') and not profile.get('email'):
                        f.write(f"Profile #{i}\n")
                        f.write("-"*40 + "\n")
                        f.write(f"URL: {profile.get('url')}\n")
                        f.write("Status: No data found\n\n")
                        continue
                    successful_count += 1
                    f.write(f"PROFILE #{i}\n")
                    f.write("="*80 + "\n")
                    f.write(f"NAME: {profile.get('name') or 'Not found'}\n")
                    f.write(f"EMAIL: {profile.get('email') or 'Not found'}\n")
                    f.write("RESEARCH INTERESTS:\n")
                    if profile.get('research'):
                        for line in profile['research'].split('\n'):
                            if line.strip():
                                f.write(f"  {line.strip()}\n")
                    else:
                        f.write("  Not found\n")
                    f.write(f"SOURCE URL: {profile.get('url')}\n\n")
                f.write("\nSUMMARY\n")
                f.write("="*80 + "\n")
                f.write(f"Total URLs processed: {len(data)}\n")
                f.write(f"Successful extractions: {successful_count}\n")
            print(f"✓ Data saved to {filename}")
        except Exception as e:
            print(f"Error saving to text file: {e}")

    def save_to_simple_txt(self, data: list, filename: str = 'faculty_data_simple.txt'):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("Name|Email|Research|URL\n")
                for profile in data:
                    name = profile.get('name') or 'N/A'
                    email = profile.get('email') or 'N/A'
                    research = profile.get('research') or 'N/A'
                    research_single = ' '.join(research.splitlines())
                    research_single = (research_single[:200] + "...") if len(research_single) > 200 else research_single
                    url = profile.get('url') or ''
                    f.write(f"{name}|{email}|{research_single}|{url}\n")
            print(f"✓ Simple format saved to {filename}")
        except Exception as e:
            print(f"Error saving simple text file: {e}")

    def print_summary(self, results: list):
        total = len(results)
        successful = sum(1 for r in results if r.get('name') or r.get('email'))
        with_research = sum(1 for r in results if r.get('research'))
        print("\n" + "="*50)
        print("SCRAPING SUMMARY")
        print("="*50)
        print(f"Total URLs processed: {total}")
        print(f"Successful extractions: {successful}")
        print(f"Profiles with research interests: {with_research}")

    def __del__(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass


# ---------------------------
# CLI entrypoint
# ---------------------------
def main():
    URLS_FILE = "urls.txt"
    OUTPUT_TXT = "faculty_data.txt"
    OUTPUT_SIMPLE_TXT = "faculty_data_simple.txt"
    USE_SELENIUM = False
    DELAY_BETWEEN_REQUESTS = 1

    print("="*50)
    print("FACULTY PROFILE SCRAPER (JS-VARIABLE SUPPORT)")
    print("="*50)

    scraper = FacultyProfileScraper(use_selenium=USE_SELENIUM)
    urls = scraper.read_urls_from_file(URLS_FILE)

    if not urls:
        print("No URLs to process. Exiting.")
        return

    print(f"\nReady to scrape {len(urls)} URLs.")
    response = input("Continue? (y/n): ").lower()
    if response != 'y':
        print("Scraping cancelled.")
        return

    results = scraper.scrape_multiple_urls(urls, delay=DELAY_BETWEEN_REQUESTS)
    scraper.print_summary(results)
    print("\nSaving results...")
    scraper.save_to_txt(results, OUTPUT_TXT)
    scraper.save_to_simple_txt(results, OUTPUT_SIMPLE_TXT)
    print("\n✓ Scraping completed successfully!")


if __name__ == "__main__":
    main()
