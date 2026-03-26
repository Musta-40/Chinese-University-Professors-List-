#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper for Chinese Universities
Updated for both Northwestern University (NWU) and Southwest University (SWU) formats
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
        
        if is_chinese:
            prompt = f"""
分析以下网页内容，提取教师的研究兴趣。

网页内容：
{content[:4000]}

提取策略：
1. 首先查找这些关键词：研究方向、主要研究方向、研究兴趣、科研方向、主要从事、研究领域、学术兴趣、研究专长、RESEARCH INTERESTS
2. 如果找到上述关键词，提取其后的研究描述内容（到下一个章节标题为止，如"学习经历"、"工作经历"、"代表性论文"、"科研项目"等）
3. 如果没有找到明确的研究方向部分，查找"代表性论文"、"发表论文"、"科研项目"、"主持项目"等部分
4. 如果找到论文或项目，根据论文标题和项目名称推断研究兴趣（简短总结，不要列举论文）
5. 研究兴趣应该是简短的学术描述，不应包含个人简历、教育背景、工作经历等

返回格式：
- 如果找到研究兴趣，直接返回研究兴趣文本
- 如果完全没有找到相关信息，返回"Not found"
"""
        else:
            prompt = f"""
Analyze the following webpage content and extract the faculty member's research interests.

Page Content:
{content[:4000]}

Extraction Strategy:
1. First look for these keywords: Research Area, Research Focus, Research Interest, Research Direction, Research Topics, Main Research, RESEARCH INTERESTS
2. If found, extract the research description that follows (until the next section like "Education", "Work Experience", "Publications", "Projects")
3. If no explicit research section found, look for "Publications", "Research Projects", "Grants" sections
4. If publications or projects found, infer research interests from paper titles and project names (provide brief summary, don't list papers)
5. Research interests should be brief academic descriptions, should not include CV, education, work experience

Return Format:
- If research interests found, return the text directly
- If no relevant information found at all, return "Not found"
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


class SmartFacultyProfileScraper:
    """Enhanced scraper for Chinese university faculty pages"""

    # Department/generic emails to ignore
    DEPARTMENT_EMAILS = [
        'bioffice@nwu.edu.cn',
        'office@nwu.edu.cn',
        'admin@nwu.edu.cn',
        'dept@nwu.edu.cn',
        'college@nwu.edu.cn',
        'school@nwu.edu.cn',
        'department@nwu.edu.cn',
        'info@nwu.edu.cn',
        'contact@nwu.edu.cn',
        'webmaster@nwu.edu.cn',
        'secretary@nwu.edu.cn',
        'dean@nwu.edu.cn',
        'bioffice@swu.edu.cn',
        'office@swu.edu.cn',
        'admin@swu.edu.cn'
    ]
    
    # Generic email patterns to ignore
    GENERIC_EMAIL_PATTERNS = [
        r'^(bio|chem|phys|math|cs|ee|me|ce|dept|admin|office|info|contact|web)',
        r'(office|admin|dept|college|school|info|contact|secretary)@',
    ]

    # Research identifiers for Chinese sites (updated for SWU)
    RESEARCH_KEYWORDS_CHINESE = [
        '研究方向', '主要研究方向', '研究兴趣', '科研方向', '主要从事',
        '研究领域', '研究内容', '学术兴趣', '研究课题', '研究重点',
        '研究专长', '学术方向', '科研领域', '主攻方向', '研究范围',
        '研究工作', '科研情况', '目前研究方向', '研究领域与方向',
        '研究方向与领域', '科研方向与领域', '研究内容与方向',
        '研究方向（RESEARCH INTERESTS）', 'RESEARCH INTERESTS'
    ]
    
    # Research identifiers for English sites
    RESEARCH_KEYWORDS_ENGLISH = [
        'Research Area', 'Research Focus', 'Research Interest', 'Research Direction',
        'Research Topics', 'Main Research', 'Research Field', 'Academic Interest',
        'RESEARCH INTERESTS'
    ]
    
    # Critical stop keywords (updated for SWU)
    STOP_KEYWORDS_CHINESE = [
        # Primary stop keywords (section headers)
        '学习经历', '工作经历', '教育背景', '代表性论文', '科研项目',
        '主持项目', '个人邮箱', '上一条：', '下一条：',
        # Original comprehensive list
        '个人简介', '简历', '教育经历', '获奖信息', '社会兼职',
        '论文成果', '发表论文', '专利', '著作成果', '教学资源',
        '授课信息', '教学成果', '团队成员', '招生信息', '联系方式',
        '办公电话', '通信地址', '主要研究成果', '承担的科研项目',
        '获得的教学和科研表彰', '论文列表', '论文目录', '论文发表列表',
        '曾经主持的科研项目', '参与的科研项目', '在研项目', '已完成项目',
        '科研项目列表', '研究项目', '承担项目', '论文发表', '论文',
        '出版论文', '发表文章', '学术论文', '主要论文', '教学工作',
        '教学任务', '教学内容', '教学情况', '教学课程', '学历背景',
        '学历学位', '职业经历', '专业经历', '工作履历', '任职经历',
        '获奖情况', '获奖记录', '获奖成果', '所获奖项', '荣誉奖项',
        '学术兼职', '学术任职', '社会任职', '学术职务', '联系信息',
        '联系电话', '联系地址', '联系邮箱', '个人简历', '个人介绍',
        '个人资料', '学术成果', '科研成果', '出版著作', '著作',
        '软件著作权', '科研奖励', '学术奖励', '社会服务', '研究生招生',
        '本科生教学', '指导学生', '培养研究生', '学术活动', '学术会议',
        '学术报告', '学术交流', '上一篇', '下一篇', '上一页', '下一页',
        '返回顶部', '返回首页', '个人主页', '实验室主页', '研究团队',
        '研究组', '课题组', '代表性成果', '近期成果', '主要成果',
        '成果展示', '成果介绍', '指导研究生', '培养计划', '教学计划',
        '课程设置', '教学大纲', '学术组织', '学术团体', '学术委员会',
        '评审专家', '研究方向与成果', '科研成果与方向', '研究内容与成果'
    ]
    
    STOP_KEYWORDS_ENGLISH = [
        'Biography', 'CV', 'Educational Background', 'Work Experience',
        'Awards', 'Honours', 'Social Affiliations', 'Professional Service',
        'Research Projects', 'Grants', 'Publications', 'Books', 'Patents',
        'Teaching', 'Research Group', 'Lab Members', 'Enrollment Information',
        'Contact', 'Office Phone', 'Address', 'Key Research Achievements',
        'Research Projects Undertaken', 'Teaching and Research Awards',
        'Education', 'Experience', 'Representative Papers'
    ]

    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls: Set[str] = set()
        self.is_chinese_site = False
        self.university_type = None  # 'NWU' or 'SWU' or None

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

    def detect_university_type(self, soup, url: str) -> str:
        """Detect which university system we're dealing with"""
        # Check URL
        if 'nwu.edu.cn' in url:
            return 'NWU'
        elif 'swu.edu.cn' in url:
            return 'SWU'
        
        # Check content patterns
        title = soup.find('title')
        if title:
            title_text = title.get_text()
            if '西北大学' in title_text or 'Northwestern University' in title_text:
                return 'NWU'
            elif '西南大学' in title_text or 'Southwest University' in title_text:
                return 'SWU'
        
        # Check for specific patterns
        if soup.find('div', class_='t_photo') or soup.find('div', class_='danpian-h1'):
            return 'NWU'
        
        return None

    def is_department_email(self, email: str) -> bool:
        """Check if an email is a department/generic email"""
        if not email:
            return False
            
        email_lower = email.lower()
        
        # Check against known department emails
        if email_lower in self.DEPARTMENT_EMAILS:
            logger.debug(f"Email {email} identified as department email (exact match)")
            return True
        
        # Check against generic patterns
        for pattern in self.GENERIC_EMAIL_PATTERNS:
            if re.search(pattern, email_lower):
                logger.debug(f"Email {email} identified as department email (pattern match: {pattern})")
                return True
        
        # Check if email starts with common department prefixes
        local_part = email_lower.split('@')[0]
        if local_part in ['office', 'admin', 'dept', 'department', 'college', 'school', 'info', 'contact', 'secretary']:
            logger.debug(f"Email {email} identified as department email (local part match)")
            return True
        
        return False

    def detect_chinese_site(self, soup) -> bool:
        """Detect if the site is in Chinese based on common patterns"""
        body_text = soup.get_text()
        if re.search(r'[\u4e00-\u9fff]', body_text):
            return True
        
        title = soup.find('title')
        if title and re.search(r'[\u4e00-\u9fff]', title.get_text()):
            return True
            
        return False

    def extract_name_swu(self, soup) -> str:
        """Extract name for Southwest University format"""
        # Strategy 1: Title tag (most reliable for SWU)
        title = soup.find('title')
        if title:
            title_text = title.get_text().strip()
            # Format: "Name-西南大学生命科学学院"
            if '-西南大学' in title_text:
                name = title_text.split('-西南大学')[0].strip()
                # Clean annotations like （兼职）
                name = re.sub(r'[（(][^）)]+[）)]', '', name).strip()
                if name:
                    logger.debug(f"SWU name found in title: {name}")
                    return name
        
        # Strategy 2: Look for name in main content headers
        for tag in ['h1', 'h2', 'h3', 'strong']:
            elements = soup.find_all(tag)
            for elem in elements:
                text = elem.get_text().strip()
                # Look for patterns that might be names (2-4 Chinese characters)
                if re.match(r'^[\u4e00-\u9fff]{2,4}$', text):
                    logger.debug(f"SWU name found in {tag}: {text}")
                    return text
        
        return "Unknown"

    def extract_name_universal(self, soup) -> str:
        """Universal name extraction strategy"""
        # First detect university type
        if self.university_type == 'SWU':
            return self.extract_name_swu(soup)
        
        # NWU extraction strategies
        # Strategy 1: Platform System - Chinese name in photo section
        photo_div = soup.find('div', class_='t_photo')
        if photo_div:
            span = photo_div.find('span')
            if span:
                name = span.get_text(strip=True)
                if name and re.search(r'[\u4e00-\u9fff]', name):
                    logger.debug(f"Name found in t_photo span: {name}")
                    return name
        
        # Strategy 2: College Site - Main title
        danpian = soup.find('div', class_='danpian-h1')
        if danpian:
            name = danpian.get_text(strip=True)
            if name and re.search(r'[\u4e00-\u9fff]', name):
                logger.debug(f"Name found in danpian-h1: {name}")
                return name
        
        # Strategy 3: Platform System - Name header
        t_name = soup.find('div', class_='t_name')
        if t_name:
            name = t_name.get_text(strip=True)
            if name and re.search(r'[\u4e00-\u9fff]', name):
                logger.debug(f"Name found in t_name: {name}")
                return name
        
        # Strategy 4: Name div with strong tag
        name_div = soup.find('div', class_='name')
        if name_div:
            strong = name_div.find('strong')
            if strong:
                name = strong.get_text(strip=True)
                if name:
                    logger.debug(f"Name found in name div strong: {name}")
                    return name
            else:
                name = name_div.get_text(strip=True)
                name = re.sub(r'\s*(教授|副教授|讲师|Professor|Associate Professor).*$', '', name)
                if name:
                    logger.debug(f"Name found in name div: {name}")
                    return name
        
        # Strategy 5: Centered h2 heading
        h2_tags = soup.find_all('h2', style=re.compile(r'text-align:\s*center', re.I))
        for h2 in h2_tags:
            name = h2.get_text(strip=True)
            if name and re.search(r'[\u4e00-\u9fff]', name):
                logger.debug(f"Name found in centered h2: {name}")
                return name
        
        # Strategy 6: Meta description fallback
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            content = meta_desc.get('content').strip()
            match = re.search(r'^([^,，\s]+)[,，]', content)
            if match:
                name = match.group(1).strip()
                if name and re.search(r'[\u4e00-\u9fff]', name):
                    logger.debug(f"Name found in meta description: {name}")
                    return name
        
        # Strategy 7: Title tag fallback
        title = soup.find('title')
        if title:
            t = title.get_text().strip()
            if '/' in t or '／' in t:
                cand = re.split(r'[/／]', t)[0].strip()
                if 2 <= len(cand) <= 10:
                    logger.debug(f"Name found in title: {cand}")
                    return cand
        
        return "Unknown"

    def extract_email_swu(self, soup) -> Optional[str]:
        """Extract email for Southwest University format"""
        html_text = str(soup)
        
        # Strategy 1: Look for "个人邮箱：" pattern
        email_pattern = r'个人邮箱[：:]\s*([a-zA-Z0-9._%+-]+@swu\.edu\.cn)'
        match = re.search(email_pattern, html_text)
        if match:
            email = match.group(1)
            if not self.is_department_email(email):
                logger.debug(f"SWU email found with 个人邮箱: {email}")
                return email
        
        # Strategy 2: Look for mailto links
        mailto_pattern = r'mailto:([a-zA-Z0-9._%+-]+@swu\.edu\.cn)'
        match = re.search(mailto_pattern, html_text)
        if match:
            email = match.group(1)
            if not self.is_department_email(email):
                logger.debug(f"SWU email found in mailto: {email}")
                return email
        
        # Strategy 3: General email pattern
        general_pattern = r'([a-zA-Z0-9._%+-]+@swu\.edu\.cn)'
        matches = re.findall(general_pattern, html_text)
        for email in matches:
            if not self.is_department_email(email):
                logger.debug(f"SWU email found: {email}")
                return email
        
        return None

    def extract_email_universal(self, soup) -> Optional[str]:
        """Universal email extraction strategy"""
        # First try SWU specific extraction if detected
        if self.university_type == 'SWU':
            email = self.extract_email_swu(soup)
            if email:
                return email
        
        html_text = str(soup)
        
        # NWU strategies
        # Strategy 1: Direct email match
        email_patterns = [
            r'[a-zA-Z0-9._%+-]+@nwu\.edu\.cn',
            r'[a-zA-Z0-9._%+-]+@swu\.edu\.cn',
            r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        ]
        
        for pattern in email_patterns:
            match = re.search(pattern, html_text)
            if match:
                email = match.group(0)
                if not self.is_department_email(email):
                    logger.debug(f"Email found directly: {email}")
                    return email
        
        # Strategy 2: Pinyin name pattern (NWU)
        pinyin_patterns = [
            r'教师拼音名称[:：]\s*([a-zA-Z]+)',
            r'拼音名[:：]\s*([a-zA-Z]+)',
            r'Pinyin[:：]\s*([a-zA-Z]+)'
        ]
        
        for pattern in pinyin_patterns:
            match = re.search(pattern, html_text)
            if match:
                pinyin = match.group(1).strip().lower()
                email = f"{pinyin}@nwu.edu.cn"
                logger.debug(f"Email constructed from pinyin: {email}")
                return email
        
        # Strategy 3: Meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and 'content' in meta_desc.attrs:
            content = meta_desc['content']
            match = re.search(r'[^,，\s]+[,，]\s*([a-zA-Z]+)', content)
            if match:
                pinyin = match.group(1).strip().lower()
                pinyin = pinyin.replace(' ', '')
                email = f"{pinyin}@nwu.edu.cn"
                logger.debug(f"Email constructed from meta: {email}")
                return email
        
        # Strategy 4: Look for E-mail: or Email: patterns
        email_label_patterns = [
            r'(?:E[-]?mail|邮箱|Email|个人邮箱)[:：]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        ]
        
        page_text = soup.get_text()
        for pattern in email_label_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                email = match.group(1)
                if not self.is_department_email(email):
                    logger.debug(f"Email found with label: {email}")
                    return email
        
        return None

    def extract_research_interests_swu(self, soup) -> str:
        """Extract research interests for Southwest University format"""
        # Strategy 1: Check meta description for "主要从事" or "主要研究方向"
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            content = meta_desc.get('content').strip()
            
            # Look for patterns
            patterns = [
                r'主要从事(.+?)(?:。|$)',
                r'主要研究方向[：:](.+?)(?:。|$)',
                r'研究方向[：:](.+?)(?:。|$)'
            ]
            
            for pattern in patterns:
                match = re.search(pattern, content)
                if match:
                    research = match.group(1).strip()
                    if research and len(research) > 5:
                        logger.debug(f"SWU research found in meta: {research}")
                        return research
        
        # Strategy 2: Look for explicit research headers in body
        for keyword in ['研究方向', '主要研究方向', '研究兴趣', '科研方向', '主要从事', 
                       '研究方向（RESEARCH INTERESTS）', 'RESEARCH INTERESTS']:
            # Find strong tags with keyword
            strong_tags = soup.find_all('strong', string=re.compile(keyword, re.I))
            for strong in strong_tags:
                # Get parent and following content
                parent = strong.parent
                if parent:
                    # Look for following paragraphs or list items
                    research_parts = []
                    for sibling in parent.find_next_siblings():
                        sibling_text = sibling.get_text(strip=True)
                        # Check for stop keywords
                        if any(stop in sibling_text for stop in self.STOP_KEYWORDS_CHINESE):
                            break
                        if sibling.name in ['p', 'li', 'div']:
                            # Check for bullet points with specific margin
                            style = sibling.get('style', '')
                            if 'margin-left: 24px' in style or sibling.name == 'li':
                                research_parts.append(sibling_text)
                            elif sibling.name == 'p' and not research_parts:
                                # First paragraph after header
                                research_parts.append(sibling_text)
                    
                    if research_parts:
                        research = '; '.join(research_parts)
                        logger.debug(f"SWU research found after {keyword}: {len(research)} chars")
                        return research
        
        # Strategy 3: Look in opening paragraphs for "主要从事"
        paragraphs = soup.find_all('p')
        for p in paragraphs[:10]:  # Check first 10 paragraphs
            text = p.get_text(strip=True)
            if '主要从事' in text:
                # Extract text after '主要从事'
                parts = text.split('主要从事', 1)
                if len(parts) > 1:
                    research = parts[1].strip()
                    # Clean up - remove ending punctuation
                    research = re.split(r'[。；]', research)[0]
                    if research and len(research) > 5:
                        logger.debug(f"SWU research found in paragraph: {research}")
                        return research
        
        return ""

    def extract_research_interests_universal(self, soup) -> str:
        """Universal research interests extraction"""
        # Try SWU specific extraction first if detected
        if self.university_type == 'SWU':
            research = self.extract_research_interests_swu(soup)
            if research:
                return research
        
        # NWU extraction strategies
        interests = []
        
        # Strategy 1: Platform System - TabbedPanels
        tabs = soup.find_all('div', class_='TabbedPanelsContent')
        if len(tabs) > 1:
            links = tabs[1].find_all('a')
            interests = [link.get_text(strip=True) for link in links if link.get_text(strip=True)]
            if interests:
                logger.debug(f"Research found in TabbedPanels: {len(interests)} items")
                return '; '.join(interests)
        
        # Strategy 2: Platform System - "研究方向" block
        research_h2 = soup.find('h2', string=re.compile(r'研究方向'))
        if research_h2:
            container = research_h2.find_parent('div', class_='shworklist')
            if container:
                links = container.find_all('a')
                interests = [link.get_text(strip=True).replace('·', '').strip() for link in links]
                if interests:
                    logger.debug(f"Research found in 研究方向 block: {len(interests)} items")
                    return '; '.join(interests)
        
        # Strategy 3: English "Research Focus" tab
        research_link = soup.find('a', string='Research Focus')
        if research_link:
            all_content_divs = soup.find_all('div', class_='content')
            if len(all_content_divs) >= 3:
                research_div = all_content_divs[2]
                links = research_div.find_all('a')
                interests = [link.get_text(strip=True) for link in links if link.get_text(strip=True)]
                if interests:
                    logger.debug(f"Research found in English tab: {len(interests)} items")
                    return '; '.join(interests)
        
        # Strategy 4: College Site - "主要研究方向"
        strong_tag = soup.find('strong', string=re.compile(r'主要研究方向[:：]'))
        if strong_tag:
            parent_p = strong_tag.parent
            text = parent_p.get_text(separator=' ', strip=True)
            parts = text.split('主要研究方向', 1)
            if len(parts) > 1:
                research_text = parts[1]
                research_text = re.sub(r'^[:：]\s*', '', research_text)
                raw_list = re.split(r'[；。]', research_text)
                interests = [item.strip() for item in raw_list if item.strip() and len(item.strip()) > 5]
                if interests:
                    logger.debug(f"Research found in 主要研究方向: {len(interests)} items")
                    return '; '.join(interests)
        
        # Strategy 5: Scan for "主要从事" in bio paragraphs
        for p in soup.find_all('p'):
            text = p.get_text(strip=True)
            if '主要从事' in text:
                parts = text.split('主要从事', 1)
                if len(parts) > 1:
                    extracted = parts[1]
                    extracted = re.split(r'[。；\s]*$', extracted)[0]
                    raw_interests = re.split(r'[，、]', extracted)
                    interests = [item.strip() for item in raw_interests if item.strip() and len(item.strip()) > 3]
                    if interests:
                        logger.debug(f"Research found in 主要从事: {len(interests)} items")
                        return '; '.join(interests)
        
        # Strategy 6: Look for any research keyword followed by content
        all_keywords = self.RESEARCH_KEYWORDS_CHINESE + self.RESEARCH_KEYWORDS_ENGLISH
        for keyword in all_keywords:
            element = soup.find(string=re.compile(rf'{keyword}[:：]?', re.I))
            if element:
                parent = element.parent
                text_parts = [parent.get_text(strip=True)]
                
                for sibling in parent.find_next_siblings():
                    sibling_text = sibling.get_text(strip=True)
                    if any(stop in sibling_text for stop in self.STOP_KEYWORDS_CHINESE + self.STOP_KEYWORDS_ENGLISH):
                        break
                    if sibling_text:
                        text_parts.append(sibling_text)
                
                full_text = ' '.join(text_parts)
                stop_pattern = '|'.join(map(re.escape, self.STOP_KEYWORDS_CHINESE + self.STOP_KEYWORDS_ENGLISH))
                match = re.search(rf'{re.escape(keyword)}[:：]?\s*(.+?)(?:$|{stop_pattern})', full_text, re.DOTALL | re.IGNORECASE)
                if match:
                    research = match.group(1).strip()
                    if research and len(research) > 10:
                        logger.debug(f"Research found with keyword {keyword}")
                        return self.clean_text(research)
        
        return ""

    def extract_publications_or_projects(self, soup) -> str:
        """Extract recent publications or projects for AI inference"""
        content_parts = []
        
        # Look for publications
        pub_keywords = ['代表性论文', '代表论文', '发表论文', '论文发表', '近期论文', 
                       'Publications', 'Papers', 'Representative Papers']
        for keyword in pub_keywords:
            heading = soup.find(['h1', 'h2', 'h3', 'strong', 'b'], string=re.compile(keyword, re.I))
            if heading:
                count = 0
                for elem in heading.find_next_siblings():
                    if elem.name in ['h1', 'h2', 'h3']:
                        break
                    text = elem.get_text(strip=True)
                    if text and count < 5:
                        content_parts.append(text)
                        count += 1
                if content_parts:
                    logger.debug(f"Found {len(content_parts)} publications")
                    return '\n'.join(content_parts)
        
        # Look for projects
        proj_keywords = ['科研项目', '主持项目', '在研项目', '研究项目', 
                        'Research Projects', 'Grants', 'Projects']
        for keyword in proj_keywords:
            heading = soup.find(['h1', 'h2', 'h3', 'strong', 'b'], string=re.compile(keyword, re.I))
            if heading:
                count = 0
                for elem in heading.find_next_siblings():
                    if elem.name in ['h1', 'h2', 'h3']:
                        break
                    text = elem.get_text(strip=True)
                    if text and count < 5:
                        content_parts.append(text)
                        count += 1
                if content_parts:
                    logger.debug(f"Found {len(content_parts)} projects")
                    return '\n'.join(content_parts)
        
        return ""

    def clean_text(self, text: str) -> str:
        """Clean extracted text"""
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Remove HTML entities
        text = re.sub(r'&[^;]+;', ' ', text)
        # Normalize whitespace
        text = re.sub(r'[ \t\r\f\v]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n', text)
        text = text.strip()
        
        # Remove common prefixes
        text = re.sub(r'^[一二三四五六七八九十]\s*、', '', text)
        text = re.sub(r'^KATEX_INLINE_OPEN\d+KATEX_INLINE_CLOSE\s*', '', text)
        text = re.sub(r'^\d+\.\s*', '', text)
        
        # Truncate if needed
        if self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        
        return text

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
                
                # Detect university type
                self.university_type = self.detect_university_type(soup, url)
                self.is_chinese_site = self.detect_chinese_site(soup)
                logger.debug(f"University: {self.university_type}, Language: {'Chinese' if self.is_chinese_site else 'English'}")
                
                # Check if page is invalid/fragmented (for SWU sources 8-10, 13)
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
                
                # Extract using universal strategies
                name = self.extract_name_universal(soup)
                email = self.extract_email_universal(soup)
                research = self.extract_research_interests_universal(soup)

                # Check if email is a department email
                if email and self.is_department_email(email):
                    logger.info(f"Department email detected ({email}), treating as 'Not found'")
                    email = None

                logger.info(f"Traditional extraction -> Name: {name}, Email: {email or 'Not found'}, Research: {len(research) if research else 0} chars")

                # AI fallback ONLY for missing research
                if (not research or len(research) < 10) and (self.ai_extractor or self.groq_extractor):
                    logger.info("Research not found via traditional extraction, trying AI...")
                    
                    # First get the page content
                    page_content = soup.get_text()[:5000]
                    
                    # Try primary AI
                    if self.ai_extractor:
                        ai_research = self.ai_extractor.extract_research_interests_from_content(
                            page_content,
                            is_chinese=self.is_chinese_site
                        )
                        if ai_research and ai_research != "Not found":
                            research = ai_research
                            logger.info(f"AI extracted research: {len(research)} chars")
                    
                    # Try Groq fallback if still missing
                    if (not research or research == "Not found") and self.groq_extractor:
                        logger.info("Trying Groq fallback...")
                        groq_research = self.groq_extractor.extract_research_interests_from_content(
                            page_content,
                            is_chinese=self.is_chinese_site
                        )
                        if groq_research and groq_research != "Not found":
                            research = groq_research
                            logger.info(f"Groq extracted research: {len(research)} chars")
                    
                    # If still not found, try to infer from publications/projects
                    if not research or research == "Not found":
                        logger.info("Attempting to infer research from publications/projects...")
                        pub_content = self.extract_publications_or_projects(soup)
                        if pub_content:
                            if self.ai_extractor:
                                inference_prompt = f"""Based on these publications/projects, infer the research interests (2-3 sentences):
{pub_content}

Return only the research interests, not the titles."""
                                ai_research = self.ai_extractor.extract_research_interests_from_content(
                                    inference_prompt,
                                    is_chinese=self.is_chinese_site
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
        description='Faculty Profile Scraper for Chinese Universities (NWU & SWU)'
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