#!/usr/bin/env python3
"""
Universal Faculty Profile Scraper for Beijing Medical University
Handles all structural variations identified in 9 sample sources
Extracts: Name, Email, Research Interest, Profile URL
With optional Groq AI enhancement for difficult cases
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.parse import urljoin
from collections import OrderedDict

import requests
from bs4 import BeautifulSoup, NavigableString

# Optional Groq support
try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BJMUProfileScraper:
    """
    Scraper for Beijing Medical University faculty profiles
    Handles all 9 identified structural patterns
    """
    
    def __init__(self, groq_api_key: Optional[str] = None, use_groq: bool = False):
        """
        Initialize scraper
        
        Args:
            groq_api_key: Optional Groq API key for enhanced extraction
            use_groq: Whether to use Groq for difficult cases
        """
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Research direction label variations (from analysis)
        self.research_labels = [
            '研究方向：',      # With full-width colon
            '研究方向:',       # With half-width colon  
            '研究方向',        # No colon
            '科研兴趣及研究方向：',  # Compound label
            '科研兴趣及研究方向',
            '主要研究方向：',
            '主要研究方向'
        ]
        
        # Section headers that mark end of research content
        self.stop_sections = [
            '个人简介', '简介', '代表性论文', '代表论文', '代表性论著', '代表论著',
            '科研项目', '科研基金', '基金来源', '主要科研项目', '承担的主要科研项目',
            '主要学术任职', '学术任职', '社会兼职', '获奖情况', '获奖',
            '主要学习及工作经历', '工作经历', '教育背景', '教育经历',
            '联系方式', '代表文章', '主要奖励', '主要兼职',
            '指导研究生获奖情况', 'Publications', 'Awards'
        ]
        
        # Misleading sections to avoid
        self.misleading_sections = [
            '研究兴趣',  # This is NOT 研究方向!
            '个人简介',
            '简介'
        ]
        
        # Academic titles to strip from names
        self.academic_titles = [
            '教授', '副教授', '研究员', '副研究员', '助理研究员',
            '博士生导师', '硕士生导师', '博士', '硕士', '讲师', '助教'
        ]
        
        # Initialize Groq if requested
        self.groq_client = None
        if use_groq and groq_api_key and GROQ_AVAILABLE:
            try:
                self.groq_client = Groq(api_key=groq_api_key)
                logger.info("Groq AI initialized for enhanced extraction")
            except Exception as e:
                logger.warning(f"Failed to initialize Groq: {e}")
        
        # Statistics
        self.stats = {
            'total': 0,
            'successful': 0,
            'names_found': 0,
            'emails_found': 0,
            'research_found': 0
        }
    
    def extract_name(self, soup: BeautifulSoup) -> str:
        """
        Extract faculty name from the page
        
        Strategy:
        1. Primary: <h3> tag inside div.articleTitle
        2. Strip trailing academic titles
        3. Handle extra spaces
        """
        name = ""
        
        # Method 1: Look for h3 in div.articleTitle (most reliable)
        article_title = soup.find('div', class_='articleTitle')
        if article_title:
            h3 = article_title.find('h3')
            if h3:
                name_text = h3.get_text(strip=True)
                # Handle multiple spaces
                name_text = ' '.join(name_text.split())
                
                # Strip academic titles
                for title in self.academic_titles:
                    name_text = name_text.replace(title, '').strip()
                
                # Extract Chinese name (2-4 characters)
                chinese_name_match = re.search(r'([\u4e00-\u9fff]{2,4})', name_text)
                if chinese_name_match:
                    name = chinese_name_match.group(1)
                    logger.debug(f"Found name in h3: {name}")
                    return name
        
        # Method 2: Look for any h3 tag with name pattern
        for h3 in soup.find_all('h3'):
            text = h3.get_text(strip=True)
            text = ' '.join(text.split())  # Normalize spaces
            
            # Try to extract Chinese name
            for title in self.academic_titles:
                if title in text:
                    potential_name = text.replace(title, '').strip()
                    if re.match(r'^[\u4e00-\u9fff]{2,4}$', potential_name):
                        logger.debug(f"Found name in h3 (method 2): {potential_name}")
                        return potential_name
        
        # Method 3: Look for centered strong text with name
        for p in soup.find_all('p', style=re.compile(r'text-align:\s*center')):
            strong = p.find('strong')
            if strong:
                text = strong.get_text(strip=True)
                text = ' '.join(text.split())
                
                # Extract Chinese name
                chinese_name_match = re.search(r'([\u4e00-\u9fff]{2,4})', text)
                if chinese_name_match:
                    name = chinese_name_match.group(1)
                    logger.debug(f"Found name in centered strong: {name}")
                    return name
        
        return "Unknown"
    
    def extract_email(self, soup: BeautifulSoup) -> str:
        """
        Extract email address from the page
        
        Strategy:
        1. Look for mailto: links
        2. Look for text patterns with Email: or E-mail:
        3. Use regex to extract email
        4. Ignore footer institutional email
        """
        # Method 1: Look for mailto: links
        for a_tag in soup.find_all('a', href=re.compile(r'^mailto:')):
            email = a_tag.get('href').replace('mailto:', '').strip()
            # Validate and exclude institutional emails
            if self._validate_email(email):
                logger.debug(f"Found email in mailto link: {email}")
                return email
        
        # Method 2: Look for Email: patterns in text
        # Handle both half-width and full-width colons
        email_patterns = [
            r'[Ee]-?mail[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'邮箱[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'电子邮[件箱][：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        ]
        
        page_text = soup.get_text()
        for pattern in email_patterns:
            matches = re.finditer(pattern, page_text, re.IGNORECASE)
            for match in matches:
                email = match.group(1)
                if self._validate_email(email):
                    logger.debug(f"Found email with pattern: {email}")
                    return email
        
        # Method 3: Look for any email pattern in specific sections
        # Focus on contact/联系方式 sections
        for elem in soup.find_all(['p', 'div', 'span']):
            text = elem.get_text(strip=True)
            if any(keyword in text for keyword in ['Email', 'E-mail', '邮箱', '联系']):
                email_match = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', text)
                if email_match:
                    email = email_match.group(1)
                    if self._validate_email(email):
                        logger.debug(f"Found email in contact section: {email}")
                        return email
        
        return "Not found"
    
    def _validate_email(self, email: str) -> bool:
        """
        Validate email and filter out institutional/footer emails
        
        Args:
            email: Email address to validate
            
        Returns:
            True if valid personal email, False otherwise
        """
        if not email or '@' not in email:
            return False
        
        # Filter out known institutional emails
        institutional_patterns = [
            'yuanzhangxx@bjmu.edu.cn',  # Footer email from samples
            'admin@', 'webmaster@', 'office@', 'department@',
            'contact@', 'info@'
        ]
        
        email_lower = email.lower()
        for pattern in institutional_patterns:
            if pattern in email_lower:
                return False
        
        # Basic email validation
        return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))
    
    def extract_research_interest(self, soup: BeautifulSoup) -> str:
        """
        Extract research interest/direction from the page
        
        Complex extraction handling multiple patterns:
        1. Inline with label (Source 1)
        2. Next single paragraph (Sources 2,4,7)
        3. Multiple paragraphs (Sources 3,5,8,9)
        4. Missing/Invalid (Source 6)
        """
        # Find research direction section
        research_element = None
        research_label_found = ""
        
        # Look for strong tags with research labels
        for strong in soup.find_all('strong'):
            strong_text = strong.get_text(strip=True)
            for label in self.research_labels:
                if label in strong_text or label.rstrip('：:') in strong_text:
                    # Check it's not a misleading section
                    if not any(misleading in strong_text for misleading in self.misleading_sections):
                        research_element = strong
                        research_label_found = label
                        logger.debug(f"Found research label: {strong_text}")
                        break
            if research_element:
                break
        
        if not research_element:
            logger.debug("No research direction section found")
            return "Not found"
        
        # Extract research content based on different patterns
        research_content = []
        
        # Pattern 1: Content inline with label (same element)
        element_text = research_element.get_text(strip=True)
        if any(sep in element_text for sep in ['：', ':']):
            # Split by colon and take the part after
            for sep in ['：', ':']:
                if sep in element_text:
                    inline_content = element_text.split(sep, 1)[1].strip()
                    if inline_content and not self._is_invalid_research_content(inline_content):
                        research_content.append(inline_content)
                        logger.debug(f"Found inline research content: {inline_content[:50]}...")
                        break
        
        # If no inline content or need to check for more paragraphs
        if not research_content or len(research_content[0]) < 10:
            # Pattern 2 & 3: Content in following paragraphs
            parent = research_element.find_parent(['p', 'div'])
            if parent:
                # Get all following siblings
                for sibling in parent.find_next_siblings():
                    # Stop if we hit another section
                    if sibling.name in ['p', 'div']:
                        sibling_text = sibling.get_text(strip=True)
                        
                        # Check for stop conditions
                        if self._should_stop_extraction(sibling):
                            break
                        
                        # Check if it's valid research content
                        if sibling_text and not self._is_invalid_research_content(sibling_text):
                            # Check if it's a numbered list item
                            if re.match(r'^\d+[\.、）KATEX_INLINE_CLOSE]', sibling_text):
                                research_content.append(sibling_text)
                            # Or if it's a regular paragraph with research content
                            elif len(sibling_text) > 5:
                                research_content.append(sibling_text)
                                # For single paragraph research, stop after one
                                if not re.match(r'^\d+[\.、）KATEX_INLINE_CLOSE]', sibling_text):
                                    break
        
        # Clean and combine research content
        if research_content:
            # Remove duplicates while preserving order
            seen = set()
            unique_content = []
            for item in research_content:
                if item not in seen:
                    seen.add(item)
                    unique_content.append(item)
            
            # Join with appropriate separator
            if len(unique_content) == 1:
                return unique_content[0]
            else:
                # Check if items are numbered
                if any(re.match(r'^\d+[\.、）KATEX_INLINE_CLOSE]', item) for item in unique_content):
                    return '\n'.join(unique_content)
                else:
                    return '；'.join(unique_content)
        
        return "Not found"
    
    def _should_stop_extraction(self, element) -> bool:
        """
        Check if we should stop extracting research content
        
        Args:
            element: BeautifulSoup element to check
            
        Returns:
            True if should stop, False otherwise
        """
        # Check for strong tag with stop section
        strong = element.find('strong')
        if strong:
            strong_text = strong.get_text(strip=True)
            for stop_section in self.stop_sections:
                if stop_section in strong_text:
                    logger.debug(f"Stop extraction at section: {strong_text}")
                    return True
        
        # Check element text for stop sections
        element_text = element.get_text(strip=True)
        for stop_section in self.stop_sections:
            if element_text.startswith(stop_section):
                logger.debug(f"Stop extraction at text: {element_text[:30]}...")
                return True
        
        return False
    
    def _is_invalid_research_content(self, text: str) -> bool:
        """
        Check if the text is invalid research content (e.g., CV, biography)
        
        Args:
            text: Text to validate
            
        Returns:
            True if invalid, False if valid research content
        """
        # Check if it starts with year (indicates CV/biography)
        if re.match(r'^(19|20)\d{2}[年\.]', text):
            logger.debug("Invalid: starts with year (CV content)")
            return True
        
        # Check if it contains degree/education keywords
        education_keywords = ['获得', '学士', '硕士', '博士', '学位', '毕业', '就读']
        if any(keyword in text[:50] for keyword in education_keywords):
            logger.debug("Invalid: contains education keywords")
            return True
        
        # Check if it's too short
        if len(text) < 5:
            logger.debug("Invalid: too short")
            return True
        
        # Check for misleading content
        if any(section in text for section in self.misleading_sections):
            logger.debug("Invalid: contains misleading section")
            return True
        
        return False
    
    def scrape_with_groq_fallback(self, soup: BeautifulSoup, url: str) -> Optional[str]:
        """
        Use Groq AI as fallback for research interest extraction
        
        Args:
            soup: BeautifulSoup object
            url: Profile URL
            
        Returns:
            Research interest or None
        """
        if not self.groq_client:
            return None
        
        try:
            # Extract page text
            page_text = soup.get_text()[:3000]  # Limit to 3000 chars
            
            prompt = f"""
Extract the research direction/interest from this Chinese faculty profile.
Look for sections labeled with: 研究方向, 研究兴趣, 科研方向, etc.
Return ONLY the actual research topics, not biography or publications.

Page content:
{page_text}

Research interest (if found):"""
            
            response = self.groq_client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=[
                    {"role": "system", "content": "Extract research interests from Chinese academic profiles."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=200
            )
            
            result = response.choices[0].message.content.strip()
            if result and "not found" not in result.lower():
                logger.info("Used Groq AI for research extraction")
                return result
        except Exception as e:
            logger.error(f"Groq extraction failed: {e}")
        
        return None
    
    def scrape_profile(self, url: str) -> Dict[str, str]:
        """
        Scrape a single faculty profile
        
        Args:
            url: Profile URL
            
        Returns:
            Dictionary with name, email, research_interest, profile_link
        """
        logger.info(f"Scraping: {url}")
        
        result = {
            'name': 'Unknown',
            'email': 'Not found',
            'research_interest': 'Not found',
            'profile_link': url
        }
        
        try:
            # Fetch page
            response = self.session.get(url, timeout=15)
            response.encoding = 'utf-8'  # Force UTF-8 for Chinese content
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract fields
            result['name'] = self.extract_name(soup)
            result['email'] = self.extract_email(soup)
            result['research_interest'] = self.extract_research_interest(soup)
            
            # Try Groq fallback if research not found
            if result['research_interest'] == "Not found" and self.groq_client:
                groq_research = self.scrape_with_groq_fallback(soup, url)
                if groq_research:
                    result['research_interest'] = groq_research
            
            # Update statistics
            self.stats['successful'] += 1
            if result['name'] != 'Unknown':
                self.stats['names_found'] += 1
            if result['email'] != 'Not found':
                self.stats['emails_found'] += 1
            if result['research_interest'] != 'Not found':
                self.stats['research_found'] += 1
            
            logger.info(f"✓ Extracted: {result['name']} | Email: {result['email'] != 'Not found'} | Research: {result['research_interest'] != 'Not found'}")
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
        
        self.stats['total'] += 1
        return result
    
    def scrape_batch(self, urls: List[str], output_file: str = 'output.txt', 
                     json_output: bool = True, delay: float = 1.0):
        """
        Scrape multiple profiles
        
        Args:
            urls: List of profile URLs
            output_file: Output file path
            json_output: Whether to save JSON
            delay: Delay between requests
        """
        results = []
        total = len(urls)
        
        logger.info(f"Starting batch scraping of {total} profiles")
        
        with open(output_file, 'w', encoding='utf-8') as f:
            for i, url in enumerate(urls, 1):
                logger.info(f"\n--- Processing {i}/{total} ---")
                
                # Scrape profile
                profile = self.scrape_profile(url)
                results.append(profile)
                
                # Write to file
                f.write(f"Name: {profile['name']}\n")
                f.write(f"Email: {profile['email']}\n")
                f.write(f"Research interest: {profile['research_interest']}\n")
                f.write(f"Profile link: {profile['profile_link']}\n")
                f.write("-" * 60 + "\n\n")
                f.flush()
                
                # Progress update
                if i % 10 == 0:
                    self.print_progress(i, total)
                
                # Respectful delay
                if i < total:
                    time.sleep(delay)
        
        # Save JSON
        if json_output:
            json_file = output_file.replace('.txt', '.json')
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"JSON saved to {json_file}")
        
        # Print final statistics
        self.print_statistics()
        
        return results
    
    def print_progress(self, current: int, total: int):
        """Print progress statistics"""
        logger.info(f"Progress: {current}/{total} ({current/total*100:.1f}%)")
        logger.info(f"Success rate: {self.stats['successful']/self.stats['total']*100:.1f}%")
        logger.info(f"Fields found - Names: {self.stats['names_found']}, "
                   f"Emails: {self.stats['emails_found']}, "
                   f"Research: {self.stats['research_found']}")
    
    def print_statistics(self):
        """Print final statistics"""
        logger.info("\n" + "="*60)
        logger.info("SCRAPING COMPLETE - FINAL STATISTICS")
        logger.info("="*60)
        logger.info(f"Total profiles: {self.stats['total']}")
        logger.info(f"Successful: {self.stats['successful']}")
        logger.info(f"Names found: {self.stats['names_found']} ({self.stats['names_found']/self.stats['total']*100:.1f}%)")
        logger.info(f"Emails found: {self.stats['emails_found']} ({self.stats['emails_found']/self.stats['total']*100:.1f}%)")
        logger.info(f"Research found: {self.stats['research_found']} ({self.stats['research_found']/self.stats['total']*100:.1f}%)")
        logger.info("="*60)


def main():
    """Main function with CLI"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Beijing Medical University Faculty Profile Scraper',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python bjmu_scraper.py --input urls.txt --output results.txt
  
  # With Groq AI fallback (for difficult cases)
  python bjmu_scraper.py --input urls.txt --groq-key YOUR_KEY
  
  # Test single URL
  python bjmu_scraper.py --test-url "http://example.edu.cn/profile.html"
  
  # Custom delay between requests
  python bjmu_scraper.py --input urls.txt --delay 2.0
        """
    )
    
    parser.add_argument('--input', '-i', help='Input file with URLs (one per line)')
    parser.add_argument('--output', '-o', default='bjmu_profiles.txt', help='Output file')
    parser.add_argument('--test-url', help='Test with single URL')
    parser.add_argument('--groq-key', help='Optional Groq API key for enhanced extraction')
    parser.add_argument('--json', action='store_true', help='Also save as JSON')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose logging')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create scraper
    scraper = BJMUProfileScraper(
        groq_api_key=args.groq_key,
        use_groq=bool(args.groq_key)
    )
    
    # Test mode
    if args.test_url:
        print(f"\nTesting with URL: {args.test_url}\n")
        result = scraper.scrape_profile(args.test_url)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    
    # Batch mode
    if args.input:
        if not os.path.exists(args.input):
            print(f"Error: Input file '{args.input}' not found")
            return
        
        with open(args.input, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        if not urls:
            print("Error: No URLs found")
            return
        
        print(f"\n{'='*60}")
        print(f"Beijing Medical University Faculty Profile Scraper")
        print(f"{'='*60}")
        print(f"URLs to process: {len(urls)}")
        print(f"Output file: {args.output}")
        print(f"Groq AI: {'Enabled' if args.groq_key else 'Disabled'}")
        print(f"{'='*60}\n")
        
        # Run scraper
        scraper.scrape_batch(urls, args.output, json_output=args.json, delay=args.delay)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()