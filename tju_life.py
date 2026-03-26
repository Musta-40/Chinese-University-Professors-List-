#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper - TJU (Tianjin University) Version
Targets the specific structure of TJU faculty pages
"""

import argparse
import logging
import random
import re
import time
from pathlib import Path
from typing import Dict, Optional, Set

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class FacultyProfileScraper:
    """Scraper specifically for TJU faculty profiles"""
    
    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls: Set[str] = set()
        self.processed_emails: Set[str] = set()
        
    def setup_driver(self):
        """Initialize Selenium WebDriver"""
        options = Options()
        if self.args.headless:
            options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        options.add_argument('--disable-gpu')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(10)
        
    def close_driver(self):
        """Close WebDriver"""
        if self.driver:
            self.driver.quit()
            
    def random_delay(self):
        """Add random delay between requests"""
        delay = random.uniform(self.args.delay_min, self.args.delay_max)
        time.sleep(delay)
        
    def extract_email(self, soup) -> Optional[str]:
        """Extract email address from TJU page"""
        # First try the specific structure with into_info class
        email_elem = soup.find('p', class_='into_info')
        if email_elem:
            span = email_elem.find('span')
            if span:
                email_text = span.get_text().strip()
                if '@' in email_text:
                    return email_text
        
        # Fallback to regex search
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        page_text = soup.get_text()
        emails = re.findall(email_pattern, page_text)
        
        # Prefer institutional emails
        for email in emails:
            if 'tju.edu.cn' in email or '.edu' in email:
                return email
                
        return emails[0] if emails else None
        
    def extract_name(self, soup) -> str:
        """Extract faculty name from TJU page"""
        # Try the into_top div first (this seems to contain the name)
        name_div = soup.find('div', class_='into_top')
        if name_div:
            name = name_div.get_text().strip()
            if name and len(name) < 50:
                return name
        
        # Try the page title as fallback
        title = soup.find('title')
        if title:
            title_text = title.get_text().strip()
            # Extract name from title (usually contains name)
            if '天津大学教师个人主页系统' in title_text:
                # Extract name between "系统 " and " Home"
                import re
                match = re.search(r'天津大学教师个人主页系统\s*([^Home]+)', title_text)
                if match:
                    name = match.group(1).strip()
                    if name and len(name) < 20:
                        return name
                        
        return "Unknown"
        
    def extract_research_interests_tju(self, soup) -> str:
        """Extract research interests using the TJU page structure"""
        
        # Method 1: Look for the Research Interests section
        # Find the edu_tit div that contains "Research Interests"
        research_titles = soup.find_all('div', class_='edu_tit')
        
        for title_div in research_titles:
            title_text = title_div.get_text().strip()
            
            # Check if this is the Research Interests section
            if 'Research Interests' in title_text or '研究兴趣' in title_text or 'Research' in title_text:
                logger.info(f"Found research section with title: {title_text}")
                
                # Find the parent div
                parent_div = title_div.parent
                
                # Look for the rese_list ul within the parent
                if parent_div:
                    rese_list = parent_div.find('ul', class_='rese_list')
                    if rese_list:
                        # Extract all list items
                        research_items = []
                        list_items = rese_list.find_all('li')
                        
                        for li in list_items:
                            span = li.find('span')
                            if span:
                                text = span.get_text().strip()
                                if text:
                                    research_items.append(text)
                            else:
                                # Try getting text directly from li
                                text = li.get_text().strip()
                                if text:
                                    research_items.append(text)
                        
                        if research_items:
                            result = '\n'.join(research_items)
                            logger.info(f"Extracted {len(research_items)} research interests")
                            return result
        
        # Method 2: Direct search for rese_list
        logger.info("Trying direct search for rese_list")
        rese_lists = soup.find_all('ul', class_='rese_list')
        for rese_list in rese_lists:
            # Check if this list is under a Research Interests heading
            # by checking the previous sibling
            prev_sibling = rese_list.find_previous_sibling('div')
            if prev_sibling and 'edu_tit' in prev_sibling.get('class', []):
                title_text = prev_sibling.get_text().strip()
                if 'Research' in title_text or '研究' in title_text:
                    research_items = []
                    list_items = rese_list.find_all('li')
                    
                    for li in list_items:
                        span = li.find('span')
                        if span:
                            text = span.get_text().strip()
                            if text:
                                research_items.append(text)
                        else:
                            text = li.get_text().strip()
                            if text:
                                research_items.append(text)
                    
                    if research_items:
                        result = '\n'.join(research_items)
                        logger.info(f"Found {len(research_items)} research interests via direct search")
                        return result
        
        # Method 3: Look for any div with id="yjfx" (研究方向)
        research_div = soup.find('div', id='yjfx')
        if research_div:
            # Find the next rese class div
            next_div = research_div.find_next('div', class_='rese')
            if next_div:
                rese_list = next_div.find('ul', class_='rese_list')
                if rese_list:
                    research_items = []
                    list_items = rese_list.find_all('li')
                    
                    for li in list_items:
                        span = li.find('span')
                        if span:
                            text = span.get_text().strip()
                            if text:
                                research_items.append(text)
                    
                    if research_items:
                        result = '\n'.join(research_items)
                        logger.info(f"Found research interests via yjfx id")
                        return result
        
        logger.warning("No research interests found on page")
        return ""
        
    def clean_research_text(self, text: str) -> str:
        """Clean the extracted research text"""
        if not text:
            return ""
            
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Split by newlines for multi-item lists
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.isspace():
                cleaned_lines.append(line)
                
        result = '\n'.join(cleaned_lines)
        
        # Apply truncation if needed
        if self.args.truncate > 0 and len(result) > self.args.truncate:
            result = result[:self.args.truncate] + ' [...]'
            
        return result
        
    def scrape_profile(self, url: str) -> Optional[Dict[str, str]]:
        """Scrape a single faculty profile"""
        # Check if already processed
        normalized_url = url.strip()
        if normalized_url in self.processed_urls:
            logger.info(f"Skipping duplicate URL: {url}")
            return None
            
        logger.info(f"Processing: {url}")
        
        for attempt in range(self.args.retries + 1):
            try:
                # Load page
                self.driver.get(url)
                
                # Wait for the specific content to load
                try:
                    # For TJU pages, wait for the intro class
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "intro"))
                    )
                except:
                    # Fallback wait
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                
                # Additional wait for dynamic content
                time.sleep(2)
                
                # Get page source
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Extract information
                name = self.extract_name(soup)
                email = self.extract_email(soup)
                
                # Check for duplicate email
                if email and email in self.processed_emails:
                    logger.info(f"Skipping duplicate email: {email}")
                    return None
                    
                # Extract research interests using TJU-specific method
                research_interests = self.extract_research_interests_tju(soup)
                research_interests = self.clean_research_text(research_interests)
                
                if not research_interests:
                    research_interests = "Not found"
                    
                # Mark as processed
                self.processed_urls.add(normalized_url)
                if email:
                    self.processed_emails.add(email)
                    
                return {
                    'name': name,
                    'email': email or '',
                    'research_interest': research_interests,
                    'profile_link': url
                }
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                if attempt == self.args.retries:
                    return {
                        'name': 'Unknown',
                        'email': '',
                        'research_interest': f'<FAILED: {str(e)}>',
                        'profile_link': url
                    }
                time.sleep(3)
                
    def write_profile(self, profile: Dict[str, str], output_file: Path):
        """Write profile to output file"""
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"Name: {profile['name']}\n")
            f.write(f"Email: {profile['email']}\n")
            f.write(f"Research interest: {profile['research_interest']}\n")
            f.write(f"Profile link: {profile['profile_link']}\n")
            f.write("---\n\n")
            
    def run(self):
        """Main execution method"""
        # Read input URLs
        input_file = Path(self.args.input_file)
        if not input_file.exists():
            logger.error(f"Input file not found: {input_file}")
            return
            
        with open(input_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
            
        logger.info(f"Found {len(urls)} URLs to process")
        
        # Setup output file
        output_file = Path(self.args.output_file)
        if output_file.exists() and not self.args.append:
            output_file.unlink()
            
        # Setup driver
        self.setup_driver()
        
        try:
            processed_count = 0
            for i, url in enumerate(urls):
                if self.args.max_profiles > 0 and processed_count >= self.args.max_profiles:
                    logger.info(f"Reached maximum profile limit: {self.args.max_profiles}")
                    break
                    
                # Scrape profile
                profile = self.scrape_profile(url)
                
                if profile:
                    self.write_profile(profile, output_file)
                    processed_count += 1
                    logger.info(f"Processed {processed_count}/{len(urls)}: {profile['name']}")
                    
                # Random delay between requests
                if i < len(urls) - 1:
                    self.random_delay()
                    
        finally:
            self.close_driver()
            
        logger.info(f"Completed! Processed {processed_count} profiles")
        

def main():
    parser = argparse.ArgumentParser(
        description='Scrape TJU faculty research interests'
    )
    
    parser.add_argument(
        '--input-file', 
        default='urls.txt',
        help='Input file containing URLs (one per line)'
    )
    
    parser.add_argument(
        '--output-file',
        default='output.txt',
        help='Output file for results'
    )
    
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode'
    )
    
    parser.add_argument(
        '--delay-min',
        type=float,
        default=1.0,
        help='Minimum delay between requests (seconds)'
    )
    
    parser.add_argument(
        '--delay-max',
        type=float,
        default=3.0,
        help='Maximum delay between requests (seconds)'
    )
    
    parser.add_argument(
        '--max-profiles',
        type=int,
        default=0,
        help='Maximum number of profiles to process (0 for unlimited)'
    )
    
    parser.add_argument(
        '--retries',
        type=int,
        default=2,
        help='Number of retries for failed requests'
    )
    
    parser.add_argument(
        '--truncate',
        type=int,
        default=4000,
        help='Maximum length for research interests text (0 for no limit)'
    )
    
    parser.add_argument(
        '--append',
        action='store_true',
        help='Append to output file instead of overwriting'
    )
    
    args = parser.parse_args()
    
    scraper = FacultyProfileScraper(args)
    scraper.run()
    

if __name__ == '__main__':
    main()