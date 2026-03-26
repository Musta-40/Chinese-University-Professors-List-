#!/usr/bin/env python3
"""
Faculty Profile Scraper for GMIS5 System (CPU University Format)
Designed for consistent HTML structure with unique IDs and classes
Clean extraction using CSS selectors - no complex parsing needed
"""

import os
import re
import time
import json
import logging
import random
from pathlib import Path
from typing import Dict, Optional, List
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraper_gmis5.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class GMIS5ProfileScraper:
    """Scraper for GMIS5 faculty profile system with standardized IDs"""
    
    def __init__(self, use_selenium=True, headless=True):
        """
        Initialize the scraper
        
        Args:
            use_selenium: Whether to use Selenium (for JS-rendered pages)
            headless: Whether to run browser in headless mode
        """
        self.use_selenium = use_selenium
        self.driver = None
        
        if use_selenium:
            self.setup_driver(headless)
        
        # Sections to avoid (misleading content)
        self.avoid_sections = [
            "个人简介",  # Personal introduction - verbose and inconsistent
            "科研项目",  # Research projects
            "发表论文",  # Published papers
            "获奖成果",  # Awards
            "教材专著"   # Textbooks/Monographs
        ]
        
        # Statistics
        self.stats = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'missing_name': 0,
            'missing_email': 0,
            'missing_research': 0
        }
    
    def setup_driver(self, headless=True):
        """Setup Selenium Chrome driver"""
        options = Options()
        if headless:
            options.add_argument('--headless=new')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--lang=zh-CN,zh;q=0.9')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        # Additional options for stability
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(10)
    
    def close_driver(self):
        """Close Selenium driver"""
        if self.driver:
            self.driver.quit()
    
    def get_page_content(self, url: str) -> Optional[str]:
        """
        Get page HTML content
        
        Args:
            url: URL to fetch
            
        Returns:
            HTML content or None if failed
        """
        try:
            if self.use_selenium:
                self.driver.get(url)
                # Wait for key elements to load
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CLASS_NAME, "jsxm"))
                    )
                except:
                    # If jsxm not found, wait for body at least
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.TAG_NAME, "body"))
                    )
                time.sleep(1)  # Additional wait for dynamic content
                return self.driver.page_source
            else:
                response = requests.get(url, timeout=10, headers={
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                })
                response.encoding = response.apparent_encoding or 'utf-8'
                return response.text
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {str(e)}")
            return None
    
    def extract_name(self, soup: BeautifulSoup) -> str:
        """
        Extract faculty name from the page
        
        Primary: <div class="jsxm">颜天华</div>
        """
        name = ""
        
        # Method 1: Try <div class="jsxm"> (most reliable for GMIS5)
        name_div = soup.find('div', class_='jsxm')
        if name_div:
            name = name_div.get_text(strip=True)
            logger.debug(f"Found name in div.jsxm: {name}")
            return name if name else "Unknown"
        
        # Method 2: Fallback to title tag
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Try to extract name from title (might be formatted as "Name - Department" or similar)
            if '-' in title_text:
                potential_name = title_text.split('-')[0].strip()
                # Check if it looks like a name (Chinese characters or reasonable length)
                if potential_name and (re.search(r'[\u4e00-\u9fff]', potential_name) or len(potential_name) < 20):
                    name = potential_name
                    logger.debug(f"Found name in title: {name}")
                    return name
        
        # Method 3: Look for name pattern in meta tags
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            content = meta_desc.get('content').strip()
            # Extract potential name from beginning
            name_match = re.match(r'^([\u4e00-\u9fff]{2,5})', content)
            if name_match:
                name = name_match.group(1)
                logger.debug(f"Found name in meta description: {name}")
                return name
        
        # Method 4: Look for any heading with teacher/professor info
        for tag in soup.find_all(['h1', 'h2', 'h3']):
            text = tag.get_text(strip=True)
            # Check if it contains Chinese name pattern
            name_match = re.search(r'([\u4e00-\u9fff]{2,5})\s*(?:教授|副教授|讲师|助教|博士|硕士)?', text)
            if name_match:
                name = name_match.group(1)
                logger.debug(f"Found name in heading: {name}")
                return name
        
        return "Unknown"
    
    def extract_email(self, soup: BeautifulSoup) -> str:
        """
        Extract email address from the page
        
        Primary: <div class="emailinfo">1020050806@cpu.edu.cn</div>
        """
        email = ""
        
        # Method 1: Try <div class="emailinfo"> (most reliable for GMIS5)
        email_div = soup.find('div', class_='emailinfo')
        if email_div:
            email = email_div.get_text(strip=True)
            if '@' in email:
                logger.debug(f"Found email in div.emailinfo: {email}")
                return email
        
        # Method 2: Look for email patterns in common locations
        # Search for divs or spans that might contain email
        for tag in soup.find_all(['div', 'span', 'p']):
            text = tag.get_text(strip=True)
            # Look for email pattern
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            if email_match:
                candidate_email = email_match.group(0)
                # Filter out common non-personal emails
                if not any(x in candidate_email.lower() for x in ['webmaster', 'admin', 'info', 'support', 'example']):
                    # Check if this is in a reasonable context (not in a long paragraph)
                    if len(text) < 100:  # Likely a dedicated email field
                        email = candidate_email
                        logger.debug(f"Found email via pattern search: {email}")
                        return email
        
        # Method 3: Search specifically after email labels
        page_text = soup.get_text()
        email_patterns = [
            r'[Ee]-?mail[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'邮箱[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'电子邮[件箱][：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        ]
        
        for pattern in email_patterns:
            match = re.search(pattern, page_text)
            if match:
                email = match.group(1)
                logger.debug(f"Found email with label pattern: {email}")
                return email
        
        return "Not found"
    
    def extract_research_interests(self, soup: BeautifulSoup) -> str:
        """
        Extract research interests/direction
        
        Primary: <div id="txtyjfx" class="d">肿瘤药理学，神经药理学，心脑血管药理学</div>
        """
        research = ""
        
        # Method 1: Try <div id="txtyjfx"> (most reliable for GMIS5)
        research_div = soup.find('div', id='txtyjfx')
        if research_div:
            research = research_div.get_text(strip=True)
            if research:
                logger.debug(f"Found research in div#txtyjfx: {research}")
                return self.clean_research_text(research)
        
        # Method 2: Try alternate IDs that might be used
        alternate_ids = ['txtyjfx', 'research-direction', 'yjfx', 'study-direction', 'research_direction']
        for alt_id in alternate_ids:
            research_div = soup.find('div', id=alt_id)
            if research_div:
                research = research_div.get_text(strip=True)
                if research:
                    logger.debug(f"Found research in div#{alt_id}: {research}")
                    return self.clean_research_text(research)
        
        # Method 3: Look for content after "研究方向" heading
        # Find h2 or h3 with "研究方向"
        for heading_tag in ['h2', 'h3', 'h4']:
            heading = soup.find(heading_tag, string=re.compile(r'研究方向|研究领域|研究兴趣|Research\s*(Direction|Interest|Area)', re.I))
            if heading:
                # Get the next sibling element
                next_elem = heading.find_next_sibling()
                if next_elem and next_elem.name in ['div', 'p', 'ul']:
                    research = next_elem.get_text(strip=True)
                    if research and not any(avoid in research for avoid in self.avoid_sections):
                        logger.debug(f"Found research after heading: {research}")
                        return self.clean_research_text(research)
        
        # Method 4: Look for a div with class that might contain research
        research_classes = ['research', 'research-content', 'yjfx', 'd']
        for class_name in research_classes:
            research_div = soup.find('div', class_=class_name)
            if research_div:
                # Check if it's not in an avoided section
                parent_text = research_div.find_parent().get_text() if research_div.find_parent() else ""
                if not any(avoid in parent_text[:100] for avoid in self.avoid_sections):
                    research = research_div.get_text(strip=True)
                    # Make sure it's not too long (avoid personal introduction sections)
                    if research and len(research) < 500:
                        logger.debug(f"Found research in div.{class_name}: {research}")
                        return self.clean_research_text(research)
        
        # Method 5: Last resort - try to extract from structured content
        # Look for lists of research areas
        for ul in soup.find_all('ul'):
            prev_elem = ul.find_previous_sibling()
            if prev_elem and '研究' in prev_elem.get_text():
                items = []
                for li in ul.find_all('li'):
                    item_text = li.get_text(strip=True)
                    if item_text and len(item_text) < 100:
                        items.append(item_text)
                if items:
                    research = '; '.join(items)
                    logger.debug(f"Found research in list format: {research}")
                    return self.clean_research_text(research)
        
        # Important: Avoid extracting from 个人简介 (personal introduction)
        # as it's verbose and inconsistent
        
        return "Not found"
    
    def clean_research_text(self, text: str) -> str:
        """
        Clean up research interest text
        
        Args:
            text: Raw research text
            
        Returns:
            Cleaned text
        """
        if not text:
            return ""
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove HTML entities
        text = re.sub(r'&[^;]+;', ' ', text)
        
        # Remove any HTML tags (shouldn't be any, but just in case)
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove numbering patterns
        text = re.sub(r'^\d+[\.、]\s*', '', text)
        text = re.sub(r'[（(]\d+[)）]', '', text)
        
        # Clean up punctuation
        text = re.sub(r'[,，]\s*$', '', text)  # Remove trailing commas
        text = re.sub(r'^[,，]\s*', '', text)  # Remove leading commas
        text = re.sub(r'[；;]+', '；', text)   # Normalize semicolons
        text = re.sub(r'\s*[；;]\s*', '；', text)  # Clean spaces around semicolons
        
        # Remove "None" or "无" if that's all there is
        if text.strip() in ['None', '无', 'N/A', 'NA', '-']:
            return "Not found"
        
        return text.strip()
    
    def scrape_profile(self, url: str) -> Dict[str, str]:
        """
        Scrape a single faculty profile
        
        Args:
            url: Profile URL
            
        Returns:
            Dictionary with name, email, research_interest, and profile_link
        """
        logger.info(f"Scraping: {url}")
        
        # Initialize result
        result = {
            'name': 'Unknown',
            'email': 'Not found',
            'research_interest': 'Not found',
            'profile_link': url
        }
        
        try:
            # Get page content
            html_content = self.get_page_content(url)
            if not html_content:
                logger.error(f"Failed to get content for {url}")
                return result
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Extract information
            result['name'] = self.extract_name(soup)
            result['email'] = self.extract_email(soup)
            result['research_interest'] = self.extract_research_interests(soup)
            
            # Update statistics
            if result['name'] == 'Unknown':
                self.stats['missing_name'] += 1
            if result['email'] == 'Not found':
                self.stats['missing_email'] += 1
            if result['research_interest'] == 'Not found':
                self.stats['missing_research'] += 1
            
            # Log results
            logger.info(f"Successfully scraped: {result['name']}")
            logger.debug(f"  Email: {result['email']}")
            research_preview = result['research_interest'][:100] + "..." if len(result['research_interest']) > 100 else result['research_interest']
            logger.debug(f"  Research: {research_preview}")
            
            # Mark as successful if we got at least name or email
            if result['name'] != 'Unknown' or result['email'] != 'Not found':
                self.stats['successful'] += 1
            else:
                self.stats['failed'] += 1
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {str(e)}")
            self.stats['failed'] += 1
        
        return result
    
    def scrape_batch(self, urls: List[str], output_file: str = 'output.txt', 
                     json_output: bool = True, delay_range: tuple = (1, 3)):
        """
        Scrape multiple URLs in batch
        
        Args:
            urls: List of URLs to scrape
            output_file: Output file path
            json_output: Whether to also save as JSON
            delay_range: (min, max) delay in seconds between requests
        """
        results = []
        self.stats['total'] = len(urls)
        
        # Reset counters
        self.stats['successful'] = 0
        self.stats['failed'] = 0
        self.stats['missing_name'] = 0
        self.stats['missing_email'] = 0
        self.stats['missing_research'] = 0
        
        # Open output file for writing
        with open(output_file, 'w', encoding='utf-8') as f:
            for i, url in enumerate(urls, 1):
                logger.info(f"Processing {i}/{len(urls)}")
                
                # Scrape profile
                profile = self.scrape_profile(url)
                results.append(profile)
                
                # Write to text file
                f.write(f"Name: {profile['name']}\n")
                f.write(f"Email: {profile['email']}\n")
                f.write(f"Research interest: {profile['research_interest']}\n")
                f.write(f"Profile link: {profile['profile_link']}\n")
                f.write("---\n\n")
                f.flush()  # Ensure data is written immediately
                
                # Random delay between requests
                if i < len(urls):
                    delay = random.uniform(*delay_range)
                    logger.debug(f"Waiting {delay:.1f} seconds...")
                    time.sleep(delay)
        
        # Save as JSON if requested
        if json_output:
            json_file = output_file.replace('.txt', '.json')
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"JSON output saved to {json_file}")
        
        # Print statistics
        self.print_statistics()
        
        return results
    
    def print_statistics(self):
        """Print scraping statistics"""
        logger.info("\n" + "="*50)
        logger.info("SCRAPING STATISTICS")
        logger.info("="*50)
        logger.info(f"Total URLs: {self.stats['total']}")
        logger.info(f"Successful: {self.stats['successful']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(f"Missing names: {self.stats['missing_name']}")
        logger.info(f"Missing emails: {self.stats['missing_email']}")
        logger.info(f"Missing research: {self.stats['missing_research']}")
        success_rate = (self.stats['successful'] / self.stats['total'] * 100) if self.stats['total'] > 0 else 0
        logger.info(f"Success rate: {success_rate:.1f}%")
        logger.info("="*50)


def test_single_url(url: str = None):
    """Test function for debugging with a single URL or sample HTML"""
    # Create scraper
    scraper = GMIS5ProfileScraper(use_selenium=False, headless=True)
    
    if url:
        # Test with actual URL
        profile = scraper.scrape_profile(url)
        print("\nExtracted Profile:")
        print(f"Name: {profile['name']}")
        print(f"Email: {profile['email']}")
        print(f"Research: {profile['research_interest']}")
    else:
        # Test with sample HTML
        test_html = """
        <!DOCTYPE html>
        <html>
        <head><title>颜天华 - 药学院</title></head>
        <body>
        <div class="jsxm">颜天华</div>
        <div class="emailinfo">1020050806@cpu.edu.cn</div>
        <h2>研究方向</h2>
        <div id="txtyjfx" class="d">
        肿瘤药理学，神经药理学，心脑血管药理学
        </div>
        </body>
        </html>
        """
        
        # Parse with BeautifulSoup
        soup = BeautifulSoup(test_html, 'html.parser')
        
        # Extract information
        name = scraper.extract_name(soup)
        email = scraper.extract_email(soup)
        research = scraper.extract_research_interests(soup)
        
        print("\nTest Extraction Results:")
        print(f"Name: {name}")
        print(f"Email: {email}")
        print(f"Research: {research}")
    
    scraper.close_driver()


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='GMIS5 Faculty Profile Scraper')
    parser.add_argument('--input', '-i', help='Input file with URLs (one per line)')
    parser.add_argument('--output', '-o', default='output_gmis5.txt', help='Output file path')
    parser.add_argument('--json', action='store_true', help='Also save output as JSON')
    parser.add_argument('--no-selenium', action='store_true', help='Use requests instead of Selenium')
    parser.add_argument('--show-browser', action='store_true', help='Show browser window (not headless)')
    parser.add_argument('--delay-min', type=float, default=1.0, help='Minimum delay between requests')
    parser.add_argument('--delay-max', type=float, default=3.0, help='Maximum delay between requests')
    parser.add_argument('--limit', type=int, help='Limit number of profiles to scrape')
    parser.add_argument('--test', action='store_true', help='Run test with sample HTML')
    parser.add_argument('--test-url', help='Test with a specific URL')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Set debug level if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run test if requested
    if args.test:
        test_single_url()
        return
    
    # Test with specific URL if provided
    if args.test_url:
        test_single_url(args.test_url)
        return
    
    # Check if input file is provided
    if not args.input:
        parser.print_help()
        print("\nError: Please provide an input file with URLs using --input or -i")
        print("\nExample usage:")
        print("  python scraper_gmis5.py --input urls.txt --output results.txt --json")
        print("  python scraper_gmis5.py --test  # Run with sample HTML")
        print("  python scraper_gmis5.py --test-url http://example.com/profile  # Test specific URL")
        return
    
    # Read URLs from input file
    try:
        with open(args.input, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
    except FileNotFoundError:
        logger.error(f"Input file not found: {args.input}")
        return
    
    # Apply limit if specified
    if args.limit:
        urls = urls[:args.limit]
    
    logger.info(f"Found {len(urls)} URLs to process")
    
    # Create scraper instance
    scraper = GMIS5ProfileScraper(
        use_selenium=not args.no_selenium,
        headless=not args.show_browser
    )
    
    try:
        # Scrape profiles
        results = scraper.scrape_batch(
            urls=urls,
            output_file=args.output,
            json_output=args.json,
            delay_range=(args.delay_min, args.delay_max)
        )
        
        logger.info(f"Results saved to {args.output}")
        
    finally:
        # Clean up
        scraper.close_driver()


if __name__ == '__main__':
    main()