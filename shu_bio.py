#!/usr/bin/env python3
"""
Universal Faculty Profile Research Interest Scraper with AI
Enhanced version for Chinese university websites with multiple structure support.
"""

import os
import argparse
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Dict, Optional, Set, List, Tuple

# Load .env robustly (works in VS Code debugger or terminal)
from dotenv import load_dotenv, find_dotenv
_loaded = load_dotenv(find_dotenv(usecwd=True))
if not _loaded:
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

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
    """AI-powered content extractor"""

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
                raise RuntimeError("OPENAI_API_KEY not set. Put it in .env, env var, or pass --ai-api-key.")
            openai.api_key = key
            self.client = openai

        elif provider == 'anthropic':
            if Anthropic is None:
                raise RuntimeError("anthropic is not installed. pip install anthropic or choose another provider.")
            key = api_key or os.getenv('ANTHROPIC_API_KEY')
            if not key:
                raise RuntimeError("ANTHROPIC_API_KEY not set. Put it in .env, env var, or pass --ai-api-key.")
            self.client = Anthropic(api_key=key)

        elif provider == 'groq':
            if Groq is None:
                raise RuntimeError("groq is not installed. pip install groq or choose another provider.")
            key = api_key or os.getenv('GROQ_API_KEY')
            if not key:
                raise RuntimeError("GROQ_API_KEY not set. Put it in .env, env var, or pass --ai-api-key.")
            self.client = Groq(api_key=key)

        elif provider == 'gemini':
            key = api_key or os.getenv('GOOGLE_API_KEY')
            if not key:
                raise RuntimeError("GOOGLE_API_KEY not set. Put it in .env, env var, or pass --ai-api-key.")
            genai.configure(api_key=key)
            self.model = genai.GenerativeModel(self.model_name)

        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

    def extract_research_interests(self, page_content: str, faculty_name: str = "", verbatim: bool = False) -> str:
        """Use AI to extract research interests from page content"""

        # Truncate content if too long (to save tokens)
        max_content_length = 8000
        if len(page_content) > max_content_length:
            page_content = page_content[:max_content_length]

        if verbatim:
            prompt = f"""
            Extract ONLY the research interests/directions from this faculty webpage VERBATIM (exactly as written).
            
            Faculty Name: {faculty_name if faculty_name else "Unknown"}
            
            Page Content:
            {page_content}
            
            Instructions:
            1. Find sections labeled as: 研究领域, 研究方向, 研究兴趣, 主要研究领域, Research Interests, Research Areas
            2. Extract the EXACT text from these sections, preserving original formatting
            3. Do NOT include: 论文, 发表, 教学, 课程, 获奖, 专利, 项目, 教育背景, 工作经历, 代表性研究成果
            4. If found, return the exact text. If not found, return "Not found"
            
            Research Interests (verbatim):
            """
        else:
            prompt = f"""
            You are analyzing a university faculty member's webpage. Extract ONLY their research interests/directions.

            Faculty Name: {faculty_name if faculty_name else "Unknown"}

            Page Content:
            {page_content}

            Instructions:
            1. Look for research interests, research directions, research areas (研究领域, 研究方向, 研究兴趣, 主要研究领域).
            2. Extract specific research topics, methodologies, and areas of focus.
            3. Exclude: 论文, 发表, 代表性论文, 教育背景, 工作经历, 获奖, 专利, 课程, 教学, 项目, 代表性研究成果
            4. If research interests are scattered, compile them into a concise list.
            5. If nothing is found, return "Not found".
            6. Output as a short bullet list or compact paragraph (max 500 words).

            Research Interests:
            """

        try:
            if self.provider == 'openai':
                response = self.client.ChatCompletion.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You extract research interests from academic webpages with high precision."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.1 if verbatim else 0.2
                )
                return response.choices[0].message.content.strip()

            elif self.provider == 'anthropic':
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=500,
                    temperature=0.1 if verbatim else 0.2,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text.strip()

            elif self.provider == 'groq':
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You extract research interests from academic webpages with high precision."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.1 if verbatim else 0.2
                )
                return response.choices[0].message.content.strip()

            elif self.provider == 'gemini':
                response = self.model.generate_content(prompt)
                return (response.text or "").strip()

        except Exception as e:
            logger.error(f"AI extraction failed ({self.provider}): {str(e)}")
            return ""

        return ""


class SmartFacultyProfileScraper:
    """Enhanced scraper with AI capabilities and multiple structure support"""

    # Common research section identifiers (English and Chinese)
    RESEARCH_KEYWORDS = [
        # Chinese - prioritized
        '研究领域', '研究方向', '研究兴趣', '科研方向', '主要研究方向',
        '主要研究领域', '研究内容', '学术兴趣', '研究课题', '研究重点', 
        '研究专长', '学术方向', '科研领域', '主攻方向', '研究范围',
        # English
        'research interest', 'research interests', 'research area', 'research areas',
        'research direction', 'research directions', 'research field', 'research fields',
        'research focus', 'research foci', 'research topic', 'research topics',
        'academic interest', 'academic interests', 'current research'
    ]
    
    # Chinese stop keywords for better extraction
    CHINESE_STOP_KEYWORDS = [
        '论文', '发表', '代表性论文', '近五年', '主要成果', '出版', '著作',
        '项目', '教育背景', '工作经历', '简历', '个人简历', '代表性研究成果',
        '学历', '获奖', '专利', '课程', '教学', '学术兼职', '社会服务',
        '科研项目', '招生', '招生信息', '指导学生', '上一篇', '下一篇', 
        '上一页', '下一页', '主讲课程', '教授课程', '联系方式', '邮箱',
        '电话', '地址', '个人主页', '返回', '关闭', '近期代表性研究成果'
    ]

    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls: Set[str] = set()
        self.processed_emails: Set[str] = set()

        # Initialize primary AI extractor if enabled
        self.ai_extractor = None
        if args.use_ai:
            try:
                self.ai_extractor = AIExtractor(
                    provider=args.ai_provider,
                    api_key=args.ai_api_key,
                    model=args.ai_model
                )
                logger.info(f"Primary AI provider initialized: {args.ai_provider} (model: {self.ai_extractor.model_name})")
            except Exception as e:
                logger.error(f"Failed to initialize primary AI provider ({args.ai_provider}): {e}")
                self.ai_extractor = None
                
        # Initialize Groq as fallback if enabled
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
                    logger.info(f"Groq fallback initialized: {self.groq_extractor.model_name}")
            except Exception as e:
                logger.error(f"Failed to initialize Groq fallback: {e}")
                self.groq_extractor = None

    def setup_driver(self):
        """Initialize Selenium WebDriver"""
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
        # Add Chinese language support
        options.add_argument('--lang=zh-CN')

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(10)

    def close_driver(self):
        """Close WebDriver"""
        if self.driver:
            self.driver.quit()

    def random_delay(self):
        """Add random delay between requests"""
        delay = random.uniform(self.args.delay_min, self.args.delay_max)
        time.sleep(delay)

    def extract_from_table_structure(self, soup) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract from table structure (Structure 2)"""
        # Find all tables or tbody elements
        for table_container in soup.find_all(['table', 'tbody']):
            rows = table_container.find_all('tr')
            
            if len(rows) >= 4:
                # Try to extract from 4-row structure
                for i in range(len(rows) - 3):
                    row1 = rows[i]
                    row2 = rows[i+1] if i+1 < len(rows) else None
                    row3 = rows[i+2] if i+2 < len(rows) else None
                    row4 = rows[i+3] if i+3 < len(rows) else None
                    
                    if not all([row1, row2, row4]):
                        continue
                    
                    # Extract text from each row
                    row1_text = row1.get_text(strip=True)
                    row2_text = row2.get_text(strip=True) if row2 else ""
                    row4_text = row4.get_text(strip=True) if row4 else ""
                    
                    # Check if this looks like a faculty profile
                    name = None
                    research = None
                    email = None
                    
                    # Extract name from row 1
                    if '姓名' in row1_text:
                        name = re.sub(r'姓名[：:]', '', row1_text).strip()
                    elif re.match(r'^[\u4e00-\u9fa5]{2,4}$', row1_text):
                        name = row1_text
                    elif row1_text and len(row1_text) <= 20:
                        # Check last td in row1 for name
                        td_elements = row1.find_all('td')
                        if td_elements:
                            last_td_text = td_elements[-1].get_text(strip=True)
                            if re.match(r'^[\u4e00-\u9fa5]{2,4}$', last_td_text):
                                name = last_td_text
                    
                    # Extract research from row 2
                    if '研究方向' in row2_text or '研究领域' in row2_text:
                        research = re.sub(r'(研究方向|研究领域)[：:]', '', row2_text).strip()
                    elif row2_text and not any(kw in row2_text for kw in ['职位', '教授', '博士', '硕士', '导师']):
                        # Check if it's research content
                        if len(row2_text) > 5 and not row2_text.isdigit():
                            research = row2_text
                    
                    # Extract email from row 4
                    email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
                    email_match = re.search(email_pattern, row4_text)
                    if email_match:
                        email = email_match.group(0)
                    
                    # If we found meaningful data, return it
                    if name or research or email:
                        return name, email, research
        
        return None, None, None

    def extract_from_meta_and_html(self, soup) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract from Structure 1 (META description and HTML patterns)"""
        name = None
        email = None
        research = None
        
        # Extract name from title tag
        title = soup.find('title')
        if title:
            title_text = title.get_text().strip()
            # Handle "Name-University" format
            if '-' in title_text or '—' in title_text:
                name_part = re.split(r'[-–—]', title_text)[0].strip()
                if name_part and 1 < len(name_part) <= 20:
                    name = name_part
        
        # Extract from META description
        meta_desc = soup.find('meta', attrs={'name': 'description', 'content': True})
        if meta_desc:
            content = meta_desc.get('content', '')
            
            # Extract email from META
            email_patterns = [
                r'E-mail[：:]\s*([\w\.-]+@[\w\.-]+\.edu\.cn)',
                r'Email[：:]\s*([\w\.-]+@[\w\.-]+\.edu\.cn)',
                r'邮箱[：:]\s*([\w\.-]+@[\w\.-]+\.edu\.cn)',
            ]
            
            for pattern in email_patterns:
                match = re.search(pattern, content, re.IGNORECASE)
                if match:
                    email = match.group(1)
                    break
            
            # If no email with prefix, try general pattern
            if not email:
                email_match = re.search(r'([\w\.-]+@[\w\.-]+\.edu\.cn)', content)
                if email_match:
                    email = email_match.group(1)
            
            # Try to extract research from META
            if '研究领域' in content:
                research_match = re.search(r'研究领域[：:](.+?)(?:。|$)', content)
                if research_match:
                    research = research_match.group(1).strip()
        
        # Extract research from HTML patterns
        if not research:
            page_html = str(soup)
            
            # Pattern 1: <strong>研究领域：</strong> followed by content
            patterns = [
                (r'<strong>研究领域[：:]?</strong>\s*</span>\s*</p>\s*<p[^>]*>\s*<span[^>]*>([^<]+)</span>', 1),
                (r'<strong>研究方向[：:]?</strong>\s*</span>\s*</p>\s*<p[^>]*>\s*<span[^>]*>([^<]+)</span>', 1),
                (r'<strong>主要研究领域[：:]?</strong>\s*</span>\s*</p>\s*<p[^>]*>\s*<span[^>]*>([^<]+)</span>', 1),
                (r'>研究领域[：:]</strong>.*?<p[^>]*>.*?<span[^>]*>([^<]+)</span>', 1),
                (r'>主要研究领域[：:]([^<]+)<', 1),
            ]
            
            for pattern, group_num in patterns:
                match = re.search(pattern, page_html, re.IGNORECASE | re.DOTALL)
                if match:
                    content = match.group(group_num).strip()
                    content = re.sub(r'<[^>]+>', '', content)
                    content = re.sub(r'&[^;]+;', ' ', content)
                    content = content.strip()
                    
                    if content and len(content) > 10:
                        # Stop at stop keywords
                        for stop_kw in self.CHINESE_STOP_KEYWORDS:
                            if stop_kw in content:
                                content = content.split(stop_kw)[0].strip()
                                break
                        if content:
                            research = content
                            break
        
        # Extract email from HTML if not found in META
        if not email:
            page_html = str(soup)
            email_patterns = [
                r'>E-mail[：:]\s*([\w\.-]+@[\w\.-]+\.edu\.cn)',
                r'>Email[：:]\s*([\w\.-]+@[\w\.-]+\.edu\.cn)',
            ]
            
            for pattern in email_patterns:
                match = re.search(pattern, page_html, re.IGNORECASE)
                if match:
                    email = match.group(1)
                    break
        
        return name, email, research

    def extract_research_interests_comprehensive(self, soup) -> str:
        """Comprehensive research extraction trying all methods"""
        # Method 1: Try table structure extraction
        _, _, research = self.extract_from_table_structure(soup)
        if research and len(research) > 10:
            return self.clean_text(research)
        
        # Method 2: Try META and HTML pattern extraction
        _, _, research = self.extract_from_meta_and_html(soup)
        if research and len(research) > 10:
            return self.clean_text(research)
        
        # Method 3: Look for research sections in paragraphs
        for p in soup.find_all('p'):
            p_html = str(p)
            p_text = p.get_text().strip()
            
            # Check if paragraph contains research keywords
            for keyword in self.RESEARCH_KEYWORDS:
                if keyword in p_text:
                    # Try to extract content after keyword
                    parts = re.split(rf'{re.escape(keyword)}[：:]?\s*', p_text, 1)
                    if len(parts) > 1:
                        content = parts[1].strip()
                        
                        # Check if there's a span with the actual content
                        if '<span' in p_html:
                            span_match = re.search(r'<span[^>]*>([^<]+)</span>', p_html)
                            if span_match:
                                span_content = span_match.group(1).strip()
                                if len(span_content) > len(content):
                                    content = span_content
                        
                        # Clean and validate
                        if content and len(content) > 10:
                            # Stop at stop keywords
                            for stop_kw in self.CHINESE_STOP_KEYWORDS[:10]:
                                if stop_kw in content:
                                    content = content.split(stop_kw)[0].strip()
                                    break
                            
                            if content and len(content) > 10:
                                # Check next paragraph if content seems to continue
                                next_p = p.find_next_sibling('p')
                                if next_p:
                                    next_text = next_p.get_text().strip()
                                    # Only add if it doesn't contain stop keywords
                                    if next_text and not any(stop in next_text[:50] for stop in self.CHINESE_STOP_KEYWORDS[:10]):
                                        content += ' ' + next_text
                                
                                return self.clean_text(content)
        
        # Method 4: Text-based extraction
        page_text = soup.get_text("\n")
        
        # Build stop pattern
        stop_pattern = '|'.join(re.escape(kw) for kw in self.CHINESE_STOP_KEYWORDS)
        
        for keyword in self.RESEARCH_KEYWORDS:
            for sep in ['：', ':']:
                pattern = re.compile(
                    rf'{re.escape(keyword)}\s*{re.escape(sep)}\s*(.+?)(?=(?:{stop_pattern})|$)',
                    re.IGNORECASE | re.DOTALL
                )
                m = pattern.search(page_text)
                if m:
                    content = m.group(1).strip()
                    content = re.sub(r'\s+', ' ', content)
                    if content and len(content) > 10:
                        lines = content.split('\n')[:10]
                        content = '\n'.join(lines)
                        return self.clean_text(content)
        
        return ""

    def extract_email(self, soup) -> Optional[str]:
        """Extract email address from page"""
        # Try Structure 1 (META and HTML)
        _, email, _ = self.extract_from_meta_and_html(soup)
        if email:
            return email
        
        # Try Structure 2 (Table)
        _, email, _ = self.extract_from_table_structure(soup)
        if email:
            return email
        
        # Fallback to text search
        page_text = soup.get_text(" ")
        email_patterns = [
            r'电子邮箱[：:]\s*([\w\.-]+@[\w\.-]+\.\w+)',
            r'邮箱[：:]\s*([\w\.-]+@[\w\.-]+\.\w+)',
            r'Email[：:]\s*([\w\.-]+@[\w\.-]+\.\w+)',
            r'E-mail[：:]\s*([\w\.-]+@[\w\.-]+\.\w+)',
        ]
        
        for pattern in email_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # General email pattern
        email_pattern = r'[\w\.-]+@[\w\.-]+\.edu\.cn'
        emails = re.findall(email_pattern, page_text)
        return emails[0] if emails else None

    def extract_name(self, soup) -> str:
        """Extract faculty name from page"""
        # Try Structure 1 (META and HTML)
        name, _, _ = self.extract_from_meta_and_html(soup)
        if name:
            return name
        
        # Try Structure 2 (Table)
        name, _, _ = self.extract_from_table_structure(soup)
        if name:
            return name
        
        # Fallback to title tag
        title = soup.find('title')
        if title:
            title_text = title.get_text().strip()
            title_text = re.sub(r'[-–—\|].*$', '', title_text).strip()
            title_text = re.sub(r'(教授|副教授|讲师|博士|老师|简介|主页|个人主页).*$', '', title_text).strip()
            if title_text and 1 < len(title_text) <= 20:
                return title_text
        
        # Look for name patterns in text
        page_text = soup.get_text()
        name_patterns = [
            r'姓名[：:]\s*([^\s,，]+)',
            r'教师姓名[：:]\s*([^\s,，]+)',
            r'Name[：:]\s*([^\s,，]+)',
        ]
        
        for pattern in name_patterns:
            match = re.search(pattern, page_text)
            if match:
                name = match.group(1).strip()
                if name and 1 < len(name) <= 20:
                    return name
        
        return "Unknown"

    def clean_text(self, text: str) -> str:
        """Clean extracted text"""
        text = re.sub(r'<[^>]+>', '', text)           # strip HTML
        text = re.sub(r'&[^;]+;', ' ', text)          # strip HTML entities
        text = re.sub(r'[ \t\r\f\v]+', ' ', text)     # collapse spaces
        text = re.sub(r'\n\s*\n+', '\n', text)        # collapse blank lines
        text = text.strip()

        if self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        return text

    def extract_research_interests_ai(self, soup, faculty_name: str, use_groq_verbatim: bool = False) -> str:
        """Use AI to extract research interests - ONLY as last resort"""
        # Remove noisy tags and get text
        for script in soup(["script", "style", "meta", "link", "noscript"]):
            script.decompose()
        page_text = soup.get_text(" ")
        page_text = re.sub(r'\s+', ' ', page_text).strip()
        page_text = page_text[:10000]  # token safety

        # Try primary AI first
        if self.ai_extractor and not use_groq_verbatim:
            result = self.ai_extractor.extract_research_interests(page_text, faculty_name)
            if result and result.lower() != "not found":
                return result
        
        # Try Groq verbatim extraction as fallback
        if self.groq_extractor and (use_groq_verbatim or self.args.use_groq_fallback):
            logger.info(f"Using Groq for verbatim extraction: {faculty_name}")
            result = self.groq_extractor.extract_research_interests(page_text, faculty_name, verbatim=True)
            if result and result.lower() != "not found":
                return result
        
        return ""

    def scrape_profile(self, url: str) -> Optional[Dict[str, str]]:
        """Scrape a single faculty profile"""
        normalized_url = url.strip()
        if normalized_url in self.processed_urls:
            logger.info(f"Skipping duplicate URL: {url}")
            return None

        logger.info(f"Processing: {url}")

        for attempt in range(self.args.retries + 1):
            try:
                self.driver.get(url)

                # Wait for body
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(2)  # Wait for dynamic content

                soup = BeautifulSoup(self.driver.page_source, 'html.parser')

                # Extract basics
                name = self.extract_name(soup)
                email = self.extract_email(soup)

                if email and email in self.processed_emails:
                    logger.info(f"Skipping duplicate email: {email}")
                    return None

                # Extract research interests - prioritize traditional methods
                research_interests = ""
                
                # 1. ALWAYS try comprehensive traditional extraction first
                logger.info(f"Trying comprehensive traditional extraction for: {name}")
                research_interests = self.extract_research_interests_comprehensive(soup)
                
                # Log what we found with traditional methods
                if research_interests:
                    logger.info(f"Traditional extraction successful for {name}: {len(research_interests)} chars")
                else:
                    logger.info(f"Traditional extraction failed for {name}")
                
                # 2. ONLY use AI if traditional extraction completely fails or is too short
                if not research_interests or len(research_interests) < 10:
                    logger.info(f"Traditional extraction insufficient for {name} (found: {len(research_interests) if research_interests else 0} chars)")
                    if self.ai_extractor:
                        logger.info(f"Using AI as fallback for: {name}")
                        ai_result = self.extract_research_interests_ai(soup, name)
                        if ai_result and len(ai_result) > len(research_interests):
                            research_interests = ai_result
                            logger.info(f"AI extraction successful for {name}: {len(research_interests)} chars")
                
                # 3. Last resort: Groq verbatim
                if (not research_interests or research_interests.lower() == "not found") and self.groq_extractor:
                    logger.info(f"Using Groq verbatim as final fallback for: {name}")
                    groq_result = self.extract_research_interests_ai(soup, name, use_groq_verbatim=True)
                    if groq_result:
                        research_interests = groq_result
                        logger.info(f"Groq extraction successful for {name}: {len(research_interests)} chars")

                if not research_interests:
                    research_interests = "Not found"

                self.processed_urls.add(normalized_url)
                if email:
                    self.processed_emails.add(email)

                return {
                    'name': name,
                    'email': email or 'Not found',
                    'research_interest': research_interests,
                    'profile_link': url
                }

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                if attempt == self.args.retries:
                    return {
                        'name': 'Unknown',
                        'email': 'Not found',
                        'research_interest': f'<FAILED: {str(e)}>',
                        'profile_link': url
                    }
                time.sleep(3)

        return None

    def write_profile(self, profile: Dict[str, str], output_file: Path):
        """Write profile to output file (plain text)"""
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
        """Main execution method"""
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
                    logger.info(f"Processed {processed_count}/{len(urls)}: {profile['name']}")

                if i < len(urls) - 1:
                    self.random_delay()

            if self.args.json_output and profiles_list:
                self.write_json_profile(profiles_list, output_file)
                logger.info(f"Saved JSON output to {output_file.with_suffix('.json')}")

        finally:
            self.close_driver()

        logger.info(f"Completed! Processed {processed_count} profiles")


def main():
    parser = argparse.ArgumentParser(
        description='Smart Faculty Profile Scraper with AI Support (Multi-structure Chinese Universities)'
    )

    # File arguments
    parser.add_argument('--input-file', default='urls.txt', help='Input file containing URLs (one per line)')
    parser.add_argument('--output-file', default='output.txt', help='Output file for results')

    # AI arguments
    parser.add_argument('--use-ai', action='store_true', help='Use AI to extract research interests (only as fallback)')
    parser.add_argument('--ai-provider', choices=['openai', 'anthropic', 'gemini', 'groq'], default='openai', 
                        help='Primary AI provider to use')
    parser.add_argument('--ai-api-key', help='API key for primary AI provider')
    parser.add_argument('--ai-model', help='Model name for primary AI provider')
    
    # Groq fallback arguments
    parser.add_argument('--use-groq-fallback', action='store_true', 
                        help='Use Groq AI as fallback for verbatim extraction when primary methods fail')
    parser.add_argument('--groq-api-key', help='API key for Groq (or set GROQ_API_KEY env var)')
    parser.add_argument('--groq-model', default='llama-3.1-70b-versatile', 
                        help='Groq model to use (default: llama-3.1-70b-versatile)')

    # Scraping arguments
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--delay-min', type=float, default=1.0, help='Minimum delay between requests (seconds)')
    parser.add_argument('--delay-max', type=float, default=3.0, help='Maximum delay between requests (seconds)')
    parser.add_argument('--max-profiles', type=int, default=0, help='Maximum number of profiles to process (0 for unlimited)')
    parser.add_argument('--retries', type=int, default=2, help='Number of retries for failed requests')
    parser.add_argument('--truncate', type=int, default=4000, help='Max length for research interests text (0 for no limit)')
    parser.add_argument('--append', action='store_true', help='Append to output file instead of overwriting')
    parser.add_argument('--json-output', action='store_true', help='Also save output as JSON')

    args = parser.parse_args()

    scraper = SmartFacultyProfileScraper(args)
    scraper.run()


if __name__ == '__main__':
    main()