#!/usr/bin/env python3
"""
Faculty Profile Research Interest Extractor
Extracts research interests from faculty profile pages (Selenium + requests/BS4 fallback)
"""

import argparse
import logging
import random
import re
import sys
import time
import warnings
from pathlib import Path
from typing import Dict, Optional, Set, Tuple
from urllib.parse import urljoin, urlparse

import requests
import urllib3
from bs4 import BeautifulSoup, NavigableString, Tag
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Suppress SSL warnings for fallback mode
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore", message="Unverified HTTPS request")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ProfileExtractor:
    """Extract research interests from faculty profile pages"""
    
    # Research interest heading patterns (case-insensitive)
    RESEARCH_HEADINGS = [
        # Chinese
        r'研究方向', r'研究兴趣', r'主要研究方向', r'研究方向与内容', r'研究领域',
        # English
        r'research\s*interest', r'research\s*focus', r'research\s*area',
        r'research\s*direction', r'research\s*field', r'research\s*topic',
        r'current\s*research', r'research\s*overview'
    ]
    
    # Stop extraction patterns (indicates non-research content)
    STOP_PATTERNS = [
        # Chinese
        r'论文', r'发表', r'代表性论文', r'近五年', r'主要成果', r'出版', 
        r'著作', r'项目', r'研究生导师', r'教育背景', r'工作经历', r'简历', 
        r'个人简历', r'获奖', r'荣誉', r'学术兼职',
        # English
        r'publication', r'paper', r'selected\s*publication', r'representative\s*paper',
        r'education', r'work\s*experience', r'employment', r'cv', r'resume',
        r'book', r'project', r'grant', r'award', r'honor', r'supervision',
        r'professional\s*experience', r'teaching', r'course', r'patent'
    ]
    
    # Content keywords for fallback heuristics
    CONTENT_KEYWORDS = ['研究', 'research', 'interest', 'focus', '方向', '领域', 
                        'study', 'investigate', 'explore', 'develop']
    
    def __init__(self, args):
        self.args = args
        self.driver = None
        self.session = None
        self.processed_urls = set()
        self.processed_emails = set()
        
    def setup_driver(self):
        """Initialize Selenium WebDriver"""
        try:
            options = Options()
            if self.args.headless:
                options.add_argument('--headless')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
            options.add_argument('--window-size=1920,1080')
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
            # Handle SSL errors
            options.add_argument('--ignore-certificate-errors')
            options.add_argument('--ignore-ssl-errors')
            
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(30)
            logger.info("Selenium WebDriver initialized")
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            self.driver = None
            
    def setup_session(self):
        """Initialize requests session for fallback"""
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        # Disable SSL verification for problematic sites
        self.session.verify = False
        
    def fetch_page_selenium(self, url: str) -> Optional[str]:
        """Fetch page using Selenium"""
        if not self.driver:
            return None
            
        try:
            self.driver.get(url)
            # Wait for main content to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(1)  # Additional wait for dynamic content
            return self.driver.page_source
        except (TimeoutException, WebDriverException) as e:
            logger.warning(f"Selenium failed for {url}: {e}")
            return None
            
    def fetch_page_requests(self, url: str) -> Optional[str]:
        """Fetch page using requests (fallback)"""
        if not self.session:
            self.setup_session()
            
        try:
            response = self.session.get(url, timeout=15, verify=False)
            response.raise_for_status()
            # Handle encoding
            response.encoding = response.apparent_encoding or 'utf-8'
            return response.text
        except Exception as e:
            logger.warning(f"Requests failed for {url}: {e}")
            return None
            
    def extract_name(self, soup: BeautifulSoup) -> str:
        """Extract faculty name from page"""
        # Strategy 1: Look for prominent headers
        for tag in ['h1', 'h2', 'h3']:
            headers = soup.find_all(tag)
            for header in headers[:3]:  # Check first few headers
                text = self.clean_text(header.get_text())
                # Simple heuristic: name-like pattern
                if text and len(text) < 50 and not any(c in text.lower() for c in ['department', '系', '学院']):
                    # For the sample, look for centered content
                    if header.find_parent('td', {'align': 'center'}):
                        return text
                    # Or if it's early in the page
                    if headers.index(header) == 0:
                        return text
                        
        # Strategy 2: Look for name class/id
        for selector in ['.name', '#name', '.faculty-name', '.profile-name']:
            elem = soup.select_one(selector)
            if elem:
                return self.clean_text(elem.get_text())
                
        return "Unknown"
        
    def extract_email(self, soup: BeautifulSoup) -> str:
        """Extract email address from page"""
        email_pattern = re.compile(r'[\w\.-]+@[\w\.-]+\.\w+', re.IGNORECASE)
        
        # Search entire page text
        page_text = soup.get_text()
        emails = email_pattern.findall(page_text)
        
        # Prefer institutional emails
        for email in emails:
            if any(domain in email.lower() for domain in 
                   ['edu.cn', 'ac.cn', 'edu', 'university']):
                return email.lower()
                
        # Return first email if found
        return emails[0].lower() if emails else ""
        
    def find_research_section(self, soup: BeautifulSoup) -> Optional[Tag]:
        """Find the research interest section heading"""
        # Compile patterns
        patterns = [re.compile(p, re.IGNORECASE) for p in self.RESEARCH_HEADINGS]
        
        # Strategy 1: Look for strong/bold text with keywords
        for strong in soup.find_all(['strong', 'b']):
            text = self.clean_text(strong.get_text())
            if any(p.search(text) for p in patterns):
                return strong.parent if strong.parent.name == 'p' else strong
                
        # Strategy 2: Look for paragraph with keywords (even if not bold)
        for p in soup.find_all('p'):
            text = self.clean_text(p.get_text())
            if any(p.search(text) for p in patterns):
                # Check if it's likely a heading (short text)
                if len(text) < 100:
                    return p
                    
        # Strategy 3: Look in headers
        for level in ['h1', 'h2', 'h3', 'h4']:
            for header in soup.find_all(level):
                text = self.clean_text(header.get_text())
                if any(p.search(text) for p in patterns):
                    return header
                    
        return None
        
    def should_stop_extraction(self, element: Tag) -> bool:
        """Check if we should stop extracting (hit non-research content)"""
        if not element:
            return True
            
        text = self.clean_text(element.get_text()).lower()
        
        # Check stop patterns
        stop_patterns = [re.compile(p, re.IGNORECASE) for p in self.STOP_PATTERNS]
        if any(p.search(text) for p in stop_patterns):
            # Special case: might be a heading we should stop at
            if element.name in ['p', 'div'] and len(text) < 100:
                return True
            # Or if it's actually a heading tag
            if element.name in ['h1', 'h2', 'h3', 'h4', 'strong', 'b']:
                return True
                
        # Check for year patterns (likely publication list)
        year_pattern = re.compile(r'^\s*\d{4}[\.）KATEX_INLINE_CLOSE]')
        if year_pattern.match(text):
            return True
            
        return False
        
    def extract_research_content(self, start_element: Tag) -> str:
        """Extract research interest content starting from heading"""
        content_parts = []
        current = start_element
        
        # Move to next sibling after heading
        current = current.find_next_sibling()
        
        while current:
            # Check if we should stop
            if self.should_stop_extraction(current):
                break
                
            # Extract text from current element
            if isinstance(current, Tag):
                text = self.clean_text(current.get_text())
                if text and len(text) > 10:  # Skip very short snippets
                    content_parts.append(text)
                    
            # Move to next sibling
            current = current.find_next_sibling()
            
            # Safety limit
            if len(content_parts) > 20:  # Max 20 paragraphs
                break
                
        return ' '.join(content_parts)
        
    def extract_research_fallback(self, soup: BeautifulSoup) -> str:
        """Fallback extraction using content heuristics"""
        # Find paragraphs with research keywords
        candidates = []
        
        for p in soup.find_all(['p', 'div']):
            text = self.clean_text(p.get_text())
            if not text or len(text) < 50:
                continue
                
            # Score based on keyword presence
            score = sum(1 for kw in self.CONTENT_KEYWORDS if kw.lower() in text.lower())
            if score > 0:
                # Penalize if contains stop words
                stop_score = sum(1 for pattern in self.STOP_PATTERNS 
                               if re.search(pattern, text, re.IGNORECASE))
                if stop_score == 0:
                    candidates.append((score, text))
                    
        # Sort by score and concatenate top candidates
        candidates.sort(key=lambda x: x[0], reverse=True)
        research_texts = [text for _, text in candidates[:3]]
        
        return ' '.join(research_texts)
        
    def clean_text(self, text: str) -> str:
        """Clean and normalize text"""
        if not text:
            return ""
            
        # Remove HTML entities
        text = BeautifulSoup(text, 'html.parser').get_text()
        
        # Normalize whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        return text
        
    def truncate_text(self, text: str) -> str:
        """Truncate text to specified limit"""
        if len(text) <= self.args.truncate:
            return text
        return text[:self.args.truncate] + ' [...]'
        
    def process_profile(self, url: str) -> Dict[str, str]:
        """Process a single faculty profile"""
        result = {
            'name': 'Unknown',
            'email': '',
            'research_interest': '',
            'profile_link': url
        }
        
        # Try Selenium first
        html = self.fetch_page_selenium(url)
        
        # Fallback to requests if Selenium fails
        if not html:
            logger.info(f"Falling back to requests for {url}")
            html = self.fetch_page_requests(url)
            
        if not html:
            logger.error(f"Failed to fetch {url}")
            result['research_interest'] = '<FAILED: Could not fetch page>'
            return result
            
        # Parse HTML
        soup = BeautifulSoup(html, 'html.parser')
        
        # Extract name and email
        result['name'] = self.extract_name(soup)
        result['email'] = self.extract_email(soup)
        
        # Extract research interest
        research_section = self.find_research_section(soup)
        
        if research_section:
            research_text = self.extract_research_content(research_section)
        else:
            logger.warning(f"No research section found for {url}, using fallback")
            research_text = self.extract_research_fallback(soup)
            
        # Clean and truncate
        research_text = self.clean_text(research_text)
        research_text = self.truncate_text(research_text)
        
        result['research_interest'] = research_text or '<No research interest found>'
        
        return result
        
    def run(self):
        """Main execution"""
        # Setup
        self.setup_driver()
        self.setup_session()
        
        # Read input URLs
        input_path = Path(self.args.input_file)
        if not input_path.exists():
            logger.error(f"Input file not found: {input_path}")
            sys.exit(1)
            
        urls = input_path.read_text(encoding='utf-8').strip().split('\n')
        urls = [u.strip() for u in urls if u.strip()]
        
        logger.info(f"Processing {len(urls)} URLs")
        
        # Process profiles
        output_path = Path(self.args.output_file)
        processed = 0
        
        with open(output_path, 'w', encoding='utf-8') as f:
            for i, url in enumerate(urls, 1):
                # Check limits
                if self.args.max_profiles and processed >= self.args.max_profiles:
                    logger.info(f"Reached max profile limit ({self.args.max_profiles})")
                    break
                    
                # Check duplicates
                normalized_url = url.lower().strip()
                if normalized_url in self.processed_urls:
                    logger.info(f"Skipping duplicate URL: {url}")
                    continue
                    
                logger.info(f"Processing {i}/{len(urls)}: {url}")
                
                # Random delay
                if processed > 0:
                    delay = random.uniform(self.args.delay_min, self.args.delay_max)
                    time.sleep(delay)
                    
                # Process with retries
                for attempt in range(self.args.retries):
                    try:
                        result = self.process_profile(url)
                        
                        # Check email duplicate
                        if result['email'] and result['email'] in self.processed_emails:
                            logger.info(f"Skipping duplicate email: {result['email']}")
                            break
                            
                        # Write result
                        f.write(f"Name: {result['name']}\n")
                        f.write(f"Email: {result['email']}\n")
                        f.write(f"Research interest: {result['research_interest']}\n")
                        f.write(f"Profile link: {result['profile_link']}\n")
                        f.write("---\n\n")
                        f.flush()
                        
                        # Track processed
                        self.processed_urls.add(normalized_url)
                        if result['email']:
                            self.processed_emails.add(result['email'])
                        processed += 1
                        
                        logger.info(f"Successfully processed: {result['name']}")
                        break
                        
                    except Exception as e:
                        logger.error(f"Attempt {attempt+1} failed for {url}: {e}")
                        if attempt == self.args.retries - 1:
                            # Write failure entry
                            f.write(f"Name: Unknown\n")
                            f.write(f"Email: \n")
                            f.write(f"Research interest: <FAILED: {str(e)}>\n")
                            f.write(f"Profile link: {url}\n")
                            f.write("---\n\n")
                            f.flush()
                            
        # Cleanup
        if self.driver:
            self.driver.quit()
            
        logger.info(f"Completed. Processed {processed} profiles to {output_path}")
        

def main():
    parser = argparse.ArgumentParser(
        description='Extract faculty research interests from profile pages'
    )
    parser.add_argument('--input-file', '-i', default='urls.txt',
                       help='Input file with URLs (one per line)')
    parser.add_argument('--output-file', '-o', default='output.txt',
                       help='Output file for extracted data')
    parser.add_argument('--headless', action='store_true',
                       help='Run browser in headless mode')
    parser.add_argument('--delay-min', type=float, default=0.5,
                       help='Minimum delay between requests (seconds)')
    parser.add_argument('--delay-max', type=float, default=2.0,
                       help='Maximum delay between requests (seconds)')
    parser.add_argument('--max-profiles', type=int, default=None,
                       help='Maximum number of profiles to process')
    parser.add_argument('--retries', type=int, default=2,
                       help='Number of retry attempts per URL')
    parser.add_argument('--truncate', type=int, default=4000,
                       help='Maximum characters for research interest')
    
    args = parser.parse_args()
    
    extractor = ProfileExtractor(args)
    extractor.run()
    

if __name__ == '__main__':
    main()