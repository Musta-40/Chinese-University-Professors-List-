#!/usr/bin/env python3
"""
Faculty Profile Scraper - Optimized for GIBH Faculty Pages
Handles both English and Chinese templates with specific extraction logic
"""
import os
import argparse
import json
import logging
import random
import re
import time
import html
from pathlib import Path
from typing import Dict, Optional, Set, List, Tuple
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup, Tag, NavigableString

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GIBHFacultyScraper:
    """Specialized scraper for GIBH faculty profiles"""
    
    # Priority keywords for research sections
    RESEARCH_PRIMARY_KEYWORDS = ['Research Areas', '研究领域']
    RESEARCH_FALLBACK_KEYWORDS = ['Representative Papers', '代表论著']
    
    # Stop keywords for research extraction
    RESEARCH_STOP_KEYWORDS = ['Patents', '专利', 'Academic Performance', '承担科研项目情况', '获奖及荣誉']
    
    # Email keywords
    EMAIL_KEYWORDS = ['Email：', '电子邮件：', '电子邮箱：', '邮箱：']
    
    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls: Set[str] = set()
        self.failed_urls: List[str] = []
        
    # ================ Helper Methods ================
    @staticmethod
    def normalize_text(s: Optional[str]) -> str:
        """Normalize text by removing extra whitespace"""
        if not s:
            return ''
        s = html.unescape(s)
        s = re.sub(r'\s+', ' ', s)
        s = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', s)  # Remove zero-width spaces
        return s.strip()
    
    @staticmethod
    def clean_html_element(element: Tag) -> None:
        """Remove style, script, and other non-content tags from element"""
        if not element:
            return
            
        # Remove style tags and their content
        for style_tag in element.find_all('style'):
            style_tag.decompose()
        
        # Remove script tags and their content
        for script_tag in element.find_all('script'):
            script_tag.decompose()
        
        # Remove noscript tags
        for noscript_tag in element.find_all('noscript'):
            noscript_tag.decompose()
            
        # Remove comment nodes
        for comment in element.find_all(text=lambda text: isinstance(text, NavigableString) and isinstance(text, type(NavigableString('')))):
            if '<!--' in str(comment):
                comment.extract()
    
    def extract_clean_text(self, element: Tag, stop_keywords: List[str] = None) -> str:
        """Extract clean text from element, optionally stopping at keywords"""
        if not element:
            return ""
        
        # Clone the element to avoid modifying the original
        element_copy = BeautifulSoup(str(element), 'html.parser')
        
        # Clean the element first
        self.clean_html_element(element_copy)
        
        texts = []
        stop_found = False
        
        # Extract text
        for p in element_copy.find_all(['p', 'div', 'span', 'li']):
            if stop_found:
                break
                
            text = p.get_text(strip=True)
            
            # Check for stop keywords
            if stop_keywords:
                for keyword in stop_keywords:
                    if keyword in text:
                        # Add text before the keyword
                        before_keyword = text.split(keyword)[0].strip()
                        if before_keyword:
                            texts.append(before_keyword)
                        stop_found = True
                        break
            
            if not stop_found and text:
                # Filter out CSS-like content
                if not self.is_css_content(text):
                    texts.append(text)
        
        # If no structured tags found, get all text
        if not texts:
            full_text = element_copy.get_text(separator='\n', strip=True)
            # Split by lines and filter
            for line in full_text.split('\n'):
                if stop_keywords:
                    for keyword in stop_keywords:
                        if keyword in line:
                            before_keyword = line.split(keyword)[0].strip()
                            if before_keyword and not self.is_css_content(before_keyword):
                                texts.append(before_keyword)
                            stop_found = True
                            break
                
                if not stop_found and line.strip() and not self.is_css_content(line):
                    texts.append(line.strip())
        
        return '\n'.join(texts)
    
    def is_css_content(self, text: str) -> bool:
        """Check if text looks like CSS content"""
        css_indicators = [
            'FONT-SIZE:', 'FONT-FAMILY:', 'TEXT-ALIGN:', 'MARGIN:',
            'TEXT-JUSTIFY:', '.MsoNormal', '.TRS_PreAppend', 'WordSection',
            'page:', 'DIV.', 'P.', 'LI.', '{', '}', 'sans-serif',
            'text/css', 'style=', '@media', 'px;', 'pt;', 'em;'
        ]
        
        # Check if text contains multiple CSS indicators
        css_count = sum(1 for indicator in css_indicators if indicator in text)
        return css_count >= 2
    
    def clean_research_text(self, text: str) -> str:
        """Clean and format research text"""
        if not text:
            return ""
        
        # Remove any remaining HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        
        # Remove CSS-like content
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip empty lines
            if not line:
                continue
            
            # Skip CSS content
            if self.is_css_content(line):
                continue
            
            # Skip if line contains stop keywords
            if any(keyword in line for keyword in self.RESEARCH_STOP_KEYWORDS):
                break
            
            # Skip numbered patent entries
            if re.match(r'^\s*\d+[\.、]\s*[A-Z].*patent', line, re.IGNORECASE):
                continue
            
            # Add valid line
            if len(line) > 2:  # Skip very short lines
                cleaned_lines.append(line)
        
        text = '\n'.join(cleaned_lines)
        
        # Clean up formatting
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove leading numbers from lines
        text = re.sub(r'^[\d]+[\.、]\s*', '', text, flags=re.MULTILINE)
        
        # Final cleanup
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\s*\n\s*', '\n', text)
        
        # Truncate if needed
        if self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        
        return text.strip()
    
    # ================ Template Detection ================
    def detect_template_type(self, soup) -> str:
        """Detect which template the page uses"""
        # English template (Sources 1-3)
        if soup.find('div', class_='info-title') and soup.find('div', class_='jbxx'):
            return 'ENGLISH_TEMPLATE'
        
        # Chinese template (Sources 4-5)
        if soup.find('div', class_='name') and soup.find('div', class_='detail-title'):
            return 'CHINESE_TEMPLATE'
        
        return 'UNKNOWN'
    
    # ================ Name Extraction ================
    def extract_name_english_template(self, soup) -> Optional[str]:
        """Extract name from English template pages"""
        try:
            # Find the first info-title under info-top
            info_top = soup.find('div', class_='info-top')
            if info_top:
                box_info = info_top.find('div', class_='box-info')
                if box_info:
                    name_div = box_info.find('div', class_='info-title')
                    if name_div:
                        return self.normalize_text(name_div.get_text())
            
            # Fallback: just find first info-title
            name_div = soup.find('div', class_='info-title')
            if name_div:
                return self.normalize_text(name_div.get_text())
                
        except Exception as e:
            logger.debug(f"Error extracting name (English): {e}")
        
        return None
    
    def extract_name_chinese_template(self, soup) -> Optional[str]:
        """Extract name from Chinese template pages"""
        try:
            name_div = soup.find('div', class_='name')
            if name_div:
                # Get first span (name), ignore second span (gender)
                first_span = name_div.find('span')
                if first_span:
                    return self.normalize_text(first_span.get_text())
                    
        except Exception as e:
            logger.debug(f"Error extracting name (Chinese): {e}")
        
        return None
    
    # ================ Email Extraction ================
    def extract_email_english_template(self, soup) -> Optional[str]:
        """Extract email from English template pages"""
        try:
            # Look for div.jbxx containing "Email："
            for div in soup.find_all('div', class_='jbxx'):
                text = div.get_text(strip=True)
                if any(keyword in text for keyword in ['Email：', 'Email:']):
                    # Find the span.txt within this div
                    txt_span = div.find('span', class_='txt')
                    if txt_span:
                        email = self.normalize_text(txt_span.get_text())
                        if email and '@' in email:
                            return email
                    
                    # Fallback: extract email from text
                    match = re.search(r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,})', text)
                    if match:
                        return match.group(1)
                        
        except Exception as e:
            logger.debug(f"Error extracting email (English): {e}")
        
        return None
    
    def extract_email_chinese_template(self, soup) -> Optional[str]:
        """Extract email from Chinese template pages"""
        try:
            # Look for div.table-info containing email keywords
            for div in soup.find_all('div', class_='table-info'):
                b_tag = div.find('b')
                if b_tag and any(keyword in b_tag.get_text() for keyword in self.EMAIL_KEYWORDS):
                    # Find the span.jbinfo
                    info_span = div.find('span', class_='jbinfo')
                    if info_span:
                        email = self.normalize_text(info_span.get_text())
                        if email:  # Could be empty
                            return email
                            
        except Exception as e:
            logger.debug(f"Error extracting email (Chinese): {e}")
        
        return None
    
    # ================ Research Extraction ================
    def extract_research_english_template(self, soup) -> str:
        """Extract research from English template pages"""
        try:
            # First try: Look for Research Areas
            for keyword in self.RESEARCH_PRIMARY_KEYWORDS:
                research_content = self._extract_research_by_keyword_english(soup, keyword)
                if research_content and len(research_content) > 10:
                    return research_content
            
            # Fallback: Look for Representative Papers
            for keyword in self.RESEARCH_FALLBACK_KEYWORDS:
                research_content = self._extract_research_by_keyword_english(soup, keyword)
                if research_content:
                    return research_content
                    
        except Exception as e:
            logger.debug(f"Error extracting research (English): {e}")
        
        return ""
    
    def _extract_research_by_keyword_english(self, soup, keyword: str) -> str:
        """Helper to extract research by specific keyword in English template"""
        try:
            # Find all info-groups
            for info_group in soup.find_all('div', class_='info-groups'):
                title_div = info_group.find('div', class_='info-title')
                if title_div and keyword in title_div.get_text():
                    # Get the corresponding info-txt
                    info_txt = info_group.find('div', class_='info-txt')
                    if info_txt:
                        # Check if empty
                        if not info_txt.get_text(strip=True):
                            return ""
                        
                        # Find TRS editor view or use info-txt directly
                        editor_view = info_txt.find('div', class_=re.compile('TRS_UEDITOR|trs_editor_view|TRS_Editor'))
                        
                        if editor_view:
                            content = self.extract_clean_text(editor_view, self.RESEARCH_STOP_KEYWORDS)
                        else:
                            content = self.extract_clean_text(info_txt, self.RESEARCH_STOP_KEYWORDS)
                        
                        return self.clean_research_text(content)
                            
        except Exception as e:
            logger.debug(f"Error in _extract_research_by_keyword_english: {e}")
        
        return ""
    
    def extract_research_chinese_template(self, soup) -> str:
        """Extract research from Chinese template pages"""
        try:
            # First try: Look for 研究领域
            for keyword in self.RESEARCH_PRIMARY_KEYWORDS:
                research_content = self._extract_research_by_keyword_chinese(soup, keyword)
                if research_content and len(research_content) > 10:
                    return research_content
            
            # Fallback: Look for 代表论著
            for keyword in self.RESEARCH_FALLBACK_KEYWORDS:
                research_content = self._extract_research_by_keyword_chinese(soup, keyword)
                if research_content:
                    return research_content
                    
        except Exception as e:
            logger.debug(f"Error extracting research (Chinese): {e}")
        
        return ""
    
    def _extract_research_by_keyword_chinese(self, soup, keyword: str) -> str:
        """Helper to extract research by specific keyword in Chinese template"""
        try:
            # Find all detail-info divs
            for detail_info in soup.find_all('div', class_='detail-info'):
                title_div = detail_info.find('div', class_='detail-title')
                if title_div:
                    title_span = title_div.find('span')
                    if title_span and keyword in title_span.get_text():
                        # Get the corresponding detail-t
                        detail_t = detail_info.find('div', class_='detail-t')
                        if detail_t:
                            # Check if empty
                            if not detail_t.get_text(strip=True):
                                return ""
                            
                            # Find TRS editor view or use detail-t directly
                            editor_view = detail_t.find('div', class_=re.compile('TRS_UEDITOR|trs_editor_view|TRS_Editor'))
                            
                            if editor_view:
                                content = self.extract_clean_text(editor_view, self.RESEARCH_STOP_KEYWORDS)
                            else:
                                content = self.extract_clean_text(detail_t, self.RESEARCH_STOP_KEYWORDS)
                            
                            return self.clean_research_text(content)
                            
        except Exception as e:
            logger.debug(f"Error in _extract_research_by_keyword_chinese: {e}")
        
        return ""
    
    # ================ Driver Setup ================
    def setup_driver(self):
        """Setup Selenium WebDriver"""
        options = Options()
        if self.args.headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        options.add_argument('--disable-gpu')
        options.add_argument('--lang=zh-CN,en-US')
        
        try:
            driver_path = ChromeDriverManager().install()
            service = Service(driver_path)
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.implicitly_wait(10)
        except Exception as e:
            logger.error(f"WebDriver setup failed: {e}")
            raise
    
    def close_driver(self):
        """Close WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
    
    # ================ Main Scraping Logic ================
    def scrape_profile(self, url: str) -> Optional[Dict[str, str]]:
        """Scrape a single faculty profile"""
        normalized_url = url.strip()
        
        # Skip if already processed
        if normalized_url in self.processed_urls:
            logger.info(f"Skipping duplicate URL: {url}")
            return None
        
        logger.info(f"Processing: {url}")
        
        for attempt in range(self.args.retries + 1):
            try:
                # Load the page
                self.driver.get(url)
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(1.5)  # Allow JS to render
                
                # Parse HTML
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # Remove all style and script tags from soup first
                for style in soup.find_all('style'):
                    style.decompose()
                for script in soup.find_all('script'):
                    script.decompose()
                
                # Detect template type
                template = self.detect_template_type(soup)
                if self.args.debug:
                    logger.debug(f"Template detected: {template}")
                
                # Initialize results
                name = "Unknown"
                email = "Not found"
                research = "Not found"
                
                # Extract based on template
                if template == 'ENGLISH_TEMPLATE':
                    name = self.extract_name_english_template(soup) or "Unknown"
                    email = self.extract_email_english_template(soup) or "Not found"
                    research = self.extract_research_english_template(soup) or "Not found"
                    
                elif template == 'CHINESE_TEMPLATE':
                    name = self.extract_name_chinese_template(soup) or "Unknown"
                    email = self.extract_email_chinese_template(soup) or "Not found"
                    research = self.extract_research_chinese_template(soup) or "Not found"
                    
                else:
                    # Try both templates
                    name = (self.extract_name_english_template(soup) or 
                           self.extract_name_chinese_template(soup) or 
                           "Unknown")
                    email = (self.extract_email_english_template(soup) or 
                            self.extract_email_chinese_template(soup) or 
                            "Not found")
                    research = (self.extract_research_english_template(soup) or 
                               self.extract_research_chinese_template(soup) or 
                               "Not found")
                
                # Clean up email
                if email and email != "Not found":
                    email = email.upper()  # Standardize to uppercase
                
                # Final validation of research content
                if research and len(research) < 5:
                    research = "Not found"
                
                # Mark as processed
                self.processed_urls.add(normalized_url)
                
                # Log results
                logger.info(f"✓ Name: {name}")
                logger.info(f"✓ Email: {email}")
                research_preview = research[:100] + "..." if len(research) > 100 else research
                logger.info(f"✓ Research: {research_preview}")
                
                return {
                    'name': name,
                    'email': email,
                    'research_interest': research,
                    'profile_link': url
                }
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                if attempt == self.args.retries:
                    self.processed_urls.add(normalized_url)
                    self.failed_urls.append(url)
                    return {
                        'name': 'Error',
                        'email': 'Error',
                        'research_interest': f'Error: {str(e)}',
                        'profile_link': url
                    }
                time.sleep(2)
        
        return None
    
    def random_delay(self):
        """Add random delay between requests"""
        delay = random.uniform(self.args.delay_min, self.args.delay_max)
        time.sleep(delay)
    
    # ================ Output Methods ================
    def write_profile(self, profile: Dict[str, str], output_file: Path):
        """Write profile to text file"""
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"Name: {profile['name']}\n")
            f.write(f"Email: {profile['email']}\n")
            f.write(f"Research interest: {profile['research_interest']}\n")
            f.write(f"Profile link: {profile['profile_link']}\n")
            f.write("---\n\n")
    
    def write_json_output(self, profiles: List[Dict], output_file: Path):
        """Write profiles to JSON file"""
        json_file = output_file.with_suffix('.json')
        json_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)
    
    def write_csv_output(self, profiles: List[Dict], output_file: Path):
        """Write profiles to CSV file"""
        import csv
        
        csv_file = output_file.with_suffix('.csv')
        csv_file.parent.mkdir(parents=True, exist_ok=True)
        
        with open(csv_file, 'w', newline='', encoding='utf-8-sig') as f:
            if profiles:
                writer = csv.DictWriter(f, fieldnames=profiles[0].keys())
                writer.writeheader()
                writer.writerows(profiles)
    
    # ================ Main Run Method ================
    def run(self):
        """Main execution method"""
        # Load URLs
        input_file = Path(self.args.input_file)
        if not input_file.exists():
            logger.error(f"Input file not found: {input_file}")
            return
        
        with open(input_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and not line.startswith('#')]
        
        logger.info(f"Found {len(urls)} URLs to process")
        
        # Setup output
        output_file = Path(self.args.output_file)
        if output_file.exists() and not self.args.append:
            output_file.unlink()
        output_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Setup driver
        self.setup_driver()
        
        profiles_list = []
        
        try:
            processed_count = 0
            
            for i, url in enumerate(urls, 1):
                # Check max profiles limit
                if self.args.max_profiles > 0 and processed_count >= self.args.max_profiles:
                    logger.info(f"Reached maximum profile limit: {self.args.max_profiles}")
                    break
                
                # Progress indicator
                logger.info(f"\n[{i}/{len(urls)}] Processing...")
                
                # Scrape profile
                profile = self.scrape_profile(url)
                
                if profile:
                    self.write_profile(profile, output_file)
                    profiles_list.append(profile)
                    processed_count += 1
                
                # Add delay between requests
                if i < len(urls):
                    self.random_delay()
            
            # Save additional output formats
            if profiles_list:
                if self.args.json_output:
                    self.write_json_output(profiles_list, output_file)
                    logger.info(f"✓ Saved JSON to {output_file.with_suffix('.json')}")
                
                if self.args.csv_output:
                    self.write_csv_output(profiles_list, output_file)
                    logger.info(f"✓ Saved CSV to {output_file.with_suffix('.csv')}")
            
            # Summary
            logger.info("\n" + "="*50)
            logger.info(f"✓ Completed! Processed {processed_count} profiles")
            logger.info(f"✓ Results saved to: {output_file}")
            
            if self.failed_urls:
                logger.warning(f"⚠ Failed URLs ({len(self.failed_urls)}):")
                for url in self.failed_urls:
                    logger.warning(f"  - {url}")
                    
        finally:
            self.close_driver()


# ================ CLI Entry Point ================
def main():
    parser = argparse.ArgumentParser(
        description='GIBH Faculty Profile Scraper - Extract name, email, and research interests'
    )
    
    # Input/Output arguments
    parser.add_argument('--input-file', 
                       default='urls.txt',
                       help='Input file containing URLs (one per line)')
    parser.add_argument('--output-file',
                       default='faculty_profiles.txt',
                       help='Output file for results')
    
    # Browser settings
    parser.add_argument('--headless',
                       action='store_true',
                       help='Run browser in headless mode')
    
    # Request settings
    parser.add_argument('--delay-min',
                       type=float,
                       default=1.0,
                       help='Minimum delay between requests (seconds)')
    parser.add_argument('--delay-max',
                       type=float,
                       default=3.0,
                       help='Maximum delay between requests (seconds)')
    parser.add_argument('--retries',
                       type=int,
                       default=2,
                       help='Number of retries for failed requests')
    
    # Processing settings
    parser.add_argument('--max-profiles',
                       type=int,
                       default=0,
                       help='Maximum number of profiles to process (0=unlimited)')
    parser.add_argument('--truncate',
                       type=int,
                       default=5000,
                       help='Maximum length for research text (0=no limit)')
    
    # Output settings
    parser.add_argument('--append',
                       action='store_true',
                       help='Append to output file instead of overwriting')
    parser.add_argument('--json-output',
                       action='store_true',
                       help='Also save output as JSON')
    parser.add_argument('--csv-output',
                       action='store_true',
                       help='Also save output as CSV')
    
    # Debug settings
    parser.add_argument('--debug',
                       action='store_true',
                       help='Enable debug mode with verbose output')
    
    args = parser.parse_args()
    
    # Set debug level if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run scraper
    scraper = GIBHFacultyScraper(args)
    scraper.run()


if __name__ == '__main__':
    main()