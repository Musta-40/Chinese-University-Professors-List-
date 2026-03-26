#!/usr/bin/env python3
"""
Faculty Profile Scraper - Optimized for Chinese University Faculty Pages
Handles multiple template structures for faculty profiles
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


class ChineseUniversityFacultyScraper:
    """Specialized scraper for Chinese University faculty profiles with multiple template support"""
    
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
        s = re.sub(r'\xa0', ' ', s)  # Replace non-breaking spaces
        s = re.sub(r'&nbsp;', ' ', s)  # Replace HTML non-breaking spaces
        return s.strip()
    
    def clean_email(self, email: str) -> str:
        """Clean and format email address"""
        if not email:
            return "Not found"
        
        # Remove 'mailto:' if present
        email = email.replace('mailto:', '')
        
        # Replace AT with @ if needed
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
    
    # ================ Template Detection ================
    def detect_template_type(self, soup) -> str:
        """Detect which template the page uses"""
        
        # Template 3: Has peos_info div with Name: and E-mail: structure
        if soup.find('div', class_='peos_info'):
            peos_info = soup.find('div', class_='peos_info')
            if peos_info:
                text = peos_info.get_text()
                if 'Name:' in text or 'Name：' in text:
                    return 'TEMPLATE_3'
        
        # Template 1: Has box-name and box-title structure
        if soup.find('div', class_='box-name') and soup.find('div', class_='box-title'):
            return 'TEMPLATE_1'
        
        # Template 2: Has TRS_Editor with Principal Investigator text
        trs_editor = soup.find('div', class_='TRS_Editor') or soup.find('div', class_='trs_editor_view')
        if trs_editor:
            text = trs_editor.get_text()
            if 'Principal Investigator' in text or 'Principal Investigator：' in text:
                return 'TEMPLATE_2'
        
        # Check for variations in template 2
        if soup.find('table'):
            table = soup.find('table')
            if table:
                table_text = table.get_text()
                if 'Principal Investigator' in table_text:
                    return 'TEMPLATE_2'
        
        return 'UNKNOWN'
    
    # ================ Template 3 Extraction Methods (New) ================
    def extract_name_template3(self, soup) -> Optional[str]:
        """Extract name from Template 3 (peos_info structure)"""
        try:
            peos_info = soup.find('div', class_='peos_info')
            if peos_info:
                # Look for paragraph containing Name:
                for p in peos_info.find_all('p'):
                    p_text = p.get_text()
                    if 'Name:' in p_text or 'Name：' in p_text:
                        # Extract text after Name:
                        name_text = re.sub(r'Name[：:]\s*', '', p_text, flags=re.IGNORECASE)
                        name = self.normalize_text(name_text)
                        if name:
                            return name
                
                # Alternative: Look for span with class="strong" containing Name
                for span in peos_info.find_all('span', class_='strong'):
                    if 'Name' in span.get_text():
                        # Get the text after this span
                        parent = span.parent
                        if parent:
                            full_text = parent.get_text()
                            name_text = re.sub(r'Name[：:]\s*', '', full_text, flags=re.IGNORECASE)
                            name = self.normalize_text(name_text)
                            if name:
                                return name
                    
        except Exception as e:
            logger.debug(f"Error extracting name (Template 3): {e}")
        
        return None
    
    def extract_email_template3(self, soup) -> Optional[str]:
        """Extract email from Template 3"""
        try:
            peos_info = soup.find('div', class_='peos_info')
            if peos_info:
                # Look for paragraph containing E-mail:
                for p in peos_info.find_all('p'):
                    p_text = p.get_text()
                    if 'E-mail:' in p_text or 'E-mail：' in p_text or 'Email:' in p_text or 'Email：' in p_text:
                        # Extract text after E-mail:
                        email_text = re.sub(r'E-?mail[：:]\s*', '', p_text, flags=re.IGNORECASE)
                        email = self.normalize_text(email_text)
                        return self.clean_email(email)
                
                # Alternative: Look for span with class="strong" containing E-mail
                for span in peos_info.find_all('span', class_='strong'):
                    if 'mail' in span.get_text().lower():
                        # Get the text after this span
                        parent = span.parent
                        if parent:
                            full_text = parent.get_text()
                            email_text = re.sub(r'E-?mail[：:]\s*', '', full_text, flags=re.IGNORECASE)
                            email = self.normalize_text(email_text)
                            return self.clean_email(email)
                    
        except Exception as e:
            logger.debug(f"Error extracting email (Template 3): {e}")
        
        return None
    
    def extract_research_template3(self, soup) -> str:
        """Extract research interests from Template 3"""
        try:
            # Find the Research Interest header
            research_header = None
            
            # Look for h3 with class="box-tit" containing "Research Interest"
            for h3 in soup.find_all('h3', class_='box-tit'):
                h3_text = h3.get_text(strip=True)
                if 'Research Interest' in h3_text or 'Research Direction' in h3_text or '研究方向' in h3_text:
                    research_header = h3
                    break
            
            if not research_header:
                logger.debug("Research Interest header not found in Template 3")
                return ""
            
            # Find the parent container
            parent_container = research_header.parent
            if not parent_container:
                return ""
            
            # Look for the box-cont div that follows
            box_cont = parent_container.find('div', class_='box-cont')
            if not box_cont:
                # Try to find next sibling
                box_cont = research_header.find_next_sibling('div', class_='box-cont')
            
            if box_cont:
                # Look for trs_editor_view inside box-cont
                trs_editor = box_cont.find('div', class_=re.compile('trs_editor_view|TRS_Editor'))
                
                if trs_editor:
                    # Get all paragraphs inside
                    research_paragraphs = []
                    for p in trs_editor.find_all('p'):
                        text = p.get_text(strip=True)
                        if text and not self.is_stop_section(text):
                            research_paragraphs.append(text)
                    
                    if research_paragraphs:
                        research_text = '\n'.join(research_paragraphs)
                        return self.clean_research_text(research_text)
                else:
                    # Fallback: get all text from box-cont
                    text = box_cont.get_text(separator='\n', strip=True)
                    if text:
                        return self.clean_research_text(text)
            
            # Alternative approach: find next div after research header
            next_div = research_header.find_next_sibling('div')
            if next_div:
                text = next_div.get_text(separator='\n', strip=True)
                if text:
                    return self.clean_research_text(text)
                    
        except Exception as e:
            logger.debug(f"Error extracting research (Template 3): {e}")
        
        return ""
    
    def is_stop_section(self, text: str) -> bool:
        """Check if text indicates a stop section"""
        stop_keywords = [
            'Education & Professional Experience',
            'Selected Publications',
            'Education',
            'Publications',
            'Awards',
            'Patents',
            '教育经历',
            '发表论文',
            '获奖',
            '专利'
        ]
        
        for keyword in stop_keywords:
            if keyword in text and len(text) < 100:  # Likely a header
                return True
        return False
    
    # ================ Template 1 Extraction Methods ================
    def extract_name_template1(self, soup) -> Optional[str]:
        """Extract name from Template 1 (box-name structure)"""
        try:
            # Look for div with class box-name and h26
            name_div = soup.find('div', class_=['box-name h26', 'box-name'])
            if name_div:
                name = self.normalize_text(name_div.get_text())
                if name:
                    return name
                    
        except Exception as e:
            logger.debug(f"Error extracting name (Template 1): {e}")
        
        return None
    
    def extract_email_template1(self, soup) -> Optional[str]:
        """Extract email from Template 1"""
        try:
            # Method 1: Find div containing "E-mail：" or "E-mail:"
            for div in soup.find_all('div'):
                div_text = div.get_text()
                if 'E-mail：' in div_text or 'E-mail:' in div_text or 'Email：' in div_text:
                    # Look for span within this div
                    email_span = div.find('span')
                    if email_span:
                        email = self.normalize_text(email_span.get_text())
                        return self.clean_email(email)
                    
                    # If no span, try to extract from text
                    match = re.search(r'(?:E-mail|Email)[：:]\s*([^\s]+@[^\s]+)', div_text)
                    if match:
                        return self.clean_email(match.group(1))
            
            # Method 2: Look for any email pattern in the page
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            for text in soup.stripped_strings:
                match = re.search(email_pattern, text)
                if match:
                    return self.clean_email(match.group(0))
                    
        except Exception as e:
            logger.debug(f"Error extracting email (Template 1): {e}")
        
        return None
    
    def extract_research_template1(self, soup) -> str:
        """Extract research interests from Template 1"""
        try:
            # Find the Research Interests section
            research_title = None
            for title_div in soup.find_all('div', class_='box-title'):
                title_text = title_div.get_text(strip=True)
                if 'Research Interests' in title_text or 'Research Interest' in title_text or '研究方向' in title_text:
                    research_title = title_div
                    break
            
            if not research_title:
                logger.debug("Research Interests section not found in Template 1")
                return ""
            
            # Get the content from the next sibling box-txt
            research_content = []
            next_sibling = research_title.find_next_sibling()
            
            while next_sibling:
                # Stop if we hit the next section
                if next_sibling.name == 'div' and 'box-title' in next_sibling.get('class', []):
                    # Check if it's a stop section
                    section_text = next_sibling.get_text(strip=True)
                    stop_sections = ['Education/degrees', 'Education', 'Publication', 'Work experience', 
                                   '教育经历', '工作经历', '发表论文', '获奖']
                    if any(stop in section_text for stop in stop_sections):
                        break
                
                # Extract content from box-txt
                if next_sibling.name == 'div' and 'box-txt' in next_sibling.get('class', []):
                    content = next_sibling.get_text(separator='\n', strip=True)
                    if content:
                        research_content.append(content)
                
                next_sibling = next_sibling.find_next_sibling()
            
            # Join and clean the research content
            if research_content:
                full_content = '\n'.join(research_content)
                return self.clean_research_text(full_content)
                
        except Exception as e:
            logger.debug(f"Error extracting research (Template 1): {e}")
        
        return ""
    
    # ================ Template 2 Extraction Methods ================
    def extract_name_template2(self, soup) -> Optional[str]:
        """Extract name from Template 2 (Principal Investigator structure)"""
        try:
            # Find the main table
            table = soup.find('table')
            if not table:
                # Try to find it within TRS_Editor
                trs_editor = soup.find('div', class_=['TRS_Editor', 'trs_editor_view'])
                if trs_editor:
                    table = trs_editor.find('table')
            
            if table:
                first_td = table.find('td')
                if first_td:
                    td_text = first_td.get_text()
                    
                    # Extract name after "Principal Investigator：" or "Principal Investigator:"
                    patterns = [
                        r'Principal Investigator[：:]\s*([^,，\n]+)',
                        r'PI[：:]\s*([^,，\n]+)',
                        r'负责人[：:]\s*([^,，\n]+)'
                    ]
                    
                    for pattern in patterns:
                        match = re.search(pattern, td_text, re.IGNORECASE)
                        if match:
                            name = match.group(1).strip()
                            # Remove titles like Ph.D., Professor, etc.
                            name = re.sub(r'\s*(Ph\.?D\.?|Professor|Prof\.|Dr\.|博士|教授).*$', '', name, flags=re.IGNORECASE)
                            return self.normalize_text(name)
                            
        except Exception as e:
            logger.debug(f"Error extracting name (Template 2): {e}")
        
        return None
    
    def extract_email_template2(self, soup) -> Optional[str]:
        """Extract email from Template 2"""
        try:
            # Find the main table
            table = soup.find('table')
            if not table:
                trs_editor = soup.find('div', class_=['TRS_Editor', 'trs_editor_view'])
                if trs_editor:
                    table = trs_editor.find('table')
            
            if table:
                first_td = table.find('td')
                if first_td:
                    # Look for mailto link
                    mailto_link = first_td.find('a', href=lambda h: h and h.startswith('mailto:'))
                    if mailto_link:
                        email = mailto_link.get_text(strip=True)
                        return self.clean_email(email)
                    
                    # Look for email pattern in text
                    td_text = first_td.get_text()
                    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
                    match = re.search(email_pattern, td_text)
                    if match:
                        return self.clean_email(match.group(0))
                        
        except Exception as e:
            logger.debug(f"Error extracting email (Template 2): {e}")
        
        return None
    
    def extract_research_template2(self, soup) -> str:
        """Extract research interests from Template 2"""
        try:
            # Look for TRS_Editor or trs_editor_view
            trs_editor = soup.find('div', class_=['TRS_Editor', 'trs_editor_view'])
            if not trs_editor:
                # Fallback: look for any div that might contain the content
                trs_editor = soup.find('div', id=re.compile('TRS|trs'))
            
            if trs_editor:
                # Method 1: First strong paragraph is research interest
                first_p = trs_editor.find('p')
                if first_p:
                    strong = first_p.find('strong')
                    if strong:
                        research = self.normalize_text(strong.get_text())
                        if research and len(research) > 10:
                            return self.clean_research_text(research)
                    
                    # If first p has content but no strong tag
                    p_text = first_p.get_text(strip=True)
                    # Check if it's not a navigation/header text
                    if p_text and len(p_text) > 20 and not any(x in p_text.lower() for x in ['home', 'faculty', 'research group']):
                        # Check if it's before the table (which contains PI info)
                        table = trs_editor.find('table')
                        if table:
                            # Check if this p comes before the table
                            for elem in trs_editor.children:
                                if elem == first_p:
                                    return self.clean_research_text(p_text)
                                elif elem == table:
                                    break
                
                # Method 2: Look for any research-related content before the table
                research_content = []
                for elem in trs_editor.children:
                    if elem.name == 'table':
                        break  # Stop at table
                    if elem.name in ['p', 'div']:
                        text = elem.get_text(strip=True)
                        # Skip navigation or very short text
                        if text and len(text) > 20:
                            # Check if it contains stop keywords
                            stop_keywords = ['Synopsis', 'Education', 'Professional experience', 'Honours', 
                                           '简历', '教育', '工作经历', '荣誉']
                            if not any(stop in text for stop in stop_keywords):
                                research_content.append(text)
                
                if research_content:
                    return self.clean_research_text('\n'.join(research_content))
                    
        except Exception as e:
            logger.debug(f"Error extracting research (Template 2): {e}")
        
        return ""
    
    # ================ Fallback Extraction Methods ================
    def extract_name_fallback(self, soup) -> Optional[str]:
        """Fallback method to extract name from any template"""
        try:
            # Try various common patterns
            patterns = [
                ('h1', None),  # Name might be in h1
                ('h2', None),  # Or h2
                ('div', {'class': re.compile('name|title|header')}),  # Divs with name-related classes
                ('span', {'class': re.compile('name|title')}),  # Spans with name-related classes
            ]
            
            for tag, attrs in patterns:
                elements = soup.find_all(tag, attrs) if attrs else soup.find_all(tag)
                for elem in elements:
                    text = self.normalize_text(elem.get_text())
                    # Check if it looks like a name (not too long, not a sentence)
                    if text and 10 < len(text) < 50 and '。' not in text and '，' not in text:
                        # Filter out common non-name texts
                        skip_words = ['research', 'faculty', 'department', 'institute', 'university', 
                                    '研究', '学院', '大学', '部门']
                        if not any(skip in text.lower() for skip in skip_words):
                            return text
                            
        except Exception as e:
            logger.debug(f"Error in fallback name extraction: {e}")
        
        return None
    
    def extract_research_fallback(self, soup) -> str:
        """Fallback method to extract research from any template"""
        try:
            # Look for any section with research keywords
            research_keywords = ['research', 'interest', 'direction', 'focus', 'area', 
                               '研究', '方向', '兴趣', '领域']
            
            for keyword in research_keywords:
                # Search in all text
                for elem in soup.find_all(['div', 'p', 'section', 'article']):
                    text = elem.get_text(strip=True)
                    if keyword in text.lower() and len(text) > 50:
                        # Extract this and following content
                        content = [text]
                        next_elem = elem.find_next_sibling()
                        count = 0
                        while next_elem and count < 5:  # Limit to 5 elements
                            next_text = next_elem.get_text(strip=True)
                            if next_text and len(next_text) > 20:
                                # Check for stop conditions
                                stop_keywords = ['publication', 'education', 'experience', 'contact',
                                              '发表', '教育', '经历', '联系']
                                if any(stop in next_text.lower() for stop in stop_keywords):
                                    break
                                content.append(next_text)
                            next_elem = next_elem.find_next_sibling()
                            count += 1
                        
                        if len(content) > 1:
                            return self.clean_research_text('\n'.join(content))
                            
        except Exception as e:
            logger.debug(f"Error in fallback research extraction: {e}")
        
        return ""
    
    def clean_research_text(self, text: str) -> str:
        """Clean and format research text"""
        if not text:
            return ""
        
        # Remove any remaining HTML tags
        text = re.sub(r'<[^>]+>', ' ', text)
        text = html.unescape(text)
        
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\s*\n\s*', '\n', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove common artifacts
        text = re.sub(r'^[\d]+[\.、)]\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[•·▪▫◦‣⁃]\s*', '', text, flags=re.MULTILINE)
        
        # Remove "The main research areas" if it appears (it's redundant)
        text = re.sub(r'The main research areas.*?[:：]', '', text, flags=re.IGNORECASE)
        
        # Clean up any CSS or style content
        text = re.sub(r'font-[^;]+;?', '', text, flags=re.IGNORECASE)
        text = re.sub(r'margin-[^;]+;?', '', text, flags=re.IGNORECASE)
        text = re.sub(r'padding-[^;]+;?', '', text, flags=re.IGNORECASE)
        text = re.sub(r'text-indent[^;]+;?', '', text, flags=re.IGNORECASE)
        
        # Final cleanup
        text = text.strip()
        
        # Truncate if needed
        if self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        
        return text
    
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
        options.add_argument('--lang=zh-CN,en-US')
        options.add_argument('--window-size=1920,1080')
        
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
                time.sleep(2)  # Allow JS to render
                
                # Parse HTML
                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # Remove all style and script tags from soup first
                for style in soup.find_all('style'):
                    style.decompose()
                for script in soup.find_all('script'):
                    script.decompose()
                for noscript in soup.find_all('noscript'):
                    noscript.decompose()
                
                # Detect template type
                template = self.detect_template_type(soup)
                if self.args.debug:
                    logger.debug(f"Template detected: {template}")
                
                # Initialize results
                name = "Unknown"
                email = "Not found"
                research = "Not found"
                
                # Extract based on template
                if template == 'TEMPLATE_3':
                    name = self.extract_name_template3(soup) or self.extract_name_fallback(soup) or "Unknown"
                    email = self.extract_email_template3(soup) or "Not found"
                    research = self.extract_research_template3(soup) or self.extract_research_fallback(soup) or "Not found"
                    
                elif template == 'TEMPLATE_1':
                    name = self.extract_name_template1(soup) or self.extract_name_fallback(soup) or "Unknown"
                    email = self.extract_email_template1(soup) or "Not found"
                    research = self.extract_research_template1(soup) or self.extract_research_fallback(soup) or "Not found"
                    
                elif template == 'TEMPLATE_2':
                    name = self.extract_name_template2(soup) or self.extract_name_fallback(soup) or "Unknown"
                    email = self.extract_email_template2(soup) or "Not found"
                    research = self.extract_research_template2(soup) or self.extract_research_fallback(soup) or "Not found"
                    
                else:
                    # Try all methods
                    name = (self.extract_name_template3(soup) or
                           self.extract_name_template1(soup) or 
                           self.extract_name_template2(soup) or 
                           self.extract_name_fallback(soup) or 
                           "Unknown")
                    email = (self.extract_email_template3(soup) or
                            self.extract_email_template1(soup) or 
                            self.extract_email_template2(soup) or 
                            "Not found")
                    research = (self.extract_research_template3(soup) or
                               self.extract_research_template1(soup) or 
                               self.extract_research_template2(soup) or 
                               self.extract_research_fallback(soup) or 
                               "Not found")
                
                # Final validation
                if research and len(research) < 5:
                    research = "Not found"
                
                # Mark as processed
                self.processed_urls.add(normalized_url)
                
                # Log results
                logger.info(f"✓ Template: {template}")
                logger.info(f"✓ Name: {name}")
                logger.info(f"✓ Email: {email}")
                research_preview = research[:100] + "..." if len(research) > 100 else research
                logger.info(f"✓ Research: {research_preview}")
                
                return {
                    'name': name,
                    'email': email,
                    'research_interest': research,
                    'profile_link': url,
                    'template_type': template
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
                        'profile_link': url,
                        'template_type': 'ERROR'
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
            if self.args.debug:
                f.write(f"Template: {profile.get('template_type', 'Unknown')}\n")
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
                # Remove template_type from CSV if not in debug mode
                if not self.args.debug:
                    profiles_copy = [{k: v for k, v in p.items() if k != 'template_type'} for p in profiles]
                else:
                    profiles_copy = profiles
                    
                writer = csv.DictWriter(f, fieldnames=profiles_copy[0].keys())
                writer.writeheader()
                writer.writerows(profiles_copy)
    
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
        template_stats = {'TEMPLATE_1': 0, 'TEMPLATE_2': 0, 'TEMPLATE_3': 0, 'UNKNOWN': 0, 'ERROR': 0}
        
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
                    
                    # Update template statistics
                    template_type = profile.get('template_type', 'UNKNOWN')
                    template_stats[template_type] = template_stats.get(template_type, 0) + 1
                
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
            
            # Template statistics
            logger.info("\nTemplate Statistics:")
            for template, count in template_stats.items():
                if count > 0:
                    logger.info(f"  {template}: {count} profiles")
            
            if self.failed_urls:
                logger.warning(f"\n⚠ Failed URLs ({len(self.failed_urls)}):")
                for url in self.failed_urls:
                    logger.warning(f"  - {url}")
                    
        finally:
            self.close_driver()


# ================ CLI Entry Point ================
def main():
    parser = argparse.ArgumentParser(
        description='Chinese University Faculty Profile Scraper - Extract name, email, and research interests'
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
    scraper = ChineseUniversityFacultyScraper(args)
    scraper.run()


if __name__ == '__main__':
    main()