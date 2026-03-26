#!/usr/bin/env python3
"""
Universal Faculty Profile Scraper for Hebei Medical University
Handles both Chinese and English profiles with different structures
Robust extraction using pattern matching and language detection
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
from bs4 import BeautifulSoup, NavigableString, Tag
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
        logging.FileHandler('scraper_hebei.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class HebeiMedicalProfileScraper:
    """Scraper for Hebei Medical University faculty profiles (both Chinese and English)"""
    
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
        
        # Chinese profile patterns
        self.chinese_section_headers = [
            r'一、\s*PI简介',
            r'二、\s*研究方向',
            r'二、\s*主要学术成就',
            r'二、\s*近期研究计划',
            r'三、\s*团队近期研究计划',
            r'三、\s*代表性论文',
            r'四、\s*代表性论文',
            r'五、\s*团队承担课题'
        ]
        
        # Chinese research start keywords
        self.chinese_research_starts = [
            '主要从事',
            '研究方向',
            '近期研究计划',
            '团队近期研究计划',
            '长期研究方向是',
            '主要关注'
        ]
        
        # Chinese research stop keywords
        self.chinese_research_stops = [
            '代表性论文',
            '发表学术论文',
            '发表研究论文',
            '目前在国际',
            '获.*?奖',
            '主持科研项目',
            '承担课题',
            '培养博士',
            '享受国务院',
            '四、',
            '五、',
            '六、'
        ]
        
        # English section headers
        self.english_section_headers = [
            'Research interests',
            'Research Direction',
            'Research Directions',
            'Representative Publications',
            'Work Experience',
            'Education',
            'Employment',
            'Academic Office'
        ]
        
        # Misleading content to avoid
        self.misleading_keywords = [
            'Publications', 'Papers', 'Grants', 'Awards', 'Patents',
            'Teaching', 'Team Members', 'Students', 'Editorial',
            '论文', '论著', '课题', '项目', '获奖', '专利', '教材', '学生'
        ]
        
        # Statistics
        self.stats = {
            'total': 0,
            'successful': 0,
            'failed': 0,
            'chinese_profiles': 0,
            'english_profiles': 0,
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
        options.add_argument('--lang=zh-CN,zh;q=0.9,en;q=0.8')
        options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
        
        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(10)
    
    def close_driver(self):
        """Close Selenium driver"""
        if self.driver:
            self.driver.quit()
    
    def get_page_content(self, url: str) -> Optional[str]:
        """Get page HTML content"""
        try:
            if self.use_selenium:
                self.driver.get(url)
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(1)
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
    
    def detect_profile_type(self, soup: BeautifulSoup) -> str:
        """
        Detect whether the profile is Chinese or English
        
        Returns:
            'chinese' or 'english'
        """
        page_text = soup.get_text()
        
        # Check for Chinese section headers
        for pattern in self.chinese_section_headers:
            if re.search(pattern, page_text):
                logger.debug("Detected Chinese profile (section headers)")
                return 'chinese'
        
        # Check for Chinese PI introduction
        if re.search(r'PI简介|主要从事|研究方向', page_text):
            logger.debug("Detected Chinese profile (keywords)")
            return 'chinese'
        
        # Check for English headers in h2 or strong tags
        for tag in soup.find_all(['h2', 'strong']):
            tag_text = tag.get_text(strip=True)
            if any(header.lower() in tag_text.lower() for header in self.english_section_headers):
                logger.debug("Detected English profile (headers)")
                return 'english'
        
        # Check for Dr./Professor in title
        if soup.find('h2', class_='title'):
            title_text = soup.find('h2', class_='title').get_text()
            if 'Dr.' in title_text or 'Professor' in title_text:
                logger.debug("Detected English profile (title)")
                return 'english'
        
        # Default based on character composition
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', page_text[:1000]))
        if chinese_chars > 100:
            return 'chinese'
        
        return 'english'
    
    # ==================== Chinese Profile Extraction ====================
    
    def extract_chinese_name(self, soup: BeautifulSoup) -> str:
        """Extract name from Chinese profile"""
        name = ""
        
        # Method 1: Look for name after <img> in PI简介 section
        pi_intro = None
        for text in soup.find_all(string=re.compile(r'一、\s*PI简介')):
            pi_intro = text.find_parent()
            break
        
        if pi_intro:
            # Find the next paragraph after PI简介 header
            next_p = pi_intro.find_next('p')
            if next_p:
                # Look for text after <img> tag
                img_tag = next_p.find('img')
                if img_tag:
                    # Get text immediately after image
                    next_text = img_tag.next_sibling
                    if next_text:
                        text = str(next_text).strip()
                        # Extract name before first comma
                        if '，' in text:
                            name = text.split('，')[0].strip()
                        elif ',' in text:
                            name = text.split(',')[0].strip()
                        else:
                            # Try to extract Chinese name pattern
                            name_match = re.match(r'^([\u4e00-\u9fff]{2,4})', text)
                            if name_match:
                                name = name_match.group(1)
                
                # If no img tag, try to extract from beginning of paragraph
                if not name:
                    p_text = next_p.get_text(strip=True)
                    # Look for Chinese name at the start
                    name_match = re.match(r'^([\u4e00-\u9fff]{2,4})[，,]', p_text)
                    if name_match:
                        name = name_match.group(1)
        
        # Method 2: Look for name pattern anywhere in the page
        if not name:
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                # Pattern: Chinese name followed by titles
                match = re.match(r'^([\u4e00-\u9fff]{2,4})[，,].{0,5}(教授|博士|研究员)', text)
                if match:
                    name = match.group(1)
                    break
        
        logger.debug(f"Extracted Chinese name: {name}")
        return name if name else "Unknown"
    
    def extract_chinese_research(self, soup: BeautifulSoup) -> str:
        """Extract research interests from Chinese profile"""
        research_parts = []
        page_text = soup.get_text()
        
        # Method 1: Look for explicit 研究方向 section
        for pattern in [r'二、\s*研究方向', r'研究方向\s*[:：]']:
            match = re.search(pattern + r'(.*?)(?:三、|四、|代表性论文)', page_text, re.DOTALL)
            if match:
                content = match.group(1).strip()
                if content and len(content) > 10:
                    research_parts.append(self.clean_chinese_text(content))
                    logger.debug(f"Found research in 研究方向 section: {content[:50]}...")
        
        # Method 2: Look for 主要从事 pattern
        if not research_parts:
            for start_kw in self.chinese_research_starts:
                pattern = f'{start_kw}(.*?)(?:{"｜".join(self.chinese_research_stops)})'
                match = re.search(pattern, page_text, re.DOTALL)
                if match:
                    content = match.group(1).strip()
                    if content and len(content) > 10:
                        research_parts.append(self.clean_chinese_text(content))
                        logger.debug(f"Found research with '{start_kw}': {content[:50]}...")
                        break
        
        # Method 3: Look for 近期研究计划 section
        if not research_parts:
            for pattern in [r'近期研究计划', r'团队近期研究计划', r'主要学术成就']:
                match = re.search(pattern + r'[:：]?(.*?)(?:三、|四、|代表性|承担课题)', 
                                 page_text, re.DOTALL)
                if match:
                    content = match.group(1).strip()
                    if content and len(content) > 10:
                        research_parts.append(self.clean_chinese_text(content))
                        logger.debug(f"Found research in {pattern}: {content[:50]}...")
        
        # Combine all found research parts
        if research_parts:
            return '; '.join(research_parts)
        
        return "Not found"
    
    def clean_chinese_text(self, text: str) -> str:
        """Clean Chinese research text"""
        # Remove team composition info
        text = re.sub(r'目前团队由.*?组成[。，]?', '', text)
        text = re.sub(r'团队现有.*?人[。，]?', '', text)
        
        # Remove publication counts
        text = re.sub(r'发表.*?论文.*?篇[。，]?', '', text)
        text = re.sub(r'目前在.*?杂志.*?篇[。，]?', '', text)
        
        # Remove funding info
        text = re.sub(r'主持.*?基金.*?项[。，]?', '', text)
        text = re.sub(r'承担.*?项目.*?项[。，]?', '', text)
        
        # Remove award info
        text = re.sub(r'获.*?等奖.*?项[。，]?', '', text)
        
        # Clean whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'^\d+[)）]\s*', '', text)  # Remove numbering
        
        return text.strip()
    
    # ==================== English Profile Extraction ====================
    
    def extract_english_name(self, soup: BeautifulSoup) -> str:
        """Extract name from English profile"""
        name = ""
        
        # Method 1: Look for name in <strong> tags
        for strong in soup.find_all('strong'):
            text = strong.get_text(strip=True)
            # Check if it looks like a name (e.g., "Yun Huang", "Yanfang Xu")
            if re.match(r'^[A-Z][a-z]+\s+[A-Z][a-z]+$', text):
                name = text
                logger.debug(f"Found name in strong tag: {name}")
                break
        
        # Method 2: Extract from h2.title
        if not name:
            title_h2 = soup.find('h2', class_='title')
            if title_h2:
                title_text = title_h2.get_text(strip=True)
                # Pattern: "Dr. Firstname Lastname - Professor" or similar
                match = re.search(r'Dr\.\s+([A-Z][a-z]+\s+[A-Z][a-z]+)', title_text)
                if match:
                    name = match.group(1)
                    logger.debug(f"Found name in h2 title: {name}")
                else:
                    # Try simpler pattern
                    match = re.search(r'([A-Z][a-z]+\s+[A-Z][a-z]+)', title_text)
                    if match:
                        name = match.group(1)
        
        # Method 3: Look for "Firstname Lastname" pattern in text
        if not name:
            for p in soup.find_all('p'):
                text = p.get_text(strip=True)
                match = re.search(r'\b([A-Z][a-z]+\s+[A-Z][a-z]+)\b', text)
                if match:
                    potential_name = match.group(1)
                    # Verify it's not a common phrase
                    if potential_name not in ['Research Direction', 'Work Experience', 'Representative Publications']:
                        name = potential_name
                        break
        
        return name if name else "Unknown"
    
    def extract_english_email(self, soup: BeautifulSoup) -> str:
        """Extract email from English profile"""
        email = ""
        
        # Method 1: Look for E-mail: or Email: label
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if re.search(r'E-?mail\s*:', text, re.IGNORECASE):
                # Extract email address
                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', text)
                if email_match:
                    email = email_match.group(0)
                    logger.debug(f"Found email with label: {email}")
                    break
        
        # Method 2: Look for any email pattern
        if not email:
            page_text = soup.get_text()
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', page_text)
            if email_match:
                email = email_match.group(0)
                logger.debug(f"Found email without label: {email}")
        
        return email if email else "Not found"
    
    def extract_english_research(self, soup: BeautifulSoup) -> str:
        """Extract research interests from English profile"""
        research = ""
        
        # Method 1: Look for Research interests/Direction header
        research_header = None
        for tag in soup.find_all(['p', 'h2', 'h3', 'strong']):
            text = tag.get_text(strip=True)
            if re.search(r'Research\s+(interests?|Directions?)', text, re.IGNORECASE):
                research_header = tag
                logger.debug(f"Found research header: {text}")
                break
        
        if research_header:
            # Collect all paragraphs until next section
            research_parts = []
            current = research_header.find_next_sibling()
            
            while current:
                if current.name == 'p':
                    text = current.get_text(strip=True)
                    
                    # Check if we've hit the next section
                    if any(keyword in text for keyword in 
                          ['Representative Publications', 'Work Experience', 
                           'Education', 'Employment', 'Academic Office']):
                        break
                    
                    # Check if this is another header (strong or bold text)
                    if current.find('strong') or current.find('b'):
                        strong_text = current.get_text(strip=True)
                        if any(keyword in strong_text for keyword in 
                              ['Publications', 'Experience', 'Education']):
                            break
                    
                    # Add non-empty content
                    if text and len(text) > 5:
                        research_parts.append(text)
                
                current = current.find_next_sibling()
                
                # Safety limit
                if len(research_parts) > 10:
                    break
            
            if research_parts:
                research = ' '.join(research_parts)
        
        return research if research else "Not found"
    
    # ==================== Main Extraction Logic ====================
    
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
            'profile_link': url,
            'profile_type': 'unknown'
        }
        
        try:
            # Get page content
            html_content = self.get_page_content(url)
            if not html_content:
                logger.error(f"Failed to get content for {url}")
                return result
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Detect profile type
            profile_type = self.detect_profile_type(soup)
            result['profile_type'] = profile_type
            
            # Extract based on profile type
            if profile_type == 'chinese':
                self.stats['chinese_profiles'] += 1
                result['name'] = self.extract_chinese_name(soup)
                result['email'] = 'Not found'  # Chinese profiles don't have email
                result['research_interest'] = self.extract_chinese_research(soup)
            else:  # english
                self.stats['english_profiles'] += 1
                result['name'] = self.extract_english_name(soup)
                result['email'] = self.extract_english_email(soup)
                result['research_interest'] = self.extract_english_research(soup)
            
            # Update statistics
            if result['name'] == 'Unknown':
                self.stats['missing_name'] += 1
            if result['email'] == 'Not found':
                self.stats['missing_email'] += 1
            if result['research_interest'] == 'Not found':
                self.stats['missing_research'] += 1
            
            # Log results
            logger.info(f"Successfully scraped ({profile_type}): {result['name']}")
            logger.debug(f"  Email: {result['email']}")
            research_preview = result['research_interest'][:100] + "..." if len(result['research_interest']) > 100 else result['research_interest']
            logger.debug(f"  Research: {research_preview}")
            
            self.stats['successful'] += 1
            
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
        for key in self.stats:
            if key != 'total':
                self.stats[key] = 0
        
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
                f.write(f"Profile type: {profile['profile_type']}\n")
                f.write("---\n\n")
                f.flush()
                
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
        logger.info("\n" + "="*60)
        logger.info("SCRAPING STATISTICS")
        logger.info("="*60)
        logger.info(f"Total URLs: {self.stats['total']}")
        logger.info(f"Successful: {self.stats['successful']}")
        logger.info(f"Failed: {self.stats['failed']}")
        logger.info(f"Chinese profiles: {self.stats['chinese_profiles']}")
        logger.info(f"English profiles: {self.stats['english_profiles']}")
        logger.info(f"Missing names: {self.stats['missing_name']}")
        logger.info(f"Missing emails: {self.stats['missing_email']} (Note: Chinese profiles don't have emails)")
        logger.info(f"Missing research: {self.stats['missing_research']}")
        success_rate = (self.stats['successful'] / self.stats['total'] * 100) if self.stats['total'] > 0 else 0
        logger.info(f"Success rate: {success_rate:.1f}%")
        logger.info("="*60)


def test_samples():
    """Test function with sample HTML snippets"""
    scraper = HebeiMedicalProfileScraper(use_selenium=False)
    
    # Test Chinese profile
    chinese_html = """
    <html>
    <body>
    <p>一、PI简介</p>
    <p><img src="photo.jpg"/>王川，药理学教授，博士生导师。主要从事心血管和神经系统疾病的发病机制研究。</p>
    <p>二、近期研究计划</p>
    <p>围绕心律失常、心肌肥厚及心衰的发生机制进行创新性研究。</p>
    <p>三、代表性论文</p>
    </body>
    </html>
    """
    
    # Test English profile
    english_html = """
    <html>
    <body>
    <h2 class="title">Dr. Yun Huang - Professor</h2>
    <p><strong>Yun Huang</strong></p>
    <p>E-mail: hy9317536@126.com</p>
    <p><strong>Research Direction</strong></p>
    <p>Interaction between active components of crude drugs and biomacromolecules</p>
    <p><strong>Work Experience</strong></p>
    </body>
    </html>
    """
    
    print("Testing Chinese profile:")
    soup = BeautifulSoup(chinese_html, 'html.parser')
    profile_type = scraper.detect_profile_type(soup)
    print(f"  Type: {profile_type}")
    print(f"  Name: {scraper.extract_chinese_name(soup)}")
    print(f"  Research: {scraper.extract_chinese_research(soup)}")
    
    print("\nTesting English profile:")
    soup = BeautifulSoup(english_html, 'html.parser')
    profile_type = scraper.detect_profile_type(soup)
    print(f"  Type: {profile_type}")
    print(f"  Name: {scraper.extract_english_name(soup)}")
    print(f"  Email: {scraper.extract_english_email(soup)}")
    print(f"  Research: {scraper.extract_english_research(soup)}")
    
    scraper.close_driver()


def main():
    """Main function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Hebei Medical University Faculty Profile Scraper')
    parser.add_argument('--input', '-i', help='Input file with URLs (one per line)')
    parser.add_argument('--output', '-o', default='output_hebei.txt', help='Output file path')
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
        test_samples()
        return
    
    # Check if input file is provided
    if not args.input:
        parser.print_help()
        print("\nError: Please provide an input file with URLs using --input or -i")
        print("\nExample usage:")
        print("  python scraper_hebei.py --input urls.txt --output results.txt --json")
        print("  python scraper_hebei.py --test  # Run with sample HTML")
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
    scraper = HebeiMedicalProfileScraper(
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