#!/usr/bin/env python3
"""
Faculty Profile Scraper for Medical School Format
Designed for consistent HTML structure with Chinese content
No AI fallback needed - pure pattern-based extraction
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
from bs4 import BeautifulSoup, NavigableString
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
        logging.FileHandler('scraper.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class MedicalSchoolProfileScraper:
    """Scraper for medical school faculty profiles with consistent structure"""
    
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
        
        # Research section identifiers
        self.research_start_keywords = [
            "研究方向",
            "研究关键词"
        ]
        
        # Stop keywords - when we see these, stop extracting research
        self.research_stop_keywords = [
            "代表性论著",
            "代表性课题",
            "学术任职",
            "执教课程",
            "荣誉奖励",
            "个人简介",
            "代表性论文",
            "科研项目",
            "获奖情况",
            "教学工作",
            "社会兼职"
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
                # Wait for content to load
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(1)  # Additional wait for dynamic content
                return self.driver.page_source
            else:
                response = requests.get(url, timeout=10)
                response.encoding = response.apparent_encoding or 'utf-8'
                return response.text
        except Exception as e:
            logger.error(f"Failed to fetch {url}: {str(e)}")
            return None
    
    def extract_name(self, soup: BeautifulSoup) -> str:
        """
        Extract faculty name from the page
        
        Priority:
        1. <h2> tag (most reliable)
        2. <title> tag (fallback)
        """
        name = ""
        
        # Try <h2> tag first
        h2_tag = soup.find('h2')
        if h2_tag:
            name = h2_tag.get_text(strip=True)
            logger.debug(f"Found name in h2: {name}")
        
        # Fallback to <title> tag
        if not name:
            title_tag = soup.find('title')
            if title_tag:
                title_text = title_tag.get_text(strip=True)
                # Extract name from title (before the dash)
                if '-' in title_text:
                    name = title_text.split('-')[0].strip()
                else:
                    name = title_text
                logger.debug(f"Found name in title: {name}")
        
        # Clean the name (remove titles if needed, but keep as shown for now)
        name = name.strip()
        
        return name if name else "Unknown"
    
    def extract_email(self, soup: BeautifulSoup) -> str:
        """
        Extract email address from the page
        
        Look for: <p>电子邮件：xxx@xxx.com</p>
        """
        email = ""
        
        # Method 1: Find <p> tag containing "电子邮件："
        for p_tag in soup.find_all('p'):
            text = p_tag.get_text(strip=True)
            if '电子邮件：' in text or '电子邮件:' in text:
                # Extract email from the text
                email = text.replace('电子邮件：', '').replace('电子邮件:', '').strip()
                if '@' in email:
                    logger.debug(f"Found email in p tag: {email}")
                    break
        
        # Method 2: Search all text nodes for email pattern after "电子邮件"
        if not email:
            page_text = soup.get_text()
            email_match = re.search(r'电子邮件[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', 
                                   page_text)
            if email_match:
                email = email_match.group(1)
                logger.debug(f"Found email using regex: {email}")
        
        # Method 3: General email search if still not found
        if not email:
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_text)
            if emails:
                # Filter out common non-personal emails
                for candidate in emails:
                    if not any(x in candidate.lower() for x in ['webmaster', 'admin', 'info', 'support']):
                        email = candidate
                        logger.debug(f"Found email in page text: {email}")
                        break
        
        return email if email else "Not found"
    
    def extract_research_interests(self, soup: BeautifulSoup) -> str:
        """
        Extract research interests including both 研究方向 and 研究关键词
        
        The actual structure in the HTML is:
        <p><strong>研究方向：</strong></p>
        <p>actual content here</p>
        """
        research_interests = []
        
        # Find all <p> tags
        all_p_tags = soup.find_all('p')
        
        for i, p_tag in enumerate(all_p_tags):
            # Check if this paragraph contains a research keyword in a strong tag
            strong_tag = p_tag.find('strong')
            if strong_tag:
                strong_text = strong_tag.get_text(strip=True)
                # Remove colon for comparison
                strong_text_clean = strong_text.rstrip('：').rstrip(':')
                
                # Check if this is a research keyword
                if any(keyword in strong_text_clean for keyword in self.research_start_keywords):
                    logger.debug(f"Found research keyword: {strong_text}")
                    
                    # Look for the content in the next <p> tag
                    if i + 1 < len(all_p_tags):
                        next_p = all_p_tags[i + 1]
                        content = next_p.get_text(strip=True)
                        
                        # Make sure the next paragraph doesn't contain another section header
                        if content and not next_p.find('strong'):
                            # Check it's not a stop keyword
                            if not any(stop_kw in content for stop_kw in self.research_stop_keywords):
                                research_interests.append(content)
                                logger.debug(f"Found research content: {content}")
            
            # Alternative: Check if the text content directly contains research keywords
            else:
                text = p_tag.get_text(strip=True)
                for keyword in self.research_start_keywords:
                    if text.startswith(keyword + '：') or text.startswith(keyword + ':'):
                        # Extract content after the colon
                        content = text.split('：', 1)[-1].split(':', 1)[-1].strip()
                        if content:
                            research_interests.append(content)
                            logger.debug(f"Found inline research content: {content}")
                            break
        
        # If still no research found, try a more aggressive search
        if not research_interests:
            logger.debug("Trying aggressive search for research interests...")
            page_text = soup.get_text()
            
            for keyword in self.research_start_keywords:
                # Look for pattern: keyword + colon + content
                pattern = rf'{keyword}[：:]\s*([^{"|".join(self.research_stop_keywords)}]+?)(?={"|".join(self.research_stop_keywords)}|\n\n|\Z)'
                match = re.search(pattern, page_text, re.MULTILINE | re.DOTALL)
                if match:
                    content = match.group(1).strip()
                    # Clean up excessive whitespace and newlines
                    content = re.sub(r'\s+', ' ', content)
                    if content and len(content) > 5:  # Ensure it's not just noise
                        research_interests.append(content)
                        logger.debug(f"Found research via regex: {content}")
        
        # Combine all research interests
        combined = '; '.join(research_interests) if research_interests else ""
        
        # Clean up the text
        if combined:
            # Remove excessive whitespace
            combined = re.sub(r'\s+', ' ', combined)
            # Remove any HTML entities
            combined = re.sub(r'&[^;]+;', ' ', combined)
            # Remove any remaining HTML tags (shouldn't be any, but just in case)
            combined = re.sub(r'<[^>]+>', '', combined)
            combined = combined.strip()
        
        return combined if combined else "Not found"
    
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
            
            logger.info(f"Successfully scraped: {result['name']}")
            logger.debug(f"  Email: {result['email']}")
            logger.debug(f"  Research: {result['research_interest'][:100]}..." if len(result['research_interest']) > 100 else f"  Research: {result['research_interest']}")
            
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
                
                # Update success counter
                if profile['name'] != 'Unknown' or profile['email'] != 'Not found':
                    self.stats['successful'] += 1
                
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
        logger.info("="*50)


def test_single_url():
    """Test function for debugging with a single URL"""
    # Create scraper
    scraper = MedicalSchoolProfileScraper(use_selenium=False, headless=True)
    
    # Test HTML content (you can paste your HTML here for testing)
    test_html = """
    <!DOCTYPE html>
    <html>
    <head><title>李严兵 教授-基础医学院</title></head>
    <body>
    <h2>李严兵 教授</h2>
    <p>电子邮件：hnlybup001@163.com</p>
    <p><strong>研究方向：</strong></p>
    <p>临床应用解剖学；医学生物力学；数字医学；医学3D打印</p>
    <p><strong>研究关键词：</strong></p>
    <p>临床应用解剖Clinical applied anatomy；生物力学；数字医学biomechanics；医学3D打印medical 3D printing；虚拟仿真virtual simulation</p>
    </body>
    </html>
    """
    
    # Parse with BeautifulSoup
    soup = BeautifulSoup(test_html, 'html.parser')
    
    # Extract information
    name = scraper.extract_name(soup)
    email = scraper.extract_email(soup)
    research = scraper.extract_research_interests(soup)
    
    print(f"Name: {name}")
    print(f"Email: {email}")
    print(f"Research: {research}")
    
    scraper.close_driver()


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Medical School Faculty Profile Scraper')
    parser.add_argument('--input', '-i', help='Input file with URLs (one per line)')
    parser.add_argument('--output', '-o', default='output.txt', help='Output file path')
    parser.add_argument('--json', action='store_true', help='Also save output as JSON')
    parser.add_argument('--no-selenium', action='store_true', help='Use requests instead of Selenium')
    parser.add_argument('--show-browser', action='store_true', help='Show browser window (not headless)')
    parser.add_argument('--delay-min', type=float, default=1.0, help='Minimum delay between requests')
    parser.add_argument('--delay-max', type=float, default=3.0, help='Maximum delay between requests')
    parser.add_argument('--limit', type=int, help='Limit number of profiles to scrape')
    parser.add_argument('--test', action='store_true', help='Run test with sample HTML')
    
    args = parser.parse_args()
    
    # Run test if requested
    if args.test:
        test_single_url()
        return
    
    # Check if input file is provided
    if not args.input:
        parser.print_help()
        print("\nError: Please provide an input file with URLs using --input or -i")
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
    scraper = MedicalSchoolProfileScraper(
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