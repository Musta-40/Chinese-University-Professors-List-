#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper - XJTU Specific Version
Targets the exact structure of XJTU faculty pages
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
    """Scraper specifically for XJTU faculty profiles"""
    
    # Research section titles to look for
    RESEARCH_TITLES = [
        '研究领域（方向）',
        '研究领域',
        '研究方向',
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
        
        # Look for email in common locations
        # First check the contact section
        contact_section = soup.find('div', class_='jiaoshi_title', string=re.compile('联系方式'))
        if contact_section:
            next_div = contact_section.find_next_sibling('div')
            if next_div:
                text = next_div.get_text()
                emails = re.findall(email_pattern, text)
                if emails:
                    return emails[0]
        
        # Fallback to searching entire page
        page_text = soup.get_text()
        emails = re.findall(email_pattern, page_text)
        
        # Prefer institutional emails
        for email in emails:
            if 'xjtu.edu.cn' in email or '.edu' in email:
                return email
                
        return emails[0] if emails else None
        
    def extract_name(self, soup) -> str:
        """Extract faculty name from page"""
        # Try the page title first
        title = soup.find('title')
        if title:
            title_text = title.get_text().strip()
            # Often the title contains the name
            if title_text and len(title_text) < 50:
                # Clean up common suffixes
                name = title_text.replace('西安交通大学', '').replace('个人主页', '').strip()
                if name and len(name) < 20:
                    return name
        
        # Look for h1/h2 tags
        for tag in ['h1', 'h2']:
            elem = soup.find(tag)
            if elem:
                text = elem.get_text().strip()
                if text and len(text) < 20:
                    return text
                    
        return "Unknown"
        
    def extract_research_interests_targeted(self, soup) -> str:
        """Extract research interests using the specific XJTU page structure"""
        
        # Method 1: Look for div with class="jiaoshi_title" containing research keywords
        title_divs = soup.find_all('div', class_='jiaoshi_title')
        
        for title_div in title_divs:
            title_text = title_div.get_text().strip()
            
            # Check if this is a research section
            is_research_section = False
            for research_keyword in self.RESEARCH_TITLES:
                if research_keyword in title_text:
                    is_research_section = True
                    logger.info(f"Found research section with title: {title_text}")
                    break
                    
            if is_research_section:
                # Get the next sibling div which should contain the content
                content_div = title_div.find_next_sibling('div')
                
                if content_div and 'jstext' in content_div.get('class', []):
                    # Extract all text from this div
                    content_parts = []
                    
                    # Get all P tags within this div
                    paragraphs = content_div.find_all('p')
                    for p in paragraphs:
                        text = p.get_text().strip()
                        if text:
                            content_parts.append(text)
                    
                    # If no P tags, get the entire text
                    if not content_parts:
                        text = content_div.get_text().strip()
                        if text:
                            content_parts.append(text)
                    
                    if content_parts:
                        result = '\n'.join(content_parts)
                        logger.info(f"Extracted research content: {result[:100]}...")
                        return result
                        
        # Method 2: Fallback - look for any element containing research keywords
        logger.info("Using fallback method to find research content")
        
        for tag in ['div', 'td', 'p']:
            elements = soup.find_all(tag)
            for elem in elements:
                elem_text = elem.get_text().strip()
                
                for research_keyword in self.RESEARCH_TITLES:
                    if research_keyword in elem_text and '：' in elem_text:
                        # Try to extract content after the colon
                        parts = elem_text.split('：', 1)
                        if len(parts) > 1:
                            content = parts[1].strip()
                            # Make sure it's not too long (to avoid getting entire page)
                            if content and len(content) < 2000:
                                logger.info(f"Found research content via fallback: {content[:100]}...")
                                return content
                                
        logger.warning("No research interests found on page")
        return ""
        
    def clean_research_text(self, text: str) -> str:
        """Clean the extracted research text"""
        if not text:
            return ""
            
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Replace P tag artifacts
        text = text.replace('</P>', '\n').replace('<P>', '')
        text = text.replace('</p>', '\n').replace('<p>', '')
        
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
                        EC.presence_of_element_located((By.CLASS_NAME, "jiaoshi_title"))
                    )
                except:
                    # If jiaoshi_title not found, wait for body
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
        description='Scrape XJTU faculty research interests'
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