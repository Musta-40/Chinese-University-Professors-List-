#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper - LZU Specific Version with Groq AI
Uses selenium-stealth to bypass bot detection and solve loading issues.
"""

import os
import argparse
import logging
import random
import re
import time
from pathlib import Path
from typing import Dict, Optional, Set

# --- Key Change: Use standard Selenium with stealth patching ---
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

try:
    from selenium_stealth import stealth
except ImportError:
    print("Error: selenium-stealth is not installed.")
    print("Please install it with: pip install selenium-stealth")
    exit(1)
# --- End Key Change ---

from bs4 import BeautifulSoup

# Load .env for API keys
from dotenv import load_dotenv
load_dotenv()

# Groq API
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("Warning: Groq not installed. Install with: pip install groq")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class LZUFacultyProfileScraper:
    """Scraper specifically for LZU faculty profiles"""
    
    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls: Set[str] = set()
        self.processed_emails: Set[str] = set()
        
        # Initialize Groq client
        self.groq_client = None
        if GROQ_AVAILABLE and args.groq_api_key:
            self.groq_client = Groq(api_key=args.groq_api_key)
            logger.info(f"Groq AI initialized with model: {args.groq_model}")
        
    def setup_driver(self):
        """Initialize a standard Selenium WebDriver and apply stealth patches."""
        options = Options()
        if self.args.headless:
            options.add_argument('--headless=new')
        
        # Options to make the browser look more human
        options.add_argument("start-maximized")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        logger.info("Setting up WebDriver with selenium-stealth...")
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        
        # --- Key Change: Apply stealth patches ---
        stealth(self.driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
                )
        # --- End Key Change ---
        
        self.driver.set_page_load_timeout(45)
        self.driver.implicitly_wait(10)
        logger.info("Driver setup complete.")
            
    def close_driver(self):
        """Close WebDriver"""
        if self.driver:
            self.driver.quit()
            
    def random_delay(self):
        """Add random delay between requests"""
        delay = random.uniform(self.args.delay_min, self.args.delay_max)
        time.sleep(delay)

    def wait_and_get_content(self, url: str) -> Optional[str]:
        """Load the page and wait for a key element to appear."""
        try:
            self.driver.get(url)
            # This wait is crucial. It waits for the main content container to be present in the HTML.
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, "teacher-detail"))
            )
            logger.info("Page content container found. Page loaded successfully.")
            # Add a small extra delay for any final scripts to render content inside the container
            time.sleep(3)
            return self.driver.page_source
        except Exception as e:
            logger.error(f"Failed to load content for {url}. The page might be blocked or structured differently. Error: {e}")
            # Save a screenshot for debugging if the page fails to load
            if self.args.debug:
                screenshot_path = f"error_load_{int(time.time())}.png"
                self.driver.save_screenshot(screenshot_path)
                logger.info(f"Saved error screenshot to {screenshot_path}")
            return None

    def extract_with_groq(self, page_text: str) -> Dict[str, str]:
        """Use Groq AI to extract all information"""
        if not self.groq_client or not page_text or len(page_text) < 100:
            return {}
            
        try:
            prompt = f"""
            From the following faculty webpage content, extract the professor's name, email, and research interests.

            Webpage Content:
            {page_text[:8000]}

            Provide the output in this exact format:
            Name: [Professor's Name]
            Email: [Professor's Email]
            Research Interests: [Research interests, separated by semicolons if multiple]

            If a piece of information is not found, write "Not found" for that field.
            """
            
            response = self.groq_client.chat.completions.create(
                model=self.args.groq_model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500,
                temperature=0.1
            )
            
            result_text = response.choices[0].message.content.strip()
            result = {}
            
            for line in result_text.split('\n'):
                if ':' in line:
                    key, value = line.split(':', 1)
                    key = key.strip()
                    value = value.strip()
                    if key == 'Name' and value.lower() != 'not found':
                        result['name'] = value
                    elif key == 'Email' and value.lower() != 'not found':
                        result['email'] = value
                    elif key == 'Research Interests' and value.lower() != 'not found':
                        result['research'] = value
                        
            return result
            
        except Exception as e:
            logger.error(f"Groq extraction failed: {str(e)}")
            return {}
            
    def scrape_profile(self, url: str) -> Optional[Dict[str, str]]:
        """Scrape a single faculty profile"""
        normalized_url = url.strip()
        if normalized_url in self.processed_urls:
            logger.info(f"Skipping duplicate URL: {url}")
            return None
            
        logger.info(f"Processing: {url}")
        
        page_source = self.wait_and_get_content(url)
        
        if not page_source:
            return {
                'name': 'Unknown',
                'email': 'Not found',
                'research_interest': '<ERROR: Page failed to load>',
                'profile_link': url
            }
        
        soup = BeautifulSoup(page_source, 'html.parser')
        page_text = soup.get_text(separator=' ', strip=True)

        logger.info("Using Groq AI to extract information...")
        groq_result = self.extract_with_groq(page_text)

        name = groq_result.get('name', 'Unknown')
        email = groq_result.get('email', 'Not found')
        research = groq_result.get('research', 'Not found')
        
        if email != 'Not found' and email in self.processed_emails:
            logger.info(f"Skipping duplicate email: {email}")
            return None
        
        if research != 'Not found' and self.args.truncate > 0 and len(research) > self.args.truncate:
            research = research[:self.args.truncate] + '...'
        
        self.processed_urls.add(normalized_url)
        if email != 'Not found':
            self.processed_emails.add(email)
            
        return {'name': name, 'email': email, 'research_interest': research, 'profile_link': url}
            
    def write_profile(self, profile: Dict[str, str], output_file: Path):
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"Name: {profile['name']}\n")
            f.write(f"Email: {profile['email']}\n")
            f.write(f"Research interest: {profile['research_interest']}\n")
            f.write(f"Profile link: {profile['profile_link']}\n")
            f.write("---\n\n")
            
    def run(self):
        input_file = Path(self.args.input_file)
        if not input_file.exists():
            logger.error(f"Input file not found: {input_file}")
            return
            
        with open(input_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip() and line.startswith('http')]
            
        logger.info(f"Found {len(urls)} URLs to process")
        
        output_file = Path(self.args.output_file)
        if output_file.exists() and not self.args.append:
            output_file.unlink()
            
        self.setup_driver()
        
        try:
            processed_count = 0
            for i, url in enumerate(urls):
                if self.args.max_profiles > 0 and processed_count >= self.args.max_profiles:
                    logger.info(f"Reached maximum profile limit: {self.args.max_profiles}")
                    break
                    
                profile = self.scrape_profile(url)
                
                if profile:
                    self.write_profile(profile, output_file)
                    processed_count += 1
                    logger.info(f"Processed {processed_count}/{len(urls)}: {profile['name']}")
                    
                if i < len(urls) - 1:
                    self.random_delay()
                    
        finally:
            self.close_driver()
            
        logger.info(f"Completed! Processed {processed_count} profiles")
        

def main():
    parser = argparse.ArgumentParser(
        description='Scrape LZU faculty profiles with robust page loading'
    )
    
    parser.add_argument('--input-file', default='urls.txt')
    parser.add_argument('--output-file', default='output.txt')
    parser.add_argument('--groq-api-key', default=os.getenv('GROQ_API_KEY'))
    parser.add_argument('--groq-model', default='llama-3.1-8b-instant')
    parser.add_argument('--headless', action='store_true')
    parser.add_argument('--debug', action='store_true', help='Save error screenshots for debugging')
    parser.add_argument('--delay-min', type=float, default=2.0)
    parser.add_argument('--delay-max', type=float, default=4.0)
    parser.add_argument('--max-profiles', type=int, default=0)
    parser.add_argument('--truncate', type=int, default=4000)
    parser.add_argument('--append', action='store_true')
    
    args = parser.parse_args()
    
    if not args.groq_api_key:
        print("Error: Groq API key is required. Set it via --groq-api-key or GROQ_API_KEY environment variable.")
        return
    
    scraper = LZUFacultyProfileScraper(args)
    scraper.run()
    
if __name__ == '__main__':
    main()