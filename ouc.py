#!/usr/bin/env python3
"""
Universal Faculty Profile Research Interest Scraper with AI
Enhanced for Chinese university websites including OUC support.
"""

import os
import argparse
import json
import logging
import random
import re
import time
import platform
from pathlib import Path
from typing import Dict, Optional, Set, List, Tuple

# Load .env robustly
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
    """AI-powered content extractor (used only as fallback)"""

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

    def extract_email_from_content(self, page_content: str, faculty_name: str = "") -> str:
        """Extract email using AI - specifically looking for 电子邮箱"""
        
        max_content_length = 8000
        if len(page_content) > max_content_length:
            page_content = page_content[:max_content_length]

        prompt = f"""
        Extract the personal email address from this faculty webpage.
        
        Faculty Name: {faculty_name if faculty_name else "Unknown"}
        
        Page Content:
        {page_content}
        
        Instructions:
        1. ACTIVELY look for keywords: 电子邮箱, 邮箱, Email, E-mail, 电子邮件
        2. Extract the email address that follows these keywords
        3. IGNORE department/generic emails like: smp@, cs@, dept@, admin@, office@ (usually 2-3 letters before @)
        4. Look for personal emails with longer usernames (e.g., wangyong8866@ouc.edu.cn)
        5. Emails may end with @ouc.edu.cn, @163.com, or other domains
        6. If multiple emails found, prefer the one with longer username
        7. If no personal email found, return "Not found"
        
        Return ONLY the email address or "Not found", nothing else.
        """

        try:
            if self.provider == 'openai':
                response = self.client.ChatCompletion.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You extract email addresses from academic webpages."},
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
                        {"role": "system", "content": "You extract email addresses from academic webpages."},
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

    def extract_research_from_content(self, page_content: str, faculty_name: str = "") -> str:
        """Extract or infer research interests from page content"""
        
        max_content_length = 10000
        if len(page_content) > max_content_length:
            page_content = page_content[:max_content_length]

        prompt = f"""
        Extract research interests from this faculty webpage.
        
        Faculty Name: {faculty_name if faculty_name else "Unknown"}
        
        Page Content:
        {page_content}
        
        Instructions:
        1. ACTIVELY look for these keywords: 研究方向, 研究领域, 研究兴趣, 主要研究领域, 研究方向及内容, Research Area, Research Direction
        2. If found, extract the content that follows (but STOP at: 个人简介, 教育背景, 工作经历)
        3. If keywords NOT found, INFER research interests from:
           - Publication titles (look for: 发表论文, Publications, 期刊论文)
           - Project titles (look for: 科研项目, 研究项目, Projects)
           - Any research-related descriptions in the text
        4. Focus on specific research topics, methodologies, and areas
        5. Do NOT include: biographical info (个人简介), education (教育背景), work experience (工作经历), awards
        6. If absolutely no research information can be found or inferred, return "Not found"
        7. Output as a coherent paragraph (max 300 words) describing their research focus
        
        Research Interests:
        """

        try:
            if self.provider == 'openai':
                response = self.client.ChatCompletion.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You analyze faculty profiles and extract/infer research interests."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=400,
                    temperature=0.2
                )
                return response.choices[0].message.content.strip()

            elif self.provider == 'anthropic':
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=400,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}]
                )
                return response.content[0].text.strip()

            elif self.provider == 'groq':
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You analyze faculty profiles and extract/infer research interests."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=400,
                    temperature=0.2
                )
                return response.choices[0].message.content.strip()

            elif self.provider == 'gemini':
                response = self.model.generate_content(prompt)
                return (response.text or "").strip()

        except Exception as e:
            logger.error(f"AI research extraction failed ({self.provider}): {str(e)}")
            return "Not found"


class SmartFacultyProfileScraper:
    """Enhanced scraper with OUC support"""

    # Research identifiers - expanded for OUC
    RESEARCH_KEYWORDS = [
        # Chinese - prioritized
        '研究方向', '研究领域', '研究兴趣', '科研方向', '主要研究方向',
        '主要研究领域', '研究内容', '学术方向', '科研领域', '研究重点',
        '研究方向及内容', '主要研究内容',
        # English
        'research area', 'research areas', 'research interest', 'research interests',
        'research direction', 'research directions', 'research field', 'research focus'
    ]
    
    # Stop sections (where research description ends) - Updated for OUC
    STOP_SECTIONS = [
        '个人简介', '教育背景', '工作经历', '学术经历', '获奖情况',
        '科研项目', '发表论文', '代表性论文', '论文发表', '教学工作',
        '学术兼职', '联系方式', '个人简历', '主要成果', '授权专利',
        '教育经历', '工作履历', '学习经历', '招生信息', '教育背景'
    ]
    
    # Department/generic email patterns to exclude
    DEPARTMENT_EMAIL_PATTERNS = [
        # Very short usernames (2-3 letters) often indicate departments
        r'^[a-z]{1,3}@',  # e.g., smp@, cs@, it@
        # Common department/office keywords
        r'^(dept|department|admin|office|info|contact|secretary|webmaster|postmaster)@',
        r'^(学院|系|办公室|院办|系办|教务|管理)@',
        # Specific OUC department abbreviations
        r'^(smp|cms|som|soe|scs|sbs|sols|spms)@',  # School abbreviations
        # Generic emails
        r'^(mail|email|service|support|help)@',
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

    def is_department_email(self, email: str) -> bool:
        """Check if email appears to be a department/generic email"""
        if not email:
            return False
        
        email_lower = email.lower()
        
        # Specific check for known department emails
        if email_lower in ['smp@ouc.edu.cn', 'cs@ouc.edu.cn', 'dept@ouc.edu.cn']:
            return True
        
        # Check against department patterns
        for pattern in self.DEPARTMENT_EMAIL_PATTERNS:
            if re.match(pattern, email_lower, re.IGNORECASE):
                logger.debug(f"Email {email} matches department pattern {pattern}")
                return True
        
        # Check username length (very short = likely department)
        username = email.split('@')[0]
        if len(username) <= 3 and username.isalpha():
            logger.debug(f"Email {email} has very short username, likely department email")
            return True
        
        return False

    def extract_from_ouc_meta(self, soup) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract from OUC META description format"""
        name = None
        email = None
        research = None
        
        # Extract name from simple title tag
        title = soup.find('title')
        if title:
            title_text = title.get_text().strip()
            # OUC often has just the name in title
            if title_text and len(title_text) <= 10:
                # Check if it looks like a Chinese name
                if re.match(r'^[\u4e00-\u9fa5]{2,4}$', title_text):
                    name = title_text
                    logger.debug(f"Extracted name from title: {name}")
        
        # Extract from META description
        meta_desc = soup.find('meta', attrs={'name': re.compile('description', re.I), 'content': True})
        if meta_desc:
            content = meta_desc.get('content', '')
            logger.debug(f"META description content length: {len(content)}")
            
            # Extract email - look for 电子邮箱：xxx@domain
            email_patterns = [
                r'电子邮箱[：:]\s*([\w\.-]+@(?:ouc\.edu\.cn|163\.com|[\w\.-]+\.[\w]+))',
                r'邮箱[：:]\s*([\w\.-]+@(?:ouc\.edu\.cn|163\.com|[\w\.-]+\.[\w]+))',
                r'Email[：:]\s*([\w\.-]+@(?:ouc\.edu\.cn|163\.com|[\w\.-]+\.[\w]+))',
                r'E-mail[：:]\s*([\w\.-]+@(?:ouc\.edu\.cn|163\.com|[\w\.-]+\.[\w]+))',
            ]
            
            for pattern in email_patterns:
                matches = re.finditer(pattern, content, re.IGNORECASE)
                for match in matches:
                    candidate_email = match.group(1)
                    # Check if it's not a department email
                    if not self.is_department_email(candidate_email):
                        email = candidate_email
                        logger.debug(f"Found personal email in META: {email}")
                        break
                    else:
                        logger.debug(f"Skipped department email: {candidate_email}")
                if email:
                    break
            
            # Extract research from META - between 研究方向： and 个人简介
            research_patterns = [
                r'研究方向[：:](.+?)(?:个人简介|教育背景|工作经历|教育经历|$)',
                r'研究领域[：:](.+?)(?:个人简介|教育背景|工作经历|教育经历|$)',
                r'主要研究领域[：:](.+?)(?:个人简介|教育背景|工作经历|教育经历|$)',
            ]
            
            for pattern in research_patterns:
                match = re.search(pattern, content, re.DOTALL)
                if match:
                    research_text = match.group(1).strip()
                    # Clean up the research text
                    research_text = re.sub(r'^\d+\.\s*', '', research_text)  # Remove leading numbers
                    research_text = re.sub(r'\s+', ' ', research_text)  # Normalize whitespace
                    
                    if research_text and len(research_text) > 10:
                        research = research_text
                        logger.debug(f"Found research in META: {len(research)} chars")
                        break
        
        return name, email, research

    def extract_name(self, soup) -> str:
        """Extract faculty name from page"""
        # Try OUC format first
        name, _, _ = self.extract_from_ouc_meta(soup)
        if name:
            return name
        
        # Try simple title extraction
        title = soup.find('title')
        if title:
            title_text = title.get_text().strip()
            # Clean up common patterns
            if '|' in title_text or '-' in title_text or '－' in title_text:
                # Take first part before separator
                title_text = re.split(r'[|\-－]', title_text)[0].strip()
            
            # Check if it's a reasonable name
            if title_text and 1 < len(title_text) <= 10:
                # Check for Chinese name pattern
                if re.match(r'^[\u4e00-\u9fa5]{2,4}$', title_text):
                    logger.debug(f"Extracted name from title: {title_text}")
                    return title_text
        
        logger.debug("Could not extract name")
        return "Unknown"

    def extract_email(self, soup) -> Optional[str]:
        """Extract email address from page (excluding department emails)"""
        # Try OUC META format first
        _, email, _ = self.extract_from_ouc_meta(soup)
        if email:
            return email
        
        # Look in page HTML for emails
        page_html = str(soup)
        email_patterns = [
            r'电子邮箱[：:]\s*([\w\.-]+@[\w\.-]+\.[\w]+)',
            r'邮箱[：:]\s*([\w\.-]+@[\w\.-]+\.[\w]+)',
            r'E-mail[：:]\s*([\w\.-]+@[\w\.-]+\.[\w]+)',
            r'Email[：:]\s*([\w\.-]+@[\w\.-]+\.[\w]+)',
        ]
        
        for pattern in email_patterns:
            matches = re.finditer(pattern, page_html, re.IGNORECASE)
            for match in matches:
                candidate_email = match.group(1)
                if not self.is_department_email(candidate_email):
                    logger.debug(f"Found personal email in HTML: {candidate_email}")
                    return candidate_email
                else:
                    logger.debug(f"Skipped department email: {candidate_email}")
        
        # General search for emails in text
        page_text = soup.get_text(" ")
        # Find all emails (including @163.com and other domains)
        all_emails = re.findall(r'[\w\.-]+@[\w\.-]+\.[\w]+', page_text, re.IGNORECASE)
        
        # Filter out department emails
        for email in all_emails:
            if not self.is_department_email(email):
                logger.debug(f"Found personal email in text: {email}")
                return email
            else:
                logger.debug(f"Skipped department email: {email}")
        
        logger.debug("No personal email found with traditional extraction")
        return None

    def extract_research_interests_comprehensive(self, soup) -> str:
        """Comprehensive research extraction trying all methods"""
        
        # Method 1: Try OUC META format
        _, _, research = self.extract_from_ouc_meta(soup)
        if research and len(research) > 20:
            logger.debug(f"Using research from OUC META format: {len(research)} chars")
            return self.clean_text(research)
        
        # Method 2: Look in page text for research sections
        page_text = soup.get_text("\n")
        
        # Build stop pattern with all stop sections
        stop_pattern = '|'.join(re.escape(stop) for stop in self.STOP_SECTIONS)
        
        for keyword in self.RESEARCH_KEYWORDS:
            # Create pattern to match research keyword and capture until stop section
            pattern = re.compile(
                rf'{re.escape(keyword)}[：:]?\s*(.+?)(?:{stop_pattern}|$)',
                re.IGNORECASE | re.DOTALL
            )
            
            match = pattern.search(page_text)
            if match:
                research_text = match.group(1).strip()
                
                # Clean up
                research_text = re.sub(r'^\d+\.\s*', '', research_text)  # Remove leading numbers
                research_text = re.sub(r'\s+', ' ', research_text)  # Normalize whitespace
                
                if research_text and len(research_text) > 30:
                    logger.debug(f"Extracted research from pattern '{keyword}': {len(research_text)} chars")
                    return self.clean_text(research_text)
        
        # Method 3: Look in HTML for specific patterns
        page_html = str(soup)
        html_patterns = [
            (r'研究方向[：:]\s*(.+?)(?:个人简介|教育背景|工作经历|$)', re.IGNORECASE | re.DOTALL),
            (r'研究领域[：:]\s*(.+?)(?:个人简介|教育背景|工作经历|$)', re.IGNORECASE | re.DOTALL),
            (r'主要研究[：:]\s*(.+?)(?:个人简介|教育背景|工作经历|$)', re.IGNORECASE | re.DOTALL),
            (r'研究方向及内容[：:]\s*(.+?)(?:个人简介|教育背景|工作经历|$)', re.IGNORECASE | re.DOTALL),
        ]
        
        for pattern, flags in html_patterns:
            match = re.search(pattern, page_html, flags)
            if match:
                research_html = match.group(1)
                # Clean HTML
                research_text = re.sub(r'<[^>]+>', ' ', research_html)
                research_text = re.sub(r'&[^;]+;', ' ', research_text)
                research_text = re.sub(r'\s+', ' ', research_text).strip()
                
                if research_text and len(research_text) > 30:
                    logger.debug(f"Extracted research from HTML pattern: {len(research_text)} chars")
                    return self.clean_text(research_text)
        
        logger.debug("Could not extract research interests with traditional methods")
        return ""

    def clean_text(self, text: str) -> str:
        """Clean extracted text"""
        text = re.sub(r'<[^>]+>', '', text)           # strip HTML
        text = re.sub(r'&[^;]+;', ' ', text)          # strip HTML entities
        text = re.sub(r'[ \t\r\f\v]+', ' ', text)     # collapse spaces
        text = re.sub(r'\n\s*\n+', '\n', text)        # collapse blank lines
        text = text.strip()

        # Remove common prefixes
        text = re.sub(r'^[：:]\s*', '', text)
        
        # Remove any stop sections that might have been included
        for stop in self.STOP_SECTIONS:
            if stop in text:
                idx = text.find(stop)
                text = text[:idx].strip()
        
        if self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        return text

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
                
                # Check if page has content
                page_text = soup.get_text().strip()
                if len(page_text) < 100:
                    logger.info(f"Page appears to be empty: {url}")
                    return {
                        'name': 'Not found',
                        'email': 'Not found',
                        'research_interest': 'Not found',
                        'profile_link': url
                    }

                # Extract basics with traditional methods
                name = self.extract_name(soup)
                email = self.extract_email(soup)
                research_interests = self.extract_research_interests_comprehensive(soup)
                
                logger.info(f"Traditional extraction - Name: {name}, Email: {email or 'Not found'}, Research: {len(research_interests) if research_interests else 0} chars")
                
                # Prepare page text for AI if needed
                page_text_for_ai = None
                if not email or not research_interests or len(research_interests) < 30:
                    for script in soup(["script", "style", "noscript"]):
                        script.decompose()
                    page_text_for_ai = soup.get_text(" ")
                    page_text_for_ai = re.sub(r'\s+', ' ', page_text_for_ai).strip()
                
                # Use AI for email if traditional extraction failed
                if not email and self.ai_extractor:
                    logger.info(f"Using AI to extract email for: {name}")
                    ai_email = self.ai_extractor.extract_email_from_content(page_text_for_ai, name)
                    if ai_email and ai_email != "Not found" and not self.is_department_email(ai_email):
                        email = ai_email
                        logger.info(f"AI extracted email: {email}")
                
                # Use AI for research if traditional extraction failed
                if (not research_interests or len(research_interests) < 30) and self.ai_extractor:
                    logger.info(f"Using AI to extract/infer research interests for: {name}")
                    ai_result = self.ai_extractor.extract_research_from_content(page_text_for_ai, name)
                    if ai_result and ai_result != "Not found" and len(ai_result) > len(research_interests or ""):
                        research_interests = ai_result
                        logger.info(f"AI extraction successful: {len(research_interests)} chars")
                
                # Try Groq as final fallback
                if self.groq_extractor:
                    if not email:
                        logger.info(f"Using Groq for email extraction: {name}")
                        groq_email = self.groq_extractor.extract_email_from_content(page_text_for_ai, name)
                        if groq_email and groq_email != "Not found" and not self.is_department_email(groq_email):
                            email = groq_email
                    
                    if not research_interests or len(research_interests) < 30:
                        logger.info(f"Using Groq for research extraction: {name}")
                        groq_result = self.groq_extractor.extract_research_from_content(page_text_for_ai, name)
                        if groq_result and groq_result != "Not found":
                            research_interests = groq_result

                # Final defaults
                if not research_interests:
                    research_interests = "Not found"
                if not name or name == "Unknown":
                    name = "Not found"
                if not email:
                    email = "Not found"

                # Only track the URL as processed
                self.processed_urls.add(normalized_url)

                return {
                    'name': name,
                    'email': email,
                    'research_interest': research_interests,
                    'profile_link': url
                }

            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed for {url}: {str(e)}")
                if attempt == self.args.retries:
                    return {
                        'name': 'Not found',
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
        description='Smart Faculty Profile Scraper with AI Support (OUC and Multi-format)'
    )

    # File arguments
    parser.add_argument('--input-file', default='urls.txt', help='Input file containing URLs (one per line)')
    parser.add_argument('--output-file', default='output.txt', help='Output file for results')

    # AI arguments
    parser.add_argument('--use-ai', action='store_true', help='Use AI to extract data (only as fallback)')
    parser.add_argument('--ai-provider', choices=['openai', 'anthropic', 'gemini', 'groq'], default='openai', 
                        help='Primary AI provider to use')
    parser.add_argument('--ai-api-key', help='API key for primary AI provider')
    parser.add_argument('--ai-model', help='Model name for primary AI provider')
    
    # Groq fallback arguments
    parser.add_argument('--use-groq-fallback', action='store_true', 
                        help='Use Groq AI as fallback when primary methods fail')
    parser.add_argument('--groq-api-key', help='API key for Groq (or set GROQ_API_KEY env var)')
    parser.add_argument('--groq-model', default='llama-3.1-70b-versatile', 
                        help='Groq model to use')

    # Scraping arguments
    parser.add_argument('--headless', action='store_true', help='Run browser in headless mode')
    parser.add_argument('--delay-min', type=float, default=1.0, help='Minimum delay between requests (seconds)')
    parser.add_argument('--delay-max', type=float, default=3.0, help='Maximum delay between requests (seconds)')
    parser.add_argument('--max-profiles', type=int, default=0, help='Maximum number of profiles to process (0 for unlimited)')
    parser.add_argument('--retries', type=int, default=2, help='Number of retries for failed requests')
    parser.add_argument('--truncate', type=int, default=4000, help='Max length for research interests text (0 for no limit)')
    parser.add_argument('--append', action='store_true', help='Append to output file instead of overwriting')
    parser.add_argument('--json-output', action='store_true', help='Also save output as JSON')
    
    # Debug
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')

    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    scraper = SmartFacultyProfileScraper(args)
    scraper.run()


if __name__ == '__main__':
    main()