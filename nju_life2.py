#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper - NJU University Style
Optimized for profiles with h1.news_title names and h3.tit > 研究方向 research sections
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
from bs4 import BeautifulSoup, NavigableString

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
分析以下网页内容，提取教师的研究兴趣/研究方向。

网页内容：
{content[:4000]}

提取策略：
1. 首先查找这些关键词：研究方向，研究领域，研究兴趣，主要从事，目前从事
2. 如果找到上述关键词，提取其后的研究描述内容
3. 如果没有找到研究方向，查找"发布"、"科研成果"、"代表性论文"、"科研项目"等部分
4. 如果找到论文或项目标题，根据这些推断研究兴趣（提供2-3句话的简短总结）
5. 研究兴趣应该是简短的学术描述，不应包含个人简历、教育背景、工作经历、年份日期、DOI号码等
6. 不要提取联系方式、办公地点、Email等信息

返回格式：
- 如果找到研究兴趣，直接返回研究兴趣文本
- 如果完全没有找到相关信息，返回"Not found"
"""

        try:
            result = ""
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
                # depending on library, adapt if necessary
                result = getattr(response, "content", "") or ""
                if isinstance(result, list) and len(result) > 0:
                    # attempt safe extraction
                    result = getattr(result[0], "text", "") or ""
                result = str(result).strip()

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


class NJUFacultyProfileScraper:
    """Scraper optimized for NJU-style faculty profiles"""
    
    # Primary research direction keyword
    RESEARCH_START_KEYWORD = '研究方向'
    
    # Alternative research triggers (rarely used)
    ALTERNATIVE_RESEARCH_TRIGGERS = [
        '研究领域', '研究兴趣', '主要从事', '目前从事'
    ]
    
    # Stop keywords for research section (next h3 headings)
    RESEARCH_STOP_KEYWORDS = [
        '学术兼职', '工作经历', '科研成果', '个人简介', 
        '获奖情况', '教育背景', '社会兼职', '联系方式',
        '代表性论文', '发表论文', '学术论文', '科研项目',
        '主持项目', '参与项目', '教学工作', '教学经历',
        '承担课程', '人才培养', '学生指导'
    ]
    
    # Additional misleading/stop keywords from previous scripts
    ADDITIONAL_STOP_KEYWORDS = [
        # General academic sections
        '个人简历', '个人信息', '基本信息', '职称', '职务',
        '教育经历', '工作经验', '学习经历', '访问学者',
        # Publications and projects
        '论文发表', '专利', '著作', '出版物', '会议论文',
        '期刊论文', '科技成果', '研究成果', '学术成就',
        # Teaching related
        '授课情况', '教学成果', '指导学生', '培养研究生',
        # Others
        '荣誉称号', '学术活动', '国际合作', '招生信息'
    ]
    
    # Content to avoid in research text
    MISLEADING_CONTENT = [
        'doi', 'DOI', '10.', 'http://', 'https://', 
        'ISBN', 'ISSN', '期刊', '会议', 'pp.', 'Vol.', 
        '年第', '月第', 'IF=', '影响因子', 'SCI', 'EI',
        '第一作者', '通讯作者', '发表于'
    ]
    
    # Keywords that might contain publication info for AI inference
    PUBLICATION_KEYWORDS = [
        '发布', '科研成果', '代表性论文', '发表论文', 
        '主要论文', '学术论文', '近期发表', '研究成果'
    ]

    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls: Set[str] = set()

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

    def extract_name(self, soup) -> str:
        """Extract name from NJU profile - h1.news_title"""
        try:
            # Primary method: Look for h1.news_title
            h1 = soup.find('h1', class_='news_title')
            if h1:
                # Get text but exclude nested span tags (like "教授")
                # Clone the element to avoid modifying the original using BeautifulSoup
                h1_clone = BeautifulSoup(str(h1), 'html.parser')
                
                # Remove all span tags
                for span in h1_clone.find_all('span'):
                    span.decompose()
                
                name = h1_clone.get_text(strip=True)
                
                if name:
                    logger.debug(f"Name found in h1.news_title: {name}")
                    return name
            
            # Fallback: Try to find name in any h1
            all_h1 = soup.find_all('h1')
            for h1 in all_h1:
                text = h1.get_text(strip=True)
                # Simple heuristic: if it's short and looks like a name
                if text and len(text) < 10 and not re.search(r'[@.]', text):
                    # Remove common titles
                    for title in ['教授', '副教授', '讲师', '博士', '研究员']:
                        text = text.replace(title, '').strip()
                    if text and len(text) > 1:
                        logger.debug(f"Name found in h1 (fallback): {text}")
                        return text
            
            return "Unknown"
            
        except Exception as e:
            logger.error(f"Error extracting name: {e}")
            return "Unknown"

    def extract_email(self, soup) -> Optional[str]:
        """Extract email from NJU profile"""
        try:
            # Method 1: Look for p.news_text containing "电子邮件："
            email_p = soup.find('p', class_='news_text', string=lambda s: '电子邮件' in str(s) if s else False)
            if not email_p:
                # Try with any p containing the text
                email_p = soup.find('p', string=lambda s: '电子邮件' in str(s) if s else False)
            
            if email_p:
                text = email_p.get_text(strip=True)
                # Split by Chinese colon
                if '：' in text:
                    email = text.split('：')[-1].strip()
                    if '@' in email:
                        logger.debug(f"Email found via 电子邮件: {email}")
                        return email
            
            # Method 2: Look for email patterns in the page
            page_text = soup.get_text()
            
            # Email patterns
            email_patterns = [
                r'电子邮件[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'Email[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'E[-]?mail[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'邮箱[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            ]
            
            for pattern in email_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    email = match.group(1)
                    logger.debug(f"Email found with pattern: {email}")
                    return email
            
            # Method 3: Find any email in the page
            all_emails = re.findall(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', page_text)
            
            # Filter out generic emails
            filtered_emails = []
            for email in all_emails:
                if not any(x in email.lower() for x in ['example', 'test', 'admin', 'webmaster', 'postmaster']):
                    filtered_emails.append(email)
            
            if filtered_emails:
                logger.debug(f"Email found (general): {filtered_emails[0]}")
                return filtered_emails[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting email: {e}")
            return None

    def extract_research_direction(self, soup) -> str:
        """Extract research direction from NJU profile"""
        try:
            # Method 1: Look for h3.tit containing "研究方向"
            research_h3 = None
            
            # Try to find h3 with class 'tit' containing the keyword
            all_h3 = soup.find_all('h3', class_='tit')
            for h3 in all_h3:
                h3_text = h3.get_text(strip=True)
                if self.RESEARCH_START_KEYWORD in h3_text:
                    research_h3 = h3
                    logger.debug(f"Found research heading in h3.tit: {h3_text}")
                    break
            
            # If not found, try any h3
            if not research_h3:
                research_h3 = soup.find('h3', string=lambda s: self.RESEARCH_START_KEYWORD in str(s) if s else False)
                if research_h3:
                    logger.debug(f"Found research heading in h3: {research_h3.get_text(strip=True)}")
            
            # If still not found, try alternative keywords
            if not research_h3:
                for alt_keyword in self.ALTERNATIVE_RESEARCH_TRIGGERS:
                    research_h3 = soup.find('h3', string=lambda s: alt_keyword in str(s) if s else False)
                    if research_h3:
                        logger.debug(f"Found alternative heading: {alt_keyword}")
                        break
            
            if research_h3:
                # Look for the next div.con
                research_content = []
                
                # Method 1: Find next sibling div.con
                next_div = research_h3.find_next_sibling('div', class_='con')
                if next_div:
                    content = next_div.get_text(strip=True)
                    research_content.append(content)
                    logger.debug(f"Found content in div.con: {len(content)} chars")
                else:
                    # Method 2: Get all siblings until next h3
                    next_elem = research_h3.find_next_sibling()
                    while next_elem:
                        # Stop at next h3 (new section)
                        if next_elem.name == 'h3':
                            # Check if it contains stop keywords
                            h3_text = next_elem.get_text(strip=True)
                            if any(stop_kw in h3_text for stop_kw in self.RESEARCH_STOP_KEYWORDS):
                                logger.debug(f"Stopping at next section: {h3_text}")
                                break
                        
                        # Collect content from div or p tags
                        if getattr(next_elem, "name", None) in ['div', 'p']:
                            content = next_elem.get_text(strip=True)
                            if content and not any(stop in content for stop in self.RESEARCH_STOP_KEYWORDS):
                                research_content.append(content)
                        
                        next_elem = next_elem.find_next_sibling()
                
                if research_content:
                    research_text = '\n'.join(research_content)
                    research_text = self.clean_research_text(research_text)
                    
                    if research_text and len(research_text) > 10:
                        logger.info(f"Research direction extracted: {len(research_text)} chars")
                        return research_text
            
            # Method 2: Text-based extraction as fallback
            page_text = soup.get_text()
            if self.RESEARCH_START_KEYWORD in page_text:
                research_text = self.extract_from_text(page_text)
                if research_text:
                    return research_text
            
            logger.debug("No research direction found using standard patterns")
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting research direction: {e}")
            return ""

    def extract_from_text(self, page_text: str) -> str:
        """Extract research from plain text as fallback"""
        try:
            # Find the start position
            start_idx = page_text.find(self.RESEARCH_START_KEYWORD)
            if start_idx == -1:
                return ""
            
            # Move past the keyword
            start_idx += len(self.RESEARCH_START_KEYWORD)
            
            # Skip any whitespace or punctuation
            while start_idx < len(page_text) and page_text[start_idx] in '：:\n\t ':
                start_idx += 1
            
            # Find the stop position
            stop_idx = len(page_text)
            all_stops = self.RESEARCH_STOP_KEYWORDS + self.ADDITIONAL_STOP_KEYWORDS
            
            for stop_kw in all_stops:
                temp_idx = page_text.find(stop_kw, start_idx)
                if temp_idx > 0 and temp_idx < stop_idx:
                    stop_idx = temp_idx
                    logger.debug(f"Found stop keyword in text: {stop_kw}")
            
            # Extract the research text
            research_text = page_text[start_idx:stop_idx].strip()
            
            # Clean and validate
            research_text = self.clean_research_text(research_text)
            
            if research_text and len(research_text) > 20:
                logger.info(f"Research extracted from text: {len(research_text)} chars")
                return research_text
            
            return ""
            
        except Exception as e:
            logger.error(f"Error in text extraction: {e}")
            return ""

    def extract_publications_for_inference(self, soup) -> str:
        """Extract publication titles or content for AI inference"""
        try:
            content_parts = []
            
            # Look for publication sections
            for keyword in self.PUBLICATION_KEYWORDS:
                # Find heading containing the keyword
                heading = soup.find(['h3', 'h4', 'h2'], string=lambda s: keyword in str(s) if s else False)
                
                if heading:
                    # Get the next content container
                    next_div = heading.find_next_sibling('div')
                    if next_div:
                        # Extract first few items (likely paper titles)
                        items = next_div.find_all(['p', 'li'])[:5]
                        for item in items:
                            text = item.get_text(strip=True)
                            if text and len(text) > 20:
                                content_parts.append(text)
                    
                    if content_parts:
                        logger.debug(f"Found {len(content_parts)} items under '{keyword}'")
                        return '\n'.join(content_parts)
            
            # Alternative: Look for any lists that might be publications
            # (sometimes papers are in ul/ol without clear headings)
            all_lists = soup.find_all(['ul', 'ol'])
            for lst in all_lists:
                items = lst.find_all('li')[:3]
                potential_papers = []
                for item in items:
                    text = item.get_text(strip=True)
                    # Check if it looks like a paper (has year, might have journal name)
                    if re.search(r'(19|20)\d{2}', text) and len(text) > 50:
                        potential_papers.append(text)
                
                if len(potential_papers) >= 2:
                    logger.debug(f"Found potential publication list with {len(potential_papers)} items")
                    return '\n'.join(potential_papers)
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting publications: {e}")
            return ""

    def clean_research_text(self, text: str) -> str:
        """Clean extracted research text"""
        if not text:
            return ""
        
        # Remove HTML entities and tags
        text = re.sub(r'&[^;]+;', ' ', text)
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Remove fenced math/code blocks like ```math ... ```
        text = re.sub(r'```math[\s\S]*?```', '', text, flags=re.IGNORECASE)
        
        # Remove misleading content lines (URLs/DOIs)
        for keyword in self.MISLEADING_CONTENT:
            if keyword in text:
                # For URLs and DOIs, remove the entire line
                if keyword in ['doi', 'DOI', 'http://', 'https://']:
                    lines = text.split('\n')
                    lines = [line for line in lines if keyword not in line]
                    text = '\n'.join(lines)
        
        # Remove publication-related patterns
        text = re.sub(r'\b(19|20)\d{2}年\d{1,2}月', '', text)  # Remove dates
        text = re.sub(r'\bVol\.\s*\d+', '', text, flags=re.IGNORECASE)  # Remove volume numbers
        text = re.sub(r'\bpp\.\s*\d+-\d+', '', text, flags=re.IGNORECASE)  # Remove page numbers
        text = re.sub(r'\b第\d+期', '', text)  # Remove issue numbers in Chinese
        # Remove code fence numeric markers
        text = re.sub(r'^```math\s*\d+```\s*', '', text, flags=re.MULTILINE)
        
        # Remove impact factor and indexing info
        text = re.sub(r'IF[=:]\s*[\d.]+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'KATEX_INLINE_OPENSCIKATEX_INLINE_CLOSE|KATEX_INLINE_OPENEIKATEX_INLINE_CLOSE|KATEX_INLINE_OPENSSCIKATEX_INLINE_CLOSE', '', text, flags=re.IGNORECASE)
        
        # Remove numbered list prefixes
        text = re.sub(r'^\d+[\.、]\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'^[①②③④⑤⑥⑦⑧⑨⑩]\s*', '', text, flags=re.MULTILINE)
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()
        
        # Remove lines that are too short (likely fragments)
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if len(line) > 5:
                # Additional check: skip lines that are just numbers or single words
                if not re.match(r'^[\d\s]+$', line):
                    cleaned_lines.append(line)
        
        text = '\n'.join(cleaned_lines).strip()
        
        # Truncate if requested
        if getattr(self.args, "truncate", 0) and self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        
        return text

    def diagnose_page_structure(self, soup, url: str):
        """Diagnostic method to understand page structure"""
        logger.debug(f"\n=== Diagnosing page structure for {url} ===")
        
        # Check for name element
        h1 = soup.find('h1', class_='news_title')
        if h1:
            # Get name without span tags
            h1_clone = BeautifulSoup(str(h1), 'html.parser')
            for span in h1_clone.find_all('span'):
                span.decompose()
            name = h1_clone.get_text(strip=True)
            logger.debug(f"✓ Found h1.news_title: {name}")
        else:
            logger.debug("✗ No h1.news_title found")
        
        # Check for email
        email_p = soup.find('p', string=lambda s: '电子邮件' in str(s) if s else False)
        if email_p:
            logger.debug(f"✓ Found email paragraph: {email_p.get_text(strip=True)[:50]}...")
        else:
            logger.debug("✗ No '电子邮件' paragraph found")
        
        # Check for research direction
        research_h3 = soup.find('h3', string=lambda s: self.RESEARCH_START_KEYWORD in str(s) if s else False)
        if research_h3:
            logger.debug(f"✓ Found research h3: {research_h3.get_text(strip=True)}")
            # Check for div.con
            next_div = research_h3.find_next_sibling('div', class_='con')
            if next_div:
                content = next_div.get_text(strip=True)[:100]
                logger.debug(f"  ✓ Found div.con with content: {content}...")
            else:
                logger.debug("  ✗ No div.con found after research h3")
        else:
            logger.debug(f"✗ Research keyword '{self.RESEARCH_START_KEYWORD}' not found in any h3")
            # Check if it exists elsewhere
            if self.RESEARCH_START_KEYWORD in soup.get_text():
                logger.debug(f"  Note: '{self.RESEARCH_START_KEYWORD}' exists in page but not in h3")
        
        # Check for stop keywords
        stop_keywords_found = []
        for stop_kw in self.RESEARCH_STOP_KEYWORDS[:5]:
            if stop_kw in soup.get_text():
                stop_keywords_found.append(stop_kw)
        if stop_keywords_found:
            logger.debug(f"✓ Found stop keywords: {stop_keywords_found}")
        
        # Check page structure
        h3_count = len(soup.find_all('h3', class_='tit'))
        div_con_count = len(soup.find_all('div', class_='con'))
        logger.debug(f"Page structure: {h3_count} h3.tit elements, {div_con_count} div.con elements")
        
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
            try:
                self.driver.quit()
            except Exception:
                pass

    def random_delay(self):
        """Random delay between requests"""
        delay = random.uniform(self.args.delay_min, self.args.delay_max)
        time.sleep(delay)

    def scrape_profile(self, url: str) -> Optional[Dict[str, str]]:
        """Scrape a single faculty profile"""
        # Check for duplicate URLs
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
                
                # Diagnostics if debug mode
                if self.args.debug:
                    self.diagnose_page_structure(soup, url)
                
                # Check page validity
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
                
                # Extract information
                name = self.extract_name(soup)
                email = self.extract_email(soup)
                research = self.extract_research_direction(soup)

                logger.info(f"Extraction -> Name: {name}, Email: {email or 'Not found'}, Research: {len(research) if research else 0} chars")

                # Use AI only if "研究方向" was not found
                should_use_ai = False
                page_text = soup.get_text()
                
                if self.RESEARCH_START_KEYWORD not in page_text:
                    should_use_ai = True
                    logger.info(f"'{self.RESEARCH_START_KEYWORD}' not found, will try AI extraction")
                elif not research or len(research) < 20:
                    should_use_ai = True
                    logger.info("Research too short or empty, will try AI extraction")
                
                if should_use_ai and (self.ai_extractor or self.groq_extractor):
                    logger.info("Using AI for research extraction...")
                    
                    # First try to get publication info for inference
                    pub_content = self.extract_publications_for_inference(soup)
                    
                    if pub_content:
                        # Use publications for inference
                        inference_prompt = f"""基于以下内容（可能包含论文标题或研究成果），推断教师的研究方向：

{pub_content}

请用2-3句话概括主要研究领域和方向，不要列举具体标题。"""
                        
                        # Try primary AI provider
                        if self.ai_extractor:
                            ai_research = self.ai_extractor.extract_research_interests_from_content(
                                inference_prompt,
                                is_chinese=True
                            )
                            if ai_research and ai_research != "Not found":
                                research = f"[Inferred] {ai_research}"
                                logger.info(f"AI inferred research from publications: {len(research)} chars")
                    
                    # If still no research, try general extraction
                    if not research or research == "Not found":
                        page_content = page_text[:5000]
                        
                        # Try primary AI provider
                        if self.ai_extractor:
                            ai_research = self.ai_extractor.extract_research_interests_from_content(
                                page_content,
                                is_chinese=True
                            )
                            if ai_research and ai_research != "Not found":
                                research = ai_research
                                logger.info(f"AI extracted research: {len(research)} chars")
                        
                        # Try Groq fallback
                        if (not research or research == "Not found") and self.groq_extractor:
                            logger.info("Trying Groq fallback...")
                            groq_research = self.groq_extractor.extract_research_interests_from_content(
                                page_content,
                                is_chinese=True
                            )
                            if groq_research and groq_research != "Not found":
                                research = groq_research
                                logger.info(f"Groq extracted research: {len(research)} chars")

                # Final defaults
                if not name or name == "Unknown":
                    name = "Unknown"
                if not email:
                    email = "Not found"
                if not research or len(research) < 5:
                    research = "Not found"

                # Mark as processed
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

        # Prepare output
        output_file = Path(self.args.output_file)
        if output_file.exists() and not self.args.append:
            output_file.unlink()

        # Setup driver
        self.setup_driver()
        profiles_list = []
        
        try:
            processed_count = 0
            for i, url in enumerate(urls):
                # Check limit
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

                # Delay
                if i < len(urls) - 1:
                    self.random_delay()

            # Save JSON if requested
            if self.args.json_output and profiles_list:
                self.write_json_profile(profiles_list, output_file)
                logger.info(f"Saved JSON output to {output_file.with_suffix('.json')}")
                
        finally:
            self.close_driver()

        logger.info(f"Completed! Processed {processed_count} profiles")
        logger.info(f"Results saved to: {output_file}")


def main():
    parser = argparse.ArgumentParser(
        description='Faculty Profile Scraper optimized for NJU-style profiles'
    )

    # File arguments
    parser.add_argument('--input-file', default='urls.txt', 
                        help='Input file containing URLs (one per line)')
    parser.add_argument('--output-file', default='output.txt', 
                        help='Output file for results')

    # AI arguments
    parser.add_argument('--use-ai', action='store_true', 
                        help='Use AI to extract research interests (only when 研究方向 not found)')
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
                        help='Groq model to use')

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
    
    # Set logging level
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create and run scraper
    scraper = NJUFacultyProfileScraper(args)
    scraper.run()


if __name__ == '__main__':
    main()
