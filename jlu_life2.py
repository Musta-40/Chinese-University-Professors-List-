#!/usr/bin/env python3
"""
Universal Faculty Profile Research Interest Scraper with AI + Tesseract OCR
Enhanced for Chinese university sites, supports multi-structure pages,
uses OCR to read image-based emails, and uses AI only as fallback (verbatim).
"""

import os
import argparse
import json
import logging
import random
import re
import time
import platform
import base64
from io import BytesIO
from pathlib import Path
from typing import Dict, Optional, Set, List, Tuple

# OCR + image + HTTP
import pytesseract
from PIL import Image
import requests

# Load .env robustly (works in VS Code debugger or terminal)
from dotenv import load_dotenv, find_dotenv
_loaded = load_dotenv(find_dotenv(usecwd=True))
if not _loaded:
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

# Configure Tesseract path (Windows)
try:
    tesseract_path = os.getenv('TESSERACT_PATH')
    if tesseract_path and os.path.exists(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    elif platform.system() == 'Windows':
        default_path = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        if os.path.exists(default_path):
            pytesseract.pytesseract.tesseract_cmd = default_path
    # Optional sanity log
    _ver = pytesseract.get_tesseract_version()
    print(f"Tesseract configured: v{_ver}")
except Exception as e:
    print(f"Warning: Tesseract not configured. OCR may fail. {e}")

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
    """AI-powered content extractor (used only as fallback, verbatim)"""

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

    def extract_faculty_data_verbatim(self, page_content: str) -> Dict[str, str]:
        """Use AI to extract Name, Email, Research verbatim as fallback."""
        # Truncate content if too long
        max_content_length = 8000
        if len(page_content) > max_content_length:
            page_content = page_content[:max_content_length]

        prompt = f"""
Extract faculty information from this webpage VERBATIM (exactly as written).

Page Content:
{page_content}

Instructions:
1. Extract Name (姓名): from patterns like "姓名：XXX" or from title.
2. Extract Email (邮件/邮箱/Email): any email address, e.g., abc@xxx.cn/.com, etc.
3. Extract Research Direction (研究方向/研究领域/主要研究领域): text after these labels, or clear standalone research paragraph.

Return in this EXACT format:
NAME: [extracted name or "Not found"]
EMAIL: [extracted email or "Not found"]
RESEARCH: [extracted research interests verbatim or "Not found"]
"""

        try:
            if self.provider == 'openai':
                response = self.client.ChatCompletion.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You extract information verbatim from academic webpages."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=800,
                    temperature=0.1
                )
                content = response.choices[0].message.content.strip()

            elif self.provider == 'anthropic':
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=800,
                    temperature=0.1,
                    messages=[{"role": "user", "content": prompt}]
                )
                content = response.content[0].text.strip()

            elif self.provider == 'groq':
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You extract information verbatim from academic webpages."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=800,
                    temperature=0.1
                )
                content = response.choices[0].message.content.strip()

            elif self.provider == 'gemini':
                response = self.model.generate_content(prompt)
                content = (response.text or "").strip()

            result = {'name': '', 'email': '', 'research': ''}
            for line in content.split('\n'):
                if line.startswith('NAME:'):
                    result['name'] = line.replace('NAME:', '').strip()
                elif line.startswith('EMAIL:'):
                    result['email'] = line.replace('EMAIL:', '').strip()
                elif line.startswith('RESEARCH:'):
                    result['research'] = line.replace('RESEARCH:', '').strip()

            return result

        except Exception as e:
            logger.error(f"AI extraction failed ({self.provider}): {str(e)}")
            return {'name': '', 'email': '', 'research': ''}


class SmartFacultyProfileScraper:
    """Enhanced scraper with AI fallback + OCR for image-based emails"""

    # Research identifiers and stop keywords
    RESEARCH_KEYWORDS = [
        '研究领域', '研究方向', '研究兴趣', '科研方向', '主要研究方向',
        '主要研究领域', '研究内容', '学术兴趣', '研究课题', '研究重点',
        '研究专长', '学术方向', '科研领域', '主攻方向', '研究范围',
        'research interest', 'research interests', 'research area', 'research areas',
        'research direction', 'research directions', 'research field', 'research fields',
        'research focus', 'research foci', 'research topic', 'research topics',
        'academic interest', 'academic interests', 'current research'
    ]
    CHINESE_STOP_KEYWORDS = [
        '论文', '发表', '代表性论文', '近五年', '主要成果', '出版', '著作',
        '项目', '教育背景', '工作经历', '简历', '个人简历', '代表性研究成果',
        '学历', '获奖', '专利', '课程', '教学', '学术兼职', '社会服务',
        '科研项目', '招生', '招生信息', '指导学生', '上一篇', '下一篇',
        '上一页', '下一页', '主讲课程', '教授课程', '联系方式', '邮箱',
        '电话', '地址', '个人主页', '返回', '关闭', '近期代表性研究成果',
        '教育经历', '工作经历', '学术成果', '科研成果'
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

        # Pillow resampling filter (compat)
        self.resample_filter = getattr(Image, 'Resampling', Image).LANCZOS if hasattr(Image, 'Resampling') else Image.LANCZOS

    # ----------------- OCR helpers -----------------

    def resolve_url(self, src: str) -> str:
        """Resolve relative or protocol-relative URLs."""
        if not src:
            return src
        if src.startswith('http://') or src.startswith('https://'):
            return src
        if src.startswith('//'):
            scheme = 'https:' if self.driver.current_url.startswith('https') else 'http:'
            return scheme + src
        base = '/'.join(self.driver.current_url.split('/')[:3])
        return base + '/' + src.lstrip('/')

    def download_image(self, img_src: str) -> Optional[Image.Image]:
        """Download image from URL or decode base64 data."""
        try:
            if not img_src:
                return None
            # Base64
            if img_src.startswith('data:image'):
                base64_str = img_src.split(',', 1)[1]
                img_data = base64.b64decode(base64_str)
                return Image.open(BytesIO(img_data))

            # URL
            url = self.resolve_url(img_src)
            headers = {'User-Agent': 'Mozilla/5.0'}
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()
            return Image.open(BytesIO(resp.content))
        except Exception as e:
            logger.debug(f"download_image failed for {img_src}: {e}")
            return None

    def extract_email_from_image_ocr(self, img_src: str) -> Optional[str]:
        """Use OCR to read an email from an image src."""
        try:
            img = self.download_image(img_src)
            if not img:
                return None

            # Convert to RGB and upscale for better OCR
            if img.mode in ('RGBA', 'LA', 'P'):
                bg = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'RGBA':
                    bg.paste(img, mask=img.split()[3])
                else:
                    bg.paste(img)
                img = bg
            w, h = img.size
            if max(w, h) < 800:
                img = img.resize((w*2, h*2), self.resample_filter)

            # OCR attempt
            try:
                text = pytesseract.image_to_string(img, lang='eng+chi_sim')
            except Exception:
                text = pytesseract.image_to_string(img, lang='eng')

            logger.debug(f"OCR text: {text}")

            # Find email pattern (general TLDs, not only .edu.cn)
            patterns = [
                r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}',
            ]
            for pat in patterns:
                m = re.search(pat, text.replace(' ', ''), re.IGNORECASE)
                if m:
                    email = m.group(0)
                    # Common OCR noise cleanup
                    email = email.replace('，', '.').replace('。', '.').replace('；', ';')
                    return email
        except Exception as e:
            logger.debug(f"OCR failed for {img_src}: {e}")
        return None

    # ----------------- Structure-specific extractors -----------------

    def extract_from_jilin_meta(self, soup) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract from META description format (name, email, research)."""
        meta_desc = soup.find('meta', attrs={'name': re.compile('description', re.I), 'content': True})
        if not meta_desc:
            return None, None, None
        content = meta_desc.get('content', '') or ''
        if not content:
            return None, None, None

        name = None
        email = None
        research = None

        # Name
        name_patterns = [
            r'姓\s*名[：:]\s*([^\s职最电邮工]+)',
            r'^([^\s：:]+?)(?:职|教授|副教授|讲师)',
        ]
        for p in name_patterns:
            m = re.search(p, content)
            if m:
                cand = m.group(1).strip()
                if 1 < len(cand) <= 20:
                    name = cand
                    break

        # Email (general domain)
        email_patterns = [
            r'邮\s*件[：:]\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})',
            r'Email[：:]\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})',
            r'E-mail[：:]\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})',
            r'([A-Za-z0-9._%+\-]+@jlu\.edu\.cn)',
        ]
        for p in email_patterns:
            m = re.search(p, content, re.IGNORECASE)
            if m:
                email = m.group(1)
                break

        # Research
        rm = re.search(r'(?:研究方向|研究领域)[：:]\s*(.+?)(?:教育经历|工作经历|$)', content)
        if rm:
            research = rm.group(1).strip()

        return name, email, research

    def extract_from_jilin_tables(self, soup) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Extract name, email, research from table structures (including OCR for email images)."""
        name = None
        email = None
        research = None

        tables = soup.find_all('table')
        for t_idx, table in enumerate(tables):
            rows = table.find_all('tr')
            for r_idx, row in enumerate(rows):
                cells = row.find_all(['td', 'th'])
                if len(cells) < 2:
                    continue
                row_text = row.get_text(strip=True)

                # Name
                if t_idx == 0 and r_idx < 3:
                    if '姓名' in row_text or '姓 名' in row_text:
                        cand = cells[1].get_text(strip=True)
                        if cand and 1 < len(cand) <= 20:
                            name = cand

                # Email (usually row 4-5)
                if t_idx == 0 and 3 <= r_idx <= 6:
                    if any(kw in row_text for kw in ['邮件', '邮 件', '邮箱', 'Email', 'E-mail']):
                        # Try text in 2nd cell
                        ctext = cells[1].get_text(" ", strip=True)
                        m = re.search(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', ctext)
                        if m:
                            email = m.group(0)
                        else:
                            # Try HTML (maybe hidden)
                            cell_html = str(cells[1])
                            m2 = re.search(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', cell_html)
                            if m2:
                                email = m2.group(0)
                            else:
                                # Look for image(s) in the cell and OCR them
                                for img in cells[1].find_all('img'):
                                    alt_text = img.get('alt', '')
                                    if '@' in alt_text:
                                        email = re.search(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', alt_text)
                                        email = email.group(0) if email else alt_text.strip()
                                        if email:
                                            break
                                    img_src = img.get('src', '')
                                    if img_src:
                                        email = self.extract_email_from_image_ocr(img_src)
                                        if email:
                                            break

                # Research (row 6-7 of table 1, or first row of table 2)
                if (t_idx == 0 and 5 <= r_idx <= 8) or (t_idx == 1 and r_idx == 0):
                    if any(k in row_text for k in ['研究方向', '研究领域', '主要研究领域']):
                        rtxt = cells[1].get_text(" ", strip=True)
                        rtxt = re.sub(r'\s+', ' ', rtxt)
                        rtxt = re.sub(r'^\d+\.\s*', '', rtxt)
                        if len(rtxt) > 5:
                            research = rtxt

        return name, email, research

    # ----------------- General extractors -----------------

    def extract_name(self, soup) -> str:
        # META
        name, _, _ = self.extract_from_jilin_meta(soup)
        if name:
            return name
        # Tables
        name, _, _ = self.extract_from_jilin_tables(soup)
        if name:
            return name
        # Title
        title = soup.find('title')
        if title:
            t = title.get_text().strip()
            if any(sep in t for sep in ['-', '–', '—']):
                cand = re.split(r'[-–—]', t)[0].strip()
                if 1 < len(cand) <= 20 and re.match(r'^[\u4e00-\u9fa5]{2,4}$', cand):
                    return cand
        # Patterns in text
        page_text = soup.get_text()
        for p in [r'姓\s*名[：:]\s*([^\s,，职最电邮工]{2,4})', r'教师姓名[：:]\s*([^\s,，]+)']:
            m = re.search(p, page_text)
            if m:
                cand = m.group(1).strip()
                if 1 < len(cand) <= 20:
                    return cand
        return "Unknown"

    def extract_email(self, soup) -> Optional[str]:
        # META
        _, email, _ = self.extract_from_jilin_meta(soup)
        if email:
            return email
        # Tables (includes OCR inside cell)
        _, email, _ = self.extract_from_jilin_tables(soup)
        if email:
            return email

        # HTML patterns
        page_html = str(soup)
        for pat in [
            r'邮\s*件[：:]\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})',
            r'邮箱[：:]\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})',
            r'(?:Email|E-mail)[：:]\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})',
        ]:
            m = re.search(pat, page_html, re.IGNORECASE)
            if m:
                return m.group(1)

        # Text fallback
        page_text = soup.get_text(" ")
        emails = re.findall(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', page_text)
        if emails:
            return emails[0]

        # OCR over likely email images (page-wide scan as last resort)
        logger.info("No text email found, trying OCR on images...")
        for img in soup.find_all('img'):
            alt = img.get('alt', '')
            if '@' in alt:
                m = re.search(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', alt)
                if m:
                    return m.group(0)
            src = img.get('src', '')
            # Heuristics: filenames or surrounding text hint
            context = (img.parent.get_text(" ", strip=True).lower() if img.parent else '')
            if any(k in (src.lower() + ' ' + context) for k in ['email', 'mail', '邮箱', '邮件', '@']):
                email = self.extract_email_from_image_ocr(src)
                if email:
                    return email

        return None

    def extract_research_interests_comprehensive(self, soup) -> str:
        # META
        _, _, research = self.extract_from_jilin_meta(soup)
        if research and len(research) > 10:
            return self.clean_text(research)

        # Tables
        _, _, research = self.extract_from_jilin_tables(soup)
        if research and len(research) > 10:
            return self.clean_text(research)

        # HTML patterns
        page_html = str(soup)
        patterns = [
            (r'<td[^>]*>研(?:究方向|究领域)[：:]?</td>\s*<td[^>]*>(.*?)</td>', 1),
            (r'>研(?:究方向|究领域|主要研究领域)[：:]([^<]+)<', 1),
            (r'研(?:究方向|究领域)[：:].*?<span[^>]*>([^<]+)</span>', 1),
            (r'研(?:究方向|究领域)[：:].*?>([\s\S]*?)</td>', 1),
        ]
        for pat, g in patterns:
            m = re.search(pat, page_html, re.IGNORECASE | re.DOTALL)
            if m:
                content = m.group(g).strip()
                content = re.sub(r'<[^>]+>', ' ', content)
                content = re.sub(r'&[^;]+;', ' ', content)
                content = re.sub(r'\s+', ' ', content).strip()
                if content and len(content) > 10:
                    for stop_kw in self.CHINESE_STOP_KEYWORDS[:10]:
                        if stop_kw in content:
                            content = content.split(stop_kw)[0].strip()
                            break
                    if content and len(content) > 10:
                        return self.clean_text(content)

        # Text-based extraction
        page_text = soup.get_text("\n")
        stop_pattern = '|'.join(re.escape(kw) for kw in self.CHINESE_STOP_KEYWORDS)
        for keyword in self.RESEARCH_KEYWORDS:
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
                        lines = content.split('\n')[:10]
                        return self.clean_text('\n'.join(lines))

        return ""

    def clean_text(self, text: str) -> str:
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r'&[^;]+;', ' ', text)
        text = re.sub(r'[ \t\r\f\v]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n', text)
        text = text.strip()
        if self.args.truncate > 0 and len(text) > self.args.truncate:
            text = text[:self.args.truncate] + '...'
        return text

    def extract_with_ai_fallback(self, soup, name: str, email: str, research: str) -> Tuple[str, str, str]:
        """Only use AI for missing/failed fields, extract verbatim."""
        missing = any([
            not name or name == "Unknown",
            not email or email == "Not found",
            not research or len(research) < 10
        ])
        if not missing:
            return name, email, research

        # Prepare page text
        for script in soup(["script", "style", "meta", "link", "noscript"]):
            script.decompose()
        page_text = soup.get_text(" ")
        page_text = re.sub(r'\s+', ' ', page_text).strip()

        # Primary AI
        if self.ai_extractor:
            logger.info("Using AI fallback (verbatim) for missing fields...")
            ai = self.ai_extractor.extract_faculty_data_verbatim(page_text)
            if (not name or name == "Unknown") and ai.get('name') and ai['name'] != "Not found":
                name = ai['name']
            if (not email or email == "Not found") and ai.get('email') and ai['email'] != "Not found":
                email = ai['email']
            if (not research or len(research) < 10) and ai.get('research') and ai['research'] != "Not found":
                research = ai['research']

        # Groq final fallback
        if self.groq_extractor and (not name or name == "Unknown" or not email or not research or len(research) < 10):
            logger.info("Using Groq fallback (verbatim)...")
            ai = self.groq_extractor.extract_faculty_data_verbatim(page_text)
            if (not name or name == "Unknown") and ai.get('name') and ai['name'] != "Not found":
                name = ai['name']
            if (not email or email == "Not found") and ai.get('email') and ai['email'] != "Not found":
                email = ai['email']
            if (not research or len(research) < 10) and ai.get('research') and ai['research'] != "Not found":
                research = ai['research']

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

                # Traditional extraction first
                name = self.extract_name(soup)
                email = self.extract_email(soup)
                research = self.extract_research_interests_comprehensive(soup)

                logger.info(f"Traditional -> Name: {name}, Email: {email or 'Not found'}, Research chars: {len(research) if research else 0}")

                if email and email in self.processed_emails:
                    logger.info(f"Skipping duplicate email: {email}")
                    return None

                # AI fallback only for missing/failed fields (verbatim)
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
        description='Smart Faculty Profile Scraper with AI Fallback + Tesseract OCR for image emails'
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
                        help='Use Groq AI as fallback for verbatim extraction when primary methods fail')
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