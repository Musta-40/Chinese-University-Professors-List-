#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper - TUST University Style
Optimized for profiles with div.subArticleTitle names and 科研领域及方向 research sections
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
1. 首先查找这些关键词：科研领域及方向，研究方向，目前主要从事，主要从事
2. 如果找到上述关键词，提取其后的研究描述内容（到下一个章节标题为止）
3. 如果没有找到明确的研究方向部分，查找Publications, Research Projects, Papers, 近期发表文章, 代表性论文, 科研项目等部分
4. 如果找到论文或项目，根据论文标题和项目名称推断研究兴趣（提供2-3句话的简短总结，不要列举论文）
5. 研究兴趣应该是简短的学术描述，不应包含个人简历、教育背景、工作经历、年份日期、个人简介、DOI号码等
6. 不要提取联系方式、办公地点、Email等信息
7. 如果文本包含编号如[1], [2]等，请保留这些研究方向的列表格式

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


class TUSTFacultyProfileScraper:
    """Scraper optimized for TUST-style faculty profiles"""
    
    # Primary research direction pattern
    RESEARCH_START_KEYWORD = '科研领域及方向'
    
    # Alternative research triggers (fallback)
    ALTERNATIVE_RESEARCH_TRIGGERS = [
        '研究方向', '目前主要从事', '主要从事', '研究领域', '研究兴趣'
    ]
    
    # Primary stop keywords for research section
    PRIMARY_RESEARCH_STOPS = [
        '科研项目情况', '主持的科研项目情况', '主要学术成果',
        '主讲课程', '教学工作', '获奖情况', '联系方式',
        '代表性论文', '发表论文', '学术论文', '科研成果'
    ]
    
    # Additional stop keywords (comprehensive list)
    ADDITIONAL_STOP_KEYWORDS = [
        # From SDNU patterns
        '相关研究成果', '先后以第一作者', '承担项目', '教学科研成果',
        # General stops
        '个人简介', '教育经历', '工作经历', '办公地点', 
        '主持项目', '参与项目', '社会兼职', '学术兼职',
        '教育背景', '工作经验', '研究项目', '科研项目',
        # Section markers
        '一、', '二、', '三、', '四、', '五、', '六、'
    ]
    
    # Misleading content to avoid
    MISLEADING_KEYWORDS = [
        'doi', 'DOI', '10.', 'http://', 'https://', 
        'ISBN', 'ISSN', '期刊', '会议', 'pp.', 'Vol.', 
        '年第', '月第'
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
        """Extract name from TUST profile - div.subArticleTitle > h2"""
        try:
            # Primary method: Look for div.subArticleTitle > h2
            title_div = soup.find('div', class_='subArticleTitle')
            if title_div:
                h2 = title_div.find('h2')
                if h2:
                    name = h2.get_text(strip=True)
                    # Remove common titles
                    titles_to_remove = ['教授', '副教授', '讲师', '博士', '研究员', '助理研究员']
                    for title in titles_to_remove:
                        name = name.replace(title, '').strip()
                    # If space exists, take first part (handle "李庆刚 教授" format)
                    if ' ' in name:
                        name = name.split()[0]
                    if name:
                        logger.debug(f"Name found in subArticleTitle: {name}")
                        return name
            
            # Fallback: Look for any h2 that might contain a name
            all_h2 = soup.find_all('h2')
            for h2 in all_h2:
                text = h2.get_text(strip=True)
                # Simple heuristic: if it's short and doesn't contain numbers/special chars
                if text and len(text) < 10 and not re.search(r'[\d@.]', text):
                    # Remove titles
                    for title in ['教授', '副教授', '讲师', '博士']:
                        text = text.replace(title, '').strip()
                    if text:
                        logger.debug(f"Name found in h2 (fallback): {text}")
                        return text.split()[0] if ' ' in text else text
            
            return "Unknown"
            
        except Exception as e:
            logger.error(f"Error extracting name: {e}")
            return "Unknown"

    def extract_email(self, soup) -> Optional[str]:
        """Extract email from TUST profile"""
        try:
            page_text = soup.get_text()
            
            # Email patterns (handles both Chinese and English colons)
            email_patterns = [
                r'Email[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'E[-]?mail[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'邮箱[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'电子邮件[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'联系方式[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            ]
            
            for pattern in email_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    email = match.group(1)
                    logger.debug(f"Email found with pattern: {email}")
                    return email
            
            # Fallback: Look for any email in the page
            all_emails = re.findall(r'\b([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})\b', page_text)
            
            # Filter out common institutional/generic emails if needed
            filtered_emails = []
            for email in all_emails:
                # Skip emails that look like examples or placeholders
                if not any(x in email.lower() for x in ['example', 'test', 'admin', 'webmaster']):
                    filtered_emails.append(email)
            
            if filtered_emails:
                # Prefer emails that appear in the contact section
                if '联系方式' in page_text:
                    contact_section = page_text[page_text.find('联系方式'):]
                    for email in filtered_emails:
                        if email in contact_section:
                            logger.debug(f"Email found in contact section: {email}")
                            return email
                
                # Return the first valid email
                logger.debug(f"Email found (general): {filtered_emails[0]}")
                return filtered_emails[0]
            
            return None
            
        except Exception as e:
            logger.error(f"Error extracting email: {e}")
            return None

    def extract_research_direction(self, soup) -> str:
        """Extract research direction from TUST profile"""
        try:
            page_text = soup.get_text()
            
            # Check if the primary keyword exists
            if self.RESEARCH_START_KEYWORD not in page_text:
                logger.debug(f"Primary keyword '{self.RESEARCH_START_KEYWORD}' not found")
                
                # Try alternative triggers
                for trigger in self.ALTERNATIVE_RESEARCH_TRIGGERS:
                    if trigger in page_text:
                        logger.debug(f"Found alternative trigger: {trigger}")
                        return self.extract_with_trigger(page_text, trigger)
                
                return ""
            
            logger.debug(f"Found primary keyword: {self.RESEARCH_START_KEYWORD}")
            
            # Method 1: Text-based extraction
            research_text = self.extract_from_text(page_text)
            if research_text:
                return research_text
            
            # Method 2: HTML structure-based extraction
            research_text = self.extract_from_html_structure(soup)
            if research_text:
                return research_text
            
            # Method 3: Paragraph-based extraction
            research_text = self.extract_from_paragraphs(soup)
            if research_text:
                return research_text
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting research direction: {e}")
            return ""

    def extract_from_text(self, page_text: str) -> str:
        """Extract research from plain text"""
        try:
            # Find the start position
            start_idx = page_text.find(self.RESEARCH_START_KEYWORD)
            if start_idx == -1:
                return ""
            
            start_idx += len(self.RESEARCH_START_KEYWORD)
            
            # Find the stop position
            stop_idx = len(page_text)
            all_stops = self.PRIMARY_RESEARCH_STOPS + self.ADDITIONAL_STOP_KEYWORDS
            
            for stop_kw in all_stops:
                temp_idx = page_text.find(stop_kw, start_idx)
                if temp_idx > 0 and temp_idx < stop_idx:
                    stop_idx = temp_idx
                    logger.debug(f"Found stop keyword: {stop_kw} at position {temp_idx}")
            
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

    def extract_from_html_structure(self, soup) -> str:
        """Extract research from HTML structure"""
        try:
            # Find the element containing the start keyword
            for elem in soup.find_all(['p', 'span', 'div', 'strong']):
                elem_text = elem.get_text(strip=True)
                if self.RESEARCH_START_KEYWORD in elem_text:
                    logger.debug(f"Found keyword in {elem.name} tag")
                    
                    research_parts = []
                    
                    # Check if content is in the same element
                    if elem_text.count(self.RESEARCH_START_KEYWORD) == 1:
                        parts = elem_text.split(self.RESEARCH_START_KEYWORD, 1)
                        if len(parts) > 1 and parts[1].strip():
                            research_parts.append(parts[1].strip())
                    
                    # Get parent and look for siblings
                    parent = elem.parent
                    if parent:
                        # Get all following siblings
                        for sibling in parent.find_all(['p', 'span', 'div', 'br']):
                            if sibling == elem:
                                continue
                            
                            sibling_text = sibling.get_text(strip=True)
                            if not sibling_text:
                                continue
                            
                            # Check for stop conditions
                            stop_found = False
                            for stop_kw in self.PRIMARY_RESEARCH_STOPS + self.ADDITIONAL_STOP_KEYWORDS:
                                if stop_kw in sibling_text:
                                    stop_found = True
                                    break
                            
                            if stop_found:
                                break
                            
                            # Check if it's a new section (has strong/b tag)
                            if sibling.find(['strong', 'b']):
                                break
                            
                            research_parts.append(sibling_text)
                    
                    # Also check immediate next siblings
                    for sibling in elem.find_next_siblings():
                        sibling_text = sibling.get_text(strip=True)
                        if not sibling_text:
                            continue
                        
                        # Check for stop conditions
                        if any(stop in sibling_text for stop in self.PRIMARY_RESEARCH_STOPS):
                            break
                        
                        if sibling.find(['strong', 'b']):
                            break
                        
                        # Limit to reasonable number of siblings
                        if len(research_parts) >= 10:
                            break
                        
                        research_parts.append(sibling_text)
                    
                    if research_parts:
                        research_text = '\n'.join(research_parts)
                        research_text = self.clean_research_text(research_text)
                        if research_text and len(research_text) > 20:
                            logger.info(f"Research extracted from HTML structure: {len(research_text)} chars")
                            return research_text
            
            return ""
            
        except Exception as e:
            logger.error(f"Error in HTML structure extraction: {e}")
            return ""

    def extract_from_paragraphs(self, soup) -> str:
        """Extract research from paragraph structure"""
        try:
            paragraphs = soup.find_all(['p', 'div'])
            
            for i, para in enumerate(paragraphs):
                para_text = para.get_text(strip=True)
                
                if self.RESEARCH_START_KEYWORD in para_text:
                    logger.debug(f"Found keyword in paragraph {i}")
                    
                    research_parts = []
                    
                    # Get content from current paragraph
                    if self.RESEARCH_START_KEYWORD in para_text:
                        parts = para_text.split(self.RESEARCH_START_KEYWORD, 1)
                        if len(parts) > 1 and parts[1].strip():
                            research_parts.append(parts[1].strip())
                    
                    # Get following paragraphs
                    for j in range(i + 1, min(i + 15, len(paragraphs))):
                        next_para = paragraphs[j]
                        next_text = next_para.get_text(strip=True)
                        
                        if not next_text:
                            continue
                        
                        # Check for stop conditions
                        stop_found = False
                        for stop_kw in self.PRIMARY_RESEARCH_STOPS + self.ADDITIONAL_STOP_KEYWORDS:
                            if stop_kw in next_text:
                                stop_found = True
                                logger.debug(f"Stop keyword found: {stop_kw}")
                                break
                        
                        if stop_found:
                            break
                        
                        # Check if it's a header (short text with strong/b)
                        if len(next_text) < 20 and next_para.find(['strong', 'b']):
                            break
                        
                        research_parts.append(next_text)
                    
                    if research_parts:
                        research_text = '\n'.join(research_parts)
                        research_text = self.clean_research_text(research_text)
                        if research_text and len(research_text) > 20:
                            logger.info(f"Research extracted from paragraphs: {len(research_text)} chars")
                            return research_text
            
            return ""
            
        except Exception as e:
            logger.error(f"Error in paragraph extraction: {e}")
            return ""

    def extract_with_trigger(self, page_text: str, trigger: str) -> str:
        """Extract research using alternative trigger words"""
        try:
            # Find the trigger position
            start_idx = page_text.find(trigger)
            if start_idx == -1:
                return ""
            
            start_idx += len(trigger)
            
            # Skip any colons or whitespace
            while start_idx < len(page_text) and page_text[start_idx] in '：: \n\t':
                start_idx += 1
            
            # Find stop position
            stop_idx = len(page_text)
            for stop_kw in self.PRIMARY_RESEARCH_STOPS + self.ADDITIONAL_STOP_KEYWORDS:
                temp_idx = page_text.find(stop_kw, start_idx)
                if temp_idx > 0 and temp_idx < stop_idx:
                    stop_idx = temp_idx
            
            # Extract and clean
            research_text = page_text[start_idx:stop_idx].strip()
            research_text = self.clean_research_text(research_text)
            
            if research_text and len(research_text) > 20:
                logger.info(f"Research extracted with trigger '{trigger}': {len(research_text)} chars")
                return research_text
            
            return ""
            
        except Exception as e:
            logger.error(f"Error in trigger extraction: {e}")
            return ""

    def clean_research_text(self, text: str) -> str:
        """Clean extracted research text"""
        if not text:
            return ""
        
        # Remove HTML entities
        text = re.sub(r'&[^;]+;', ' ', text)
        text = re.sub(r'<[^>]+>', ' ', text)
        
        # Remove misleading content
        for keyword in self.MISLEADING_KEYWORDS:
            if keyword in text:
                # If DOI or URL, remove the whole line containing it
                if keyword in ['doi', 'DOI', 'http://', 'https://']:
                    lines = text.split('\n')
                    lines = [line for line in lines if keyword not in line]
                    text = '\n'.join(lines)
        
        # Remove years that appear with publication patterns
        text = re.sub(r'\b(19|20)\d{2}年\d{1,2}月', '', text)
        text = re.sub(r'\b(19|20)\d{2}\s*[-,]\s*\d{1,2}\s*[-,]', '', text)
        
        # Remove volume/issue patterns
        text = re.sub(r'\bVol\.\s*\d+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\bpp\.\s*\d+', '', text, flags=re.IGNORECASE)
        text = re.sub(r'\b第\d+期', '', text)
        text = re.sub(r'\b第\d+卷', '', text)
        
        # Remove numbered list prefixes but keep the content
        text = re.sub(r'^\d+[\.、]\s*', '', text, flags=re.MULTILINE)
        # Remove markdown math fences like ```math ... ```
        text = re.sub(r'```math[\s\S]*?```', '', text, flags=re.MULTILINE)
        
        # Remove section headers that might slip through
        for stop_kw in self.ADDITIONAL_STOP_KEYWORDS:
            if stop_kw in text:
                text = text.split(stop_kw)[0]
        
        # Clean up whitespace
        text = re.sub(r'\s+', ' ', text).strip()
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # Remove lines that are too short (likely headers or fragments)
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if len(line) > 5:  # Keep lines with more than 5 characters
                cleaned_lines.append(line)
        text = '\n'.join(cleaned_lines)
        
        # Final cleanup
        text = text.strip()
        
        # Truncate if requested
        if self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        
        return text

    def extract_publications_or_projects(self, soup) -> str:
        """Extract publications or projects for AI inference (fallback)"""
        content_parts = []
        
        # Keywords for publications and projects
        pub_keywords = ['代表性论文', '发表论文', '主要论文', '学术论文', '近期发表', '主要学术成果']
        proj_keywords = ['科研项目', '承担项目', '主持项目', '研究项目', '科研项目情况']
        
        page_text = soup.get_text()
        
        # Try to find publications
        for keyword in pub_keywords:
            if keyword in page_text:
                start_idx = page_text.find(keyword)
                end_idx = start_idx + 2000  # Get next 2000 chars
                content = page_text[start_idx:end_idx]
                
                # Clean up and extract paper titles
                lines = content.split('\n')
                for line in lines[1:6]:  # Get first 5 lines after keyword
                    line = line.strip()
                    if line and len(line) > 20:
                        content_parts.append(line)
                
                if content_parts:
                    return '\n'.join(content_parts)
        
        # Try to find projects
        for keyword in proj_keywords:
            if keyword in page_text:
                start_idx = page_text.find(keyword)
                end_idx = start_idx + 2000
                content = page_text[start_idx:end_idx]
                
                lines = content.split('\n')
                for line in lines[1:6]:
                    line = line.strip()
                    if line and len(line) > 20:
                        content_parts.append(line)
                
                if content_parts:
                    return '\n'.join(content_parts)
        
        return ""

    def diagnose_page_structure(self, soup, url: str):
        """Diagnostic method to understand page structure"""
        logger.debug(f"\n=== Diagnosing page structure for {url} ===")
        
        # Check for name element
        title_div = soup.find('div', class_='subArticleTitle')
        if title_div:
            h2 = title_div.find('h2')
            if h2:
                logger.debug(f"✓ Found name element: {h2.get_text(strip=True)}")
            else:
                logger.debug("✗ No h2 in subArticleTitle")
        else:
            logger.debug("✗ No div.subArticleTitle found")
        
        # Check for research keyword
        page_text = soup.get_text()
        if self.RESEARCH_START_KEYWORD in page_text:
            logger.debug(f"✓ Found research keyword: {self.RESEARCH_START_KEYWORD}")
            # Find context around keyword
            idx = page_text.find(self.RESEARCH_START_KEYWORD)
            context = page_text[max(0, idx-50):idx+200]
            logger.debug(f"Context: ...{context}...")
        else:
            logger.debug(f"✗ Research keyword '{self.RESEARCH_START_KEYWORD}' not found")
            # Check for alternatives
            for alt in self.ALTERNATIVE_RESEARCH_TRIGGERS:
                if alt in page_text:
                    logger.debug(f"✓ Found alternative keyword: {alt}")
                    break
        
        # Check for emails
        emails = re.findall(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b', page_text)
        if emails:
            logger.debug(f"✓ Found {len(emails)} email(s): {emails[:2]}...")
        else:
            logger.debug("✗ No emails found")
        
        # Check for stop keywords
        stop_keywords_found = []
        for stop_kw in self.PRIMARY_RESEARCH_STOPS[:5]:
            if stop_kw in page_text:
                stop_keywords_found.append(stop_kw)
        if stop_keywords_found:
            logger.debug(f"✓ Found stop keywords: {stop_keywords_found}")
        
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

                # Use AI only if the primary keyword was not found
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
                    
                    # Get page content for AI
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
                    
                    # Last resort: infer from publications
                    if (not research or research == "Not found") and self.ai_extractor:
                        logger.info("Attempting to infer from publications/projects...")
                        pub_content = self.extract_publications_or_projects(soup)
                        if pub_content:
                            inference_prompt = f"""基于以下论文/项目标题，推断研究方向（用2-3句话概括主要研究领域）：

{pub_content}

只返回研究方向描述，不要列举具体标题。"""
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
        processed_count = 0
        
        try:
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
        description='Faculty Profile Scraper optimized for TUST-style profiles'
    )

    # File arguments
    parser.add_argument('--input-file', default='urls.txt', 
                        help='Input file containing URLs (one per line)')
    parser.add_argument('--output-file', default='output.txt', 
                        help='Output file for results')

    # AI arguments
    parser.add_argument('--use-ai', action='store_true', 
                        help='Use AI to extract research interests (only when keyword not found)')
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
    scraper = TUSTFacultyProfileScraper(args)
    scraper.run()


if __name__ == '__main__':
    main()
