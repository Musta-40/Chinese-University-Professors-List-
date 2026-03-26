#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper - SEU English Version
Targets the exact structure of SEU English faculty pages
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
    """Scraper specifically for SEU English faculty profiles"""
    
    # Research section titles to look for (English version)
    RESEARCH_TITLES = [
        'Academic expertise and research direction',
        'Research Interests',
        'Research Areas',
        'Research Direction',
        'Research Focus',
        'Areas of Expertise',
        'Research Topics'
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
        
    def extract_from_table(self, soup, field_name: str) -> Optional[str]:
        """Extract a field from the table structure"""
        # Look for table cells
        all_tds = soup.find_all('td')
        
        for i, td in enumerate(all_tds):
            td_text = td.get_text().strip()
            # Check if this cell contains the field name
            if field_name.lower() in td_text.lower():
                # Get the next td which should contain the value
                if i + 1 < len(all_tds):
                    value_td = all_tds[i + 1]
                    value = value_td.get_text().strip()
                    # Clean up HTML entities and extra spaces
                    value = re.sub(r'\s+', ' ', value)
                    value = value.replace('\xa0', ' ')
                    return value
        return None
        
    def extract_email(self, soup) -> Optional[str]:
        """Extract email address from page"""
        # First try to find it in the table structure
        email = self.extract_from_table(soup, 'Email')
        if email and '@' in email:
            # Clean up the email
            email = email.strip()
            # Extract just the email part if there's extra text
            email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
            emails = re.findall(email_pattern, email)
            if emails:
                return emails[0]
        
        # Fallback: search entire page for SEU email
        email_pattern = r'[\w\.-]+@seu\.edu\.cn'
        page_text = soup.get_text()
        emails = re.findall(email_pattern, page_text)
        
        if emails:
            return emails[0]
            
        # Try any email as last resort
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        emails = re.findall(email_pattern, page_text)
        
        # Prefer institutional emails
        for email in emails:
            if 'seu.edu.cn' in email or '.edu' in email:
                return email
                
        return emails[0] if emails else None
        
    def extract_name(self, soup) -> str:
        """Extract faculty name from page"""
        # Method 1: Try to find it in the table
        name = self.extract_from_table(soup, 'Name')
        if name and len(name) < 50 and name != 'Unknown':
            return name.strip()
        
        # Method 2: Try the h1 with class arti_title
        h1 = soup.find('h1', class_='arti_title')
        if h1:
            name = h1.get_text().strip()
            if name and len(name) < 50:
                return name
        
        # Method 3: Try the page title
        title = soup.find('title')
        if title:
            title_text = title.get_text().strip()
            # Often the title contains just the name
            if title_text and len(title_text) < 50:
                return title_text
                    
        return "Unknown"
        
    def extract_research_interests_targeted(self, soup) -> str:
        """Extract research interests using the specific SEU English page table structure"""
        
        # Method 1: Look for research fields in table structure
        for research_keyword in self.RESEARCH_TITLES:
            content = self.extract_from_table(soup, research_keyword)
            if content:
                logger.info(f"Found research content for '{research_keyword}': {content[:100]}...")
                return content
        
        # Method 2: Look for table rows containing research keywords
        all_trs = soup.find_all('tr')
        for tr in all_trs:
            tr_text = tr.get_text().strip()
            for research_keyword in self.RESEARCH_TITLES:
                if research_keyword.lower() in tr_text.lower():
                    # Find all tds in this row
                    tds = tr.find_all('td')
                    if len(tds) >= 2:
                        # The second td should contain the content
                        content = tds[1].get_text().strip()
                        content = re.sub(r'\s+', ' ', content)
                        content = content.replace('\xa0', ' ')
                        if content and len(content) > 20:  # Make sure it's not just a label
                            logger.info(f"Found research content via row search: {content[:100]}...")
                            return content
        
        # Method 3: Fallback - look for paragraphs after research keywords
        for tag in ['p', 'div', 'td']:
            elements = soup.find_all(tag)
            for elem in elements:
                elem_text = elem.get_text().strip()
                for research_keyword in self.RESEARCH_TITLES:
                    if research_keyword.lower() in elem_text.lower():
                        # Try to extract content from the same element
                        if len(elem_text) > len(research_keyword) + 20:
                            # There's substantial content in the same element
                            parts = elem_text.split(research_keyword, 1)
                            if len(parts) > 1:
                                content = parts[1].strip()
                                # Remove any leading colons or punctuation
                                content = re.sub(r'^[:\s]+', '', content)
                                if content and len(content) > 20:
                                    logger.info(f"Found research content via fallback: {content[:100]}...")
                                    return content
                                
        logger.warning("No research interests found on page")
        return ""
        
    def clean_research_text(self, text: str) -> str:
        """Clean the extracted research text"""
        if not text:
            return ""
            
        # Remove HTML entities
        text = text.replace('&nbsp;', ' ')
        text = text.replace('\xa0', ' ')
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove any remaining HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        
        # Clean up
        text = text.strip()
        
        # Apply truncation if needed
        if self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + ' [...]'
            
        return text
        
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
                
                # Wait for the content to load (looking for table or article content)
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.TAG_NAME, "table"))
                    )
                except:
                    # If table not found, wait for article
                    try:
                        WebDriverWait(self.driver, 10).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "wp_articlecontent"))
                        )
                    except:
                        # Last resort: wait for body
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
        description='Scrape SEU English faculty research interests'
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