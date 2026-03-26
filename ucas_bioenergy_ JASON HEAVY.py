#!/usr/bin/env python3
"""
Faculty profile scraper - corrected regexes and minor hardening.
Usage: put URLs (one per line) in urls.txt and run the script.
"""
import requests
from bs4 import BeautifulSoup
import re
import json
import time
from typing import Dict, Optional, List
import html


class FacultyProfileScraper:
    def __init__(self, use_selenium: bool = False):
        """
        Initialize the scraper
        """
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

    def clean_html_text(self, html_string: str) -> str:
        """
        Clean HTML string and extract text properly
        """
        # Unescape HTML entities
        html_string = html.unescape(html_string)

        # Replace escaped characters commonly found in JS strings
        html_string = html_string.replace('\\n', '\n')
        html_string = html_string.replace('\\/', '/')
        html_string = html_string.replace('\\"', '"')
        html_string = html_string.replace('\\r', '')

        # Parse HTML and extract text
        soup = BeautifulSoup(html_string, 'html.parser')

        # Extract text from common container elements
        text_parts = []
        for element in soup.find_all(['p', 'div', 'li']):
            text = element.get_text(separator=' ', strip=True)
            if text:
                text_parts.append(text)

        # Fallback: whole text
        if not text_parts:
            text = soup.get_text(separator='\n', strip=True)
            text_parts = [line.strip() for line in text.split('\n') if line.strip()]

        return '\n'.join(text_parts)

    def scrape_from_javascript(self, html_content: str) -> Dict[str, Optional[str]]:
        """
        Extract data from JavaScript variables embedded in the page HTML.
        Uses safer regex patterns that properly escape quotes and backslashes.
        """
        data = {'name': None, 'email': None, 'research': None}

        # Extract name (example var name - adjust if different)
        name_pattern = r'var\s+xm_en\s*=\s*"([^"]*)"'
        name_match = re.search(name_pattern, html_content)
        if name_match:
            data['name'] = name_match.group(1).strip()

        # Extract email (example var name)
        email_pattern = r'var\s+dzyj\s*=\s*"([^"]*)"'
        email_match = re.search(email_pattern, html_content)
        if email_match:
            data['email'] = email_match.group(1).strip()

        # Extract research interests: capture a JS double-quoted string allowing escaped quotes.
        # Pattern explanation: "((?:[^"\\]|\\.)*)" -> capture any number of characters that are not " or \ OR an escaped char like \" or \n
        research_pattern = r'var\s+enyjfx\s*=\s*"((?:[^"\\]|\\.)*)"'
        research_match = re.search(research_pattern, html_content, re.DOTALL)
        if research_match:
            research_html = research_match.group(1)
            data['research'] = self.clean_html_text(research_html)

            # If the extracted text is too small or empty, try fallback: find #yjfx div on page
            if not data['research'] or data['research'].strip() == '&nbsp;' or len(data['research'].strip()) < 10:
                soup = BeautifulSoup(html_content, 'html.parser')
                research_div = soup.find('div', id='yjfx')
                if research_div:
                    content_divs = research_div.find_all('div', class_='Custom_UnionStyle')
                    research_texts = []
                    for div in content_divs:
                        text = div.get_text(separator=' ', strip=True)
                        if text and text.lower() != 'research':
                            research_texts.append(text)
                    if research_texts:
                        data['research'] = '\n'.join(research_texts)

        # Fallback: try publication variable if research still not found
        if not data['research'] or data['research'].strip() == '&nbsp;' or len(data.get('research', '') or '') < 10:
            pub_pattern = r'var\s+endblz\s*=\s*"((?:[^"\\]|\\.)*)"'
            pub_match = re.search(pub_pattern, html_content, re.DOTALL)
            if pub_match:
                pub_html = pub_match.group(1)
                pub_text = self.clean_html_text(pub_html)
                if pub_text and len(pub_text) > 10:
                    data['research'] = f"Research publications:\n{pub_text[:500]}..." if len(pub_text) > 500 else f"Research publications:\n{pub_text}"

        return data

    def scrape_with_selenium(self, url: str) -> Dict[str, Optional[str]]:
        """
        Scrape using Selenium for JS-rendered pages (optional).
        """
        from selenium.webdriver.common.by import By
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.common.exceptions import TimeoutException

        data = {'name': None, 'email': None, 'research': None}

        try:
            self.driver.get(url)
            time.sleep(2)  # allow JS to run a bit
            wait = WebDriverWait(self.driver, 10)

            # Name (class example from UBs/Chinese pages)
            try:
                name_element = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "ryname_l")))
                data['name'] = name_element.text.strip()
            except TimeoutException:
                pass

            # Email: try an element with ID dzyj
            try:
                email_element = self.driver.find_element(By.ID, "dzyj")
                data['email'] = email_element.text.strip()
            except Exception:
                pass

            # Research
            try:
                time.sleep(1)
                research_section = self.driver.find_element(By.ID, "yjfx")
                all_text = research_section.text or ''
                if all_text:
                    lines = all_text.splitlines()
                    research_lines = [ln.strip() for ln in lines if ln.strip() and ln.strip().lower() != 'research']
                    data['research'] = '\n'.join(research_lines).strip()
            except Exception:
                pass

        except Exception as e:
            print(f"Error scraping with Selenium: {e}")

        return data

    def scrape(self, url: str) -> Dict[str, Optional[str]]:
        """
        Main scraping method (requests by default; Selenium if enabled).
        """
        if self.use_selenium:
            return self.scrape_with_selenium(url)

        try:
            response = requests.get(
                url,
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'},
                timeout=10
            )
            if response.status_code != 200:
                print(f"Failed to fetch {url}: Status code {response.status_code}")
                return {'name': None, 'email': None, 'research': None}

            html_content = response.text
            # Extract from JS variables where available
            data = self.scrape_from_javascript(html_content)
            # As a last fallback, try to find name/email directly in parsed DOM
            if not data['name'] or not data['email']:
                soup = BeautifulSoup(html_content, 'html.parser')
                if not data['name']:
                    # common heading selectors - adjust as needed
                    h = soup.find(['h1', 'h2'], class_='ryname_l') or soup.find('h1') or soup.find('h2')
                    if h:
                        data['name'] = h.get_text(strip=True)
                if not data['email']:
                    email_tag = soup.find(text=re.compile(r'[\w\.-]+@[\w\.-]+\.\w+'))
                    if email_tag:
                        # if direct text contains an email
                        em = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', email_tag)
                        if em:
                            data['email'] = em.group(0)

            return data

        except requests.RequestException as e:
            print(f"Error fetching {url}: {e}")
            return {'name': None, 'email': None, 'research': None}

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
                if data.get('research') and data['research'] != '&nbsp;':
                    preview = data['research'][:50] + "..." if len(data['research']) > 50 else data['research']
                    print(f"    Research: {preview}")
            else:
                print(f"  ✗ No data found")

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
                        f.write("Status: No data found\n")
                        f.write("\n" + "="*80 + "\n\n")
                        continue

                    successful_count += 1
                    f.write(f"PROFILE #{i}\n")
                    f.write("="*80 + "\n")
                    f.write(f"NAME: {profile.get('name') or 'Not found'}\n")
                    f.write("-"*40 + "\n")
                    f.write(f"EMAIL: {profile.get('email') or 'Not found'}\n")
                    f.write("-"*40 + "\n")
                    f.write("RESEARCH INTERESTS:\n")
                    if profile.get('research') and profile['research'] != '&nbsp;':
                        research_lines = profile['research'].split('\n')
                        for line in research_lines:
                            if line.strip():
                                f.write(f"  {line.strip()}\n")
                    else:
                        f.write("  Not found\n")
                    f.write("-"*40 + "\n")
                    f.write(f"SOURCE URL: {profile.get('url')}\n")
                    f.write("\n" + "="*80 + "\n\n")

                f.write("\n" + "="*80 + "\n")
                f.write("SUMMARY\n")
                f.write("="*80 + "\n")
                f.write(f"Total URLs processed: {len(data)}\n")
                f.write(f"Successful extractions: {successful_count}\n")
                f.write(f"Failed extractions: {len(data) - successful_count}\n")
                if successful_count > 0:
                    f.write(f"Success rate: {(successful_count/len(data))*100:.1f}%\n")
            print(f"\n✓ Data saved to {filename}")
        except Exception as e:
            print(f"Error saving to text file: {e}")

    def save_to_simple_txt(self, data: list, filename: str = 'faculty_data_simple.txt'):
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                f.write("Name|Email|Research|URL\n")
                f.write("-"*80 + "\n")
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
        with_research = sum(1 for r in results if r.get('research') and r.get('research') != '&nbsp;')
        print("\n" + "="*50)
        print("SCRAPING SUMMARY")
        print("="*50)
        print(f"Total URLs processed: {total}")
        print(f"Successful extractions: {successful}")
        print(f"Profiles with research interests: {with_research}")
        print(f"Failed extractions: {total - successful}")
        if successful > 0 and total > 0:
            print(f"\nSuccess rate: {(successful/total)*100:.1f}%")

    def __del__(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass


def main():
    URLS_FILE = "urls.txt"
    OUTPUT_TXT = "faculty_data.txt"
    OUTPUT_SIMPLE_TXT = "faculty_data_simple.txt"
    USE_SELENIUM = False
    DELAY_BETWEEN_REQUESTS = 1

    print("="*50)
    print("FACULTY PROFILE SCRAPER")
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

    print("\nStarting scraping process...")
    results = scraper.scrape_multiple_urls(urls, delay=DELAY_BETWEEN_REQUESTS)
    scraper.print_summary(results)
    print("\nSaving results...")
    scraper.save_to_txt(results, OUTPUT_TXT)
    scraper.save_to_simple_txt(results, OUTPUT_SIMPLE_TXT)
    print("\n✓ Scraping completed successfully!")
    print(f"✓ Check '{OUTPUT_TXT}' for detailed results")
    print(f"✓ Check '{OUTPUT_SIMPLE_TXT}' for simple format")


if __name__ == "__main__":
    main()
