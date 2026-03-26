#!/usr/bin/env python3
"""
Faculty Profile Scraper for Harbin Medical University Format
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
from typing import Dict, Optional, List, Tuple
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
        logging.FileHandler('scraper_harbin.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class HarbinMedicalProfileScraper:
    """Scraper for Harbin Medical University faculty profiles"""
    
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
        
        # Research section identifiers (in priority order)
        self.research_primary_keywords = [
            "学科/专业",
            "主要研究方向"
        ]
        
        # Fallback keyword for research
        self.research_fallback_keyword = "科研论文代表作"
        
        # Stop keywords - when we see these, stop extracting
        self.stop_keywords = [
            "主要学术成果",
            "科研论文代表作",
            "其他",
            "办公电话",
            "学习经历",
            "工作经历",
            "导师类别",
            "职称",
            "学历",
            "发布时间",
            "浏览次数"
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
        1. <div class="cotit"> (most reliable)
        2. <title> tag (before the dash)
        3. <p>姓名：xxx</p> pattern
        """
        name = ""
        
        # Method 1: Try <div class="cotit"> first (most reliable)
        cotit_div = soup.find('div', class_='cotit')
        if cotit_div:
            name = cotit_div.get_text(strip=True)
            logger.debug(f"Found name in div.cotit: {name}")
            return name if name else "Unknown"
        
        # Method 2: Try <title> tag
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Extract name from title (before the dash)
            if '-' in title_text:
                name = title_text.split('-')[0].strip()
                logger.debug(f"Found name in title: {name}")
                if name:
                    return name
        
        # Method 3: Look for pattern <p>姓名：xxx</p>
        for p_tag in soup.find_all('p'):
            text = p_tag.get_text(strip=True)
            if text.startswith('姓名：') or text.startswith('姓名:'):
                name = text.replace('姓名：', '').replace('姓名:', '').strip()
                logger.debug(f"Found name in p tag: {name}")
                if name:
                    return name
        
        return name if name else "Unknown"
    
    def extract_email(self, soup: BeautifulSoup) -> str:
        """
        Extract email address from the page
        
        Look for: <p>Email：xxx@xxx.com</p> within .v_news_content
        Note: Uses Chinese colon ：
        """
        email = ""
        
        # Find the content area first
        content_div = soup.find('div', class_='v_news_content')
        if not content_div:
            # Fallback to id-based selection
            content_div = soup.find('div', id='vsb_content_4')
        if not content_div:
            # If still not found, search entire page
            content_div = soup
        
        # Method 1: Find <p> tag containing "Email："
        for p_tag in content_div.find_all('p'):
            text = p_tag.get_text(strip=True)
            if 'Email：' in text or 'Email:' in text or 'email：' in text or 'email:' in text:
                # Extract email from the text
                email = re.sub(r'[Ee]mail[：:]', '', text).strip()
                if '@' in email:
                    logger.debug(f"Found email in p tag: {email}")
                    return email
        
        # Method 2: Search for email pattern after "Email"
        if not email:
            content_text = content_div.get_text()
            email_match = re.search(r'[Ee]mail[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', 
                                   content_text)
            if email_match:
                email = email_match.group(1)
                logger.debug(f"Found email using regex: {email}")
                return email
        
        # Method 3: General email search as last resort
        if not email:
            emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content_div.get_text())
            if emails:
                # Filter out common non-personal emails
                for candidate in emails:
                    if not any(x in candidate.lower() for x in ['webmaster', 'admin', 'info', 'support']):
                        email = candidate
                        logger.debug(f"Found email in content: {email}")
                        return email
        
        return email if email else "Not found"
    
    def extract_research_interests(self, soup: BeautifulSoup) -> str:
        """
        Extract research interests with priority:
        1. Combine 学科/专业 + 主要研究方向 if both exist
        2. Use whichever one exists
        3. Fallback to 科研论文代表作 (last resort)
        """
        research_parts = []
        
        # Find the content area
        content_div = soup.find('div', class_='v_news_content')
        if not content_div:
            content_div = soup.find('div', id='vsb_content_4')
        if not content_div:
            content_div = soup
        
        # Get all <p> tags in content area
        all_p_tags = content_div.find_all('p')
        
        # Extract 学科/专业
        major = self.extract_field_content(all_p_tags, "学科/专业")
        if major:
            research_parts.append(major)
            logger.debug(f"Found 学科/专业: {major}")
        
        # Extract 主要研究方向
        direction = self.extract_field_content(all_p_tags, "主要研究方向")
        if direction:
            research_parts.append(direction)
            logger.debug(f"Found 主要研究方向: {direction}")
        
        # If we have primary research information, combine and return
        if research_parts:
            combined = "; ".join(research_parts)
            return self.clean_research_text(combined)
        
        # Fallback: Extract 科研论文代表作 (only if no primary research found)
        logger.debug("No primary research found, trying fallback to papers...")
        papers = self.extract_papers(all_p_tags)
        if papers:
            # Format papers as research interest (you can adjust format as needed)
            papers_text = "Research publications: " + "; ".join(papers[:3])  # Limit to first 3
            return self.clean_research_text(papers_text)
        
        return "Not found"
    
    def extract_field_content(self, p_tags: List, field_name: str) -> str:
        """
        Extract content for a specific field (e.g., 学科/专业, 主要研究方向)
        
        Args:
            p_tags: List of <p> BeautifulSoup tags
            field_name: Field name to search for (without colon)
            
        Returns:
            Extracted content or empty string
        """
        content = ""
        
        for i, p_tag in enumerate(p_tags):
            text = p_tag.get_text(strip=True)
            
            # Check if this paragraph starts with the field name
            if text.startswith(f"{field_name}：") or text.startswith(f"{field_name}:"):
                # Extract content after the colon in the same paragraph
                content = text.split('：', 1)[-1].split(':', 1)[-1].strip()
                
                # If content is empty or very short, check next paragraphs
                if len(content) < 5 and i + 1 < len(p_tags):
                    # Look at next paragraphs until we hit a stop keyword
                    for j in range(i + 1, min(i + 5, len(p_tags))):  # Check next 5 paragraphs max
                        next_text = p_tags[j].get_text(strip=True)
                        
                        # Stop if we hit another field or stop keyword
                        if any(keyword in next_text for keyword in self.stop_keywords):
                            break
                        if any(next_text.startswith(f"{kw}：") or next_text.startswith(f"{kw}:") 
                               for kw in ["学科", "主要", "科研", "其他", "办公"]):
                            break
                        
                        # Add this content
                        if next_text and not next_text.startswith("（") and not next_text.startswith("("):
                            if content:
                                content += "; " + next_text
                            else:
                                content = next_text
                
                return content
        
        return ""
    
    def extract_papers(self, p_tags: List) -> List[str]:
        """
        Extract paper titles from 科研论文代表作 section
        
        Args:
            p_tags: List of <p> BeautifulSoup tags
            
        Returns:
            List of paper titles (up to 5)
        """
        papers = []
        found_section = False
        
        for i, p_tag in enumerate(p_tags):
            text = p_tag.get_text(strip=True)
            
            # Check if we've found the papers section
            if "科研论文代表作" in text:
                found_section = True
                continue
            
            if found_section:
                # Stop if we hit another section
                if any(keyword in text for keyword in ["其他：", "办公电话：", "主要学术成果："]):
                    break
                
                # Extract paper if it looks like a citation (contains year pattern or starts with number)
                if text and (re.search(r'\d{4}', text) or re.match(r'^\d+[\.\、]', text)):
                    # Clean up the paper text
                    paper = re.sub(r'^\d+[\.\、]\s*', '', text)  # Remove numbering
                    papers.append(paper)
                    
                    if len(papers) >= 5:  # Limit to 5 papers
                        break
        
        return papers
    
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
        
        # Remove parenthetical notes like (原则上不超过5篇)
        text = re.sub(r'[（(][^）)]*不超过[^）)]*[）)]', '', text)
        
        # Clean up punctuation
        text = re.sub(r'：+', '：', text)
        text = re.sub(r'；+', '；', text)
        text = re.sub(r'\s*[;；]\s*', '; ', text)
        
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
                else:
                    self.stats['failed'] += 1
                
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


def test_single_url():
    """Test function for debugging with a single URL"""
    # Create scraper
    scraper = HarbinMedicalProfileScraper(use_selenium=False, headless=True)
    
    # Test HTML content
    test_html = """
    <!DOCTYPE html>
    <html>
    <head><title>张瑶-哈尔滨医科大学基础医学部</title></head>
    <body>
    <div class="cotit">张瑶</div>
    <div class="v_news_content">
        <p>姓名：张瑶</p>
        <p>学科/专业：神经生物学/神经生物</p>
        <p>主要研究方向：（1）神经退行性疾病的机制研究；（2）神经保护药物的开发</p>
        <p>Email：zhangyao@hrbmu.edu.cn</p>
        <p>科研论文代表作：(原则上不超过5篇)</p>
        <p>1. Zhang Y, et al. Nature 2023...</p>
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
    
    print(f"Name: {name}")
    print(f"Email: {email}")
    print(f"Research: {research}")
    
    scraper.close_driver()


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Harbin Medical University Faculty Profile Scraper')
    parser.add_argument('--input', '-i', help='Input file with URLs (one per line)')
    parser.add_argument('--output', '-o', default='output_harbin.txt', help='Output file path')
    parser.add_argument('--json', action='store_true', help='Also save output as JSON')
    parser.add_argument('--no-selenium', action='store_true', help='Use requests instead of Selenium')
    parser.add_argument('--show-browser', action='store_true', help='Show browser window (not headless)')
    parser.add_argument('--delay-min', type=float, default=1.0, help='Minimum delay between requests')
    parser.add_argument('--delay-max', type=float, default=3.0, help='Maximum delay between requests')
    parser.add_argument('--limit', type=int, help='Limit number of profiles to scrape')
    parser.add_argument('--test', action='store_true', help='Run test with sample HTML')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Set debug level if requested
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
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
    scraper = HarbinMedicalProfileScraper(
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