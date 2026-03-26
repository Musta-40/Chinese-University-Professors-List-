#!/usr/bin/env python3
"""
Faculty Profile Research Interest Extractor - Simplified and Robust Version
Extracts ONLY research interests from faculty profile pages.
"""

import argparse
import logging
import re
import time
import random
from pathlib import Path
from typing import Optional, Dict, List

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ResearchInterestExtractor:
    """Main class for extracting research interests from faculty profiles."""
    
    # Stop keywords - immediately stop extraction when these are encountered
    STOP_KEYWORDS_CN = [
        '论文', '发表', '代表性论文', '近五年', '主要成果', '出版', '著作',
        '项目', '研究生导师', '教育背景', '工作经历', '简历', '个人简历',
        '学术论文', '科研成果', '获奖', '专利', '教学', '课程', '学历',
        '毕业', '博士后', '访问学者', '主持项目', '参与项目', '基金',
        '主讲课程', '获奖情况', '主要论文', '论著', '主持的项目',
        '第一作者论文', '通讯作者论文', '既非第一作者'
    ]
    
    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls = set()
        self.processed_emails = set()
        self.output_file = Path(args.output_file)
        
    def setup_driver(self):
        """Initialize Selenium WebDriver with Chrome."""
        options = Options()
        if self.args.headless:
            options.add_argument('--headless=new')  # Use new headless mode
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        options.add_argument('--window-size=1920,1080')
        options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        # Suppress warnings
        options.add_argument('--log-level=3')
        options.add_argument('--silent')
        
        try:
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.set_page_load_timeout(30)
            
            # Remove webdriver property
            self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            logger.info("WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise
            
    def cleanup_driver(self):
        """Clean up WebDriver resources."""
        if self.driver:
            try:
                self.driver.quit()
            except:
                pass
    
    def extract_name_from_title(self, title_text: str) -> str:
        """Extract name from title tag text."""
        if not title_text:
            return "Unknown"
        
        # Pattern: "姓名 - 职称 - ..."
        parts = title_text.split('-')
        if parts:
            name = parts[0].strip()
            # Remove common titles
            name = re.sub(r'(教授|副教授|讲师|博士|硕导|博导|研究员).*$', '', name).strip()
            if name:
                return name
        return "Unknown"
    
    def extract_research_content(self, full_text: str) -> str:
        """Extract research content from the full text."""
        research_text = ""
        
        # Look for research direction markers
        research_markers = ['【研究方向】', '研究方向：', '研究方向:', '研究领域', '主要研究方向']
        
        for marker in research_markers:
            if marker in full_text:
                # Split by the marker and get content after it
                parts = full_text.split(marker)
                if len(parts) > 1:
                    after_marker = parts[1]
                    
                    # Find where to stop - look for next section markers
                    stop_markers = [
                        '【主讲课程】', '【获奖情况】', '【基本情况】', '【',
                        '主要论文', '论文论著', '第一作者论文', '通讯作者论文',
                        '主持的项目', '获奖', '教学', '代表性论文'
                    ]
                    
                    stop_pos = len(after_marker)
                    for stop_marker in stop_markers:
                        pos = after_marker.find(stop_marker)
                        if pos > 0 and pos < stop_pos:
                            stop_pos = pos
                    
                    research_text = after_marker[:stop_pos].strip()
                    
                    # Clean up - remove lines that contain stop keywords
                    lines = research_text.split('\n')
                    clean_lines = []
                    for line in lines:
                        # Check if line contains stop keywords
                        contains_stop = False
                        for stop_word in self.STOP_KEYWORDS_CN:
                            if stop_word in line:
                                contains_stop = True
                                break
                        
                        if not contains_stop:
                            clean_lines.append(line)
                        else:
                            break  # Stop at first line with stop keywords
                    
                    research_text = '\n'.join(clean_lines)
                    break
        
        return research_text
    
    def clean_text(self, text: str) -> str:
        """Clean and normalize extracted text."""
        if not text:
            return ""
        
        # Remove HTML entities and tags
        text = re.sub(r'&[a-z]+;', ' ', text)
        text = re.sub(r'&#\d+;', ' ', text)
        text = re.sub(r'<[^>]+>', '', text)
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n\s*\n', '\n', text)
        
        # Remove leading/trailing whitespace
        text = text.strip()
        
        # Truncate if needed
        if self.args.truncate and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + " [...]"
        
        return text
    
    def process_url(self, url: str) -> Dict[str, str]:
        """Process a single faculty profile URL."""
        result = {
            'name': 'Unknown',
            'email': '',
            'research_interest': '<FAILED: Unable to extract>',
            'profile_link': url
        }
        
        try:
            logger.info(f"Processing: {url}")
            
            # Navigate to URL
            self.driver.get(url)
            
            # Wait a bit for page to load
            time.sleep(5)  # Simple wait instead of complex conditions
            
            # Try to wait for some content to appear
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
            except:
                pass  # Continue even if wait fails
            
            # Scroll to trigger any lazy loading
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight/2);")
            time.sleep(2)
            
            # Get page source
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract name from title
            title = soup.find('title')
            if title:
                result['name'] = self.extract_name_from_title(title.get_text(strip=True))
            
            # Also try to get name from profile box
            name_elem = soup.find('span', style=lambda value: value and '#0080c1' in value)
            if name_elem and name_elem.get_text(strip=True):
                result['name'] = name_elem.get_text(strip=True)
            
            # Extract email
            email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            
            # Look for email in specific element
            email_elem = soup.find('dd', class_='text6')
            if email_elem:
                text = email_elem.get_text(strip=True)
                emails = re.findall(email_pattern, text)
                if emails:
                    result['email'] = emails[0]
            
            # If no email found, search entire page
            if not result['email']:
                page_text = soup.get_text()
                emails = re.findall(email_pattern, page_text)
                for email in emails:
                    if 'lzu.edu.cn' in email.lower():
                        result['email'] = email
                        break
                if not result['email'] and emails:
                    result['email'] = emails[0]
            
            # Extract research interests
            research_text = ""
            
            # Method 1: Look for slideTxtBox structure
            slide_box = soup.find('div', class_='slideTxtBox')
            if slide_box:
                bd_div = slide_box.find('div', class_='bd')
                if bd_div:
                    # Get all ul elements (tabs)
                    uls = bd_div.find_all('ul')
                    if uls and len(uls) > 0:
                        # First ul is typically personal info
                        first_ul = uls[0]
                        full_text = first_ul.get_text(separator='\n', strip=True)
                        research_text = self.extract_research_content(full_text)
            
            # Method 2: If no slideTxtBox, search entire page
            if not research_text:
                # Get all text content
                all_text = soup.get_text(separator='\n', strip=True)
                research_text = self.extract_research_content(all_text)
            
            # Method 3: Look for paragraphs containing research keywords
            if not research_text:
                paragraphs = soup.find_all(['p', 'div'])
                for para in paragraphs:
                    text = para.get_text(strip=True)
                    if any(keyword in text for keyword in ['研究方向', '研究领域', '研究内容', '主要从事']):
                        # Get this paragraph and maybe the next one
                        research_text = text
                        # Find next sibling
                        next_elem = para.find_next_sibling()
                        if next_elem and not any(stop in next_elem.get_text() for stop in self.STOP_KEYWORDS_CN):
                            research_text += '\n' + next_elem.get_text(strip=True)
                        break
            
            if research_text:
                result['research_interest'] = self.clean_text(research_text)
                logger.info(f"Successfully extracted research for: {result['name']}")
            else:
                result['research_interest'] = '<FAILED: No research interests found>'
                logger.warning(f"No research interests found for: {result['name']}")
            
        except TimeoutException:
            logger.error(f"Timeout loading URL: {url}")
            result['research_interest'] = '<FAILED: Page load timeout>'
        except Exception as e:
            logger.error(f"Error processing URL {url}: {str(e)}")
            result['research_interest'] = f'<FAILED: {str(e)}>'
        
        return result
    
    def write_result(self, result: Dict[str, str]):
        """Write a single result to the output file."""
        with open(self.output_file, 'a', encoding='utf-8') as f:
            f.write(f"Name: {result['name']}\n")
            f.write(f"Email: {result['email']}\n")
            f.write(f"Research interest: {result['research_interest']}\n")
            f.write(f"Profile link: {result['profile_link']}\n")
            f.write("---\n\n")
    
    def run(self):
        """Main execution method."""
        # Read input URLs
        input_file = Path(self.args.input_file)
        if not input_file.exists():
            logger.error(f"Input file not found: {input_file}")
            return
        
        with open(input_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        logger.info(f"Found {len(urls)} URLs to process")
        
        # Clear output file if it exists
        if self.output_file.exists() and not self.args.append:
            self.output_file.unlink()
        
        # Setup WebDriver
        self.setup_driver()
        
        try:
            processed_count = 0
            for i, url in enumerate(urls, 1):
                # Check max profiles limit
                if self.args.max_profiles and processed_count >= self.args.max_profiles:
                    logger.info(f"Reached maximum profile limit: {self.args.max_profiles}")
                    break
                
                # Skip duplicates
                normalized_url = url.lower().strip('/')
                if normalized_url in self.processed_urls:
                    logger.info(f"Skipping duplicate URL: {url}")
                    continue
                
                # Process URL
                result = self.process_url(url)
                
                # Check for duplicate email
                if result['email'] and result['email'] in self.processed_emails:
                    logger.info(f"Skipping duplicate email: {result['email']}")
                else:
                    self.write_result(result)
                    if result['email']:
                        self.processed_emails.add(result['email'])
                    processed_count += 1
                
                self.processed_urls.add(normalized_url)
                
                # Random delay between requests
                if i < len(urls):
                    delay = random.uniform(self.args.delay_min, self.args.delay_max)
                    logger.info(f"Waiting {delay:.1f} seconds before next request...")
                    time.sleep(delay)
                
                # Progress update
                if i % 5 == 0:
                    logger.info(f"Progress: {i}/{len(urls)} URLs processed")
        
        finally:
            self.cleanup_driver()
        
        logger.info(f"Extraction complete. Results written to: {self.output_file}")

def main():
    parser = argparse.ArgumentParser(
        description='Extract faculty research interests from profile pages'
    )
    parser.add_argument(
        '--input-file',
        default='urls.txt',
        help='Input file containing URLs (one per line)'
    )
    parser.add_argument(
        '--output-file',
        default='output.txt',
        help='Output file for extracted profiles'
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
        default=None,
        help='Maximum number of profiles to process'
    )
    parser.add_argument(
        '--retries',
        type=int,
        default=1,
        help='Number of retry attempts for failed extractions'
    )
    parser.add_argument(
        '--truncate',
        type=int,
        default=4000,
        help='Maximum characters for research interest text (0 = no limit)'
    )
    parser.add_argument(
        '--append',
        action='store_true',
        help='Append to output file instead of overwriting'
    )
    
    args = parser.parse_args()
    
    # Validate arguments
    if args.delay_min > args.delay_max:
        parser.error("--delay-min must be less than or equal to --delay-max")
    
    # Run extractor
    extractor = ResearchInterestExtractor(args)
    try:
        extractor.run()
    except KeyboardInterrupt:
        logger.info("Extraction interrupted by user")
        extractor.cleanup_driver()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        extractor.cleanup_driver()
        raise

if __name__ == '__main__':
    main()