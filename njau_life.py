#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper for Chinese Universities
Specialized for Nanjing Agricultural University format with Chinese content
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
        """Use AI to infer research interests from page content"""
        if not content.strip():
            return ""
        
        if is_chinese:
            prompt = f"""
基于以下网页内容，提取该教师的研究兴趣。请专注于研究描述部分，忽略其他部分如教育背景、工作经历或科研项目。

网页内容：
{content}

指令：
- 仅提取研究兴趣，按照原文表述
- 如果研究部分未找到，查找类似标题的内容
- 在"科研项目"、"曾经主持的科研项目"、"代表论文"等部分之前停止提取
- 返回的研究兴趣中不应包含论文列表、项目列表、教学工作、教育背景、工作经历、获奖情况等内容
- 只返回研究兴趣文本，不要包含其他内容
- 如果没有研究兴趣信息，返回"Not found"
"""
        else:
            prompt = f"""
Based SOLELY on the following webpage content, extract the research interests of this faculty member.
Focus specifically on the research description section and ignore other sections like education, professional experience, or research projects.

Page Content:
{content}

Instructions:
- Extract ONLY the research interests as described in the research section
- If the research section is not found, look for similar headings
- Stop extraction before sections like research projects, previously hosted research projects, or representative papers
- The extracted research interests should NOT include paper lists, project lists, teaching work, educational background, work experience, or award information
- Return ONLY the research interests text, nothing else
- If no research interests information is found, return "Not found"
"""

        try:
            if self.provider == 'openai':
                response = self.client.ChatCompletion.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are a research analyst who extracts research interests from faculty profiles."},
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
                        {"role": "system", "content": "You are a research analyst who extracts research interests from faculty profiles."},
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
        
        return ""

    def extract_research_interests_from_publications(self, publications_text: str, is_chinese: bool = True) -> str:
        """Use AI to infer research interests from publications list"""
        if not publications_text.strip():
            return ""
            
        if is_chinese:
            prompt = f"""
基于以下近期发表的论文列表，识别该教师的核心研究兴趣。重点关注多篇论文中一致的主题。

近期发表论文：
{publications_text}

请提供研究兴趣的简明总结（2-3句话以内）。不要包含论文标题或作者，仅关注研究主题。
"""
        else:
            prompt = f"""
Based SOLELY on these recent publications, identify the core research interests of this faculty member.
Focus on the consistent themes across multiple publications. Be specific about research areas, methodologies, and applications.

Recent Publications:
{publications_text}

Provide a concise summary of research interests (2-3 sentences maximum). 
DO NOT include publication titles or authors. Focus only on research themes.
"""

        try:
            if self.provider == 'openai':
                response = self.client.ChatCompletion.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are a research analyst who extracts core research themes from publication lists."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    temperature=0.1
                )
                return response.choices[0].message.content.strip()

            elif self.provider == 'anthropic':
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=300,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text.strip()

            elif self.provider == 'groq':
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You are a research analyst who extracts core research themes from publication lists."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=300,
                    temperature=0.1
                )
                return response.choices[0].message.content.strip()

            elif self.provider == 'gemini':
                response = self.model.generate_content(prompt)
                return (response.text or "").strip()

        except Exception as e:
            logger.error(f"AI research extraction failed ({self.provider}): {str(e)}")
        
        return ""


class SmartFacultyProfileScraper:
    """Enhanced scraper for Chinese university faculty pages"""

    # Research identifiers and stop keywords for Chinese sites
    RESEARCH_KEYWORDS_CHINESE = [
        '研究领域', '研究方向', '研究兴趣', '科研方向', '主要研究方向',
        '主要研究领域', '研究内容', '学术兴趣', '研究课题', '研究重点',
        '研究专长', '学术方向', '科研领域', '主攻方向', '研究范围',
        '研究工作', '科研情况', '目前研究方向', '研究领域与方向',
        '研究方向与领域', '科研方向与领域', '研究内容与方向'
    ]
    
    # Stop keywords (sections to stop before) - UPDATED WITH ALL REQUESTED KEYWORDS
    STOP_KEYWORDS_CHINESE = [
        '代表论文：', '代表论文', '论文列表', '论文目录', '论文发表列表',
        '科研项目', '曾经主持的科研项目', '主持的科研项目', '参与的科研项目',
        '在研项目', '已完成项目', '科研项目列表', '研究项目', '承担项目',
        '发表论文', '代表性论文', '论文发表', '论文目录', '论文列表',
        '论文', '出版论文', '发表文章', '学术论文', '主要论文',
        '教学工作', '教学任务', '教学内容', '教学情况', '教学课程',
        '教育背景', '学历背景', '学习经历', '教育经历', '学历学位',
        '工作经历', '职业经历', '专业经历', '工作履历', '任职经历',
        '获奖情况', '获奖记录', '获奖成果', '所获奖项', '荣誉奖项',
        '学术兼职', '社会兼职', '学术任职', '社会任职', '学术职务',
        '联系方式', '联系信息', '联系电话', '联系地址', '联系邮箱',
        '个人简历', '简历', '个人简介', '个人介绍', '个人资料',
        '发表论文', '代表性论文', '论文', '教育背景', '工作经历', 
        '获奖', '教学', '学术任职', '专业经历', '职业经历',
        '论文发表', '学术成果', '科研成果', '出版著作', '著作',
        '专利', '软件著作权', '科研奖励', '学术奖励', '社会服务',
        '招生信息', '研究生招生', '本科生教学', '指导学生', '培养研究生',
        '社会服务', '学术活动', '学术会议', '学术报告', '学术交流',
        '上一篇', '下一篇', '上一页', '下一页', '返回顶部', '返回首页',
        '个人主页', '实验室主页', '研究团队', '研究组', '课题组',
        '代表性成果', '近期成果', '主要成果', '成果展示', '成果介绍',
        '指导研究生', '培养计划', '教学计划', '课程设置', '教学大纲',
        '社会兼职', '学术组织', '学术团体', '学术委员会', '评审专家',
        '研究方向与成果', '科研成果与方向', '研究内容与成果'
    ]

    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls: Set[str] = set()
        self.processed_emails: Set[str] = set()
        self.is_chinese_site = False  # Will be detected during scraping

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

    # ----------------- Specialized extractors for Chinese university format -----------------

    def detect_chinese_site(self, soup) -> bool:
        """Detect if the site is in Chinese based on common patterns"""
        # Check for Chinese characters in body
        body_text = soup.get_text()
        if re.search(r'[\u4e00-\u9fff]', body_text):
            return True
        
        # Check for common Chinese site elements
        if soup.find(string=re.compile(r'南京农业大学|生命科学学院|教授|大学')):
            return True
            
        # Check title
        title = soup.find('title')
        if title and re.search(r'[\u4e00-\u9fff]', title.get_text()):
            return True
            
        return False

    def extract_name_from_title_chinese(self, soup) -> str:
        """Extract name from Chinese title tag (e.g., '沈文飚/教授-南京农业大学生命科学学院')"""
        title = soup.find('title')
        if title:
            t = title.get_text().strip()
            # Handle formats like "沈文飚/教授-南京农业大学生命科学学院"
            if '-' in t:
                cand = t.split('-')[0].strip()
                # Remove trailing titles like "/教授"
                cand = re.sub(r'[/／][^/]+$', '', cand)
                if 2 <= len(cand) <= 10 and re.search(r'[\u4e00-\u9fff]', cand):
                    return cand
            # Handle formats like "沈文飚_南京农业大学"
            if '_' in t:
                cand = t.split('_')[0].strip()
                cand = re.sub(r'[/／][^/]+$', '', cand)
                if 2 <= len(cand) <= 10 and re.search(r'[\u4e00-\u9fff]', cand):
                    return cand
        return ""

    def extract_name_from_meta_chinese(self, soup) -> str:
        """Extract name from Chinese meta tags"""
        # Try keywords meta
        keywords_meta = soup.find('meta', attrs={'name': 'keywords'})
        if keywords_meta and keywords_meta.get('content'):
            content = keywords_meta.get('content').strip()
            # Look for patterns like "南京农业大学生命科学学院,沈文,教授"
            parts = content.split(',')
            if len(parts) > 1:
                # Try second part (after university name)
                cand = parts[1].strip()
                if 2 <= len(cand) <= 10 and re.search(r'[\u4e00-\u9fff]', cand):
                    return cand
                # Try first part if it contains Chinese characters
                cand = parts[0].strip()
                if 2 <= len(cand) <= 10 and re.search(r'[\u4e00-\u9fff]', cand):
                    return cand
        
        # Try description meta for name pattern
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            content = meta_desc.get('content').strip()
            # Look for patterns like "个人信息：鲍依群，生命科学学院生物化学与分子生物学教授"
            m = re.search(r'个人信息[：:]\s*([^\s，,]+)', content)
            if m:
                return m.group(1).strip()
        
        return ""

    def extract_email_from_meta_chinese(self, soup) -> Optional[str]:
        """Extract email from Chinese meta description tag"""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            content = meta_desc.get('content').strip()
            # Look for email pattern after "Email:" or "邮箱:"
            m = re.search(r'(?:E[-]?mail|邮箱|Email|e[-]?mail)[：:]\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', content, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

    def extract_email_from_html_chinese(self, soup) -> Optional[str]:
        """Extract email from Chinese HTML content"""
        page_html = str(soup)
        # Look for patterns like "E-mail: hongguila@njau.edn.cn"
        m = re.search(r'(?:E[-]?mail|邮箱|Email|e[-]?mail)[：:]\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', page_html, re.IGNORECASE)
        if m:
            return m.group(1)
        
        # Text fallback
        page_text = soup.get_text(" ")
        emails = re.findall(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', page_text)
        if emails:
            return emails[0]
        
        return None

    def extract_research_interests_chinese_format(self, soup) -> str:
        """
        Extract research interests from pages with Chinese headings like '研究工作', '研究方向'
        Specifically designed for Nanjing Agricultural University format
        """
        # Check if we're dealing with a Chinese site
        self.is_chinese_site = self.detect_chinese_site(soup)
        if not self.is_chinese_site:
            return ""
        
        # Look for research headings
        research_content = ""
        
        # Method 1: Look for specific heading patterns
        for heading in soup.find_all(['h1', 'h2', 'h3', 'strong', 'b']):
            heading_text = heading.get_text().strip()
            if any(kw in heading_text for kw in self.RESEARCH_KEYWORDS_CHINESE):
                # Get content until next section
                content_parts = []
                for elem in heading.find_all_next():
                    # Stop if we hit a stop keyword
                    elem_text = elem.get_text().strip()
                    if any(kw in elem_text for kw in self.STOP_KEYWORDS_CHINESE):
                        break
                    
                    # Only collect paragraph content
                    if elem.name == 'p' or (elem.name == 'div' and 'views-field' in str(elem.get('class', ''))):
                        text = elem.get_text().strip()
                        if text and len(text) > 10:
                            content_parts.append(text)
                
                if content_parts:
                    research_content = "\n".join(content_parts)
                    break
        
        # Method 2: Look for specific structure patterns
        if not research_content:
            # Look for patterns like "目前研究方向："
            research_heading = soup.find(string=re.compile(r'目前研究方向|研究方向[:：]', re.I))
            if research_heading:
                # Find the next paragraph
                for elem in research_heading.parent.find_all_next():
                    if elem.name in ['p', 'div']:
                        text = elem.get_text().strip()
                        if any(kw in text for kw in self.STOP_KEYWORDS_CHINESE):
                            break
                        if len(text) > 20:  # Reasonable length for research description
                            research_content = text
                            break
        
        # Method 3: Look for h3 headings with specific classes
        if not research_content:
            h3_elements = soup.find_all('h3', class_=re.compile(r'szdw-title|research', re.I))
            for h3 in h3_elements:
                h3_text = h3.get_text().strip()
                if any(kw in h3_text for kw in self.RESEARCH_KEYWORDS_CHINESE):
                    # Get the following content
                    for elem in h3.find_all_next():
                        if elem.name in ['h3', 'h2', 'h1']:
                            next_heading = elem.get_text().strip()
                            if any(kw in next_heading for kw in self.STOP_KEYWORDS_CHINESE):
                                break
                        if elem.name in ['p', 'div']:
                            text = elem.get_text().strip()
                            if text and len(text) > 10:
                                research_content += text + "\n"
        
        # Method 4: Look for specific content patterns
        if not research_content:
            # Look for patterns like "主要以拟南芥为材料，从事..."
            research_para = soup.find('p', string=re.compile(r'目前研究|主要以|研究方向|研究领域', re.I))
            if research_para:
                # Check if it's followed by bullet points
                next_siblings = []
                for sibling in research_para.find_next_siblings():
                    if sibling.name in ['p', 'div', 'li']:
                        text = sibling.get_text().strip()
                        if any(kw in text for kw in self.STOP_KEYWORDS_CHINESE):
                            break
                        if text and len(text) > 10:
                            next_siblings.append(text)
                if next_siblings:
                    research_content = "\n".join([research_para.get_text().strip()] + next_siblings[:5])
        
        # Method 5: Look for table-based structure
        if not research_content:
            tables = soup.find_all('table')
            for table in tables:
                for row in table.find_all('tr'):
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        header = cells[0].get_text().strip()
                        if any(kw in header for kw in self.RESEARCH_KEYWORDS_CHINESE):
                            content = cells[1].get_text().strip()
                            if content and len(content) > 20:
                                research_content = content
                                break
                if research_content:
                    break
        
        if research_content:
            return self.clean_text(research_content)
        
        return ""

    def extract_publications_section(self, soup) -> str:
        """Extract publications or research projects section for AI fallback"""
        publications_text = ""
        
        # Look for publication headings
        for heading in soup.find_all(['h1', 'h2', 'h3', 'strong', 'b']):
            heading_text = heading.get_text().strip()
            if re.search(r'代表论文|发表论文|代表性论文|论文发表|科研成果|出版著作', heading_text):
                # Get all text until next section
                next_siblings = []
                for sibling in heading.find_next_siblings():
                    if sibling.name in ['h1', 'h2', 'h3', 'strong', 'b']:
                        next_heading = sibling.get_text().strip()
                        if re.search(r'|'.join(map(re.escape, self.STOP_KEYWORDS_CHINESE)), next_heading):
                            break
                    if sibling.name in ['p', 'div', 'li']:
                        text = sibling.get_text().strip()
                        if text:
                            next_siblings.append(text)
                publications_text = "\n".join(next_siblings[:5])  # Limit to first 5 entries
                break
        
        # If no publications, try research projects
        if not publications_text:
            for heading in soup.find_all(['h1', 'h2', 'h3', 'strong', 'b']):
                heading_text = heading.get_text().strip()
                if re.search(r'科研项目|在研项目|已完成项目|主持项目|参与项目', heading_text):
                    # Get all text until next section
                    next_siblings = []
                    for sibling in heading.find_next_siblings():
                        if sibling.name in ['h1', 'h2', 'h3', 'strong', 'b']:
                            next_heading = sibling.get_text().strip()
                            if re.search(r'|'.join(map(re.escape, self.STOP_KEYWORDS_CHINESE)), next_heading):
                                break
                        if sibling.name in ['p', 'div', 'li']:
                            text = sibling.get_text().strip()
                            if text:
                                next_siblings.append(text)
                    publications_text = "\n".join(next_siblings[:5])  # Limit to first 5 projects
                    break
        
        return publications_text

    # ----------------- General extractors -----------------

    def extract_name(self, soup) -> str:
        """Extract name using multiple strategies for both Chinese and English sites"""
        # First detect if it's a Chinese site
        self.is_chinese_site = self.detect_chinese_site(soup)
        
        if self.is_chinese_site:
            # Try Chinese-specific methods first
            name = self.extract_name_from_meta_chinese(soup)
            if name:
                return name
            name = self.extract_name_from_title_chinese(soup)
            if name:
                return name
        
        # Try English methods (for hybrid sites)
        name = self.extract_name_from_title(soup)
        if name:
            return name
        name = self.extract_name_from_meta(soup)
        if name:
            return name
        
        # Fallback to patterns in text
        page_text = soup.get_text()
        if self.is_chinese_site:
            for p in [
                r'<strong[^>]*>([\u4e00-\u9fff]{2,4})</strong>\s*教授',
                r'<h1[^>]*>([\u4e00-\u9fff]{2,4})</h1>',
                r'([\u4e00-\u9fff]{2,4})\s*教授'
            ]:
                m = re.search(p, page_text)
                if m:
                    cand = m.group(1).strip()
                    if 2 <= len(cand) <= 4 and re.search(r'[\u4e00-\u9fff]', cand):
                        return cand
        else:
            for p in [
                r'<strong[^>]*>([A-Za-z\s]+)</strong>\s*Ph\.D\.',
                r'<h1[^>]*>([A-Za-z\s]+)</h1>',
                r'Professor\s+([A-Za-z\s]+)'
            ]:
                m = re.search(p, page_text)
                if m:
                    cand = m.group(1).strip()
                    if 1 < len(cand) <= 50:
                        return cand
        
        return "Unknown"

    def extract_name_from_title(self, soup) -> str:
        """Extract name from title tag (e.g., 'Fei Qi-School of Life Sciences, Xiamen University')"""
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
        """Extract name from meta tags (e.g., <meta name="pageTitle" content="Fei Qi">)"""
        page_title_meta = soup.find('meta', attrs={'name': 'pageTitle'})
        if page_title_meta and page_title_meta.get('content'):
            content = page_title_meta.get('content').strip()
            if content and 1 < len(content) <= 50:
                return content
        
        # Try description meta for name pattern
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            content = meta_desc.get('content').strip()
            # Look for patterns like "Fei Qi, Ph.D."
            m = re.search(r'^([A-Za-z\s]+),', content)
            if m:
                return m.group(1).strip()
        
        return ""

    def extract_email(self, soup) -> Optional[str]:
        """Extract email using multiple strategies for both Chinese and English sites"""
        # First detect if it's a Chinese site
        self.is_chinese_site = self.detect_chinese_site(soup)
        
        if self.is_chinese_site:
            # Try Chinese-specific methods first
            email = self.extract_email_from_meta_chinese(soup)
            if email:
                return email
            email = self.extract_email_from_html_chinese(soup)
            if email:
                return email
        else:
            # Try English methods
            email = self.extract_email_from_meta(soup)
            if email:
                return email
            
            # Try HTML patterns
            page_html = str(soup)
            for pat in [
                r'Email:\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})',
                r'E-mail:\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})',
                r'([A-Za-z0-9._%+\-]+@xmu\.edu\.cn)'
            ]:
                m = re.search(pat, page_html, re.IGNORECASE)
                if m:
                    return m.group(1)
        
        # Text fallback (works for both)
        page_text = soup.get_text(" ")
        emails = re.findall(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', page_text)
        if emails:
            return emails[0]
        
        return None

    def extract_research_interests_comprehensive(self, soup) -> str:
        """Extract research interests with priority on the appropriate format"""
        # First detect if it's a Chinese site
        self.is_chinese_site = self.detect_chinese_site(soup)
        
        # Try Chinese format first if it's a Chinese site
        if self.is_chinese_site:
            research = self.extract_research_interests_chinese_format(soup)
            if research and len(research) > 10:
                return self.clean_text(research)
        
        # Then try English format
        research = self.extract_research_interests_english_format(soup)
        if research and len(research) > 10:
            return self.clean_text(research)
        
        # Then try meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            content = meta_desc.get('content').strip()
            # Look for research patterns in description
            if self.is_chinese_site:
                m = re.search(r'(?:研究方向|研究领域|研究工作)[：:]\s*(.+?)(?:' + '|'.join(map(re.escape, self.STOP_KEYWORDS_CHINESE)) + '|$)', content, re.DOTALL)
            else:
                m = re.search(r'Research\s*Area[：:]\s*(.+?)(?:Education|Professional\s*Experience|$)', content, re.DOTALL)
            if m:
                research = m.group(1).strip()
                if len(research) > 10:
                    return self.clean_text(research)
        
        # HTML patterns
        page_html = str(soup)
        if self.is_chinese_site:
            patterns = [
                (r'<td[^>]*>(?:研究方向|研究领域|研究工作)[：:]?</td>\s*<td[^>]*>(.*?)</td>', 1),
                (r'>(?:研究方向|研究领域|研究工作)[：:]([^<]+)<', 1),
                (r'(?:研究方向|研究领域|研究工作)[：:].*?<span[^>]*>([^<]+)</span>', 1),
                (r'(?:研究方向|研究领域|研究工作)[：:].*?>([\s\S]*?)</td>', 1),
            ]
        else:
            patterns = [
                (r'<td[^>]*>Research\s*Area[：:]?</td>\s*<td[^>]*>(.*?)</td>', 1),
                (r'>Research\s*Area[：:]([^<]+)<', 1),
                (r'Research\s*Area[：:].*?<span[^>]*>([^<]+)</span>', 1),
                (r'Research\s*Area[：:].*?>([\s\S]*?)</td>', 1),
            ]
        
        for pat, g in patterns:
            m = re.search(pat, page_html, re.IGNORECASE | re.DOTALL)
            if m:
                content = m.group(g).strip()
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'&[^;]+;', ' ', content)
                content = re.sub(r'\s+', ' ', content).strip()
                if content and len(content) > 10:
                    return self.clean_text(content)

        # Text-based extraction
        page_text = soup.get_text("\n")
        if self.is_chinese_site:
            stop_pattern = '|'.join(re.escape(kw) for kw in self.STOP_KEYWORDS_CHINESE)
            research_keywords = self.RESEARCH_KEYWORDS_CHINESE
        else:
            stop_pattern = '|'.join(re.escape(kw) for kw in self.STOP_KEYWORDS_ENGLISH)
            research_keywords = self.RESEARCH_KEYWORDS_ENGLISH
            
        for keyword in research_keywords:
            for sep in ['：', ':']:
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
        """
        Extract research interests from pages with English headings like 'Research Area'
        Specifically designed for the Xiamen University format
        """
        # Look for the "Research Area" heading
        for heading in soup.find_all(['h1', 'h2', 'h3', 'strong', 'b']):
            heading_text = heading.get_text().strip().lower()
            if any(kw in heading_text for kw in ['research area', 'research focus', 'research interest']):
                # Get all content until the next section heading
                content_parts = []
                for elem in heading.find_all_next():
                    # Stop if we hit a new section heading
                    if elem.name in ['h1', 'h2', 'h3', 'strong', 'b']:
                        next_heading = elem.get_text().strip().lower()
                        if any(kw in next_heading for kw in [kw.lower() for kw in self.STOP_KEYWORDS_ENGLISH]):
                            break
                    
                    # Only collect paragraph content
                    if elem.name == 'p':
                        text = elem.get_text().strip()
                        if text and len(text) > 10:
                            content_parts.append(text)
                
                if content_parts:
                    return " ".join(content_parts)
        
        # Alternative approach: look for the specific structure in the example
        research_area = soup.find(string=re.compile(r'Research\s*Area', re.I))
        if research_area and research_area.parent:
            # Find the next paragraph after the heading
            for elem in research_area.parent.find_all_next():
                if elem.name == 'p':
                    content = elem.get_text().strip()
                    # Stop if we hit a section we don't want
                    if any(kw in content.lower() for kw in [kw.lower() for kw in self.STOP_KEYWORDS_ENGLISH]):
                        break
                    if len(content) > 20:  # Reasonable length for research description
                        return content
        
        return ""

    def clean_text(self, text: str) -> str:
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&[^;]+;', ' ', text)
        text = re.sub(r'[ \t\r\f\v]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n', text)
        text = text.strip()
        
        # Remove common Chinese prefixes
        text = re.sub(r'^[一二三四五六七八九十]\s*、', '', text)
        text = re.sub(r'^\(\d+\)\s*', '', text)
        text = re.sub(r'^\d+\.\s*', '', text)
        
        # Remove any trailing stop keywords
        for kw in self.STOP_KEYWORDS_CHINESE:
            if text.endswith(kw):
                text = text[:-len(kw)].strip()
        
        if self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        return text

    def extract_with_ai_fallback(self, soup, name: str, email: str, research: str) -> Tuple[str, str, str]:
        """Only use AI for missing/failed research field, using publications to infer interests"""
        research_missing = not research or len(research) < 10
        if not research_missing:
            return name, email, research

        # Extract publications/projects section for AI analysis
        publications_text = self.extract_publications_section(soup)
        
        # Primary AI extraction from publications/projects
        if self.ai_extractor and publications_text:
            logger.info("Using AI to infer research interests from publications/projects...")
            research = self.ai_extractor.extract_research_interests_from_publications(
                publications_text, 
                is_chinese=self.is_chinese_site
            )
        
        # Groq fallback if primary AI failed and publications exist
        if self.groq_extractor and not research and publications_text:
            logger.info("Using Groq to infer research interests from publications/projects...")
            research = self.groq_extractor.extract_research_interests_from_publications(
                publications_text, 
                is_chinese=self.is_chinese_site
            )
        
        # If still missing, try general page content
        if not research or len(research) < 10:
            logger.info("Publications-based AI failed, trying general page content...")
            page_text = soup.get_text(" ")[:5000]  # Limit to first 5000 chars
            
            # Check if the page is mostly empty
            if len(page_text.strip()) < 50:
                research = "Not found"
            else:
                research = self.ai_extractor.extract_research_interests_from_content(
                    page_text, 
                    is_chinese=self.is_chinese_site
                ) if self.ai_extractor else "Not found"
            
            # Double-check if we got a valid response
            if not research or research.strip() == "Not found" or "error" in research.lower():
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
        # Set language to Chinese for better compatibility with Chinese sites
        options.add_argument('--lang=zh-CN')

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
                
                # Check if the page is empty
                body_text = soup.body.get_text().strip() if soup.body else ""
                if len(body_text) < 50:
                    logger.warning(f"Page appears to be empty for {url}")
                    return {
                        'name': 'Unknown',
                        'email': 'Not found',
                        'research_interest': 'Not found',
                        'profile_link': url
                    }

                # Traditional extraction first
                name = self.extract_name(soup)
                email = self.extract_email(soup)
                research = self.extract_research_interests_comprehensive(soup)

                logger.info(f"Traditional -> Name: {name}, Email: {email or 'Not found'}, Research chars: {len(research) if research else 0}")

                if email and email in self.processed_emails:
                    logger.info(f"Skipping duplicate email: {email}")
                    return None

                # AI fallback ONLY for missing/failed research fields
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
        description='Faculty Profile Scraper for Chinese Universities'
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
                        help='Use Groq AI as fallback for research interest extraction')
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