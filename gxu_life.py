#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper - Updated for GXU-style profiles
Optimized for consistent structure with h1 names and 研究方向 sections
"""

import os
import argparse
import json
import logging
import random
import re
import time
import platform
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional, Set, List, Tuple

# HTTP and parsing
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

# For AI extraction
import openai
try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None
try:
    from groq import Groq
except ImportError:
    Groq = None
import google.generativeai as genai

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AIExtractor:
    """AI-powered research interest extractor (used only as fallback)"""

    def __init__(self, provider='openai', api_key=None, model=None):
        self.provider = provider
        self.model_name = model or (
            'gpt-3.5-turbo' if provider == 'openai'
            else 'claude-3-haiku-20240307' if provider == 'anthropic'
            else 'llama-3.1-70b-versatile' if provider == 'groq'
            else 'gemini-1.5-flash'
        )

        if provider == 'openai':
            key = api_key or os.getenv('OPENAI_API_KEY')
            if not key:
                raise RuntimeError("OPENAI_API_KEY not set.")
            openai.api_key = key
            self.client = openai

        elif provider == 'anthropic':
            if Anthropic is None:
                raise RuntimeError("anthropic not installed.")
            key = api_key or os.getenv('ANTHROPIC_API_KEY')
            if not key:
                raise RuntimeError("ANTHROPIC_API_KEY not set.")
            self.client = Anthropic(api_key=key)

        elif provider == 'groq':
            if Groq is None:
                raise RuntimeError("groq not installed.")
            key = api_key or os.getenv('GROQ_API_KEY')
            if not key:
                raise RuntimeError("GROQ_API_KEY not set.")
            self.client = Groq(api_key=key)

        elif provider == 'gemini':
            key = api_key or os.getenv('GOOGLE_API_KEY')
            if not key:
                raise RuntimeError("GOOGLE_API_KEY not set.")
            genai.configure(api_key=key)
            self.model = genai.GenerativeModel(self.model_name)

        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

    def extract_research_interests_from_content(self, content: str, is_chinese: bool = True) -> str:
        """Use AI to extract research interests, actively looking for keywords"""
        if not content.strip():
            return "Not found"
        
        prompt = f"""
分析以下网页内容，提取教师的研究兴趣。

网页内容：
{content[:4000]}

提取策略：
1. 首先查找这个关键词：研究方向：或 研究方向:
2. 如果找到"研究方向："，提取其后的研究描述内容（到下一个章节标题为止，如代表性论文：、主持承担的主要科研项目：、教学和科研成果：、发表论文：、科研项目：、指导的学生获奖：、专利：，或任何年份如2023, 2022, 2020, 2019, 2018等）
3. 如果没有找到"研究方向："部分，查找Publications, Research Projects, Papers, 近期发表文章, 代表性论文, 科研项目等部分
4. 如果找到论文或项目，根据论文标题和项目名称推断研究兴趣（提供2-3句话的简短总结，不要列举论文）
5. 研究兴趣应该是简短的学术描述，不应包含个人简历、教育背景、工作经历、年份日期等
6. 如果内容是PDF嵌入或无法解析，返回"Not found"

返回格式：
- 如果找到研究兴趣，直接返回研究兴趣文本
- 如果完全没有找到相关信息，返回"Not found"
"""

        try:
            if self.provider == 'openai':
                response = self.client.ChatCompletion.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are a research analyst specializing in extracting research interests from faculty profiles."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.1
                )
                result = response.choices[0].message.content.strip()

            elif self.provider == 'anthropic':
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=500,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}]
                )
                result = response.content[0].text.strip()

            elif self.provider == 'groq':
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are a research analyst specializing in extracting research interests from faculty profiles."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.1
                )
                result = response.choices[0].message.content.strip()

            elif self.provider == 'gemini':
                response = self.model.generate_content(prompt)
                result = (response.text or "").strip()
            
            # Clean up the result
            if not result or result.lower() in ['not found', 'none', 'n/a', '']:
                return "Not found"
            
            return result

        except Exception as e:
            logger.error(f"AI research extraction failed ({self.provider}): {str(e)}")
        
        return "Not found"


class GXUFacultyProfileScraper:
    """Scraper optimized for GXU-style faculty profiles with consistent structure"""

    # Research section start keyword (EXACT match required)
    RESEARCH_START_KEYWORD = '研究方向'
    
    # Stop keywords for research interest extraction
    RESEARCH_STOP_KEYWORDS = [
        '代表性论文：',
        '主持承担的主要科研项目：',
        '教学和科研成果：',
        '发表论文：',
        '科研项目：',
        '指导的学生获奖：',
        '专利：',
        '获奖情况：',
        '主要论文：',
        '学术论文：',
        '承担项目：',
        '主持项目：',
        '参与项目：',
        '教学情况：',
        '教学工作：',
        '社会兼职：',
        '学术兼职：',
        '荣誉称号：',
        '获得荣誉：',
        '指导学生：',
        '培养学生：',
        '个人简介：',
        '工作经历：',
        '教育经历：',
        '联系方式：'
    ]
    
    # Keywords that are misleading and should NOT be used as start triggers
    MISLEADING_KEYWORDS = [
        '研究',  # Too broad, appears everywhere
        '方向',  # Too generic
        '兴趣',  # Not used in Chinese academic context
        '工作',  # Appears in intro, not formal section
        '简介',  # Contains narrative, not structured interests
        '内容'   # Too vague
    ]

    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls: Set[str] = set()  # Track processed URLs to skip duplicates

        # Initialize AI extractor if enabled
        self.ai_extractor = None
        if args.use_ai:
            try:
                self.ai_extractor = AIExtractor(
                    provider=args.ai_provider,
                    api_key=args.ai_api_key,
                    model=args.ai_model
                )
                logger.info(f"AI provider initialized: {args.ai_provider}")
            except Exception as e:
                logger.error(f"Failed to initialize AI provider: {e}")
                self.ai_extractor = None

        # Groq fallback if requested
        self.groq_extractor = None
        if args.use_groq_fallback:
            try:
                groq_key = args.groq_api_key or os.getenv('GROQ_API_KEY')
                if groq_key:
                    self.groq_extractor = AIExtractor(
                        provider='groq',
                        api_key=groq_key,
                        model=args.groq_model
                    )
                    logger.info(f"Groq fallback initialized")
            except Exception as e:
                logger.error(f"Failed to initialize Groq fallback: {e}")
                self.groq_extractor = None

    def diagnose_page_structure(self, soup, url: str):
        """Diagnostic method to understand page structure"""
        logger.debug(f"\n=== Diagnosing page structure for {url} ===")
        
        # Check for h1
        h1 = soup.find('h1')
        if h1:
            logger.debug(f"✓ Found h1: {h1.get_text(strip=True)}")
        else:
            logger.debug("✗ No h1 found")
        
        # Check for email patterns
        email_pattern = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        emails = soup.find_all(string=email_pattern)
        if emails:
            logger.debug(f"✓ Found {len(emails)} email(s)")
        else:
            logger.debug("✗ No emails found")
        
        # Check for research keyword
        page_text = soup.get_text()
        if '研究方向' in page_text:
            logger.debug("✓ Found '研究方向' in page text")
            # Find all occurrences
            research_elements = soup.find_all(string=re.compile(r'研究方向'))
            logger.debug(f"  Found in {len(research_elements)} text node(s)")
            for elem in research_elements[:2]:  # Show first 2
                parent = elem.parent
                logger.debug(f"  Parent tag: <{parent.name}>, text: {elem[:50]}")
        else:
            logger.debug("✗ '研究方向' not found in page text")
        
        # Check page size
        page_size = len(page_text)
        logger.debug(f"Page text size: {page_size} characters")
        
        logger.debug("=== End diagnosis ===\n")

    def extract_name_gxu(self, soup) -> str:
        """Extract name from GXU-style profile - first h1 in main content"""
        # Strategy 1: Look for h1 in div#right (most common container)
        right_div = soup.find('div', id='right')
        if right_div:
            h1 = right_div.find('h1')
            if h1:
                name = h1.get_text(strip=True)
                if name:
                    logger.debug(f"Name found in div#right h1: {name}")
                    return name
        
        # Strategy 2: Look for h1 in div.xnew_font
        xnew_div = soup.find('div', class_='xnew_font')
        if xnew_div:
            h1 = xnew_div.find('h1')
            if h1:
                name = h1.get_text(strip=True)
                if name:
                    logger.debug(f"Name found in div.xnew_font h1: {name}")
                    return name
        
        # Strategy 3: Just find the first h1 on the page (fallback)
        h1 = soup.find('h1')
        if h1:
            name = h1.get_text(strip=True)
            # Filter out navigation or generic h1s
            if name and len(name) < 50 and not any(x in name.lower() for x in ['welcome', 'home', '首页', '学院']):
                logger.debug(f"Name found in first h1: {name}")
                return name
        
        return "Unknown"

    def extract_email_gxu(self, soup) -> Optional[str]:
        """Extract email from GXU-style profile"""
        # Find the h1 first to know where to start looking
        h1 = soup.find('h1')
        if not h1:
            logger.debug("No h1 found, cannot locate email section")
            return None
        
        # Strategy 1: Look for p tags after h1 containing E-mail: or @
        for p in h1.find_all_next('p'):
            p_text = p.get_text(strip=True)
            
            # Check for E-mail: pattern (with or without space)
            if 'E-mail:' in p_text or 'E-mail：' in p_text or 'Email:' in p_text or 'e-mail:' in p_text.lower():
                # Extract email after the label
                email_match = re.search(r'[Ee]-?mail[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', p_text, re.IGNORECASE)
                if email_match:
                    email = email_match.group(1)
                    logger.debug(f"Email found with E-mail label: {email}")
                    return email
            
            # Check for @ symbol without label
            if '@' in p_text:
                email_match = re.search(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', p_text)
                if email_match:
                    email = email_match.group(1)
                    logger.debug(f"Email found with @ symbol: {email}")
                    return email
            
            # Stop if we hit research section or other major sections
            if any(keyword in p_text for keyword in ['研究方向', '代表性论文', '科研项目']):
                break
        
        # Strategy 2: Check in the raw HTML for email patterns (sometimes in spans)
        html_text = str(soup)
        email_patterns = [
            r'[Ee]-?mail[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'\b([a-zA-Z0-9._%+-]+@gxu\.edu\.cn)\b',
            r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b'
        ]
        
        for pattern in email_patterns:
            match = re.search(pattern, html_text, re.IGNORECASE)
            if match:
                email = match.group(1) if '(' in pattern else match.group(0)
                logger.debug(f"Email found in HTML: {email}")
                return email
        
        return None

    def extract_research_interests_gxu(self, soup) -> str:
        """Extract research interests from GXU-style profile using exact keyword matching"""
        research_content = []
        
        # Strategy 1: Find the exact text node containing "研究方向："
        # This handles nested structures like <p><strong><span>研究方向：</span></strong></p>
        research_nodes = soup.find_all(string=re.compile(r'研究方向[:：]'))
        
        if research_nodes:
            logger.debug(f"Found {len(research_nodes)} text nodes with '研究方向'")
            
            for text_node in research_nodes:
                # Get the parent element that contains this text
                parent = text_node.parent
                
                # Navigate up to find the containing paragraph or div
                container = parent
                while container and container.name not in ['p', 'div', 'li', 'td', 'section']:
                    container = container.parent
                
                if not container:
                    container = parent
                
                logger.debug(f"Research keyword found in {container.name} tag")
                
                # Check if there's content after the keyword in the same element
                container_text = container.get_text(strip=True)
                # Split by the keyword and get what comes after
                parts = re.split(r'研究方向[:：]', container_text, maxsplit=1)
                if len(parts) > 1 and parts[1].strip():
                    text_after = parts[1].strip()
                    # Check it doesn't immediately start with a stop keyword
                    if not any(text_after.startswith(stop) for stop in self.RESEARCH_STOP_KEYWORDS):
                        research_content.append(text_after)
                        logger.debug(f"Found content in same element: {text_after[:50]}...")
                
                # Get following siblings of the container
                for sibling in container.find_next_siblings():
                    sibling_text = sibling.get_text(strip=True)
                    
                    # Stop conditions
                    if not sibling_text:
                        continue
                        
                    # Check for stop keywords
                    if any(stop in sibling_text for stop in self.RESEARCH_STOP_KEYWORDS):
                        logger.debug(f"Stopped at stop keyword: {sibling_text[:50]}...")
                        break
                    
                    # Check for year
                    if re.search(r'\b(19|20)\d{2}\b', sibling_text):
                        logger.debug(f"Stopped at year: {sibling_text[:50]}...")
                        break
                    
                    # Skip if it's another heading with 研究方向
                    if '研究方向' in sibling_text:
                        continue
                    
                    research_content.append(sibling_text)
                    
                    # Limit to reasonable amount of content
                    if len(' '.join(research_content)) > 1000:
                        break
                
                # If we found content, break (use first occurrence)
                if research_content:
                    break
        
        # Strategy 2: Search in a broader way if nothing found
        if not research_content:
            logger.debug("Trying broader search for research interests")
            
            # Look for elements that might contain the keyword
            for elem in soup.find_all(['p', 'div', 'span', 'strong', 'td']):
                elem_html = str(elem)
                elem_text = elem.get_text(strip=True)
                
                if '研究方向' in elem_text:
                    # Try to extract content after 研究方向
                    match = re.search(r'研究方向[:：]\s*(.+)', elem_text, re.DOTALL)
                    if match:
                        content = match.group(1).strip()
                        
                        # Clean up and check for stop keywords
                        for stop_keyword in self.RESEARCH_STOP_KEYWORDS:
                            if stop_keyword in content:
                                content = content.split(stop_keyword)[0]
                        
                        # Check for years
                        year_match = re.search(r'\b(19|20)\d{2}\b', content)
                        if year_match:
                            content = content[:year_match.start()]
                        
                        content = content.strip()
                        if content and len(content) > 10:
                            research_content = [content]
                            logger.debug(f"Found research via broader search: {content[:50]}...")
                            break
        
        # Strategy 3: Sometimes the content is in the very next element after a header
        if not research_content:
            logger.debug("Trying next element strategy")
            # Find any element with just "研究方向：" as its content
            for elem in soup.find_all(string=re.compile(r'^\s*研究方向[:：]\s*$')):
                parent = elem.parent
                
                # Get the top-level container
                container = parent
                while container.parent and container.parent.name in ['p', 'div', 'td', 'section']:
                    container = container.parent
                
                # Look for the next element with actual content
                next_elem = container.find_next_sibling()
                attempts = 0
                while next_elem and attempts < 5:
                    next_text = next_elem.get_text(strip=True)
                    if next_text and not any(stop in next_text for stop in self.RESEARCH_STOP_KEYWORDS):
                        if not re.search(r'\b(19|20)\d{2}\b', next_text):  # No year
                            research_content.append(next_text)
                            logger.debug(f"Found research in next element: {next_text[:50]}...")
                            break
                    next_elem = next_elem.find_next_sibling()
                    attempts += 1
                
                if research_content:
                    break
        
        # Join and clean the content
        if research_content:
            research = ' '.join(research_content)
            research = self.clean_research_text(research)
            if research:
                logger.info(f"Research interests extracted: {len(research)} characters")
                return research
        
        # Debug: Check if the keyword exists at all
        page_text = soup.get_text()
        if '研究方向' in page_text:
            logger.warning("Keyword '研究方向' found in page but couldn't extract content")
            # Log some context around the keyword for debugging
            index = page_text.find('研究方向')
            context = page_text[max(0, index-50):min(len(page_text), index+200)]
            logger.debug(f"Context around keyword: ...{context}...")
        else:
            logger.warning("Keyword '研究方向' not found in page text at all")
        
        return ""

    def clean_research_text(self, text: str) -> str:
        """Clean extracted research text"""
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove numbered list prefixes
        text = re.sub(r'^\d+[\.、]\s*', '', text)
        
        # Remove any trailing stop keywords that might have been included
        for stop_keyword in self.RESEARCH_STOP_KEYWORDS:
            if stop_keyword in text:
                text = text.split(stop_keyword)[0]
        
        # Remove years and everything after
        year_match = re.search(r'\b(19|20)\d{2}\b', text)
        if year_match:
            text = text[:year_match.start()]
        
        # Remove HTML entities
        text = re.sub(r'&[^;]+;', ' ', text)
        
        # Final cleanup
        text = text.strip()
        
        # Truncate if requested
        if self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        
        return text

    def extract_publications_or_projects(self, soup) -> str:
        """Extract recent publications or projects for AI inference"""
        content_parts = []
        
        # Look for publication sections
        pub_keywords = ['代表性论文', '发表论文', '主要论文', '学术论文', 
                       'Publications', 'Papers']
        
        for keyword in pub_keywords:
            elements = soup.find_all(string=re.compile(keyword))
            if elements:
                for element in elements:
                    parent = element.parent
                    count = 0
                    
                    # Get following siblings
                    for sibling in parent.find_next_siblings():
                        if count >= 5:  # Limit to 5 items
                            break
                        text = sibling.get_text(strip=True)
                        if text:
                            content_parts.append(text)
                            count += 1
                    
                    if content_parts:
                        logger.debug(f"Found {len(content_parts)} publications")
                        return '\n'.join(content_parts)
        
        # Look for project sections
        proj_keywords = ['科研项目', '主持承担的主要科研项目', '主持项目', 
                        'Research Projects', 'Projects']
        
        for keyword in proj_keywords:
            elements = soup.find_all(string=re.compile(keyword))
            if elements:
                for element in elements:
                    parent = element.parent
                    count = 0
                    
                    for sibling in parent.find_next_siblings():
                        if count >= 5:
                            break
                        text = sibling.get_text(strip=True)
                        if text:
                            content_parts.append(text)
                            count += 1
                    
                    if content_parts:
                        logger.debug(f"Found {len(content_parts)} projects")
                        return '\n'.join(content_parts)
        
        return ""

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
        """Scrape a single faculty profile"""
        # Normalize URL and check for duplicates
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
                time.sleep(2)  # Additional wait for dynamic content

                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                
                # Add diagnostics if in debug mode
                if self.args.debug:
                    self.diagnose_page_structure(soup, url)
                
                # Check if page is valid
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
                
                # Extract using GXU-specific methods
                name = self.extract_name_gxu(soup)
                email = self.extract_email_gxu(soup)
                research = self.extract_research_interests_gxu(soup)

                logger.info(f"Traditional extraction -> Name: {name}, Email: {email or 'Not found'}, Research: {len(research) if research else 0} chars")

                # AI fallback ONLY for missing research interests
                if (not research or len(research) < 10) and (self.ai_extractor or self.groq_extractor):
                    logger.info("Research not found via traditional extraction, trying AI...")
                    
                    # Get page content for AI
                    page_content = soup.get_text()[:5000]
                    
                    # Try primary AI provider
                    if self.ai_extractor:
                        ai_research = self.ai_extractor.extract_research_interests_from_content(
                            page_content,
                            is_chinese=True
                        )
                        if ai_research and ai_research != "Not found":
                            research = ai_research
                            logger.info(f"AI extracted research: {len(research)} chars")
                    
                    # Try Groq fallback if still no research
                    if (not research or research == "Not found") and self.groq_extractor:
                        logger.info("Trying Groq fallback...")
                        groq_research = self.groq_extractor.extract_research_interests_from_content(
                            page_content,
                            is_chinese=True
                        )
                        if groq_research and groq_research != "Not found":
                            research = groq_research
                            logger.info(f"Groq extracted research: {len(research)} chars")
                    
                    # Last resort: infer from publications/projects
                    if not research or research == "Not found":
                        logger.info("Attempting to infer research from publications/projects...")
                        pub_content = self.extract_publications_or_projects(soup)
                        if pub_content and self.ai_extractor:
                            inference_prompt = f"""Based on these publications/projects, infer the research interests (2-3 sentences in Chinese):
{pub_content}

Return only the research interests, not the titles."""
                            ai_research = self.ai_extractor.extract_research_interests_from_content(
                                inference_prompt,
                                is_chinese=True
                            )
                            if ai_research and ai_research != "Not found":
                                research = f"[Inferred] {ai_research}"
                                logger.info("Successfully inferred research from publications/projects")

                # Final defaults
                if not name or name == "Unknown":
                    name = "Unknown"
                if not email:
                    email = "Not found"
                if not research or len(research) < 5:
                    research = "Not found"

                # Mark URL as processed
                self.processed_urls.add(normalized_url)

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

        # Read URLs
        with open(input_file, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        logger.info(f"Found {len(urls)} URLs to process")

        # Prepare output file
        output_file = Path(self.args.output_file)
        if output_file.exists() and not self.args.append:
            output_file.unlink()

        # Setup driver
        self.setup_driver()
        profiles_list = []
        
        try:
            processed_count = 0
            for i, url in enumerate(urls):
                # Check max profiles limit
                if self.args.max_profiles > 0 and processed_count >= self.args.max_profiles:
                    logger.info(f"Reached maximum profile limit: {self.args.max_profiles}")
                    break

                # Process profile
                profile = self.scrape_profile(url)
                if profile:
                    self.write_profile(profile, output_file)
                    profiles_list.append(profile)
                    processed_count += 1
                    logger.info(f"Processed {processed_count}/{len(urls)}: {profile['name']} - {profile['email']}")

                # Delay between requests
                if i < len(urls) - 1:
                    self.random_delay()

            # Save JSON output if requested
            if self.args.json_output and profiles_list:
                self.write_json_profile(profiles_list, output_file)
                logger.info(f"Saved JSON output to {output_file.with_suffix('.json')}")
                
        finally:
            self.close_driver()

        logger.info(f"Completed! Processed {processed_count} profiles")
        logger.info(f"Results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Faculty Profile Scraper optimized for GXU-style profiles'
    )

    # File arguments
    parser.add_argument('--input-file', default='urls.txt', 
                        help='Input file containing URLs (one per line)')
    parser.add_argument('--output-file', default='output.txt', 
                        help='Output file for results')

    # AI arguments
    parser.add_argument('--use-ai', action='store_true', 
                        help='Use AI to extract research interests (only as fallback)')
    parser.add_argument('--ai-provider', 
                        choices=['openai', 'anthropic', 'gemini', 'groq'], 
                        default='openai',
                        help='Primary AI provider to use')
    parser.add_argument('--ai-api-key', 
                        help='API key for primary AI provider')
    parser.add_argument('--ai-model', 
                        help='Model name for primary AI provider')

    # Groq fallback arguments
    parser.add_argument('--use-groq-fallback', action='store_true',
                        help='Use Groq AI as fallback for research interest extraction')
    parser.add_argument('--groq-api-key', 
                        help='API key for Groq (or set GROQ_API_KEY env var)')
    parser.add_argument('--groq-model', 
                        default='llama-3.1-70b-versatile',
                        help='Groq model to use (default: llama-3.1-70b-versatile)')

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
    
    # Set logging level based on debug flag
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and run scraper
    scraper = GXUFacultyProfileScraper(args)
    scraper.run()


if __name__ == '__main__':
    main()