#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper - SJTU Specific Version
Targets the exact structure of SJTU faculty pages
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
    """Scraper specifically for SJTU faculty profiles"""
    
    # Research section titles to look for
    RESEARCH_TITLES = [
        '研究方向',
        '研究领域',
        '研究领域（方向）',
        '主要研究方向',
        '研究兴趣',
        '研究内容',
        '科研方向'
    ]
    
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
        """Extract email address from page"""
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        
        # Look for email in the txtk div (SJTU structure)
        txtk_div = soup.find('div', class_='txtk')
        if txtk_div:
            text = txtk_div.get_text()
            # Look for email after "邮箱：" pattern
            if '邮箱：' in text or '邮箱:' in text:
                emails = re.findall(email_pattern, text)
                if emails:
                    return emails[0]
        
        # Fallback to searching entire page
        page_text = soup.get_text()
        emails = re.findall(email_pattern, page_text)
        
        # Prefer institutional emails
        for email in emails:
            if 'sjtu.edu.cn' in email or '.edu' in email:
                return email
                
        return emails[0] if emails else None
        
    def extract_name(self, soup) -> str:
        """Extract faculty name from page"""
        # For SJTU pages, look in the txtk div for h2 tag
        txtk_div = soup.find('div', class_='txtk')
        if txtk_div:
            h2_tag = txtk_div.find('h2')
            if h2_tag:
                name = h2_tag.get_text().strip()
                if name and len(name) < 20:
                    return name
        
        # Fallback to page title
        title = soup.find('title')
        if title:
            title_text = title.get_text().strip()
            # Extract name from title (format: "姓名-上海交通大学药学院")
            if '-' in title_text:
                name = title_text.split('-')[0].strip()
                if name and len(name) < 20:
                    return name
                    
        return "Unknown"
        
    def extract_research_interests_targeted(self, soup) -> str:
        """Extract research interests using the specific SJTU page structure"""
        
        # Method 1: Look for research content in mls_n divs
        # The tab structure has ml_lm with links, and corresponding mls_n divs with content
        ml_lm = soup.find('div', class_='ml_lm')
        
        if ml_lm:
            # Find all tab links
            tab_links = ml_lm.find_all('a')
            
            # Find the research tab index
            research_tab_index = -1
            for i, link in enumerate(tab_links):
                link_text = link.get_text().strip()
                for research_keyword in self.RESEARCH_TITLES:
                    if research_keyword in link_text:
                        research_tab_index = i
                        logger.info(f"Found research tab: {link_text} at index {i}")
                        break
                if research_tab_index >= 0:
                    break
            
            # If we found the research tab, get the corresponding content
            if research_tab_index >= 0:
                # Find all content divs
                mls_n_divs = soup.find_all('div', class_='mls_n')
                
                # Get the content from the corresponding index
                if research_tab_index < len(mls_n_divs):
                    content_div = mls_n_divs[research_tab_index]
                    
                    # Look for ab_nr div within this section
                    ab_nr = content_div.find('div', class_='ab_nr')
                    if ab_nr:
                        # Extract text from this div
                        text = ab_nr.get_text().strip()
                        if text:
                            logger.info(f"Extracted research content: {text[:100]}...")
                            return text
        
        # Method 2: Direct search for research content by looking for keywords
        logger.info("Using fallback method to find research content")
        
        # Look through all mls_n divs for research content
        mls_n_divs = soup.find_all('div', class_='mls_n')
        for div in mls_n_divs:
            ab_nr = div.find('div', class_='ab_nr')
            if ab_nr:
                text = ab_nr.get_text().strip()
                # Check if this contains research keywords
                for keyword in ['药物', '研究', '研发', '新型', '抗肿瘤', '抗感染', '抗糖尿病', '分子', '机制']:
                    if keyword in text and len(text) > 50:  # Likely research content
                        logger.info(f"Found potential research content via keyword matching: {text[:100]}...")
                        return text
        
        # Method 3: Last resort - check all ab_nr divs
        ab_nr_divs = soup.find_all('div', class_='ab_nr')
        if len(ab_nr_divs) >= 2:  # Usually the second one is research
            text = ab_nr_divs[1].get_text().strip()
            if text:
                logger.info(f"Using second ab_nr div as research content: {text[:100]}...")
                return text
                        
        logger.warning("No research interests found on page")
        return ""
        
    def clean_research_text(self, text: str) -> str:
        """Clean the extracted research text"""
        if not text:
            return ""
            
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Handle <br /> tags properly
        text = text.replace('<br />', '\n').replace('<br/>', '\n').replace('<br>', '\n')
        
        # Clean up
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
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "mls_n"))
                    )
                except:
                    # If mls_n not found, wait for body
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
                    
                # Extract research interests
                research_interests = self.extract_research_interests_targeted(soup)
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
        description='Scrape SJTU faculty research interests'
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