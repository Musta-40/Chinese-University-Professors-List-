#!/usr/bin/env python3
"""
Faculty Profile Research Interest Scraper - Enhanced with USTC Chinese Template Support
Based on comprehensive analysis of 14 USTC faculty pages
Updated: Years and DOI patterns as stop keywords
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
from bs4.element import Tag

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class DualTemplateFacultyProfileScraper:
    """Scraper supporting multiple templates including USTC Chinese pages."""

    # ---------- USTC Chinese Keywords (from 14 sources analysis) ----------
    CHINESE_START_KEYWORDS = [
        "主要研究方向",           # Main research directions
        "主要研究兴趣",           # Main research interests  
        "研究方向",               # Research directions (minimal)
        "研究兴趣",               # Research interests (minimal)
        "主要研究方向及内容",      # Main research directions and content
        "主要研究兴趣：",         # With Chinese colon
        "主要研究方向：",         # With Chinese colon
        "研究兴趣:",              # With English colon
        "研究兴趣和方向：",       # Research interests AND directions
        "研究兴趣与方向：",       # Research interests AND directions (formal)
        "研究兴趣：",             # Most minimal form
        "研究方向："              # With Chinese colon
    ]
    
    CHINESE_STOP_KEYWORDS = [
        # Paper sections
        "主要论文", "代表论文", "代表性论文", "发表论文",
        "近期代表论文", "代表性研究论文", "近期代表性论文",
        "近年发表论文", "代表性论文：", "近五年主要科研论文",
        
        # Contact sections
        "联系方式", "联系方法", "实验室网址", "联系方式：",
        "E-mail", "Email", "e-mail", "电话", "Tel:", "Phone:", "邮箱",
        
        # Career/Education sections
        "教育经历", "工作经历", "主持的科研项目", "个人简介",
        
        # Other sections
        "招生招聘", "课题组招聘", "主要在研课题", "招生招聘：",
        "荣誉", "奖励", "基金", "项目", "课题",
        "所获学术荣誉", "更多文章：", "网页：", "research ID"
    ]
    
    CHINESE_MISLEADING_KEYWORDS = [
        # Education/Career
        "毕业于", "获得.*学位", "博士后", "就读于", "工作于",
        
        # Achievements
        "获.*基金", "奖项", "奖励", "当选", "荣获", "院士",
        
        # Publications
        "发表于", "发表在", "被引.*次", "研究成果", "他引.*次",
        
        # Positions
        "现任", "兼任", "曾任", "担任", "理事", "委员",
        
        # Vague descriptions
        "长期从事", "近年来", "致力于", "首次", "阐明",
        "入选", "获评", "主持", "工作发表", "封面文章"
    ]

    # ---------- English Keywords (Original) ----------
    START_HEADING_VARIANTS = [
        'Main Research Areas (Recruitment Fields) and Content',
        'Primary Research Areas (Graduate Programs) and Content',
        'Research Interests',
        'Main Research Directions (Recruitment Fields) and Content',
        'Research Focus',
        'Research Areas',
        'Research Focus (Recruitment Fields)',
        'Main Research Areas (Graduate Programs)',
        'Main Research Directions (Recruitment Specialties) and Content',
        'Primary Research Directions and Specializations',
        'Main Research Directions (Admissions Major) and Content',
        'Main Research Directions',
        'Research Fields of Interests',
        'Research Interest',
        '　RESEARCH INTERESTS',
        'Research Field of Interest:',
    ]

    STOP_HEADING_VARIANTS = [
        'Representative Papers (Last Five Years)',
        'Selected Publications',
        'Publication',
        'Pulications (Chronologically, First Author, Corresponding Author):',
        'Awards and Honors',
        'Education',
        'Selected Publications (Last Five Years)',
        'Professional Titles and Honors',
        'Lab Recruitment',
        'Honors & Awards',
        'Job Opportunities',
        'Study Experience',
    ]

    MISLEADING_HEADINGS = [
        'Education and Work Experience',
        'Academic Achievements and Impact',
        'Ongoing Projects (Principal Investigator Only)',
        'Current Research Projects (Main Investigator Only)',
        'Current Projects (as Principal Investigator)',
        'Contact Information',
        'Personal Profile',
        'Recruitment',
        'Major Research Achievements'
    ]

    # Enhanced patterns for years and DOIs
    YEAR_PATTERN = r'\b(19[5-9]\d|20[0-2]\d)\b'  # Years from 1950-2029
    DOI_PATTERN = r'(?:doi|DOI)[\s:]*10\.\d{4,}[\d\w\-\./]*'
    
    # Additional year patterns for Chinese context
    CHINESE_YEAR_PATTERNS = [
        r'\b(19[5-9]\d|20[0-2]\d)[年\s]',  # 2018年, 1999年
        r'\b(19[5-9]\d|20[0-2]\d)\s*[-–—]\s*(19[5-9]\d|20[0-2]\d)',  # 2018-2020
        r'^\s*```math\n?\d+```?\s*(19[5-9]\d|20[0-2]\d)',  # [1] 2018 (publication list)
    ]

    MISLEADING_CONTENT = [
        'doi', 'DOI', '10.', 'http://', 'https://',
        'ISBN', 'ISSN', '期刊', '会议', 'pp.', 'Vol.',
        '年第', '月第', 'IF=', '影响因子', 'SCI', 'EI',
        '第一作者', '通讯作者', '发表于'
    ]

    def __init__(self, args):
        self.args = args
        self.driver = None
        self.processed_urls: Set[str] = set()

    # ---------- Helpers ----------
    @staticmethod
    def normalize_heading_text(text: Optional[str]) -> str:
        if not text:
            return ''
        return re.sub(r'\s+', ' ', text).strip()

    def is_messy_heading(self, h: Tag) -> bool:
        """Check if heading contains no readable text or only punctuation."""
        try:
            raw_text = self.normalize_heading_text(h.get_text(separator=' ', strip=True))
            if not raw_text:
                contents = (h.decode_contents() or '').strip()
                if re.search(r'<br\s*/?>', contents, flags=re.IGNORECASE):
                    return True
                if re.sub(r'<[^>]+>', '', contents).strip() == '':
                    return True
                return True
            if re.match(r'^[\W_]+$', raw_text):
                return True
            return False
        except Exception:
            return False

    def contains_year_or_doi(self, text: str) -> bool:
        """Check if text contains a year or DOI pattern."""
        if not text:
            return False
        
        # Check for DOI
        if re.search(self.DOI_PATTERN, text):
            return True
        
        # Check for year patterns
        if re.search(self.YEAR_PATTERN, text):
            # Check if it's at the beginning of a line (likely publication)
            lines = text.split('\n')
            for line in lines:
                line = line.strip()
                # Year at the beginning of line
                if re.match(r'^```math\n?\d+```?\s*(19[5-9]\d|20[0-2]\d)', line):
                    return True
                # Year followed by publication indicators
                if re.search(r'(19[5-9]\d|20[0-2]\d)\s*[,，]\s*[A-Z]', line):
                    return True
                # Chinese year format in publication context
                if re.search(r'(19[5-9]\d|20[0-2]\d)[年]\s*[,，、]', line):
                    return True
        
        return False

    # ---------- Template detection ----------
    def detect_template_type(self, soup) -> str:
        """Detect template type including new USTC Chinese template."""
        # Check for USTC Chinese template first
        tits_heading = soup.find('h2', class_='tits')
        wp_articlecontent = soup.find('div', class_='wp_articlecontent')
        if tits_heading and wp_articlecontent:
            return 'TEMPLATE_USTC'
        
        # Original template detection
        teacher_box = soup.find('div', class_='teacher-box')
        if teacher_box:
            return 'TEMPLATE_1'
        arti_title = soup.find('h1', class_='arti_title')
        if arti_title:
            return 'TEMPLATE_2'
        content_div = soup.find('div', class_='content')
        if content_div:
            return 'TEMPLATE_CONTENT_DIV'
        return 'UNKNOWN'

    # ---------- USTC Chinese Template Methods ----------
    def extract_name_ustc(self, soup) -> str:
        """Extract name from USTC template."""
        try:
            name_elem = soup.find('h2', class_='tits')
            if name_elem:
                name = name_elem.get_text(strip=True)
                # Clean common titles
                name = re.sub(r'\s*(博士|硕士|教授|副教授|讲师|助理研究员|研究员|院士)\s*', '', name)
                if name:
                    return name
            # Fallback to title
            return self.extract_name_from_title(soup) or "Unknown"
        except Exception as e:
            logger.error(f"Error extracting USTC name: {e}")
            return "Unknown"

    def extract_email_ustc(self, soup) -> Optional[str]:
        """Extract email from USTC template."""
        try:
            content_div = soup.find('div', class_='wp_articlecontent')
            if not content_div:
                return None
            
            # Try mailto links first
            mailto_links = content_div.find_all('a', href=re.compile(r'mailto:'))
            if mailto_links:
                for link in mailto_links:
                    email = link.get('href', '').replace('mailto:', '').strip()
                    if '@' in email:
                        return email
            
            # Search for email patterns in text
            text = content_div.get_text(separator=' ', strip=True)
            
            # Multiple email patterns
            patterns = [
                r'[Ee]?-?mail[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'邮箱[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'电子邮件[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'([a-zA-Z0-9._%+-]+@ustc\.edu\.cn)'  # Direct USTC email pattern
            ]
            
            for pattern in patterns:
                match = re.search(pattern, text, flags=re.IGNORECASE)
                if match:
                    return match.group(1).strip()
            
            return None
        except Exception as e:
            logger.error(f"Error extracting USTC email: {e}")
            return None

    def extract_research_ustc(self, soup) -> str:
        """Extract research interests from USTC template with year/DOI stopping."""
        try:
            content_div = soup.find('div', class_='wp_articlecontent')
            if not content_div:
                return ""
            
            content_text = content_div.get_text(separator='\n', strip=False)
            
            # Find earliest occurrence of any start keyword
            best_start_pos = -1
            best_start_keyword = ""
            
            for keyword in self.CHINESE_START_KEYWORDS:
                # Try both with and without colons
                patterns = [keyword, keyword + '：', keyword + ':']
                for pattern in patterns:
                    pos = content_text.find(pattern)
                    if pos != -1 and (best_start_pos == -1 or pos < best_start_pos):
                        best_start_pos = pos
                        best_start_keyword = pattern
            
            if best_start_pos == -1:
                logger.debug("No Chinese start keyword found in USTC template")
                return ""
            
            # Extract from start keyword position
            start_text = content_text[best_start_pos + len(best_start_keyword):]
            
            # Split into lines for line-by-line checking
            lines = start_text.split('\n')
            collected_lines = []
            
            for line in lines:
                line_stripped = line.strip()
                
                # Stop if line is empty after several content lines
                if not line_stripped and len(collected_lines) > 3:
                    # Check if next non-empty line contains stop indicators
                    remaining_lines = lines[lines.index(line)+1:]
                    next_content = ' '.join(remaining_lines[:5])
                    if self.contains_year_or_doi(next_content):
                        break
                
                # Stop at year or DOI patterns
                if self.contains_year_or_doi(line_stripped):
                    logger.debug(f"Stopping at year/DOI line: {line_stripped[:50]}")
                    break
                
                # Stop at any stop keyword
                stop_found = False
                for keyword in self.CHINESE_STOP_KEYWORDS:
                    if keyword in line_stripped:
                        logger.debug(f"Stopping at keyword '{keyword}'")
                        stop_found = True
                        break
                
                if stop_found:
                    break
                
                # Add line if it has content
                if line_stripped:
                    collected_lines.append(line_stripped)
            
            # Join collected lines
            research_text = '\n'.join(collected_lines)
            
            # Clean the extracted text
            research_text = self.clean_chinese_research_text(research_text)
            
            if research_text and len(research_text) > 5:
                logger.info(f"USTC research extracted (keyword='{best_start_keyword}'): {len(research_text)} chars")
                return research_text
            
            return ""
            
        except Exception as e:
            logger.error(f"Error extracting USTC research: {e}")
            return ""

    def clean_chinese_research_text(self, text: str) -> str:
        """Clean Chinese research text with year/DOI filtering."""
        if not text:
            return ""
        
        # Remove HTML entities and tags
        text = html.unescape(text)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;|\xa0', ' ', text)
        
        # Filter lines containing misleading keywords or years/DOIs
        lines = text.split('\n')
        filtered_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # Skip lines with years at the beginning (publication pattern)
            if re.match(r'^```math\n?\d+```?\s*(19[5-9]\d|20[0-2]\d)', line):
                logger.debug(f"Filtering out publication line: {line[:50]}")
                continue
            
            # Skip lines with DOI
            if re.search(self.DOI_PATTERN, line):
                logger.debug(f"Filtering out DOI line: {line[:50]}")
                continue
            
            # Skip lines with year in publication context
            if re.search(r'(19[5-9]\d|20[0-2]\d)[年\s].*(发表|论文|期刊|会议)', line):
                logger.debug(f"Filtering out year-publication line: {line[:50]}")
                continue
            
            # Skip lines with misleading content
            skip = False
            for keyword in self.CHINESE_MISLEADING_KEYWORDS:
                if keyword in line:
                    skip = True
                    break
            
            # Additional publication indicators
            if any(pub_word in line for pub_word in ['发表于', '发表在', 'IF=', 'SCI', 'EI', '影响因子']):
                skip = True
            
            if not skip:
                filtered_lines.append(line)
        
        text = '\n'.join(filtered_lines)
        
        # Clean up formatting
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()
        
        # Truncate if needed
        if getattr(self.args, 'truncate', 0) and self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        
        return text

    # ---------- Name extraction ----------
    def extract_name_from_title(self, soup) -> Optional[str]:
        if soup.title and soup.title.string:
            title = soup.title.string.strip()
            # Try to extract name from title if it contains Chinese characters
            # Common pattern: "姓名-职称-单位"
            if '-' in title:
                parts = title.split('-')
                if parts[0] and len(parts[0]) <= 10:  # Reasonable name length
                    return parts[0].strip()
            return title
        return None

    def extract_name_template1(self, soup) -> str:
        try:
            name_elem = soup.select_one('div.teacher-field.title > span.field-info')
            if name_elem:
                name = name_elem.get_text(strip=True)
                name = re.sub(r'\s*(博士|硕士|教授|副教授|讲师|助理研究员|研究员)\s*', '', name)
                if name:
                    return name
            return self.extract_name_from_title(soup) or "Unknown"
        except Exception:
            return "Unknown"

    def extract_name_template2(self, soup) -> str:
        try:
            h1 = soup.find('h1', class_='arti_title')
            if h1:
                n = h1.get_text(strip=True)
                if n:
                    return n
            return self.extract_name_from_title(soup) or "Unknown"
        except Exception:
            return "Unknown"

    # ---------- Email extraction (existing methods) ----------
    def extract_email_from_contact_section(self, soup) -> Optional[str]:
        try:
            for h3 in soup.find_all('h3'):
                h3_text = (h3.get_text(strip=True) or '').lower()
                if 'contact' in h3_text or '联系' in h3_text:
                    for sib in h3.find_next_siblings():
                        if sib.name and sib.name.lower() == 'p':
                            text = sib.get_text(separator=' ', strip=True)
                            if re.search(r'\b(e-?mail|email|E-?mail|Email|邮箱)\b', text, flags=re.IGNORECASE):
                                m = re.search(r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', text)
                                if m:
                                    return m.group(1).strip()
                        if sib.name and sib.name.lower().startswith('h'):
                            break
            return None
        except Exception:
            return None

    def extract_email_from_content_div(self, soup) -> Optional[str]:
        try:
            content_div = soup.find('div', class_='content')
            if not content_div:
                return None
            for p in content_div.find_all('p'):
                text = p.get_text(separator=' ', strip=True)
                if re.search(r'\b(e-?mail|email|E-?mail|Email|邮箱)\b', text, flags=re.IGNORECASE):
                    m = re.search(r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', text)
                    if m:
                        return m.group(1).strip()
            text_blob = content_div.get_text(separator=' ', strip=True)
            m = re.search(r'\b(e-?mail|email|E-?mail|Email|邮箱)\b.*?([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', text_blob, flags=re.IGNORECASE)
            if m:
                return m.group(2).strip()
            return None
        except Exception:
            return None

    def extract_email_template1(self, soup) -> Optional[str]:
        try:
            email_elem = soup.select_one('div.teacher-field.dh > span.field-info.i2')
            if email_elem:
                text = email_elem.get_text(strip=True).replace('邮箱：', '').replace('邮箱:', '').strip()
                m = re.search(r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', text)
                if m:
                    return m.group(1)
            return self.extract_email_from_contact_section(soup) or self.extract_email_from_content_div(soup)
        except Exception:
            return None

    def extract_email_template2(self, soup) -> Optional[str]:
        try:
            for p in soup.find_all('p'):
                text = p.get_text(separator=' ', strip=True)
                if re.search(r'\b(e-?mail|email|E-?mail|Email|邮箱)\b', text, flags=re.IGNORECASE):
                    m = re.search(r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', text)
                    if m:
                        return m.group(1)
            return self.extract_email_from_contact_section(soup) or self.extract_email_from_content_div(soup)
        except Exception:
            m = re.search(r'([A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,})', soup.get_text(separator=' ', strip=True))
            if m:
                return m.group(1)
            return None

    # ---------- Research extraction with year/DOI stopping ----------
    def extract_research_from_content_div(self, soup) -> str:
        """Consolidated extraction for English content div with year/DOI stopping."""
        try:
            content_div = soup.find('div', class_='content')
            if not content_div:
                return ""

            # Check if this might be Chinese content
            sample_text = content_div.get_text()[:500]
            if any(keyword in sample_text for keyword in self.CHINESE_START_KEYWORDS):
                # Use Chinese extraction logic
                return self.extract_research_chinese_content_div(content_div)

            # Continue with English extraction
            start_variants = [self.normalize_heading_text(s).lower() for s in self.START_HEADING_VARIANTS]
            stop_variants = [self.normalize_heading_text(s).lower() for s in self.STOP_HEADING_VARIANTS]
            misleading_variants = [self.normalize_heading_text(s).lower() for s in self.MISLEADING_HEADINGS]

            for h3 in content_div.find_all('h3'):
                heading_text = self.normalize_heading_text(h3.get_text(strip=True)).lower()

                is_start = any(sv.strip().lower() in heading_text for sv in start_variants)
                if not is_start:
                    continue

                collected_parts: List[str] = []
                for sibling in h3.find_next_siblings():
                    if isinstance(sibling, Tag) and sibling.name and sibling.name.lower() == 'h3':
                        sib_text = self.normalize_heading_text(sibling.get_text(strip=True)).lower()

                        if self.is_messy_heading(sibling):
                            logger.debug("Stopping due to messy heading pattern.")
                            break

                        if any(stop.strip().lower() in sib_text for stop in stop_variants):
                            logger.debug(f"Stopping at stop heading: {sib_text}")
                            break

                        if any(mis.strip().lower() in sib_text for mis in misleading_variants):
                            logger.debug(f"Stopping at misleading heading: {sib_text}")
                            break

                        # Stop if heading contains year or DOI
                        if self.contains_year_or_doi(sib_text):
                            logger.debug("Stopping at heading containing year or DOI.")
                            break

                        continue

                    text = sibling.get_text(separator=' ', strip=True)
                    if not text:
                        continue

                    # Stop if the sibling contains year or DOI patterns
                    if self.contains_year_or_doi(text):
                        logger.debug("Stopping at sibling containing year or DOI.")
                        break

                    if any(stop.strip().lower() in text.lower() for stop in stop_variants + misleading_variants):
                        logger.debug("Stopping because sibling contains a stop/misleading keyword.")
                        break

                    if len(text) >= 6:
                        collected_parts.append(text)

                if collected_parts:
                    research_text = '\n\n'.join(collected_parts)
                    research_text = self.clean_research_text(research_text)
                    if research_text and len(research_text) > 5:
                        logger.info(f"Research extracted (content div): {len(research_text)} chars")
                        return research_text

            return ""
        except Exception as e:
            logger.error(f"Error extracting research from content div: {e}")
            return ""

    def extract_research_chinese_content_div(self, content_div) -> str:
        """Extract Chinese research from content div with year/DOI stopping."""
        content_text = content_div.get_text(separator='\n', strip=False)
        
        best_start_pos = -1
        best_start_keyword = ""
        
        for keyword in self.CHINESE_START_KEYWORDS:
            patterns = [keyword, keyword + '：', keyword + ':']
            for pattern in patterns:
                pos = content_text.find(pattern)
                if pos != -1 and (best_start_pos == -1 or pos < best_start_pos):
                    best_start_pos = pos
                    best_start_keyword = pattern
        
        if best_start_pos == -1:
            return ""
        
        start_text = content_text[best_start_pos + len(best_start_keyword):]
        
        # Process line by line with year/DOI checking
        lines = start_text.split('\n')
        collected_lines = []
        
        for line in lines:
            line_stripped = line.strip()
            
            # Stop at year or DOI
            if self.contains_year_or_doi(line_stripped):
                break
            
            # Stop at stop keywords
            stop_found = False
            for keyword in self.CHINESE_STOP_KEYWORDS:
                if keyword in line_stripped:
                    stop_found = True
                    break
            
            if stop_found:
                break
            
            if line_stripped:
                collected_lines.append(line_stripped)
        
        research_text = '\n'.join(collected_lines)
        research_text = self.clean_chinese_research_text(research_text)
        
        if research_text and len(research_text) > 5:
            return research_text
        
        return ""

    def extract_research_template1(self, soup) -> str:
        try:
            research_elem = soup.select_one('div.teacher-field.dh > span.field-info.i4 > p')
            if research_elem:
                research_text = research_elem.get_text(strip=True)
                for keyword in ['研究方向：', '研究方向:', '研究兴趣：', '研究兴趣:']:
                    if research_text.startswith(keyword):
                        research_text = research_text[len(keyword):].strip()
                research_text = self.clean_research_text(research_text)
                if research_text and len(research_text) > 5:
                    return research_text

            research_elem = soup.select_one('div.teacher-field.dh > span.field-info.i4')
            if research_elem:
                research_text = research_elem.get_text(strip=True)
                for keyword in ['研究方向：', '研究方向:', '研究兴趣：', '研究兴趣:']:
                    if research_text.startswith(keyword):
                        research_text = research_text[len(keyword):].strip()
                research_text = self.clean_research_text(research_text)
                if research_text and len(research_text) > 5:
                    return research_text

            cd = self.extract_research_from_content_div(soup)
            if cd:
                return cd
            meta_extracted = self.extract_from_meta_description(soup)
            if meta_extracted:
                return meta_extracted
            return ""
        except Exception:
            return ""

    def extract_research_template2(self, soup) -> str:
        try:
            # Check for Chinese keywords first
            content_text = soup.get_text()[:1000]
            has_chinese = any(keyword in content_text for keyword in self.CHINESE_START_KEYWORDS)
            
            if has_chinese:
                # Use Chinese extraction with year/DOI stopping
                for keyword in self.CHINESE_START_KEYWORDS:
                    for elem in soup.find_all(['p', 'h2', 'h3', 'h4', 'strong', 'div']):
                        elem_text = elem.get_text(strip=True)
                        if keyword in elem_text:
                            research_content = []
                            if elem_text != keyword and len(elem_text) > len(keyword) + 5:
                                content = elem_text.replace(keyword, '').replace('：', '').replace(':', '').strip()
                                if content and not any(stop in content for stop in self.CHINESE_STOP_KEYWORDS):
                                    # Check for year/DOI
                                    if not self.contains_year_or_doi(content):
                                        research_content.append(content)
                            
                            for sibling in elem.find_next_siblings():
                                sibling_text = sibling.get_text(strip=True)
                                
                                # Stop at year/DOI
                                if self.contains_year_or_doi(sibling_text):
                                    break
                                
                                if any(stop in sibling_text for stop in self.CHINESE_STOP_KEYWORDS):
                                    break
                                
                                if sibling_text and len(sibling_text) > 5:
                                    research_content.append(sibling_text)
                            
                            if research_content:
                                research_text = '\n'.join(research_content)
                                return self.clean_chinese_research_text(research_text)
            else:
                # Use English extraction with year/DOI stopping
                research_content = []
                found_start = False
                for keyword in ['研究兴趣', '研究方向', 'Research Interest', 'Research Focus']:
                    for elem in soup.find_all(['p', 'h2', 'h3', 'h4', 'strong', 'div']):
                        elem_text = elem.get_text(strip=True)
                        if keyword in elem_text:
                            found_start = True
                            if elem_text != keyword and len(elem_text) > len(keyword) + 5:
                                content = elem_text.replace(keyword, '').strip()
                                if content and not any(stop in content for stop in self.STOP_HEADING_VARIANTS):
                                    if not self.contains_year_or_doi(content):
                                        research_content.append(content)
                            
                            for sibling in elem.find_next_siblings():
                                sibling_text = sibling.get_text(strip=True)
                                
                                # Stop at year/DOI
                                if self.contains_year_or_doi(sibling_text):
                                    break
                                
                                if any(stop in sibling_text for stop in self.STOP_HEADING_VARIANTS):
                                    break
                                
                                if sibling_text and len(sibling_text) > 5:
                                    research_content.append(sibling_text)
                            
                            if research_content:
                                break
                    if found_start:
                        break

                if research_content:
                    research_text = '\n'.join(research_content)
                    research_text = self.clean_research_text(research_text)
                    if research_text and len(research_text) > 5:
                        return research_text

            cd = self.extract_research_from_content_div(soup)
            if cd:
                return cd

            meta_extracted = self.extract_from_meta_description(soup)
            if meta_extracted:
                return meta_extracted

            return ""
        except Exception:
            return ""

    def extract_from_meta_description(self, soup) -> str:
        try:
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
            content = html.unescape(content).replace('\xa0', ' ').replace('&nbsp;', ' ')
            pattern = re.compile(r'(?:研究方向|研究兴趣|研究领域)[:：]\s*([^；;。．.，,专业姓名]+)', flags=re.UNICODE)
            m = pattern.search(content)
            if m:
                extracted = m.group(1).strip()
                extracted = self.clean_research_text(extracted)
                if extracted:
                    return extracted
            return ""
        except Exception:
            return ""

    def clean_research_text(self, text: str) -> str:
        """Clean research text with enhanced year/DOI filtering."""
        if not text:
            return ""
        
        # Check if text is primarily Chinese
        chinese_chars = len(re.findall(r'[\u4e00-\u9fff]', text))
        total_chars = len(text)
        
        if total_chars > 0 and chinese_chars / total_chars > 0.3:
            # Use Chinese cleaning
            return self.clean_chinese_research_text(text)
        
        # Original English cleaning with enhanced year/DOI filtering
        text = html.unescape(text)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'&nbsp;|\xa0', ' ', text)
        
        # Remove lines starting with years or containing DOIs
        lines = text.split('\n')
        filtered_lines = []
        
        for line in lines:
            line = line.strip()
            
            # Skip lines starting with year patterns
            if re.match(r'^```math\n?\d+```?\s*(19[5-9]\d|20[0-2]\d)', line):
                continue
            
            # Skip lines with DOI
            if re.search(self.DOI_PATTERN, line):
                continue
            
            # Skip lines that are likely publications
            if re.search(r'(19[5-9]\d|20[0-2]\d).*\.(pdf|PDF)', line):
                continue
            
            # Skip lines with publication indicators
            skip = False
            for keyword in self.MISLEADING_CONTENT:
                if keyword in ['doi', 'DOI', 'http://', 'https://']:
                    continue
                if keyword in line:
                    skip = True
                    break
            
            if not skip and line:
                filtered_lines.append(line)
        
        text = '\n'.join(filtered_lines)
        
        # Additional cleanup
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = text.strip()
        
        if getattr(self.args, 'truncate', 0) and self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        
        return text

    # ---------- Driver setup and scraping ----------
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
                WebDriverWait(self.driver, 20).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                time.sleep(1.0)

                soup = BeautifulSoup(self.driver.page_source, 'html.parser')
                template = self.detect_template_type(soup)

                if self.args.debug:
                    logger.debug(f"Template detected: {template}")

                name = "Unknown"
                email = None
                research = ""

                if template == 'TEMPLATE_USTC':
                    # Use USTC-specific extraction
                    name = self.extract_name_ustc(soup)
                    email = self.extract_email_ustc(soup)
                    research = self.extract_research_ustc(soup)
                elif template == 'TEMPLATE_1':
                    name = self.extract_name_template1(soup)
                    email = self.extract_email_template1(soup)
                    research = self.extract_research_template1(soup)
                elif template == 'TEMPLATE_2':
                    name = self.extract_name_template2(soup)
                    email = self.extract_email_template2(soup)
                    research = self.extract_research_template2(soup)
                elif template == 'TEMPLATE_CONTENT_DIV':
                    title_name = self.extract_name_from_title(soup)
                    name = title_name or self.extract_name_template1(soup) or "Unknown"
                    email = self.extract_email_from_contact_section(soup) or self.extract_email_from_content_div(soup)
                    research = self.extract_research_from_content_div(soup)
                    if not research:
                        research = self.extract_from_meta_description(soup)
                else:
                    # Try all methods for unknown template
                    name = self.extract_name_ustc(soup) or self.extract_name_template1(soup) or self.extract_name_template2(soup) or self.extract_name_from_title(soup) or "Unknown"
                    email = self.extract_email_ustc(soup) or self.extract_email_template1(soup) or self.extract_email_template2(soup)
                    research = self.extract_research_ustc(soup) or self.extract_research_template1(soup) or self.extract_research_template2(soup) or self.extract_research_from_content_div(soup) or self.extract_from_meta_description(soup)

                if not name or name == "Unknown":
                    name = "Unknown"
                if not email:
                    email = "Not found"
                if not research or len(research) < 5:
                    research = "Not found"

                self.processed_urls.add(normalized_url)

                logger.info(f"Extraction -> Name: {name}, Email: {email}, Research: {research[:100]}{'...' if len(research)>100 else ''}")

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
                time.sleep(2)

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
    parser = argparse.ArgumentParser(description='Faculty Profile Scraper with Year/DOI Stop Detection')
    parser.add_argument('--input-file', default='urls.txt', help='Input file containing URLs (one per line)')
    parser.add_argument('--output-file', default='output.txt', help='Output file for results')
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--delay-min', type=float, default=1.0, help='Minimum delay between requests (seconds)')
    parser.add_argument('--delay-max', type=float, default=3.0, help='Maximum delay between requests (seconds)')
    parser.add_argument('--max-profiles', type=int, default=0, help='Max number of profiles to process (0=unlimited)')
    parser.add_argument('--retries', type=int, default=2, help='Number of retries for failed requests')
    parser.add_argument('--truncate', type=int, default=4000, help='Max length for research text (0=no limit)')
    parser.add_argument('--append', action='store_true', help='Append to output file instead of overwriting')
    parser.add_argument('--json-output', action='store_true', help='Also save output as JSON')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode with diagnostic output')

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    scraper = DualTemplateFacultyProfileScraper(args)
    scraper.run()


if __name__ == '__main__':
    main()
