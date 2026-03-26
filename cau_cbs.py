#!/usr/bin/env python3
"""
Universal Faculty Profile Research Interest Scraper with AI
Enhanced version that uses AI to intelligently extract research interests.
"""

import os
import argparse
import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Dict, Optional, Set, List

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

        elif provider == 'gemini':
            key = api_key or os.getenv('GOOGLE_API_KEY')
            if not key:
                raise RuntimeError("GOOGLE_API_KEY not set. Put it in .env, env var, or pass --ai-api-key.")
            genai.configure(api_key=key)
            self.model = genai.GenerativeModel(self.model_name)

        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

    def extract_research_interests(self, page_content: str, faculty_name: str = "") -> str:
        """Use AI to extract research interests from page content"""

        # Truncate content if too long (to save tokens)
        max_content_length = 8000
        if len(page_content) > max_content_length:
            page_content = page_content[:max_content_length]

        prompt = f"""
        You are analyzing a university faculty member's webpage. Extract ONLY their research interests/directions.

        Faculty Name: {faculty_name if faculty_name else "Unknown"}

        Page Content:
        {page_content}

        Instructions:
        1. Look for research interests, research directions, research areas, or similar sections (English or Chinese).
        2. Extract specific research topics, methodologies, and areas of focus.
        3. Exclude biography, education, teaching, publications, awards, and contact info.
        4. If research interests are scattered, compile them into a concise list.
        5. If nothing is found, return "Not found".
        6. Output as a short bullet list or compact paragraph (max 500 words).

        Research Interests:
        """

        try:
            if self.provider == 'openai':
                # Using the classic OpenAI ChatCompletion API for broad compatibility
                response = self.client.ChatCompletion.create(
                    model=self.model_name,
                    messages=[
                        {"role": "system", "content": "You extract research interests from academic webpages with high precision."},
                        {"role": "user", "content": prompt}
                    ],
                    max_tokens=500,
                    temperature=0.2
                )
                return response.choices[0].message.content.strip()

            elif self.provider == 'anthropic':
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=500,
                    temperature=0.2,
                    messages=[{"role": "user", "content": prompt}]
                )
                # Anthropic SDK returns a list of content blocks
                return response.content[0].text.strip()

            elif self.provider == 'gemini':
                response = self.model.generate_content(prompt)
                return (response.text or "").strip()

        except Exception as e:
            logger.error(f"AI extraction failed: {str(e)}")
            return ""

        return ""


class SmartFacultyProfileScraper:
    """Enhanced scraper with AI capabilities"""

    # Common research section identifiers (English and Chinese)
    RESEARCH_KEYWORDS = [
        # Chinese
        '研究领域', '研究方向', '研究兴趣', '科研方向', '主要研究',
        '研究内容', '学术兴趣', '研究课题', '研究重点', '研究专长',
        '学术方向', '科研领域', '主攻方向',
        # English
        'research interest', 'research interests', 'research area', 'research areas',
        'research direction', 'research directions', 'research field', 'research fields',
        'research focus', 'research foci', 'research topic', 'research topics',
        'academic interest', 'academic interests', 'current research'
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
                logger.info(f"AI provider initialized: {args.ai_provider} (model: {self.ai_extractor.model_name})")
            except Exception as e:
                logger.error(f"Failed to initialize AI provider ({args.ai_provider}): {e}")
                logger.error("Continuing WITHOUT AI. Falling back to rule-based extraction.")
                self.ai_extractor = None

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

    def extract_email(self, soup) -> Optional[str]:
        """Extract email address from page"""
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        page_text = soup.get_text(" ")
        emails = re.findall(email_pattern, page_text)

        # Prioritize institutional emails (China .edu.cn and CSU domain)
        pref = [e for e in emails if e.lower().endswith(('.edu.cn', '.edu')) or 'csu.edu.cn' in e.lower()]
        if pref:
            return pref[0]
        return emails[0] if emails else None

    def extract_name(self, soup) -> str:
        """Extract faculty name from page"""
        # 1) Try page title
        title = soup.find('title')
        if title:
            title_text = title.get_text().strip()
            patterns = [
                r'^([^-–—\|]+)[-–—\|]',     # Name before dash/pipe
                r'^(.+?)(?:教授|副教授|讲师|博士)',  # Name before Chinese title
                r'^\s*([^\d\|_/]{2,20})\s*$' # Simple fallback short title
            ]
            for p in patterns:
                m = re.search(p, title_text)
                if m:
                    name = m.group(1).strip()
                    if 1 < len(name) <= 30:
                        return name

        # 2) Look for headings
        for tag in ['h1', 'h2', 'h3']:
            for elem in soup.find_all(tag):
                text = elem.get_text().strip()
                if text and 1 < len(text) <= 30 and not any(ch.isdigit() for ch in text):
                    # Avoid obvious section headers
                    if not any(k in text for k in ['研究', 'Research', '联系方式', 'Contact']):
                        return text

        # 3) Look for common name classes/ids
        name_indicators = ['name', 'faculty-name', 'teacher-name', 'professor-name', 'realname']
        for indicator in name_indicators:
            elem = soup.find(attrs={'class': re.compile(indicator, re.I)}) or \
                   soup.find(attrs={'id': re.compile(indicator, re.I)})
            if elem:
                text = elem.get_text().strip()
                if text and 1 < len(text) <= 30:
                    return text

        return "Unknown"

    def extract_research_interests_traditional(self, soup) -> str:
        """Traditional rule-based extraction of research interests"""

        # Remove script/style
        for script in soup(["script", "style", "noscript"]):
            script.decompose()

        page_text = soup.get_text("\n")

        # Strategy 1: regex window around keywords to next typical section markers
        stop_markers = r'(?:教学|教育|课程|发表|论文|著作|专利|获奖|联系|个人|简介|教授|博士|硕士|项目|服务|社会|荣誉)'
        for keyword in self.RESEARCH_KEYWORDS:
            pattern = re.compile(
                rf'{re.escape(keyword)}\s*[：: ]*\s*(.+?)(?=\n\s*{stop_markers}|$)',
                re.IGNORECASE | re.DOTALL
            )
            m = pattern.search(page_text)
            if m:
                content = m.group(1).strip()
                if content and len(content) > 10:
                    return self.clean_text(content)

        # Strategy 2: search DOM blocks containing research keywords
        for element in soup.find_all(['div', 'section', 'article', 'p', 'td', 'li']):
            text = element.get_text("\n").strip()
            if not text:
                continue
            low = text.lower()
            if any(k.lower() in low for k in self.RESEARCH_KEYWORDS):
                lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
                # collect lines after the first keyword line
                capture = False
                collected = []
                for ln in lines:
                    if not capture and any(k.lower() in ln.lower() for k in self.RESEARCH_KEYWORDS):
                        capture = True
                        parts = re.split(r'[：:]', ln, 1)
                        if len(parts) > 1 and parts[1].strip():
                            collected.append(parts[1].strip())
                        continue
                    if capture:
                        if re.search(stop_markers, ln):
                            break
                        collected.append(ln)
                if collected:
                    content = "\n".join(collected[:12])
                    if len(content) > 20:
                        return self.clean_text(content)

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

    def extract_research_interests_ai(self, soup, faculty_name: str) -> str:
        """Use AI to extract research interests"""
        if not self.ai_extractor:
            return ""

        # Remove noisy tags and get text
        for script in soup(["script", "style", "meta", "link", "noscript"]):
            script.decompose()
        page_text = soup.get_text(" ")
        page_text = re.sub(r'\s+', ' ', page_text).strip()
        page_text = page_text[:10000]  # token safety

        result = self.ai_extractor.extract_research_interests(page_text, faculty_name)
        return result if result else ""

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
                time.sleep(1.5)  # small extra wait

                soup = BeautifulSoup(self.driver.page_source, 'html.parser')

                # Extract basics
                name = self.extract_name(soup)
                email = self.extract_email(soup)

                if email and email in self.processed_emails:
                    logger.info(f"Skipping duplicate email: {email}")
                    return None

                # AI first (if available), else rule-based
                research_interests = ""
                if self.ai_extractor:
                    logger.info(f"Using AI to extract research interests for: {name}")
                    research_interests = self.extract_research_interests_ai(soup, name)

                if not research_interests or research_interests.lower() == "not found":
                    logger.info(f"Using traditional extraction for: {name}")
                    rb = self.extract_research_interests_traditional(soup)
                    research_interests = rb if rb else (research_interests or "")

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
        description='Smart Faculty Profile Scraper with AI Support'
    )

    # File arguments
    parser.add_argument('--input-file', default='urls.txt', help='Input file containing URLs (one per line)')
    parser.add_argument('--output-file', default='output.txt', help='Output file for results')

    # AI arguments
    parser.add_argument('--use-ai', action='store_true', help='Use AI to extract research interests')
    parser.add_argument('--ai-provider', choices=['openai', 'anthropic', 'gemini'], default='openai', help='AI provider to use')
    parser.add_argument('--ai-api-key', help='API key for AI provider (or set via environment variable)')
    parser.add_argument('--ai-model', help='Model name (e.g., gemini-1.5-flash, gemini-1.5-pro, gpt-3.5-turbo)')

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