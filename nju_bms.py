#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper - Dual Template Support (AI removed)
Supports both "Teacher Box" and "Article Title" template formats
This variant removes AI extraction and uses only traditional extraction,
including a specific handler for research keywords found inside meta description.
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
from typing import Dict, Optional, Set, List

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


class DualTemplateFacultyProfileScraper:
    """Scraper supporting two template formats (no AI)"""
    
    # Primary research keywords
    RESEARCH_START_KEYWORDS = ['研究兴趣', '研究方向']
    
    # Alternative research triggers
    ALTERNATIVE_RESEARCH_TRIGGERS = [
        '研究领域', '主要从事', '目前从事', '研究内容', '研究工作'
    ]
    
    # Stop keywords for research section
    RESEARCH_STOP_KEYWORDS = [
        '代表性论文', '发表论文', '学术论文', '科研成果',
        '科研项目', '承担项目', '主持项目', '参与项目',
        '获奖情况', '教育背景', '工作经历', '个人简介',
        '联系方式', '学术兼职', '社会兼职', '教学工作',
        '人才培养', '学生指导', '专利', '著作',
        '科研情况简介', '承担科研项目', '获奖情况'
    ]
    
    # Additional stop indicators
    YEAR_PATTERN = r'\b(19|20)\d{2}\b'  # Matches years like 1999, 2012
    DOI_PATTERN = r'(doi|DOI)[\s:]*10\.\d{4,}'  # Matches DOI patterns
    
    # Content to avoid in research text
    MISLEADING_CONTENT = [
        'doi', 'DOI', '10.', 'http://', 'https://', 
        'ISBN', 'ISSN', '期刊', '会议', 'pp.', 'Vol.', 
        '年第', '月第', 'IF=', '影响因子', 'SCI', 'EI',
        '第一作者', '通讯作者', '发表于', 'Email', 'email'
    ]
    
    # Keywords for publication sections (for inference if needed)
    PUBLICATION_KEYWORDS = [
        '代表性论文', '发表论文', '近期发表', '科研成果',
        '学术成果', '研究成果', '论文列表'
    ]

    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls: Set[str] = set()

    def detect_template_type(self, soup) -> str:
        """Detect which template type the page uses"""
        teacher_box = soup.find('div', class_='teacher-box')
        if teacher_box:
            logger.debug("Detected Template 1: Teacher Box format")
            return 'TEMPLATE_1'
        
        arti_title = soup.find('h1', class_='arti_title')
        if arti_title:
            logger.debug("Detected Template 2: Article Title format")
            return 'TEMPLATE_2'
        
        logger.warning("Could not detect template type")
        return 'UNKNOWN'

    def extract_from_meta_description(self, soup) -> str:
        """Extract research interest if it appears inside meta description or og:description."""
        # Common meta keys to check
        candidates = [
            ('name', 'description'),
            ('property', 'og:description'),
            ('name', 'twitter:description'),
            ('property', 'description')
        ]
        content = ""
        for attr, val in candidates:
            meta = soup.find('meta', attrs={attr: val})
            if meta and meta.get('content'):
                content = meta.get('content')
                if content:
                    break
        
        if not content:
            return ""

        # Unescape HTML entities and normalize non-breaking spaces
        content = html.unescape(content).replace('\xa0', ' ').replace('&nbsp;', ' ')
        # Try to match common research indicators and capture the following phrase
        # Stop capture before common field markers like "专业", "学历", or punctuation.
        pattern = re.compile(
            r'(?:研究方向|研究兴趣|研究领域)[:：]\s*([^；;。．.，,专业姓名]+)',
            flags=re.UNICODE
        )
        m = pattern.search(content)
        if m:
            extracted = m.group(1).strip()
            extracted = self.clean_research_text(extracted)
            if extracted:
                logger.debug(f"Extracted from meta description: {extracted}")
                return extracted
        
        # Fallback: more permissive capture until next known label or end
        pattern2 = re.compile(r'(?:研究方向|研究兴趣|研究领域)[:：]\s*(.+)$', flags=re.UNICODE)
        m2 = pattern2.search(content)
        if m2:
            # Trim on common separators if present
            tail = m2.group(1).strip()
            tail = re.split(r'(专业|学历|联系方式|；|;|。|\.|，|,)', tail)[0].strip()
            tail = self.clean_research_text(tail)
            if tail:
                logger.debug(f"Extracted (fallback) from meta description: {tail}")
                return tail
        
        return ""

    def extract_name_template1(self, soup) -> str:
        """Extract name from Template 1 (Teacher Box)"""
        try:
            name_elem = soup.select_one('div.teacher-field.title > span.field-info')
            if name_elem:
                name = name_elem.get_text(strip=True)
                name = re.sub(r'\s*(博士|硕士|教授|副教授|讲师|助理研究员|研究员)\s*', '', name)
                if name:
                    logger.debug(f"Name found (Template 1): {name}")
                    return name
            return "Unknown"
        except Exception as e:
            logger.error(f"Error extracting name (Template 1): {e}")
            return "Unknown"

    def extract_name_template2(self, soup) -> str:
        """Extract name from Template 2 (Article Title)"""
        try:
            h1 = soup.find('h1', class_='arti_title')
            if h1:
                name = h1.get_text(strip=True)
                if name:
                    logger.debug(f"Name found (Template 2): {name}")
                    return name
            return "Unknown"
        except Exception as e:
            logger.error(f"Error extracting name (Template 2): {e}")
            return "Unknown"

    def extract_email_template1(self, soup) -> Optional[str]:
        """Extract email from Template 1 (Teacher Box)"""
        try:
            email_elem = soup.select_one('div.teacher-field.dh > span.field-info.i2')
            if email_elem:
                text = email_elem.get_text(strip=True)
                text = text.replace('邮箱：', '').replace('邮箱:', '').strip()
                if '@' in text:
                    logger.debug(f"Email found (Template 1): {text}")
                    return text
            return None
        except Exception as e:
            logger.error(f"Error extracting email (Template 1): {e}")
            return None

    def extract_email_template2(self, soup) -> Optional[str]:
        """Extract email from Template 2 (Article Title)"""
        try:
            email_pattern = r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            # Search in common places
            for p in soup.find_all('p'):
                text = p.get_text()
                if 'Email' in text or 'email' in text or '邮箱' in text:
                    m = re.search(email_pattern, text)
                    if m:
                        email = m.group(1)
                        logger.debug(f"Email found (Template 2): {email}")
                        return email
            page_text = soup.get_text()
            m = re.search(email_pattern, page_text)
            if m:
                logger.debug(f"Email found in page (Template 2): {m.group(1)}")
                return m.group(1)
            return None
        except Exception as e:
            logger.error(f"Error extracting email (Template 2): {e}")
            return None

    def extract_research_template1(self, soup) -> str:
        """Extract research from Template 1 (Teacher Box)"""
        try:
            research_elem = soup.select_one('div.teacher-field.dh > span.field-info.i4 > p')
            if research_elem:
                research_text = research_elem.get_text(strip=True)
                for keyword in ['研究方向：', '研究方向:', '研究兴趣：', '研究兴趣:']:
                    if research_text.startswith(keyword):
                        research_text = research_text[len(keyword):].strip()
                research_text = self.clean_research_text(research_text)
                if research_text and len(research_text) > 5:
                    logger.info(f"Research extracted (Template 1): {len(research_text)} chars")
                    return research_text

            # Alternative: i4 without p child
            research_elem = soup.select_one('div.teacher-field.dh > span.field-info.i4')
            if research_elem:
                research_text = research_elem.get_text(strip=True)
                for keyword in ['研究方向：', '研究方向:', '研究兴趣：', '研究兴趣:']:
                    if research_text.startswith(keyword):
                        research_text = research_text[len(keyword):].strip()
                research_text = self.clean_research_text(research_text)
                if research_text and len(research_text) > 5:
                    logger.info(f"Research extracted (Template 1, alt): {len(research_text)} chars")
                    return research_text

            # Try meta description as fallback
            meta_extracted = self.extract_from_meta_description(soup)
            if meta_extracted:
                logger.info("Research extracted from meta description (Template 1 fallback)")
                return meta_extracted

            return ""
        except Exception as e:
            logger.error(f"Error extracting research (Template 1): {e}")
            return ""

    def extract_research_template2(self, soup) -> str:
        """Extract research from Template 2 (Article Title)"""
        try:
            research_content = []
            found_start = False
            
            # Look for any element containing research keywords
            for keyword in self.RESEARCH_START_KEYWORDS:
                for elem in soup.find_all(['p', 'h2', 'h3', 'h4', 'strong', 'div']):
                    elem_text = elem.get_text(strip=True)
                    if keyword in elem_text:
                        found_start = True
                        logger.debug(f"Found research start keyword '{keyword}' in {elem.name}")
                        
                        if elem_text != keyword and len(elem_text) > len(keyword) + 5:
                            content = elem_text.replace(keyword, '').strip()
                            if content and not any(stop in content for stop in self.RESEARCH_STOP_KEYWORDS):
                                research_content.append(content)
                        
                        for sibling in elem.find_next_siblings():
                            sibling_text = sibling.get_text(strip=True)
                            if any(stop in sibling_text for stop in self.RESEARCH_STOP_KEYWORDS):
                                logger.debug(f"Stopping at: {sibling_text[:50]}...")
                                break
                            if re.search(self.YEAR_PATTERN, sibling_text):
                                if re.match(self.YEAR_PATTERN, sibling_text.strip()):
                                    logger.debug("Stopping at year pattern")
                                    break
                            if re.search(self.DOI_PATTERN, sibling_text):
                                logger.debug("Stopping at DOI pattern")
                                break
                            if sibling_text and len(sibling_text) > 5:
                                if re.search(r'[(（]\d+[)）]|[①②③④⑤⑥⑦⑧⑨⑩]', sibling_text):
                                    research_content.append(sibling_text)
                                elif sibling.name in ['p', 'div', 'li']:
                                    research_content.append(sibling_text)
                        
                        if research_content:
                            break
                if found_start:
                    break
            
            if research_content:
                research_text = '\n'.join(research_content)
                research_text = self.clean_research_text(research_text)
                if research_text and len(research_text) > 5:
                    logger.info(f"Research extracted (Template 2): {len(research_text)} chars")
                    return research_text

            # Try meta description fallback
            meta_extracted = self.extract_from_meta_description(soup)
            if meta_extracted:
                logger.info("Research extracted from meta description (Template 2 fallback)")
                return meta_extracted

            return ""
        except Exception as e:
            logger.error(f"Error extracting research (Template 2): {e}")
            return ""

    def extract_publications_for_inference(self, soup) -> str:
        """Extract publication titles (kept for completeness though no AI inference)."""
        try:
            content_parts = []
            for keyword in self.PUBLICATION_KEYWORDS:
                for elem in soup.find_all(['p', 'h2', 'h3', 'h4', 'strong']):
                    if keyword in elem.get_text():
                        logger.debug(f"Found publication section: {keyword}")
                        count = 0
                        for sibling in elem.find_next_siblings():
                            if count >= 5:
                                break
                            text = sibling.get_text(strip=True)
                            if text and len(text) > 30:
                                text = re.sub(r'```[\s\S]*?```', '', text, flags=re.DOTALL)
                                text = re.sub(r'IF[=:]\s*[\d.]+', '', text, flags=re.IGNORECASE)
                                content_parts.append(text)
                                count += 1
                        if content_parts:
                            return '\n'.join(content_parts)
            return ""
        except Exception as e:
            logger.error(f"Error extracting publications: {e}")
            return ""

    def clean_research_text(self, text: str) -> str:
        """Clean extracted research text"""
        if not text:
            return ""
        
        text = html.unescape(text)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;|\xa0', ' ', text)
        text = re.sub(r'^\s*\b(19|20)\d{2}\b\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'\s*\b(19|20)\d{2}\b\s*$', '', text, flags=re.MULTILINE)
        text = re.sub(r'(doi|DOI)[\s:]*10\.\d{4,}[^\s]*', '', text)
        text = re.sub(r'https?://[^\s]+', '', text)
        text = re.sub(r'```[\s\S]*?```', '', text, flags=re.DOTALL)

        # Remove lines that contain misleading tokens
        for keyword in self.MISLEADING_CONTENT:
            if keyword in ['doi', 'DOI', 'http://', 'https://']:
                continue
            lines = text.split('\n')
            lines = [line for line in lines if keyword not in line]
            text = '\n'.join(lines)

        text = re.sub(r'\b(19|20)\d{2}年\d{1,2}月', '', text)
        text = re.sub(r'\bVol\.\s*\d+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bpp\.\s*\d+-\d+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'第\d+期', '', text)
        text = re.sub(r'第\d+卷', '', text)
        text = re.sub(r'IF[=:]\s*[\d.]+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'KATEX_INLINE_OPENSCIKATEX_INLINE_CLOSE|KATEX_INLINE_OPENEIKATEX_INLINE_CLOSE|KATEX_INLINE_OPENSSCIKATEX_INLINE_CLOSE', '', text, flags=re.IGNORECASE)
        text = re.sub(r'^[\d]+\.\s*$', '', text, flags=re.MULTILINE)

        # Collapse multiple spaces but keep newlines where present
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = '\n'.join([line.strip() for line in text.splitlines() if line.strip()])
        text = text.strip()

        if getattr(self.args, 'truncate', 0) and self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        
        return text

    def diagnose_page_structure(self, soup, url: str):
        """Diagnostic method to understand page structure"""
        logger.debug(f"\n=== Diagnosing page structure for {url} ===")
        template = self.detect_template_type(soup)
        logger.debug(f"Template type: {template}")
        if template == 'TEMPLATE_1':
            name_elem = soup.select_one('div.teacher-field.title > span.field-info')
            logger.debug(f"Name element present: {bool(name_elem)}")
            email_elem = soup.select_one('div.teacher-field.dh > span.field-info.i2')
            logger.debug(f"Email element present: {bool(email_elem)}")
            research_elem = soup.select_one('div.teacher-field.dh > span.field-info.i4')
            logger.debug(f"Research element present: {bool(research_elem)}")
        elif template == 'TEMPLATE_2':
            h1 = soup.find('h1', class_='arti_title')
            logger.debug(f"h1.arti_title present: {bool(h1)}")
            page_text = soup.get_text()
            found_keywords = [k for k in self.RESEARCH_START_KEYWORDS + self.ALTERNATIVE_RESEARCH_TRIGGERS if k in page_text]
            logger.debug(f"Found research keywords: {found_keywords}")
        logger.debug("=== End diagnosis ===\n")

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
        options.add_argument('--lang=zh-CN')

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(10)

    def close_driver(self):
        """Close Selenium WebDriver"""
        if self.driver:
            self.driver.quit()

    def random_delay(self):
        """Random delay between requests"""
        delay = random.uniform(self.args.delay_min, self.args.delay_max)
        time.sleep(delay)

    def scrape_profile(self, url: str) -> Optional[Dict[str, str]]:
        """Scrape a single faculty profile using only traditional extraction"""
        normalized_url = url.strip()
        if normalized_url in self.processed_urls:
            logger.info(f"Skipping duplicate URL: {url}")
            return None

        logger.info(f"Processing: {url}")
        
        for attempt in range(self.args.retries + 1):
            try:
                self.driver.get(url)
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(2)

                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                template = self.detect_template_type(soup)
                
                if self.args.debug:
                    self.diagnose_page_structure(soup, url)
                
                body_text = soup.body.get_text(strip=True) if soup.body else ""
                if len(body_text) < 100:
                    logger.warning(f"Page appears to be empty or invalid for {url}")
                    self.processed_urls.add(normalized_url)
                    return {
                        'name': 'Unknown',
                        'email': 'Not found',
                        'research_interest': 'Not found',
                        'profile_link': url
                    }
                
                if template == 'TEMPLATE_1':
                    name = self.extract_name_template1(soup)
                    email = self.extract_email_template1(soup)
                    research = self.extract_research_template1(soup)
                elif template == 'TEMPLATE_2':
                    name = self.extract_name_template2(soup)
                    email = self.extract_email_template2(soup)
                    research = self.extract_research_template2(soup)
                else:
                    logger.warning("Unknown template, trying both extraction methods")
                    name = self.extract_name_template1(soup) or self.extract_name_template2(soup)
                    email = self.extract_email_template1(soup) or self.extract_email_template2(soup)
                    research = self.extract_research_template1(soup) or self.extract_research_template2(soup)

                # As a final fallback, check meta description for research interest
                if not research or len(research) < 5:
                    meta_extracted = self.extract_from_meta_description(soup)
                    if meta_extracted:
                        research = meta_extracted
                        logger.info("Extracted research interest from meta description (final fallback)")

                if not name or name == "Unknown":
                    name = "Unknown"
                if not email:
                    email = "Not found"
                if not research or len(research) < 5:
                    research = "Not found"

                self.processed_urls.add(normalized_url)

                logger.info(f"Extraction -> Name: {name}, Email: {email}, Research: {research[:60]}{'...' if len(research)>60 else ''}")

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
                    return {
                        'name': 'Unknown',
                        'email': 'Not found',
                        'research_interest': 'Not found',
                        'profile_link': url
                    }
                time.sleep(3)
        
        return None

    def write_profile(self, profile: Dict[str, str], output_file: Path):
        """Write profile to output file"""
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"Name: {profile['name']}\n")
            f.write(f"Email: {profile['email']}\n")
            f.write(f"Research interest: {profile['research_interest']}\n")
            f.write(f"Profile link: {profile['profile_link']}\n")
            f.write("---\n\n")

    def write_json_profile(self, profiles: List[Dict], output_file: Path):
        """Write profiles to JSON file"""
        json_file = output_file.with_suffix('.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)

    def run(self):
        """Main execution function"""
        input_file = Path(self.args.input_file)
        if not input_file.exists():
            logger.error(f"Input file not found: {input_file}")
            return

        with open(input_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        logger.info(f"Found {len(urls)} URLs to process")

        output_file = Path(self.args.output_file)
        if output_file.exists() and not self.args.append:
            output_file.unlink()

        self.setup_driver()
        profiles_list = []
        
        try:
            processed_count = 0
            for i, url in enumerate(urls):
                if self.args.max_profiles > 0 and processed_count >= self.args.max_profiles:
                    logger.info(f"Reached maximum profile limit: {self.args.max_profiles}")
                    break

                profile = self.scrape_profile(url)
                if profile:
                    self.write_profile(profile, output_file)
                    profiles_list.append(profile)
                    processed_count += 1
                    logger.info(f"Processed {processed_count}/{len(urls)}: {profile['name']} - {profile['email']}")

                if i < len(urls) - 1:
                    self.random_delay()

            if self.args.json_output and profiles_list:
                self.write_json_profile(profiles_list, output_file)
                logger.info(f"Saved JSON output to {output_file.with_suffix('.json')}")
                
        finally:
            self.close_driver()

        logger.info(f"Completed! Processed {processed_count} profiles")
        logger.info(f"Results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Faculty Profile Scraper with Dual Template Support (no AI)'
    )

    parser.add_argument('--input-file', default='urls.txt', 
                        help='Input file containing URLs (one per line)')
    parser.add_argument('--output-file', default='output.txt', 
                        help='Output file for results')

    # Scraping arguments
    parser.add_argument('--headless', action='store_true', 
                        help='Run browser in headless mode')
    parser.add_argument('--delay-min', type=float, default=1.0, 
                        help='Minimum delay between requests (seconds)')
    parser.add_argument('--delay-max', type=float, default=3.0, 
                        help='Maximum delay between requests (seconds)')
    parser.add_argument('--max-profiles', type=int, default=0, 
                        help='Max number of profiles to process (0=unlimited)')
    parser.add_argument('--retries', type=int, default=2, 
                        help='Number of retries for failed requests')
    parser.add_argument('--truncate', type=int, default=4000, 
                        help='Max length for research text (0=no limit)')
    parser.add_argument('--append', action='store_true', 
                        help='Append to output file instead of overwriting')
    parser.add_argument('--json-output', action='store_true', 
                        help='Also save output as JSON')
    parser.add_argument('--debug', action='store_true',
                        help='Enable debug mode with diagnostic output')

    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    scraper = DualTemplateFacultyProfileScraper(args)
    scraper.run()


if __name__ == '__main__':
    main()
