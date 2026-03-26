#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper - PKU Bio Version
Targets the structure of PKU School of Life Sciences faculty pages
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
    """Scraper specifically for PKU Bio faculty profiles"""
    
    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls: Set[str] = set()
        self.processed_emails: Set[str] = set()

        # Precompile obfuscation patterns for performance and safety
        self._obf_patterns = [
            re.compile(r'\s*KATEX_INLINE_OPENATKATEX_INLINE_CLOSE\s*', re.IGNORECASE),
            re.compile(r'\s*```math\s*AT```\s*', re.IGNORECASE),  # fixed: no literal newline
            re.compile(r'\s*\(AT\)\s*', re.IGNORECASE),
            re.compile(r'\s*\[AT\]\s*', re.IGNORECASE),
            re.compile(r'\s+AT\s+', re.IGNORECASE),
            re.compile(r'\s+at\s+', re.IGNORECASE),
            re.compile(r'＠', re.IGNORECASE),  # full-width at sign
        ]
        
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

    def _normalize_obfuscated_at(self, text: str) -> str:
        """Replace common obfuscations of '@' with a literal '@'."""
        if not text:
            return text
        for pat in self._obf_patterns:
            text = pat.sub('@', text)
        return text
        
    def extract_email(self, soup) -> Optional[str]:
        """Extract email address from page"""
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        
        # Look for email in the info section with specific format
        # PKU uses format like: 邮  箱： qulj (AT) pku.edu.cn
        info_section = soup.find('div', class_='info_r')
        if info_section:
            paragraphs = info_section.find_all('p')
            for p in paragraphs:
                text = p.get_text()
                # Check for email field with flexible spacing
                if '邮' in text and '箱' in text:
                    # Extract everything after the colon
                    if '：' in text or ':' in text:
                        # Split by Chinese or English colon
                        parts = re.split('[：:]', text, 1)
                        if len(parts) > 1:
                            email_text = parts[1].strip()
                        else:
                            email_text = text
                    else:
                        email_text = text
                    
                    # Clean up the email format - handle various AT formats using helper
                    email_text = self._normalize_obfuscated_at(email_text)
                    
                    # Extract email pattern
                    emails = re.findall(email_pattern, email_text)
                    if emails:
                        logger.info(f"Found email: {emails[0]}")
                        return emails[0]
        
        # Fallback to searching entire page
        page_text = soup.get_text()
        # Replace common obfuscations using helper
        page_text = self._normalize_obfuscated_at(page_text)
        emails = re.findall(email_pattern, page_text)
        
        # Prefer institutional emails
        for email in emails:
            if 'pku.edu.cn' in email or '.edu' in email:
                return email
                
        return emails[0] if emails else None
        
    def extract_name(self, soup) -> str:
        """Extract faculty name from page"""
        # For PKU Bio, the name is in h5 tag within info_r div
        info_section = soup.find('div', class_='info_r')
        if info_section:
            h5_tag = info_section.find('h5')
            if h5_tag:
                name = h5_tag.get_text().strip()
                if name:
                    return name
        
        # Fallback to title
        title = soup.find('title')
        if title:
            title_text = title.get_text().strip()
            # Clean up common suffixes
            name = title_text.replace('北京大学生命科学学院', '').replace('个人主页', '').strip()
            if name and len(name) < 20:
                return name
                    
        return "Unknown"
        
    def extract_research_interests_from_tabs(self) -> str:
        """Extract research interests by clicking on the research tab"""
        try:
            # Wait for the tab structure to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "teacher_content"))
            )
            
            # Find the tabs
            tabs = self.driver.find_elements(By.CSS_SELECTOR, ".teacher_content > ul > li")
            
            # Look for the research tab (usually "科研领域" or similar)
            research_tab_index = -1
            for i, tab in enumerate(tabs):
                tab_text = tab.text.strip()
                logger.info(f"Found tab: {tab_text}")
                if any(keyword in tab_text for keyword in ['科研', '研究', 'Research']):
                    research_tab_index = i
                    break
            
            if research_tab_index >= 0:
                # Click the research tab
                logger.info(f"Clicking research tab at index {research_tab_index}")
                tabs[research_tab_index].click()
                time.sleep(1)  # Wait for content to switch
                
                # Get the updated page source
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Find the research content
                items = soup.find_all('div', class_='item')
                if len(items) > research_tab_index:
                    research_content = items[research_tab_index].get_text().strip()
                    # Remove leading whitespace and special characters
                    research_content = re.sub(r'^[\s\u3000\xa0&nbsp;]+', '', research_content)
                    return research_content
            
        except Exception as e:
            logger.warning(f"Failed to extract from tabs: {str(e)}")
        
        return ""
        
    def extract_research_interests_static(self, soup) -> str:
        """Extract research interests from static HTML (fallback method)"""
        # Look for all div.item elements
        teacher_item = soup.find('div', class_='teacher_item')
        if teacher_item:
            items = teacher_item.find_all('div', class_='item')
            
            # Usually the second item contains research interests
            # (first is personal intro, second is research, third is publications)
            if len(items) >= 2:
                # Get the second item (index 1)
                research_item = items[1]
                research_text = research_item.get_text().strip()
                
                # Clean up the text - remove leading special characters and spaces
                research_text = re.sub(r'^[\s\u3000\xa0&nbsp;　]+', '', research_text)
                
                if research_text and len(research_text) > 10:
                    logger.info(f"Found research content in second item: {research_text[:100]}...")
                    return research_text
            
            # If not in expected position, search all items for research keywords
            for item in items:
                item_text = item.get_text().strip()
                # Clean up the text
                item_text = re.sub(r'^[\s\u3000\xa0&nbsp;　]+', '', item_text)
                
                # Check if this looks like research content (not too short, not publications)
                if len(item_text) > 50 and not any(year in item_text for year in ['2023', '2022', '2021', '2020', '2019']):
                    # Check for research-related keywords
                    if any(keyword in item_text for keyword in ['研究', '机制', '调控', '分子', '基因', '蛋白', '细胞', '生物', '发育', '生殖']):
                        logger.info(f"Found potential research content: {item_text[:100]}...")
                        return item_text
        
        return ""
        
    def clean_research_text(self, text: str) -> str:
        """Clean the extracted research text"""
        if not text:
            return ""
            
        # Remove HTML entities and special spaces
        text = text.replace('&nbsp;', ' ')
        text = text.replace('\u3000', ' ')
        text = text.replace('\xa0', ' ')
        text = text.replace('　', ' ')  # Full-width space
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove leading special characters and whitespace
        text = re.sub(r'^[\s　]+', '', text)
        
        # Clean up line breaks
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            line = line.strip()
            if line and not line.isspace():
                cleaned_lines.append(line)
                
        result = ' '.join(cleaned_lines) if len(cleaned_lines) <= 3 else '\n'.join(cleaned_lines)
        
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
                
                # Wait for the content to load
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "teacher_content"))
                    )
                except:
                    # If teacher_content not found, wait for body
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                
                # Additional wait for dynamic content
                time.sleep(2)
                
                # Get initial page source for name and email
                page_source = self.driver.page_source
                soup = BeautifulSoup(page_source, 'html.parser')
                
                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()
                
                # Extract basic information
                name = self.extract_name(soup)
                email = self.extract_email(soup)
                
                # Check for duplicate email
                if email and email in self.processed_emails:
                    logger.info(f"Skipping duplicate email: {email}")
                    return None
                
                # Try to extract research interests using tab clicking
                research_interests = self.extract_research_interests_from_tabs()
                
                # If tab clicking didn't work, try static extraction
                if not research_interests:
                    research_interests = self.extract_research_interests_static(soup)
                
                # Clean the text
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
        description='Scrape PKU Bio faculty research interests'
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
