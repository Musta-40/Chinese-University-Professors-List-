import requests
from bs4 import BeautifulSoup, NavigableString
import re
import time
from typing import Dict, Optional, List
import os

class FacultyProfileScraperV3:
    """
    Enhanced scraper for faculty profiles that handles research text in the same paragraph as heading
    """
    
    def __init__(self, verbose=True):
        """
        Initialize the scraper
        """
        self.verbose = verbose
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
        # Keywords to identify research section
        self.research_keywords = [
            'Research Areas',
            'Research Interest',
            'Research Interests',
            'Research Focus'
        ]
        
        # Keywords to stop research extraction
        self.stop_keywords = [
            'Brief Biography',
            'Selected Publications',
            'Publications',
            'Education',
            'Experience',
            'Awards',
            'Lab Page Link',
            'Teaching',
            'Professional Activities'
        ]
    
    def extract_name(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract name from div.pi_name strong
        """
        try:
            # Primary method: div.pi_name strong
            name_elem = soup.select_one('div.pi_name strong')
            if name_elem:
                name = name_elem.get_text(strip=True)
                if self.verbose:
                    print(f"  ✓ Name found: {name}")
                return name
            
            # Fallback: try div.pi_name directly
            name_elem = soup.select_one('div.pi_name')
            if name_elem:
                # Remove any font tags and get text
                name = name_elem.get_text(strip=True)
                if name:
                    if self.verbose:
                        print(f"  ✓ Name found (fallback): {name}")
                    return name
            
            if self.verbose:
                print("  ✗ Name not found")
            return None
            
        except Exception as e:
            if self.verbose:
                print(f"  ✗ Error extracting name: {e}")
            return None
    
    def extract_email(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract email from div.pi_contact p containing "Email:"
        """
        try:
            # Find div.pi_contact
            contact_div = soup.select_one('div.pi_contact')
            if not contact_div:
                if self.verbose:
                    print("  ✗ Contact div not found")
                return None
            
            # Find all p tags in contact div
            p_tags = contact_div.find_all('p')
            
            for p in p_tags:
                text = p.get_text(strip=True)
                # Check if this paragraph contains email
                if 'email:' in text.lower():
                    # Extract email address
                    if ':' in text:
                        email = text.split(':', 1)[1].strip()
                    else:
                        email = text.replace('Email', '').replace('email', '').strip()
                    
                    # Validate email format
                    if '@' in email:
                        if self.verbose:
                            print(f"  ✓ Email found: {email}")
                        return email
            
            # Alternative: look for email pattern in contact div
            email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
            contact_text = contact_div.get_text()
            email_match = re.search(email_pattern, contact_text)
            if email_match:
                email = email_match.group(0)
                if self.verbose:
                    print(f"  ✓ Email found (regex): {email}")
                return email
            
            if self.verbose:
                print("  ✗ Email not found")
            return None
            
        except Exception as e:
            if self.verbose:
                print(f"  ✗ Error extracting email: {e}")
            return None
    
    def extract_research_interests(self, soup: BeautifulSoup) -> Optional[str]:
        """
        Extract research interests - handles text in same paragraph as heading
        """
        try:
            research_content = []
            
            # Strategy 1: Find paragraph containing "Research Areas" and extract text after <br/>
            for keyword in self.research_keywords:
                # Find all elements containing the research keyword
                elements = soup.find_all(text=re.compile(keyword, re.I))
                
                for element in elements:
                    # Get the parent paragraph
                    parent = element.parent
                    while parent and parent.name not in ['p', 'div']:
                        parent = parent.parent
                    
                    if parent and parent.name == 'p':
                        # Get the full text of the paragraph
                        full_text = parent.get_text(separator='\n', strip=True)
                        
                        # Split by the keyword and take everything after it
                        if keyword in full_text:
                            parts = full_text.split(keyword, 1)
                            if len(parts) > 1:
                                research_text = parts[1].strip()
                                if research_text and len(research_text) > 50:  # Ensure meaningful content
                                    if self.verbose:
                                        preview = research_text[:100] + "..." if len(research_text) > 100 else research_text
                                        print(f"  ✓ Research found in same paragraph: {preview}")
                                    return research_text
            
            # Strategy 2: Find the div containing "Research Areas" and get subsequent content
            for keyword in self.research_keywords:
                # Find strong/span elements with the keyword
                for elem in soup.find_all(['strong', 'span']):
                    if keyword in elem.get_text(strip=True):
                        # Get the parent container
                        container = elem.parent
                        while container and 'trs_editor_view' not in container.get('class', []):
                            container = container.parent
                        
                        if container:
                            # Get all paragraphs in the container
                            paragraphs = container.find_all('p')
                            found_research = False
                            
                            for p in paragraphs:
                                p_text = p.get_text(strip=True)
                                
                                # Check if this is the research areas paragraph
                                if keyword in p_text:
                                    # Extract text after the keyword
                                    if keyword in p_text:
                                        parts = p_text.split(keyword, 1)
                                        if len(parts) > 1:
                                            research_text = parts[1].strip()
                                            if research_text and len(research_text) > 50:
                                                research_content.append(research_text)
                                                found_research = True
                                elif found_research:
                                    # Check if we've hit a stop keyword
                                    should_stop = False
                                    for stop_keyword in self.stop_keywords:
                                        if stop_keyword in p_text[:100]:  # Check first 100 chars
                                            should_stop = True
                                            break
                                    
                                    if should_stop:
                                        break
                                    
                                    # Add this paragraph if it's substantial
                                    if len(p_text) > 20:
                                        research_content.append(p_text)
            
            # Strategy 3: Use the structure of the div.trs_editor_view
            if not research_content:
                editor_div = soup.find('div', class_='trs_editor_view')
                if editor_div:
                    # Find all paragraphs
                    all_p = editor_div.find_all('p')
                    
                    for i, p in enumerate(all_p):
                        p_text = p.get_text(strip=True)
                        # Check if this paragraph contains research areas
                        for keyword in self.research_keywords:
                            if keyword in p_text:
                                # Extract content after the keyword in the same paragraph
                                parts = p_text.split(keyword, 1)
                                if len(parts) > 1 and len(parts[1]) > 50:
                                    research_text = parts[1].strip()
                                    if self.verbose:
                                        preview = research_text[:100] + "..." if len(research_text) > 100 else research_text
                                        print(f"  ✓ Research interests found: {preview}")
                                    return research_text
            
            # Return combined content if found
            if research_content:
                combined_research = ' '.join(research_content)
                if self.verbose:
                    preview = combined_research[:100] + "..." if len(combined_research) > 100 else combined_research
                    print(f"  ✓ Research interests found: {preview}")
                return combined_research
            
            if self.verbose:
                print("  ✗ No research content found")
            return None
            
        except Exception as e:
            if self.verbose:
                print(f"  ✗ Error extracting research interests: {e}")
            return None
    
    def scrape_profile(self, url: str) -> Dict[str, Optional[str]]:
        """
        Scrape a single faculty profile
        """
        result = {
            'url': url,
            'name': None,
            'email': None,
            'research': None,
            'error': None
        }
        
        try:
            # Fetch the page
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract fields
            result['name'] = self.extract_name(soup)
            result['email'] = self.extract_email(soup)
            result['research'] = self.extract_research_interests(soup)
            
        except requests.RequestException as e:
            result['error'] = f"Request error: {str(e)}"
            if self.verbose:
                print(f"  ✗ Error fetching URL: {e}")
        except Exception as e:
            result['error'] = f"Parsing error: {str(e)}"
            if self.verbose:
                print(f"  ✗ Error parsing page: {e}")
        
        return result
    
    def scrape_multiple_urls(self, urls: List[str], delay: float = 1.0) -> List[Dict]:
        """
        Scrape multiple URLs with delay between requests
        """
        results = []
        total = len(urls)
        
        print(f"\n{'='*60}")
        print(f"Starting to scrape {total} URLs")
        print(f"{'='*60}\n")
        
        for i, url in enumerate(urls, 1):
            print(f"[{i}/{total}] Processing: {url}")
            
            # Scrape the profile
            result = self.scrape_profile(url)
            results.append(result)
            
            # Print summary
            if result['error']:
                print(f"  ⚠ Error: {result['error']}")
            else:
                success_count = sum(1 for v in [result['name'], result['email'], result['research']] if v)
                print(f"  ✓ Extracted {success_count}/3 fields")
            
            # Delay between requests
            if i < total:
                time.sleep(delay)
        
        return results
    
    def read_urls_from_file(self, filename: str) -> List[str]:
        """
        Read URLs from a text file (one per line)
        """
        urls = []
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                for line in f:
                    url = line.strip()
                    # Skip empty lines and comments
                    if url and not url.startswith('#'):
                        urls.append(url)
            print(f"✓ Loaded {len(urls)} URLs from {filename}")
        except FileNotFoundError:
            print(f"✗ File not found: {filename}")
        except Exception as e:
            print(f"✗ Error reading file: {e}")
        
        return urls
    
    def save_to_txt(self, results: List[Dict], filename: str = 'faculty_profiles.txt'):
        """
        Save results to a formatted text file
        """
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                # Write header
                f.write("="*80 + "\n")
                f.write("FACULTY PROFILES - EXTRACTED DATA\n")
                f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Profiles: {len(results)}\n")
                f.write("="*80 + "\n\n")
                
                successful = 0
                
                for i, result in enumerate(results, 1):
                    f.write(f"PROFILE #{i}\n")
                    f.write("-"*40 + "\n")
                    
                    # Check if we have any data
                    if result['error']:
                        f.write(f"ERROR: {result['error']}\n")
                        f.write(f"URL: {result['url']}\n\n")
                        continue
                    
                    has_data = result['name'] or result['email'] or result['research']
                    if has_data:
                        successful += 1
                    
                    # Write name
                    f.write(f"NAME: {result['name'] if result['name'] else 'Not found'}\n\n")
                    
                    # Write email
                    f.write(f"EMAIL: {result['email'] if result['email'] else 'Not found'}\n\n")
                    
                    # Write research interests
                    f.write("RESEARCH INTERESTS:\n")
                    if result['research']:
                        # Wrap long text for readability
                        import textwrap
                        wrapped = textwrap.fill(result['research'], width=75)
                        f.write(wrapped + "\n\n")
                    else:
                        f.write("Not found\n\n")
                    
                    # Write URL
                    f.write(f"SOURCE URL: {result['url']}\n")
                    f.write("="*80 + "\n\n")
                
                # Write summary
                f.write("\nSUMMARY\n")
                f.write("-"*40 + "\n")
                f.write(f"Total profiles processed: {len(results)}\n")
                f.write(f"Successful extractions: {successful}\n")
                f.write(f"Failed extractions: {len(results) - successful}\n")
                if successful > 0:
                    f.write(f"Success rate: {(successful/len(results))*100:.1f}%\n")
            
            print(f"\n✓ Results saved to {filename}")
            
        except Exception as e:
            print(f"✗ Error saving results: {e}")


def main():
    """
    Main function to run the scraper
    """
    # Configuration
    URLS_FILE = "urls.txt"
    OUTPUT_TXT = "faculty_profiles.txt"
    REQUEST_DELAY = 1.0  # Seconds between requests
    VERBOSE = True  # Show detailed extraction info
    
    print("\n" + "="*60)
    print("FACULTY PROFILE SCRAPER V3")
    print("Enhanced extraction for research in same paragraph as heading")
    print("="*60)
    
    # Initialize scraper
    scraper = FacultyProfileScraperV3(verbose=VERBOSE)
    
    # Read URLs
    urls = scraper.read_urls_from_file(URLS_FILE)
    
    if not urls:
        print("No URLs to process. Please check your urls.txt file.")
        return
    
    # Confirm before proceeding
    print(f"\nReady to scrape {len(urls)} URLs")
    response = input("Continue? (y/n): ").strip().lower()
    
    if response != 'y':
        print("Scraping cancelled.")
        return
    
    # Scrape all URLs
    results = scraper.scrape_multiple_urls(urls, delay=REQUEST_DELAY)
    
    # Save results
    print("\nSaving results...")
    scraper.save_to_txt(results, OUTPUT_TXT)
    
    # Print final summary
    successful = sum(1 for r in results if not r['error'] and (r['name'] or r['email'] or r['research']))
    with_research = sum(1 for r in results if r['research'])
    
    print("\n" + "="*60)
    print("SCRAPING COMPLETE")
    print(f"Total processed: {len(results)}")
    print(f"Successful: {successful}")
    print(f"With research interests: {with_research}")
    print(f"Success rate: {(successful/len(results))*100:.1f}%")
    print("="*60)


if __name__ == "__main__":
    main()