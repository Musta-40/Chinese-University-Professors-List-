#!/usr/bin/env python3
"""
Universal Faculty Profile Research Interest Scraper with AI
Enhanced version for Chinese university websites with tabular data support.
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
            1. Find sections labeled as: 研究方向, 研究领域, 研究兴趣, Research Interests, Research Areas, Research Directions
            2. Extract the EXACT text from these sections, preserving original formatting
            3. Do NOT include: 论文, 发表, 教学, 课程, 获奖, 专利, 项目, 教育背景, 工作经历
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
            1. Look for research interests, research directions, research areas (研究方向, 研究领域, 研究兴趣).
            2. Extract specific research topics, methodologies, and areas of focus.
            3. Exclude: 论文, 发表, 代表性论文, 教育背景, 工作经历, 获奖, 专利, 课程, 教学, 项目
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
    """Enhanced scraper with AI capabilities and table extraction"""

    # Common research section identifiers (English and Chinese)
    RESEARCH_KEYWORDS = [
        # Chinese - prioritized
        '研究方向', '研究领域', '研究兴趣', '科研方向', '主要研究方向',
        '研究内容', '学术兴趣', '研究课题', '研究重点', '研究专长',
        '学术方向', '科研领域', '主攻方向', '研究范围',
        # English
        'research interest', 'research interests', 'research area', 'research areas',
        'research direction', 'research directions', 'research field', 'research fields',
        'research focus', 'research foci', 'research topic', 'research topics',
        'academic interest', 'academic interests', 'current research'
    ]
    
    # Chinese stop keywords for better extraction
    CHINESE_STOP_KEYWORDS = [
        '论文', '发表', '代表性论文', '近五年', '主要成果', '出版', '著作',
        '项目', '教育背景', '工作经历', '简历', '个人简历',
        '学历', '获奖', '专利', '课程', '教学', '学术兼职', '社会服务',
        '科研项目', '招生', '招生信息', '指导学生', '上一篇', '下一篇', 
        '上一页', '下一页', '主讲课程', '教授课程', '联系方式', '邮箱',
        '电话', '地址', '个人主页', '返回', '关闭'
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

    def extract_from_table(self, soup) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract name, email, and research from table structure"""
        name = None
        email = None
        research = None
        
        # Find all tables or tbody elements
        for table_container in soup.find_all(['table', 'tbody']):
            rows = table_container.find_all('tr')
            
            # Process each faculty entry (usually multiple faculty in one table)
            for i in range(0, len(rows), 4):  # Process in groups of 4 rows
                if i + 3 < len(rows):
                    # Extract from 4 consecutive rows
                    row1_text = rows[i].get_text(strip=True)
                    row2_text = rows[i+1].get_text(strip=True) if i+1 < len(rows) else ""
                    row3_text = rows[i+2].get_text(strip=True) if i+2 < len(rows) else ""
                    row4_text = rows[i+3].get_text(strip=True) if i+3 < len(rows) else ""
                    
                    # Pattern 1: Labeled format (姓名：xxx)
                    if '姓名' in row1_text or 'Name' in row1_text:
                        name_match = re.search(r'(?:姓名|Name)[：:]\s*(.+)', row1_text)
                        if name_match:
                            name = name_match.group(1).strip()
                    else:
                        # Pattern 2: Direct value (just the name)
                        # Check if it looks like a Chinese name (2-4 characters)
                        if re.match(r'^[\u4e00-\u9fa5]{2,4}$', row1_text):
                            name = row1_text
                    
                    # Extract research direction (row 2)
                    if '研究方向' in row2_text or 'Research' in row2_text:
                        research_match = re.search(r'(?:研究方向|研究领域|Research)[：:]\s*(.+)', row2_text)
                        if research_match:
                            research = research_match.group(1).strip()
                    elif row2_text and not any(kw in row2_text for kw in ['职位', '教授', '博士', '硕士', '导师']):
                        # Direct research text
                        research = row2_text
                    
                    # Extract email (row 4)
                    if '邮箱' in row4_text or 'Email' in row4_text or 'E-mail' in row4_text:
                        email_match = re.search(r'(?:邮箱|Email|E-mail)[：:]\s*([\w\.-]+@[\w\.-]+\.\w+)', row4_text)
                        if email_match:
                            email = email_match.group(1)
                    else:
                        # Look for email pattern directly
                        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
                        email_match = re.search(email_pattern, row4_text)
                        if email_match:
                            email = email_match.group(0)
                    
                    # If we found data, return it (assuming single faculty per page)
                    if name or research or email:
                        return name, email, research
        
        # Alternative: Look for definition lists or divs with consistent structure
        for container in soup.find_all(['div', 'section', 'article']):
            lines = container.get_text('\n').strip().split('\n')
            lines = [l.strip() for l in lines if l.strip()]
            
            if len(lines) >= 4:
                # Check if this looks like our pattern
                for i in range(len(lines) - 3):
                    line1, line2, line3, line4 = lines[i:i+4]
                    
                    # Check for name pattern
                    if '姓名' in line1:
                        name = re.sub(r'姓名[：:]', '', line1).strip()
                    elif re.match(r'^[\u4e00-\u9fa5]{2,4}$', line1):
                        name = line1
                    else:
                        continue
                    
                    # Check for research pattern
                    if '研究方向' in line2:
                        research = re.sub(r'研究方向[：:]', '', line2).strip()
                    elif not any(kw in line2 for kw in ['职位', '教授', '博士']):
                        research = line2
                    
                    # Check for email pattern
                    if '@' in line4:
                        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', line4)
                        if email_match:
                            email = email_match.group(0)
                    
                    if name or research or email:
                        return name, email, research
        
        return None, None, None

    def extract_email(self, soup) -> Optional[str]:
        """Extract email address from page - optimized for Chinese sites"""
        # First try table extraction
        _, email, _ = self.extract_from_table(soup)
        if email:
            return email
            
        # Try the specific pattern mentioned: ">E-mail: ...@ecust.edu.cn"
        page_html = str(soup)
        email_pattern = r'>E-mail:\s*([\w\.-]+@[\w\.-]+\.edu\.cn)'
        match = re.search(email_pattern, page_html, re.IGNORECASE)
        if match:
            return match.group(1)
        
        # Also try Chinese patterns
        chinese_email_patterns = [
            r'电子邮箱[：:]\s*([\w\.-]+@[\w\.-]+\.\w+)',
            r'邮箱[：:]\s*([\w\.-]+@[\w\.-]+\.\w+)',
            r'Email[：:]\s*([\w\.-]+@[\w\.-]+\.\w+)',
            r'E-mail[：:]\s*([\w\.-]+@[\w\.-]+\.\w+)',
        ]
        
        page_text = soup.get_text(" ")
        for pattern in chinese_email_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        # Fallback to general email pattern
        email_pattern = r'[\w\.-]+@[\w\.-]+\.edu\.cn'
        emails = re.findall(email_pattern, page_text)
        return emails[0] if emails else None

    def extract_name(self, soup) -> str:
        """Extract faculty name from page - prioritize table then title tag"""
        # First try table extraction
        name, _, _ = self.extract_from_table(soup)
        if name:
            return name
            
        # Priority: <title> tag (as mentioned by user)
        title = soup.find('title')
        if title:
            title_text = title.get_text().strip()
            # Clean up common suffixes
            title_text = re.sub(r'[-–—\|].*$', '', title_text).strip()
            title_text = re.sub(r'(教授|副教授|讲师|博士|老师|简介|主页|个人主页).*$', '', title_text).strip()
            if title_text and 1 < len(title_text) <= 20:
                return title_text

        # Look for name in specific patterns
        name_patterns = [
            r'姓名[：:]\s*([^\s,，]+)',
            r'教师姓名[：:]\s*([^\s,，]+)',
            r'Name[：:]\s*([^\s,，]+)',
        ]
        
        page_text = soup.get_text()
        for pattern in name_patterns:
            match = re.search(pattern, page_text)
            if match:
                name = match.group(1).strip()
                if name and 1 < len(name) <= 20:
                    return name

        # Look for headings
        for tag in ['h1', 'h2', 'h3']:
            for elem in soup.find_all(tag):
                text = elem.get_text().strip()
                if text and 1 < len(text) <= 20:
                    # Check if it looks like a Chinese name
                    if re.match(r'^[\u4e00-\u9fa5]{2,4}$', text):
                        return text

        return "Unknown"

    def extract_research_interests_traditional(self, soup) -> str:
        """Traditional rule-based extraction of research interests - with table support"""
        # First try table extraction
        _, _, research = self.extract_from_table(soup)
        if research:
            return self.clean_text(research)
            
        # Remove script/style
        for script in soup(["script", "style", "noscript"]):
            script.decompose()

        page_text = soup.get_text("\n")
        
        # Build stop pattern from Chinese stop keywords
        stop_pattern = '|'.join(re.escape(kw) for kw in self.CHINESE_STOP_KEYWORDS)

        # Strategy 1: regex window around keywords to next stop marker
        for keyword in self.RESEARCH_KEYWORDS:
            # Try both colon styles
            for sep in ['：', ':']:
                pattern = re.compile(
                    rf'{re.escape(keyword)}\s*{re.escape(sep)}\s*(.+?)(?=(?:{stop_pattern})|$)',
                    re.IGNORECASE | re.DOTALL
                )
                m = pattern.search(page_text)
                if m:
                    content = m.group(1).strip()
                    # Clean up the content
                    content = re.sub(r'\s+', ' ', content)
                    if content and len(content) > 10:
                        # Limit length and clean
                        lines = content.split('\n')[:10]  # Take first 10 lines
                        content = '\n'.join(lines)
                        return self.clean_text(content)

        # Strategy 2: search for structured lists after research keywords
        lines = page_text.split('\n')
        for i, line in enumerate(lines):
            if any(keyword in line for keyword in self.RESEARCH_KEYWORDS):
                # Collect next several lines
                collected = []
                for j in range(i+1, min(i+15, len(lines))):
                    next_line = lines[j].strip()
                    if not next_line:
                        continue
                    # Stop if we hit a stop keyword
                    if any(stop in next_line for stop in self.CHINESE_STOP_KEYWORDS):
                        break
                    # Look for numbered or bulleted items
                    if re.match(r'^[\d一二三四五六七八九十]+[\.、，,)]', next_line):
                        collected.append(next_line)
                    elif re.match(r'^[•·●◆▪▫◦‣⁃]', next_line):
                        collected.append(next_line)
                    elif len(collected) > 0:  # Continue collecting if we already started
                        collected.append(next_line)
                
                if collected:
                    return self.clean_text('\n'.join(collected))

        return ""

    def clean_text(self, text: str) -> str:
        """Clean extracted text"""
        text = re.sub(r'<[^>]+>', '', text)           # strip HTML
        text = re.sub(r'[ \t\r\f\v]+', ' ', text)     # collapse spaces
        text = re.sub(r'\n\s*\n+', '\n', text)        # collapse blank lines
        text = text.strip()

        if self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        return text

    def extract_research_interests_ai(self, soup, faculty_name: str, use_groq_verbatim: bool = False) -> str:
        """Use AI to extract research interests"""
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
                time.sleep(2)  # slightly longer wait for Chinese sites

                soup = BeautifulSoup(self.driver.page_source, 'html.parser')

                # Extract basics (now with table support)
                name = self.extract_name(soup)
                email = self.extract_email(soup)

                if email and email in self.processed_emails:
                    logger.info(f"Skipping duplicate email: {email}")
                    return None

                # Try multiple extraction methods
                research_interests = ""
                
                # 1. Try traditional extraction first (includes table extraction)
                logger.info(f"Trying traditional extraction for: {name}")
                research_interests = self.extract_research_interests_traditional(soup)
                
                # 2. If traditional fails, try AI
                if not research_interests or len(research_interests) < 20:
                    if self.ai_extractor:
                        logger.info(f"Using AI to extract research interests for: {name}")
                        ai_result = self.extract_research_interests_ai(soup, name)
                        if ai_result:
                            research_interests = ai_result
                
                # 3. If still no good result, try Groq verbatim
                if (not research_interests or research_interests.lower() == "not found") and self.groq_extractor:
                    logger.info(f"Using Groq verbatim extraction as final fallback for: {name}")
                    groq_result = self.extract_research_interests_ai(soup, name, use_groq_verbatim=True)
                    if groq_result:
                        research_interests = groq_result

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
        description='Smart Faculty Profile Scraper with AI Support (Table-aware for Chinese Universities)'
    )

    # File arguments
    parser.add_argument('--input-file', default='urls.txt', help='Input file containing URLs (one per line)')
    parser.add_argument('--output-file', default='output.txt', help='Output file for results')

    # AI arguments
    parser.add_argument('--use-ai', action='store_true', help='Use AI to extract research interests')
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