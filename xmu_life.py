#!/usr/bin/env python3
"""
Universal Faculty Profile Research Interest Scraper for Xiamen University
Specialized for English-format faculty pages with Research Area sections
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

    def extract_research_interests_from_publications(self, publications_text: str) -> str:
        """Use AI to infer research interests from publications list"""
        if not publications_text.strip():
            return ""
            
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
    """Enhanced scraper for Xiamen University faculty pages"""

    # Research identifiers and stop keywords
    RESEARCH_KEYWORDS = [
        '研究领域', '研究方向', '研究兴趣', '科研方向', '主要研究方向',
        '主要研究领域', '研究内容', '学术兴趣', '研究课题', '研究重点',
        'research interest', 'research interests', 'research area', 'research areas',
        'research direction', 'research directions', 'research field', 'research fields',
        'research focus', 'research foci', 'research topic', 'research topics',
        'academic interest', 'academic interests', 'current research'
    ]
    
    # Added English equivalents to stop keywords
    STOP_KEYWORDS = [
        '论文', '发表', '代表性论文', '近五年', '主要成果', '出版', '著作',
        '项目', '教育背景', '工作经历', '简历', '个人简历', '代表性研究成果',
        '学历', '获奖', '专利', '课程', '教学', '学术兼职', '社会服务',
        '科研项目', '招生', '招生信息', '指导学生', '上一篇', '下一篇',
        '上一页', '下一页', '主讲课程', '教授课程', '联系方式', '邮箱',
        '电话', '地址', '个人主页', '返回', '关闭', '近期代表性研究成果',
        '教育经历', '工作经历', '学术成果', '科研成果',
        # English equivalents
        'Selected Publications', 'Publications', 'Recent Publications', 'Key Publications',
        'Education', 'Professional Experience', 'Work Experience', 'Career',
        'Contact', 'Email', 'Phone', 'Address', 'Links', 'Biography'
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

    # ----------------- Specialized extractors for Xiamen University format -----------------

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

    def extract_email_from_meta(self, soup) -> Optional[str]:
        """Extract email from meta description tag"""
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            content = meta_desc.get('content').strip()
            # Look for email pattern after "Email:"
            m = re.search(r'Email:\s*([A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})', content, re.IGNORECASE)
            if m:
                return m.group(1)
        return None

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
                        if any(kw in next_heading for kw in [kw.lower() for kw in self.STOP_KEYWORDS]):
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
                    if any(kw in content.lower() for kw in [kw.lower() for kw in self.STOP_KEYWORDS]):
                        break
                    if len(content) > 20:  # Reasonable length for research description
                        return content
        
        return ""

    def extract_publications_section(self, soup) -> str:
        """Extract the publications section for AI fallback"""
        publications_text = ""
        for heading in soup.find_all(['h1', 'h2', 'h3', 'strong', 'b']):
            heading_text = heading.get_text().strip().lower()
            if 'publications' in heading_text:
                # Get all text until next section
                next_siblings = []
                for sibling in heading.find_next_siblings():
                    if sibling.name in ['h1', 'h2', 'h3', 'strong', 'b']:
                        next_heading = sibling.get_text().strip().lower()
                        if any(kw in next_heading for kw in ['education', 'experience', 'contact', 'research']):
                            break
                    if sibling.name in ['p', 'div', 'li']:
                        text = sibling.get_text().strip()
                        if text:
                            next_siblings.append(text)
                publications_text = "\n".join(next_siblings[:5])  # Limit to first 5 publication entries
                break
        return publications_text

    # ----------------- General extractors -----------------

    def extract_name(self, soup) -> str:
        """Extract name using multiple strategies"""
        # Try meta tags first
        name = self.extract_name_from_meta(soup)
        if name:
            return name
        
        # Try title tag
        name = self.extract_name_from_title(soup)
        if name:
            return name
        
        # Fallback to patterns in text
        page_text = soup.get_text()
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

    def extract_email(self, soup) -> Optional[str]:
        """Extract email using multiple strategies"""
        # Try meta description
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
        
        # Text fallback
        page_text = soup.get_text(" ")
        emails = re.findall(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}', page_text)
        if emails:
            return emails[0]
        
        return None

    def extract_research_interests_comprehensive(self, soup) -> str:
        """Extract research interests with priority on the English format"""
        # First try the specialized English format extraction
        research = self.extract_research_interests_english_format(soup)
        if research and len(research) > 10:
            return self.clean_text(research)
        
        # Then try meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            content = meta_desc.get('content').strip()
            # Look for research patterns in description
            m = re.search(r'Research\s*Area[：:]\s*(.+?)(?:Education|Professional\s*Experience|$)', content, re.DOTALL)
            if m:
                research = m.group(1).strip()
                if len(research) > 10:
                    return self.clean_text(research)
        
        # HTML patterns
        page_html = str(soup)
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
        stop_pattern = '|'.join(re.escape(kw) for kw in self.STOP_KEYWORDS)
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
                        return self.clean_text(content)

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
        """Only use AI for missing/failed research field, using publications to infer interests"""
        research_missing = not research or len(research) < 10
        if not research_missing:
            return name, email, research

        # Extract publications section for AI analysis
        publications_text = self.extract_publications_section(soup)
        
        # Primary AI extraction from publications
        if self.ai_extractor and publications_text:
            logger.info("Using AI to infer research interests from publications...")
            research = self.ai_extractor.extract_research_interests_from_publications(publications_text)
        
        # Groq fallback if primary AI failed and publications exist
        if self.groq_extractor and not research and publications_text:
            logger.info("Using Groq to infer research interests from publications...")
            research = self.groq_extractor.extract_research_interests_from_publications(publications_text)

        # If still missing, try general page content
        if not research or len(research) < 10:
            logger.info("Publications-based AI failed, trying general page content...")
            page_text = soup.get_text(" ")[:5000]  # Limit to first 5000 chars
            prompt = f"""
Extract the research interests from the following webpage content. Focus specifically on the research description section
and ignore other sections like education, professional experience, or publications.

Page Content:
{page_text}

Instructions:
- Extract ONLY the research interests as described in the research section
- If the research section is not found, look for similar headings
- Stop extraction before sections like publications, education, or professional experience
- Return ONLY the research interests text, nothing else
"""
            try:
                if self.ai_extractor:
                    response = self.ai_extractor.client.chat.completions.create(
                        model=self.ai_extractor.model_name,
                        messages=[
                            {"role": "system", "content": "You are a research analyst."},
                            {"role": "user", "content": prompt}
                        ],
                        max_tokens=300,
                        temperature=0.1
                    )
                    research = response.choices[0].message.content.strip()
            except:
                pass

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
        options.add_argument('--lang=en-US')

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
        description='Faculty Profile Scraper for Xiamen University'
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