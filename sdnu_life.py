#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper - Updated for SDNU-style profiles
Optimized for consistent structure with h3.bt1 names and numbered research sections
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
分析以下网页内容，提取教师的研究兴趣/研究方向。

网页内容：
{content[:4000]}

提取策略：
1. 首先查找这些关键词：二、研究方向，研究方向：，研究方向，目前主要从事，主要从事
2. 如果找到上述关键词，提取其后的研究描述内容（到下一个章节标题为止，如三、，四、，承担项目，科研项目，教学科研成果，代表性论文，相关研究成果，先后以第一作者，主要经历等）
3. 如果没有找到明确的研究方向部分，查找Publications, Research Projects, Papers, 近期发表文章, 代表性论文, 科研项目等部分
4. 如果找到论文或项目，根据论文标题和项目名称推断研究兴趣（提供2-3句话的简短总结，不要列举论文）
5. 研究兴趣应该是简短的学术描述，不应包含个人简历、教育背景、工作经历、年份日期、个人简介等
6. 不要提取联系方式、办公地点、Email等信息

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


class SDNUFacultyProfileScraper:
    """Scraper optimized for SDNU-style faculty profiles"""

    # Institutional/generic email to avoid (footer email)
    INSTITUTIONAL_EMAIL = '620214@sdnu.edu.cn'
    
    # Research direction patterns
    PATTERN_A_START = ['二、研究方向']
    PATTERN_A_STOP = ['三、', '四、', '五、', '六、']
    
    PATTERN_B_TRIGGERS = ['目前主要从事', '主要从事', '研究方向']
    PATTERN_B_STOPS = ['相关研究成果', '先后以第一作者', '承担项目', '代表性论文', 
                       '发表论文', '科研项目', '教学科研成果']
    
    PATTERN_C_START = '研究方向：'
    PATTERN_C_STOP = '主要经历：'
    
    # Misleading keywords to avoid
    MISLEADING_KEYWORDS = [
        '个人简介', '一、个人简介', '教育经历', '工作经历', 
        '承担项目', '科研项目', '教学科研成果', '代表性论文',
        '获奖', '荣誉', '联系方式', '办公地点'
    ]
    
    # Additional stop keywords for general use
    GENERAL_STOP_KEYWORDS = [
        '个人简介', '教育经历', '工作经历', '获奖情况', '联系方式',
        '办公地点', '代表性成果', '科研成果', '学术论文', '发表文章',
        '主持项目', '参与项目', '教学工作', '社会兼职', '学术兼职'
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

    def extract_name_sdnu(self, soup) -> str:
        """Extract name from SDNU profile - h3.bt1 inside div.displaynews"""
        try:
            # Primary method: Look for h3.bt1
            displaynews = soup.find('div', class_='displaynews')
            if displaynews:
                h3 = displaynews.find('h3', class_='bt1')
                if h3:
                    name = h3.get_text(strip=True)
                    if name:
                        logger.debug(f"Name found in h3.bt1: {name}")
                        return name
            
            # Fallback: Look for h3.bt1 anywhere
            h3 = soup.find('h3', class_='bt1')
            if h3:
                name = h3.get_text(strip=True)
                if name:
                    logger.debug(f"Name found in h3.bt1 (fallback): {name}")
                    return name
            
            return "Unknown"
        except Exception as e:
            logger.error(f"Error extracting name: {e}")
            return "Unknown"

    def extract_email_sdnu(self, soup) -> Optional[str]:
        """Extract email from SDNU profile - avoiding footer institutional email"""
        try:
            # Look in the main content area
            content_div = soup.find('div', class_='v_news_content')
            if not content_div:
                # Fallback to any content div
                content_div = soup.find('div', class_='displaynews')
            
            if content_div:
                # Convert to text for searching
                content_text = content_div.get_text()
                
                # Pattern 1: E-mail: format
                email_patterns = [
                    r'E[-]?mail[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                    r'邮箱[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                    r'电子邮件[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                ]
                
                for pattern in email_patterns:
                    match = re.search(pattern, content_text, re.IGNORECASE)
                    if match:
                        email = match.group(1)
                        # Skip institutional email
                        if email != self.INSTITUTIONAL_EMAIL:
                            logger.debug(f"Email found: {email}")
                            return email
                
                # Pattern 2: Look for any email that's not the institutional one
                all_emails = re.findall(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', content_text)
                for email in all_emails:
                    if email != self.INSTITUTIONAL_EMAIL:
                        logger.debug(f"Email found (general pattern): {email}")
                        return email
            
            # Last resort: check entire page but still avoid footer
            page_text = soup.get_text()
            # Remove footer section if identifiable
            footer_start = page_text.find('版权所有')
            if footer_start > 0:
                page_text = page_text[:footer_start]
            
            all_emails = re.findall(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', page_text)
            for email in all_emails:
                if email != self.INSTITUTIONAL_EMAIL:
                    logger.debug(f"Email found (page-wide): {email}")
                    return email
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting email: {e}")
            return None

    def extract_research_direction_sdnu(self, soup) -> str:
        """Extract research direction using three patterns identified"""
        try:
            # Get the main content
            content_div = soup.find('div', class_='v_news_content')
            if not content_div:
                content_div = soup.find('div', class_='displaynews')
            
            if not content_div:
                logger.debug("No content div found")
                return ""
            
            content_text = content_div.get_text()
            content_html = str(content_div)
            
            # Pattern A: Numbered section "二、研究方向" (most common)
            for start_kw in self.PATTERN_A_START:
                if start_kw in content_text:
                    logger.debug(f"Found Pattern A start: {start_kw}")
                    
                    # Find start position
                    start_idx = content_text.find(start_kw)
                    
                    # Find stop position
                    stop_idx = len(content_text)
                    for stop_kw in self.PATTERN_A_STOP:
                        temp_idx = content_text.find(stop_kw, start_idx + len(start_kw))
                        if temp_idx > 0 and temp_idx < stop_idx:
                            stop_idx = temp_idx
                            logger.debug(f"Found Pattern A stop: {stop_kw}")
                    
                    # Extract content
                    research_text = content_text[start_idx + len(start_kw):stop_idx].strip()
                    
                    # Clean up
                    research_text = self.clean_research_text(research_text)
                    if research_text and len(research_text) > 10:
                        logger.info(f"Research direction extracted (Pattern A): {len(research_text)} chars")
                        return research_text
            
            # Pattern B: Trigger phrases
            for trigger in self.PATTERN_B_TRIGGERS:
                if trigger in content_text:
                    logger.debug(f"Found Pattern B trigger: {trigger}")
                    
                    # Build regex pattern
                    stop_pattern = '|'.join(re.escape(s) for s in self.PATTERN_B_STOPS)
                    pattern = rf'{re.escape(trigger)}(.+?)(?:{stop_pattern}|$)'
                    
                    match = re.search(pattern, content_text, re.DOTALL)
                    if match:
                        research_text = match.group(1).strip()
                        research_text = self.clean_research_text(research_text)
                        if research_text and len(research_text) > 10:
                            logger.info(f"Research direction extracted (Pattern B): {len(research_text)} chars")
                            return research_text
            
            # Pattern C: Labeled field "研究方向："
            if self.PATTERN_C_START in content_text:
                logger.debug(f"Found Pattern C start: {self.PATTERN_C_START}")
                
                pattern = rf'{re.escape(self.PATTERN_C_START)}\s*(.+?)(?:{re.escape(self.PATTERN_C_STOP)}|$)'
                match = re.search(pattern, content_text, re.DOTALL)
                if match:
                    research_text = match.group(1).strip()
                    research_text = self.clean_research_text(research_text)
                    if research_text and len(research_text) > 10:
                        logger.info(f"Research direction extracted (Pattern C): {len(research_text)} chars")
                        return research_text
            
            # Alternative: Try to find research direction in paragraphs
            paragraphs = content_div.find_all('p')
            for i, p in enumerate(paragraphs):
                p_text = p.get_text(strip=True)
                
                # Check if this paragraph contains any start keyword
                for start_kw in self.PATTERN_A_START + self.PATTERN_B_TRIGGERS + [self.PATTERN_C_START]:
                    if start_kw in p_text:
                        # Extract from this and following paragraphs
                        research_parts = []
                        
                        # Get content from current paragraph
                        if start_kw in p_text:
                            parts = p_text.split(start_kw, 1)
                            if len(parts) > 1:
                                research_parts.append(parts[1].strip())
                        
                        # Get following paragraphs until stop keyword
                        for j in range(i+1, min(i+10, len(paragraphs))):
                            next_p_text = paragraphs[j].get_text(strip=True)
                            
                            # Check for stop conditions
                            stop_found = False
                            for stop_kw in (self.PATTERN_A_STOP + self.PATTERN_B_STOPS + 
                                          [self.PATTERN_C_STOP] + self.GENERAL_STOP_KEYWORDS):
                                if stop_kw in next_p_text:
                                    stop_found = True
                                    break
                            
                            if stop_found:
                                break
                            
                            if next_p_text:
                                research_parts.append(next_p_text)
                        
                        if research_parts:
                            research_text = ' '.join(research_parts)
                            research_text = self.clean_research_text(research_text)
                            if research_text and len(research_text) > 10:
                                logger.info(f"Research direction extracted (paragraph method): {len(research_text)} chars")
                                return research_text
            
            logger.debug("No research direction found using patterns")
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting research direction: {e}")
            return ""

    def clean_research_text(self, text: str) -> str:
        """Clean extracted research text"""
        if not text:
            return ""
        
        # Remove misleading keywords if they appear at the start
        for keyword in self.MISLEADING_KEYWORDS:
            if text.startswith(keyword):
                text = text[len(keyword):].strip()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        
        # Remove numbered list prefixes
        text = re.sub(r'^\d+[\.、]\s*', '', text)
        
        # Remove any remaining section headers
        for stop_kw in self.GENERAL_STOP_KEYWORDS:
            if stop_kw in text:
                text = text.split(stop_kw)[0]
        
        # Remove years and everything after (if year appears late in text)
        year_match = re.search(r'\b(19|20)\d{2}年\b', text)
        if year_match and year_match.start() > len(text) * 0.7:  # Only if year is in last 30%
            text = text[:year_match.start()]
        
        # Remove HTML entities
        text = re.sub(r'&[^;]+;', ' ', text)
        
        # Remove excessive punctuation
        text = re.sub(r'[。；;]{2,}', '。', text)
        
        # Final cleanup
        text = text.strip()
        
        # Truncate if requested
        if self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        
        return text

    def diagnose_page_structure(self, soup, url: str):
        """Diagnostic method to understand page structure"""
        logger.debug(f"\n=== Diagnosing page structure for {url} ===")
        
        # Check for name
        h3 = soup.find('h3', class_='bt1')
        if h3:
            logger.debug(f"✓ Found h3.bt1: {h3.get_text(strip=True)}")
        else:
            logger.debug("✗ No h3.bt1 found")
        
        # Check for content div
        content_div = soup.find('div', class_='v_news_content')
        if content_div:
            logger.debug("✓ Found div.v_news_content")
        else:
            logger.debug("✗ No div.v_news_content found")
        
        # Check for research patterns
        page_text = soup.get_text()
        patterns_found = []
        for pattern in self.PATTERN_A_START + self.PATTERN_B_TRIGGERS + [self.PATTERN_C_START]:
            if pattern in page_text:
                patterns_found.append(pattern)
        
        if patterns_found:
            logger.debug(f"✓ Found research patterns: {patterns_found}")
        else:
            logger.debug("✗ No research patterns found")
        
        # Check for emails
        emails = re.findall(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', page_text)
        non_institutional = [e for e in emails if e != self.INSTITUTIONAL_EMAIL]
        if non_institutional:
            logger.debug(f"✓ Found {len(non_institutional)} non-institutional email(s)")
        else:
            logger.debug("✗ No personal emails found")
        
        logger.debug("=== End diagnosis ===\n")

    def extract_publications_or_projects(self, soup) -> str:
        """Extract publications or projects for AI inference"""
        content_parts = []
        
        # Publication keywords
        pub_keywords = ['代表性论文', '发表论文', '主要论文', '学术论文', '近期发表']
        
        content_div = soup.find('div', class_='v_news_content')
        if not content_div:
            content_div = soup
        
        for keyword in pub_keywords:
            if keyword in content_div.get_text():
                # Find the section
                for elem in content_div.find_all(['p', 'div']):
                    if keyword in elem.get_text():
                        # Get next few elements
                        count = 0
                        for sibling in elem.find_next_siblings():
                            if count >= 5:
                                break
                            text = sibling.get_text(strip=True)
                            if text and not any(stop in text for stop in self.GENERAL_STOP_KEYWORDS):
                                content_parts.append(text)
                                count += 1
                        break
                
                if content_parts:
                    return '\n'.join(content_parts)
        
        # Project keywords
        proj_keywords = ['科研项目', '承担项目', '主持项目', '研究项目']
        
        for keyword in proj_keywords:
            if keyword in content_div.get_text():
                for elem in content_div.find_all(['p', 'div']):
                    if keyword in elem.get_text():
                        count = 0
                        for sibling in elem.find_next_siblings():
                            if count >= 5:
                                break
                            text = sibling.get_text(strip=True)
                            if text and not any(stop in text for stop in self.GENERAL_STOP_KEYWORDS):
                                content_parts.append(text)
                                count += 1
                        break
                
                if content_parts:
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
                
                # Extract using SDNU-specific methods
                name = self.extract_name_sdnu(soup)
                email = self.extract_email_sdnu(soup)
                research = self.extract_research_direction_sdnu(soup)

                logger.info(f"Traditional extraction -> Name: {name}, Email: {email or 'Not found'}, Research: {len(research) if research else 0} chars")

                # AI fallback ONLY for missing research
                if (not research or len(research) < 10) and (self.ai_extractor or self.groq_extractor):
                    logger.info("Research not found via patterns, trying AI...")
                    
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
                    
                    # Last resort: infer from publications
                    if not research or research == "Not found":
                        logger.info("Attempting to infer from publications/projects...")
                        pub_content = self.extract_publications_or_projects(soup)
                        if pub_content and self.ai_extractor:
                            inference_prompt = f"""基于以下论文/项目，推断研究方向（2-3句话）：
{pub_content}

只返回研究方向，不要列举标题。"""
                            ai_research = self.ai_extractor.extract_research_interests_from_content(
                                inference_prompt,
                                is_chinese=True
                            )
                            if ai_research and ai_research != "Not found":
                                research = f"[Inferred] {ai_research}"
                                logger.info("Successfully inferred research from publications")

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
        description='Faculty Profile Scraper optimized for SDNU-style profiles'
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
    scraper = SDNUFacultyProfileScraper(args)
    scraper.run()


if __name__ == '__main__':
    main()