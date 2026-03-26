#!/usr/bin/env python3
"""
Faculty Profile Scraper - Optimized for BIG CAS Faculty Pages
Handles faculty profiles from english.big.cas.cn
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


class BIGCASFacultyScraper:
    """Specialized scraper for BIG CAS faculty profiles"""
    
    # Research section keywords
    RESEARCH_START_KEYWORDS = ['Research Interests', 'Research Interest', 'Research Areas', 'Research Focus']
    
    # Stop keywords for research extraction - these mark the end of research section
    RESEARCH_STOP_KEYWORDS = [
        'Projects & Resources',
        'Projects &amp; Resources',
        'Selected Publications',
        'Publications',
        'Group Members',
        'Group&nbsp;Members',
        'Group Members:',
        'Awards',
        'Education',
        'Professional Experience',
        'Contact Information'
    ]
    
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
    
    def clean_email(self, email: str) -> str:
        """Clean and format email address"""
        if not email:
            return "Not found"
        
        # Replace AT with @
        email = email.replace(' AT ', '@')
        email = email.replace(' at ', '@')
        email = email.replace('AT', '@')
        email = email.replace('at', '@')
        
        # Remove extra spaces
        email = email.strip()
        
        # Validate email format
        if '@' in email and '.' in email:
            return email.lower()
        
        return "Not found"
    
    def extract_research_content(self, soup, start_element) -> str:
        """Extract research content starting from the research interests header"""
        if not start_element:
            return ""
        
        research_lines = []
        current = start_element.find_next_sibling()
        
        while current:
            # Check if we've hit a stop section
            text = current.get_text(strip=True)
            
            # Check for stop keywords
            is_stop = False
            for stop_keyword in self.RESEARCH_STOP_KEYWORDS:
                if stop_keyword in text:
                    # Check if it's a header (usually in strong or as a standalone short text)
                    if current.find('strong') or len(text) < 100:
                        is_stop = True
                        break
            
            if is_stop:
                break
            
            # Extract text from current element
            if text and not text.isspace():
                # Skip if it's just whitespace or nbsp
                if text != "&nbsp;" and text != "\xa0":
                    # Clean the text
                    cleaned_text = self.normalize_text(text)
                    if cleaned_text and len(cleaned_text) > 2:
                        research_lines.append(cleaned_text)
            
            # Move to next sibling
            current = current.find_next_sibling()
        
        return '\n'.join(research_lines)
    
    # ================ Name Extraction ================
    def extract_name(self, soup) -> Optional[str]:
        """Extract name from the page"""
        try:
            # Primary method: Look for <abbr id="xm">
            name_abbr = soup.find('abbr', id='xm')
            if name_abbr:
                name = self.normalize_text(name_abbr.get_text())
                if name:
                    return name
            
            # Fallback 1: Look for name in title or h1 tags
            h1_tags = soup.find_all('h1')
            for h1 in h1_tags:
                text = self.normalize_text(h1.get_text())
                # Check if it looks like a name (not too long, not a navigation item)
                if text and len(text) < 50 and not any(x in text.lower() for x in ['home', 'people', 'research']):
                    return text
            
            # Fallback 2: Look in page title
            title_tag = soup.find('title')
            if title_tag:
                title = self.normalize_text(title_tag.get_text())
                # Often formatted as "Name - Institution"
                if '-' in title:
                    name_part = title.split('-')[0].strip()
                    if len(name_part) < 50:
                        return name_part
                        
        except Exception as e:
            logger.debug(f"Error extracting name: {e}")
        
        return None
    
    # ================ Email Extraction ================
    def extract_email(self, soup) -> Optional[str]:
        """Extract email from the page"""
        try:
            # Primary method: Look for <abbr id="email">
            email_abbr = soup.find('abbr', id='email')
            if email_abbr:
                email = email_abbr.get_text(strip=True)
                return self.clean_email(email)
            
            # Fallback: Search for email patterns in the page
            # Look for text containing @ or AT
            text_content = soup.get_text()
            
            # Pattern 1: Standard email with @
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            match = re.search(email_pattern, text_content)
            if match:
                return match.group(0).lower()
            
            # Pattern 2: Email with AT instead of @
            at_pattern = r'[a-zA-Z0-9._%+-]+\s*(?:AT|at)\s*[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            match = re.search(at_pattern, text_content, re.IGNORECASE)
            if match:
                return self.clean_email(match.group(0))
            
            # Pattern 3: Look for Email: label
            email_label_pattern = r'(?:Email|E-mail|Mail)\s*[:：]\s*([a-zA-Z0-9._%+-]+(?:@|AT|at)[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            match = re.search(email_label_pattern, text_content, re.IGNORECASE)
            if match:
                return self.clean_email(match.group(1))
                
        except Exception as e:
            logger.debug(f"Error extracting email: {e}")
        
        return None
    
    # ================ Research Extraction ================
    def extract_research(self, soup) -> str:
        """Extract research interests from the page"""
        try:
            # Method 1: Look for Research Interests section
            for keyword in self.RESEARCH_START_KEYWORDS:
                # Search for the keyword in various contexts
                
                # Check in strong tags
                for strong in soup.find_all('strong'):
                    if keyword.lower() in strong.get_text().lower():
                        # Find the parent paragraph
                        parent = strong.find_parent(['p', 'div'])
                        if parent:
                            research_content = self.extract_research_content(soup, parent)
                            if research_content and len(research_content) > 10:
                                return self.clean_research_text(research_content)
                
                # Check in paragraphs directly
                for p in soup.find_all('p'):
                    text = p.get_text(strip=True)
                    if keyword.lower() in text.lower() and len(text) < 100:  # Likely a header
                        research_content = self.extract_research_content(soup, p)
                        if research_content and len(research_content) > 10:
                            return self.clean_research_text(research_content)
            
            # Method 2: If no research section found, look for content in people-info div
            people_info = soup.find('div', id='people-info')
            if people_info:
                # Get all paragraphs after skipping navigation and headers
                paragraphs = []
                in_content = False
                
                for element in people_info.find_all(['p', 'div', 'ul']):
                    text = element.get_text(strip=True)
                    
                    # Skip empty elements
                    if not text or text == "&nbsp;":
                        continue
                    
                    # Check if we've reached a main content area
                    if not in_content:
                        # Look for signs we're in the main content
                        if any(kw in text.lower() for kw in ['research', 'work', 'focus', 'interest', 'study']):
                            in_content = True
                    
                    if in_content:
                        # Stop at obvious end sections
                        if any(stop in text for stop in ['Publications', 'Contact', 'Copyright']):
                            break
                        
                        # Add non-header content
                        if len(text) > 20:  # Not just a short header
                            paragraphs.append(text)
                
                if paragraphs:
                    combined = '\n'.join(paragraphs[:10])  # Limit to first 10 paragraphs
                    return self.clean_research_text(combined)
            
            # Method 3: Fallback - get main content from the page
            main_content = soup.find('div', class_='main-content') or soup.find('div', id='content')
            if main_content:
                # Extract text, filtering out navigation and headers
                text = main_content.get_text(separator='\n', strip=True)
                lines = [line.strip() for line in text.split('\n') if line.strip()]
                
                # Filter lines
                content_lines = []
                for line in lines:
                    # Skip short lines (likely headers/navigation)
                    if len(line) < 20:
                        continue
                    # Skip lines with navigation keywords
                    if any(kw in line.lower() for kw in ['home', 'sitemap', 'contact us', 'copyright']):
                        continue
                    content_lines.append(line)
                
                if content_lines:
                    return self.clean_research_text('\n'.join(content_lines[:20]))
                    
        except Exception as e:
            logger.debug(f"Error extracting research: {e}")
        
        return ""
    
    def clean_research_text(self, text: str) -> str:
        """Clean and format research text"""
        if not text:
            return ""
        
        # Remove any remaining HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\s*\n\s*', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove leading numbers/bullets from lines
        text = re.sub(r'^[\d]+[\.、)]\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[•·▪▫◦‣⁃]\s*', '', text, flags=re.MULTILINE)
        
        # Truncate if needed
        if self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        
        return text.strip()
    
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
        options.add_argument('--lang=en-US')
        
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
                
                # Extract information
                name = self.extract_name(soup) or "Unknown"
                email = self.extract_email(soup) or "Not found"
                research = self.extract_research(soup) or "Not found"
                
                # Final validation
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
        description='BIG CAS Faculty Profile Scraper - Extract name, email, and research interests'
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
    scraper = BIGCASFacultyScraper(args)
    scraper.run()


if __name__ == '__main__':
    main()