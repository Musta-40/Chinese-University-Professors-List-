#!/usr/bin/env python3
"""
Universal Faculty Profile Research Interest Scraper for Multiple Universities
Supports both English and Chinese format faculty pages
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

    def extract_chinese_research_interests(self, page_text: str) -> str:
        """Extract research interests from Chinese faculty pages"""
        prompt = f"""
从以下中文教师主页内容中提取研究方向信息。

请按以下优先级查找：
1. 首先查找标题包含"主要研究领域"、"研究简介"、"研究方向"、"研究内容"、"研究兴趣"等关键词的部分
2. 提取该部分的内容直到遇到"学术兼职"、"获奖及荣誉"、"代表性著作"、"教育背景"、"工作经历"等其他部分
3. 如果找不到明确的研究方向部分，请从"代表性著作"或"科研项目"中推断主要研究方向

页面内容：
{page_text[:8000]}

请只返回研究方向的具体内容（不要包含标题），如果确实找不到，返回"Not found"。
"""
        try:
            if self.provider == 'openai':
                response = self.client.ChatCompletion.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "你是一个专门提取教师研究方向的助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.1
                )
                return response.choices[0].message.content.strip()

            elif self.provider == 'anthropic':
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=500,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text.strip()

            elif self.provider == 'groq':
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "你是一个专门提取教师研究方向的助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.1
                )
                return response.choices[0].message.content.strip()

            elif self.provider == 'gemini':
                response = self.model.generate_content(prompt)
                return (response.text or "").strip()

        except Exception as e:
            logger.error(f"AI research extraction failed ({self.provider}): {str(e)}")
        
        return "Not found"

    def extract_chinese_email(self, page_text: str) -> str:
        """Extract email from Chinese faculty pages"""
        prompt = f"""
从以下中文教师主页内容中提取教师的个人电子邮箱。

查找规则：
1. 查找"电子邮箱"、"邮箱"、"E-mail"、"Email"等关键词后面的邮箱地址
2. 邮箱通常包含@符号，常见域名有@mail.buct.edu.cn、@buct.edu.cn等
3. 排除部门邮箱（如buctsmxy@126.com这种明显是部门的邮箱）
4. 只返回教师个人邮箱

页面内容：
{page_text[:5000]}

只返回邮箱地址，如果找不到返回"Not found"。
"""
        try:
            if self.provider == 'openai':
                response = self.client.ChatCompletion.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "你是一个专门提取邮箱地址的助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=100,
                    temperature=0.1
                )
                return response.choices[0].message.content.strip()

            elif self.provider == 'anthropic':
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=100,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text.strip()

            elif self.provider == 'groq':
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "你是一个专门提取邮箱地址的助手。"},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=100,
                    temperature=0.1
                )
                return response.choices[0].message.content.strip()

            elif self.provider == 'gemini':
                response = self.model.generate_content(prompt)
                return (response.text or "").strip()

        except Exception as e:
            logger.error(f"AI email extraction failed ({self.provider}): {str(e)}")
        
        return "Not found"


class SmartFacultyProfileScraper:
    """Enhanced scraper for multiple university faculty pages"""

    # Research identifiers for both Chinese and English
    RESEARCH_KEYWORDS = [
        '研究领域', '研究方向', '研究兴趣', '科研方向', '主要研究方向',
        '主要研究领域', '研究内容', '学术兴趣', '研究课题', '研究重点',
        '研究简介', '主要研究内容',
        'research interest', 'research interests', 'research area', 'research areas',
        'research direction', 'research directions', 'research field', 'research fields',
        'research focus', 'research foci', 'research topic', 'research topics',
        'academic interest', 'academic interests', 'current research'
    ]
    
    # Chinese stop keywords for research section
    CHINESE_RESEARCH_STOP_KEYWORDS = [
        '学术兼职', '获奖及荣誉', '代表性著作', '学术成绩', '教育背景',
        '工作经历', '教学工作', '科研项目', '发表论文', '专利',
        '教师寄语', '招生要求', '联系方式', '个人简历', '学历',
        '获奖', '成果', '项目', '课程', '教学', '社会服务',
        '学术成果', '科研成果', '教育经历', '个人主页'
    ]
    
    # English stop keywords
    ENGLISH_STOP_KEYWORDS = [
        'Selected Publications', 'Publications', 'Recent Publications', 'Key Publications',
        'Education', 'Professional Experience', 'Work Experience', 'Career',
        'Contact', 'Email', 'Phone', 'Address', 'Links', 'Biography',
        'Awards', 'Projects', 'Teaching', 'Courses'
    ]

    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls: Set[str] = set()
        self.processed_emails: Set[str] = set()

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

    # ----------------- Chinese format extractors -----------------

    def extract_chinese_name_from_title(self, soup) -> str:
        """Extract Chinese name from title tag"""
        title = soup.find('title')
        if title:
            name = title.get_text().strip()
            # Chinese names are typically 2-4 characters
            if 2 <= len(name) <= 5 and not any(c in name for c in ['-', '|', '.']):
                # Check if it contains Chinese characters
                if any('\u4e00' <= c <= '\u9fff' for c in name):
                    return name
        return ""

    def extract_chinese_email(self, soup) -> Optional[str]:
        """Extract email from Chinese faculty pages"""
        page_text = soup.get_text()
        page_html = str(soup)
        
        # Patterns for Chinese email extraction
        patterns = [
            r'(?:电子邮箱|邮箱|E-?mail)[：:]\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})',
            r'(?:电子邮箱|邮箱)[：:]\s*</?\w+>\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})',
            r'([A-Za-z0-9._%+\-]+@mail\.buct\.edu\.cn)',
            r'([A-Za-z0-9._%+\-]+@buct\.edu\.cn)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, page_html, re.IGNORECASE)
            if match:
                email = match.group(1)
                # Filter out department emails
                if not any(dept in email.lower() for dept in ['buctsmxy', 'department', 'office', 'admin']):
                    # Check if email looks personal (has personal identifier)
                    if len(email.split('@')[0]) >= 3:  # Username should be at least 3 chars
                        return email
        
        # Try text-based search
        match = re.search(r'(?:邮箱|电子邮箱)[：:]\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', 
                         page_text, re.IGNORECASE)
        if match:
            email = match.group(1)
            if not any(dept in email.lower() for dept in ['buctsmxy', 'department', 'office']):
                return email
        
        return None

    def extract_chinese_research_interests(self, soup) -> str:
        """Extract research interests from Chinese faculty pages"""
        page_text = soup.get_text()
        page_html = str(soup)
        
        # Keywords for research section
        research_keywords = ['主要研究领域', '研究简介', '研究方向', '研究内容', '研究兴趣', '科研方向']
        stop_keywords = self.CHINESE_RESEARCH_STOP_KEYWORDS
        
        # Try to find research section
        for keyword in research_keywords:
            # Pattern to match research section with proper boundaries
            pattern = rf'{keyword}[：:]\s*(.*?)(?:{"｜".join(stop_keywords)}|$)'
            match = re.search(pattern, page_text, re.DOTALL | re.IGNORECASE)
            
            if match:
                content = match.group(1).strip()
                # Clean up the content
                content = re.sub(r'<[^>]+>', ' ', content)  # Remove HTML tags
                content = re.sub(r'\s+', ' ', content)  # Normalize whitespace
                
                # Check for numbered list format (1. xxx 2. xxx 3. xxx)
                if re.search(r'[1-9]\.\s*[\u4e00-\u9fff]', content):
                    # Extract numbered items
                    items = re.findall(r'[1-9]\.\s*([^1-9]+?)(?=[1-9]\.|$)', content)
                    if items:
                        content = ' '.join(item.strip() for item in items)
                
                if len(content) > 10 and len(content) < 2000:
                    return content
        
        # Alternative: Look for research content in structured format
        # Search in HTML for better structure preservation
        for keyword in research_keywords:
            pattern = rf'>{keyword}[：:].*?</?\w+>(.*?)(?:</?(?:p|div|td)[^>]*>(?:{"｜".join(stop_keywords)}))'
            match = re.search(pattern, page_html, re.DOTALL | re.IGNORECASE)
            if match:
                content = match.group(1)
                # Clean HTML
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'&[^;]+;', ' ', content)
                content = re.sub(r'\s+', ' ', content).strip()
                
                if len(content) > 10:
                    return content
        
        return ""

    # ----------------- General extractors -----------------

    def extract_name(self, soup) -> str:
        """Extract name using multiple strategies for both formats"""
        # First check if it's a Chinese page
        page_text = soup.get_text()
        
        # Check for Chinese characters in the page
        if re.search(r'[\u4e00-\u9fff]', page_text[:1000]):  # Chinese detected in first 1000 chars
            # Try Chinese extraction
            name = self.extract_chinese_name_from_title(soup)
            if name:
                return name
            
            # Try to find name pattern in content (姓名：XXX)
            match = re.search(r'姓名[：:]\s*([\u4e00-\u9fff]{2,5})', page_text)
            if match:
                return match.group(1)
        
        # Try English extraction methods
        name = self.extract_name_from_meta(soup)
        if name:
            return name
        
        name = self.extract_name_from_title(soup)
        if name:
            return name
        
        return "Unknown"

    def extract_name_from_title(self, soup) -> str:
        """Extract name from title tag (English format)"""
        title = soup.find('title')
        if title:
            t = title.get_text().strip()
            # Handle formats like "Fei Qi-School of Life Sciences, Xiamen University"
            if '-' in t:
                cand = t.split('-')[0].strip()
                # Check if it looks like a name (2-3 words, alphabetic)
                if 2 <= len(cand.split()) <= 3 and all(word.isalpha() for word in cand.split()):
                    return cand
            # Handle formats like "Fei Qi | School of Life Sciences"
            if '|' in t:
                cand = t.split('|')[0].strip()
                if 2 <= len(cand.split()) <= 3 and all(word.isalpha() for word in cand.split()):
                    return cand
        return ""

    def extract_name_from_meta(self, soup) -> str:
        """Extract name from meta tags"""
        page_title_meta = soup.find('meta', attrs={'name': 'pageTitle'})
        if page_title_meta and page_title_meta.get('content'):
            content = page_title_meta.get('content').strip()
            if content and 1 < len(content) <= 50:
                return content
        
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            content = meta_desc.get('content').strip()
            m = re.search(r'^([A-Za-z\s]+),', content)
            if m:
                return m.group(1).strip()
        
        return ""

    def extract_email(self, soup) -> Optional[str]:
        """Extract email using multiple strategies for both formats"""
        page_text = soup.get_text()
        
        # Check if it's a Chinese page
        if re.search(r'[\u4e00-\u9fff]', page_text[:1000]):
            # Try Chinese email extraction
            email = self.extract_chinese_email(soup)
            if email:
                return email
        
        # Try English extraction methods
        email = self.extract_email_from_meta(soup)
        if email:
            return email
        
        # General email pattern
        page_html = str(soup)
        emails = re.findall(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', page_html)
        
        # Filter and return the most likely personal email
        for email in emails:
            if not any(dept in email.lower() for dept in ['department', 'office', 'admin', 'buctsmxy']):
                if len(email.split('@')[0]) >= 3:  # Username should be meaningful
                    return email
        
        return None

    def extract_email_from_meta(self, soup) -> Optional[str]:
        """Extract email from meta description tag"""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            content = meta_desc.get('content').strip()
            m = re.search(r'Email:\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', content, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    def extract_research_interests_comprehensive(self, soup) -> str:
        """Extract research interests for both Chinese and English formats"""
        page_text = soup.get_text()
        
        # Check if it's a Chinese page
        if re.search(r'[\u4e00-\u9fff]', page_text[:1000]):
            # Try Chinese research extraction
            research = self.extract_chinese_research_interests(soup)
            if research and len(research) > 10:
                return self.clean_text(research)
        
        # Try English format extraction
        research = self.extract_research_interests_english_format(soup)
        if research and len(research) > 10:
            return self.clean_text(research)
        
        # Try generic patterns
        for keyword in self.RESEARCH_KEYWORDS:
            for sep in ['：', ':']:
                # Build stop pattern based on language
                if any('\u4e00' <= c <= '\u9fff' for c in keyword):
                    stop_pattern = '|'.join(re.escape(kw) for kw in self.CHINESE_RESEARCH_STOP_KEYWORDS)
                else:
                    stop_pattern = '|'.join(re.escape(kw) for kw in self.ENGLISH_STOP_KEYWORDS)
                
                regex = re.compile(
                    rf'{re.escape(keyword)}\s*{re.escape(sep)}\s*(.+?)(?=(?:{stop_pattern})|$)',
                    re.IGNORECASE | re.DOTALL
                )
                m = regex.search(page_text)
                if m:
                    content = m.group(1).strip()
                    content = re.sub(r'\s+', ' ', content)
                    if content and len(content) > 10:
                        return self.clean_text(content)
        
        return ""

    def extract_research_interests_english_format(self, soup) -> str:
        """Extract research interests from English format pages"""
        for heading in soup.find_all(['h1', 'h2', 'h3', 'strong', 'b']):
            heading_text = heading.get_text().strip().lower()
            if any(kw in heading_text for kw in ['research area', 'research focus', 'research interest']):
                content_parts = []
                for elem in heading.find_all_next():
                    if elem.name in ['h1', 'h2', 'h3', 'strong', 'b']:
                        next_heading = elem.get_text().strip().lower()
                        if any(kw.lower() in next_heading for kw in self.ENGLISH_STOP_KEYWORDS):
                            break
                    
                    if elem.name == 'p':
                        text = elem.get_text().strip()
                        if text and len(text) > 10:
                            content_parts.append(text)
                
                if content_parts:
                    return " ".join(content_parts)
        
        return ""

    def clean_text(self, text: str) -> str:
        """Clean extracted text"""
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&[^;]+;', ' ', text)
        text = re.sub(r'[ \t\r\f\v]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n', text)
        text = text.strip()
        if self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        return text

    def extract_with_ai_fallback(self, soup, name: str, email: str, research: str) -> Tuple[str, str, str]:
        """Use AI only for missing fields"""
        page_text = soup.get_text()
        is_chinese = re.search(r'[\u4e00-\u9fff]', page_text[:1000])
        
        # Check what's missing
        email_missing = not email or email == "Not found"
        research_missing = not research or len(research) < 10
        
        if not email_missing and not research_missing:
            return name, email, research
        
        # Use AI for missing fields
        if self.ai_extractor:
            if email_missing and is_chinese:
                logger.info("Using AI to extract email from Chinese page...")
                ai_email = self.ai_extractor.extract_chinese_email(page_text)
                if ai_email and ai_email != "Not found" and '@' in ai_email:
                    email = ai_email
            
            if research_missing and is_chinese:
                logger.info("Using AI to extract research interests from Chinese page...")
                ai_research = self.ai_extractor.extract_chinese_research_interests(page_text)
                if ai_research and ai_research != "Not found":
                    research = ai_research
        
        # Groq fallback if still missing
        if self.groq_extractor:
            if email_missing and is_chinese:
                logger.info("Using Groq fallback for email extraction...")
                groq_email = self.groq_extractor.extract_chinese_email(page_text)
                if groq_email and groq_email != "Not found" and '@' in groq_email:
                    email = groq_email
            
            if research_missing and is_chinese:
                logger.info("Using Groq fallback for research extraction...")
                groq_research = self.groq_extractor.extract_chinese_research_interests(page_text)
                if groq_research and groq_research != "Not found":
                    research = groq_research
        
        # Set defaults for still missing fields
        if not email or email == "Not found":
            email = "Not found"
        if not research or len(research) < 10:
            research = "Not found"
        
        return name, email, research

    # ----------------- Selenium flow -----------------

    def setup_driver(self):
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
        options.add_argument('--lang=zh-CN,zh;q=0.9,en;q=0.8')  # Support Chinese

        service = Service(ChromeDriverManager().install())
        self.driver = webdriver.Chrome(service=service, options=options)
        self.driver.implicitly_wait(10)

    def close_driver(self):
        if self.driver:
            self.driver.quit()

    def random_delay(self):
        delay = random.uniform(self.args.delay_min, self.args.delay_max)
        time.sleep(delay)

    def scrape_profile(self, url: str) -> Optional[Dict[str, str]]:
        normalized_url = url.strip()
        if normalized_url in self.processed_urls:
            logger.info(f"Skipping duplicate URL: {url}")
            return None

        logger.info(f"Processing: {url}")
        for attempt in range(self.args.retries + 1):
            try:
                self.driver.get(url)
                WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                time.sleep(2)

                soup = BeautifulSoup(self.driver.page_source, 'html.parser')

                # Traditional extraction first
                name = self.extract_name(soup)
                email = self.extract_email(soup)
                research = self.extract_research_interests_comprehensive(soup)

                logger.info(f"Traditional -> Name: {name}, Email: {email or 'Not found'}, Research chars: {len(research) if research else 0}")

                if email and email in self.processed_emails:
                    logger.info(f"Skipping duplicate email: {email}")
                    return None

                # AI fallback ONLY for missing fields
                if self.ai_extractor or self.groq_extractor:
                    name, email, research = self.extract_with_ai_fallback(soup, name, email, research)

                # Defaults
                if not name or name == "Unknown":
                    name = "Unknown"
                if not email:
                    email = "Not found"
                if not research:
                    research = "Not found"

                self.processed_urls.add(normalized_url)
                if email and email != "Not found":
                    self.processed_emails.add(email)

                return {
                    'name': name,
                    'email': email,
                    'research_interest': research,
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
        with open(output_file, 'a', encoding='utf-8') as f:
            f.write(f"Name: {profile['name']}\n")
            f.write(f"Email: {profile['email']}\n")
            f.write(f"Research interest: {profile['research_interest']}\n")
            f.write(f"Profile link: {profile['profile_link']}\n")
            f.write("---\n\n")

    def write_json_profile(self, profiles: List[Dict], output_file: Path):
        json_file = output_file.with_suffix('.json')
        with open(json_file, 'w', encoding='utf-8') as f:
            json.dump(profiles, f, ensure_ascii=False, indent=2)

    def run(self):
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
        description='Universal Faculty Profile Scraper for Multiple Universities'
    )

    # File arguments
    parser.add_argument('--input-file', default='urls.txt', help='Input file containing URLs (one per line)')
    parser.add_argument('--output-file', default='output.txt', help='Output file for results')

    # AI arguments
    parser.add_argument('--use-ai', action='store_true', help='Use AI to extract missing fields (only as fallback)')
    parser.add_argument('--ai-provider', choices=['openai', 'anthropic', 'gemini', 'groq'], default='openai',
                        help='Primary AI provider to use')
    parser.add_argument('--ai-api-key', help='API key for primary AI provider')
    parser.add_argument('--ai-model', help='Model name for primary AI provider')

    # Groq fallback arguments
    parser.add_argument('--use-groq-fallback', action='store_true',
                        help='Use Groq AI as fallback for extraction')
    parser.add_argument('--groq-api-key', help='API key for Groq (or set GROQ_API_KEY env var)')
    parser.add_argument('--groq-model', default='llama-3.1-70b-versatile',
                        help='Groq model to use (default: llama-3.1-70b-versatile)')

    # Scraping arguments
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--delay-min', type=float, default=1.0, help='Minimum delay between requests (seconds)')
    parser.add_argument('--delay-max', type=float, default=3.0, help='Maximum delay between requests (seconds)')
    parser.add_argument('--max-profiles', type=int, default=0, help='Max number of profiles to process (0=unlimited)')
    parser.add_argument('--retries', type=int, default=2, help='Number of retries for failed requests')
    parser.add_argument('--truncate', type=int, default=4000, help='Max length for research text (0=no limit)')
    parser.add_argument('--append', action='store_true', help='Append to output file instead of overwriting')
    parser.add_argument('--json-output', action='store_true', help='Also save output as JSON')

    args = parser.parse_args()
    scraper = SmartFacultyProfileScraper(args)
    scraper.run()


if __name__ == '__main__':
    main()