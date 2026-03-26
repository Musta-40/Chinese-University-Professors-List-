import requests
from bs4 import BeautifulSoup
import csv
import time
from urllib.parse import urljoin
import re
import socket
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry

def test_connection(url):
    """
    Test if the website is accessible
    """
    print(f"Testing connection to {url}...")
    try:
        # Try to resolve the domain
        domain = url.split('/')[2]
        ip = socket.gethostbyname(domain)
        print(f"✓ Domain resolved to IP: {ip}")
        
        # Try to connect
        response = requests.get(url, timeout=10)
        print(f"✓ HTTP Status Code: {response.status_code}")
        return True
    except socket.gaierror:
        print(f"✗ Failed to resolve domain: {domain}")
        print("  Possible causes:")
        print("  - Website is blocked in your region")
        print("  - DNS issues")
        print("  - Website is down")
        print("  - You might need a VPN")
        return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Connection error: {str(e)}")
        return False

def create_session_with_retries():
    """
    Create a requests session with retry strategy
    """
    session = requests.Session()
    retry = Retry(
        total=3,
        read=3,
        connect=3,
        backoff_factor=0.3,
        status_forcelist=(500, 502, 504)
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session

def extract_research_interests(profile_soup):
    """
    Extract research interests from the professor's profile page
    Looking for various headings related to basic research
    """
    research_interests = []
    
    # Find the content div
    content_div = profile_soup.find('div', class_='content')
    
    if content_div:
        # Find all heading tags in the content
        heading_tags = content_div.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'b'])
        
        for heading in heading_tags:
            heading_text = heading.get_text(strip=True).lower()
            # Check for various research-related keywords (including basic research-specific)
            if any(keyword in heading_text for keyword in [
                'research interest', 'research direction', 'main research',
                'research area', 'research focus', 'research field',
                'scientific interest', 'research topic', 'research theme',
                'research work', 'current research', 'research project',
                'research program', 'laboratory focus', 'lab interest',
                'research objective', 'research goal', 'research activities',
                'scientific focus', 'area of expertise', 'research expertise'
            ]):
                # Get all content after this heading until the next heading
                current = heading.find_next_sibling()
                
                while current and current.name not in ['h1', 'h2', 'h3', 'h4', 'h5']:
                    if current.name == 'p':
                        text = current.get_text(strip=True)
                        if text and len(text) > 10:  # Filter out very short text
                            research_interests.append(text)
                    elif current.name in ['ol', 'ul']:
                        # Handle lists
                        list_items = current.find_all('li')
                        for li in list_items:
                            li_text = li.get_text(strip=True)
                            if li_text:
                                research_interests.append(li_text)
                    elif current.name == 'div':
                        # Sometimes content is in div tags
                        div_text = current.get_text(strip=True)
                        if div_text and len(div_text) > 10:
                            # Check if it's not another section
                            if not any(skip in div_text.lower()[:50] for skip in [
                                'publication', 'education', 'contact', 'award',
                                'teaching', 'course', 'grant', 'patent'
                            ]):
                                research_interests.append(div_text)
                    
                    current = current.find_next_sibling()
                
                break  # Found research section, stop looking
    
    # If no structured research section found, try looking for basic research keywords
    if not research_interests and content_div:
        all_text_elements = content_div.find_all(['p', 'li'])
        for elem in all_text_elements:
            text = elem.get_text(strip=True)
            # Look for basic research-specific keywords
            if any(keyword in text.lower() for keyword in [
                'molecular', 'cellular', 'genetic', 'protein', 'gene expression',
                'signal transduction', 'pathway', 'mechanism', 'biochemical',
                'structural biology', 'systems biology', 'computational',
                'bioinformatics', 'genomics', 'proteomics', 'metabolomics',
                'cell biology', 'molecular biology', 'developmental biology',
                'neuroscience', 'immunology', 'microbiology', 'research'
            ]):
                if len(text) > 50 and len(text) < 1000:
                    # Check if it's actually about research (not just mentioning keywords)
                    if any(action in text.lower() for action in [
                        'study', 'investigate', 'research', 'explore', 'analyze',
                        'develop', 'understand', 'elucidate', 'characterize'
                    ]):
                        research_interests.append(text)
                        if len(research_interests) >= 3:  # Limit to 3 paragraphs
                            break
    
    # Join all research interests into a single string
    if research_interests:
        return ' '.join(research_interests)
    
    return 'N/A'

def extract_email(profile_soup):
    """
    Extract email address from the professor's profile page
    """
    email = 'N/A'
    
    # Method 1: Look in the content div for Email: pattern
    content_div = profile_soup.find('div', class_='content')
    
    if content_div:
        content_text = content_div.get_text()
        
        # Look for various email patterns
        email_patterns = [
            r'Email[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'E-mail[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'email[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'Electronic mail[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            r'Contact[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        ]
        
        for pattern in email_patterns:
            email_match = re.search(pattern, content_text, re.IGNORECASE)
            if email_match:
                email = email_match.group(1).strip()
                # Clean up common artifacts
                email = email.rstrip('/').replace('\\', '').replace(',', '').replace(';', '').strip()
                return email
    
    # Method 2: Look for mailto links
    mailto_links = profile_soup.find_all('a', href=re.compile(r'^mailto:'))
    if mailto_links:
        for link in mailto_links:
            email_href = link.get('href', '')
            if email_href.startswith('mailto:'):
                potential_email = email_href.replace('mailto:', '').strip()
                # Validate it's an actual email
                if '@' in potential_email and '.' in potential_email.split('@')[1]:
                    email = potential_email.split('?')[0]  # Remove any URL parameters
                    break
    
    # Method 3: General email pattern search in entire page
    if email == 'N/A':
        page_text = profile_soup.get_text()
        email_patterns = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', page_text)
        
        # Filter out invalid emails
        valid_emails = []
        for e in email_patterns:
            if '@' in e and '.' in e.split('@')[1]:
                # Exclude common false positives
                if not any(skip in e.lower() for skip in ['example.', 'email.', 'test.', 'sample.', 'user@', 'name@']):
                    valid_emails.append(e)
        
        if valid_emails:
            email = valid_emails[0]
    
    return email.rstrip('/').strip()

def extract_professor_name(profile_soup):
    """
    Extract professor name from their profile page
    """
    # Look for name in div with class="name"
    name_div = profile_soup.find('div', class_='name')
    if name_div:
        return name_div.get_text(strip=True)
    
    # Alternative: Look for name in single-bio div
    single_bio = profile_soup.find('div', class_='single-bio')
    if single_bio:
        name_div = single_bio.find('div', class_='name')
        if name_div:
            return name_div.get_text(strip=True)
    
    # Look for name in h1 or h2 tags
    for tag in ['h1', 'h2']:
        name_heading = profile_soup.find(tag)
        if name_heading:
            text = name_heading.get_text(strip=True)
            # Check if it looks like a name (not too long, not a common page title)
            if len(text) < 50 and text not in ['Faculty', 'Professor', 'Staff', 'Basic Research', 'Research']:
                return text
    
    # Fallback: look in title tag
    title_tag = profile_soup.find('title')
    if title_tag:
        title_text = title_tag.get_text(strip=True)
        if title_text and len(title_text) < 50 and title_text not in ['Faculty', 'Professor', 'Staff', 'Basic Research']:
            return title_text
    
    return 'N/A'

def extract_professor_title(profile_soup):
    """
    Extract professor's academic title from their profile page
    """
    # Look for title in div with class="title"
    title_div = profile_soup.find('div', class_='title')
    if title_div:
        return title_div.get_text(strip=True)
    
    # Alternative: Look in single-bio div
    single_bio = profile_soup.find('div', class_='single-bio')
    if single_bio:
        title_div = single_bio.find('div', class_='title')
        if title_div:
            return title_div.get_text(strip=True)
    
    # Look for common title patterns in content
    content_div = profile_soup.find('div', class_='content')
    if content_div:
        content_text = content_div.get_text()[:500]  # Check first 500 chars
        title_patterns = [
            r'Title[:\s]+([^\n]+)',
            r'Position[:\s]+([^\n]+)',
            r'Academic Title[:\s]+([^\n]+)',
            r'Professional Title[:\s]+([^\n]+)',
            r'Academic Position[:\s]+([^\n]+)'
        ]
        
        for pattern in title_patterns:
            title_match = re.search(pattern, content_text, re.IGNORECASE)
            if title_match:
                return title_match.group(1).strip()
    
    return 'N/A'

def extract_research_field(profile_soup):
    """
    Extract specific research field or discipline
    """
    fields = []
    
    # Common basic research fields to look for
    research_fields = [
        'molecular biology', 'cell biology', 'biochemistry', 'genetics',
        'genomics', 'proteomics', 'structural biology', 'systems biology',
        'computational biology', 'bioinformatics', 'neuroscience', 'immunology',
        'microbiology', 'virology', 'developmental biology', 'stem cell biology',
        'cancer biology', 'epigenetics', 'metabolomics', 'synthetic biology',
        'chemical biology', 'biophysics', 'pharmacology', 'physiology',
        'plant biology', 'evolutionary biology', 'ecology'
    ]
    
    content_div = profile_soup.find('div', class_='content')
    if content_div:
        content_text = content_div.get_text().lower()
        
        # Look for field patterns
        field_patterns = [
            r'Research Field[:\s]+([^,\n]+)',
            r'Field[:\s]+([^,\n]+)',
            r'Discipline[:\s]+([^,\n]+)',
            r'Department[:\s]+([^,\n]+)',
            r'Laboratory[:\s]+([^,\n]+)'
        ]
        
        for pattern in field_patterns:
            field_match = re.search(pattern, content_text, re.IGNORECASE)
            if field_match:
                fields.append(field_match.group(1).strip())
        
        # Also check for research fields mentioned in text
        for field in research_fields:
            if field in content_text:
                if field not in [f.lower() for f in fields]:
                    fields.append(field.title())
                    if len(fields) >= 3:  # Limit to 3 fields
                        break
    
    return ', '.join(fields) if fields else 'Basic Research'

def extract_lab_info(profile_soup):
    """
    Extract laboratory name or affiliation
    """
    lab_info = 'N/A'
    
    content_div = profile_soup.find('div', class_='content')
    if content_div:
        content_text = content_div.get_text()
        
        # Look for lab patterns
        lab_patterns = [
            r'Laboratory[:\s]+([^\n]+)',
            r'Lab[:\s]+([^\n]+)',
            r'Research Group[:\s]+([^\n]+)',
            r'Group[:\s]+([^\n]+)',
            r'Center[:\s]+([^\n]+)',
            r'Institute[:\s]+([^\n]+)'
        ]
        
        for pattern in lab_patterns:
            lab_match = re.search(pattern, content_text, re.IGNORECASE)
            if lab_match:
                lab_info = lab_match.group(1).strip()
                break
    
    return lab_info

def scrape_basic_research_faculty():
    """
    Main function to scrape Basic Research faculty list
    """
    base_url = "https://enbiomed.ustc.edu.cn"
    list_url = "https://enbiomed.ustc.edu.cn/BasicResearch/list.htm"
    
    # Test connection first
    if not test_connection(list_url):
        print("\n" + "=" * 70)
        print("CONNECTION FAILED - TROUBLESHOOTING TIPS:")
        print("=" * 70)
        print("\n1. Check if you need a VPN (the site might be region-restricted)")
        print("2. Try accessing the site in your browser:")
        print(f"   {list_url}")
        print("3. If you can access it in browser but not via script:")
        print("   - Your IP might be blocked")
        print("   - You might need to add additional headers")
        print("4. Try using alternative domains or mirrors if available")
        print("5. As a last resort, save the HTML pages manually and process offline")
        return []
    
    # Create session with retries
    session = create_session_with_retries()
    
    # Headers to mimic a browser request
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'same-origin',
        'Cache-Control': 'max-age=0',
        'Referer': 'https://enbiomed.ustc.edu.cn/SchoolofLifeSciences/list.htm'
    }
    
    professors_data = []
    
    try:
        print("\nFetching Basic Research faculty list page...")
        response = session.get(list_url, headers=headers, timeout=20, verify=False)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all professor bio-cards
        bio_cards = soup.find_all('div', class_='bio-card')
        
        if not bio_cards:
            print("No bio-cards found. Checking for alternative page structure...")
            # Try alternative selectors
            bio_cards = soup.find_all('div', class_=['faculty-card', 'professor-card', 'staff-card', 'researcher-card'])
            
            # If still no cards, try to find links in list format
            if not bio_cards:
                list_container = soup.find('div', class_='list_body')
                if list_container:
                    bio_cards = list_container.find_all('li')
                    if not bio_cards:
                        # Try finding all links that might be faculty profiles
                        bio_cards = list_container.find_all('a', href=re.compile(r'/\d{4}/\d{4}/'))
                        
                # Last resort: find any div with faculty information
                if not bio_cards:
                    bio_cards = soup.find_all('div', class_=re.compile(r'faculty|professor|researcher|staff', re.I))
        
        print(f"Found {len(bio_cards)} faculty members in Basic Research department")
        print("=" * 70)
        
        for i, card in enumerate(bio_cards, 1):
            professor_info = {}
            
            # Extract basic info from card
            if card.name == 'div':
                name_elem = card.find('div', class_='name')
                temp_name = name_elem.text.strip() if name_elem else 'N/A'
                
                # Get title from card (if available)
                title_elem = card.find('div', class_='title')
                temp_title = ''
                if title_elem:
                    title_link = title_elem.find('a')
                    temp_title = title_link.get('title', '').strip() if title_link else title_elem.get_text(strip=True)
                
                # Get profile link
                profile_link_elem = card.find('a')
            else:
                # Handle list or link format
                if card.name == 'a':
                    profile_link_elem = card
                else:
                    profile_link_elem = card.find('a')
                temp_name = profile_link_elem.get_text(strip=True) if profile_link_elem else 'N/A'
                temp_title = ''
            
            if profile_link_elem and profile_link_elem.get('href'):
                professor_info['profile_link'] = urljoin(base_url, profile_link_elem['href'])
                
                # Visit the professor's profile page
                print(f"\n[{i}/{len(bio_cards)}] Processing {temp_name}...")
                if temp_title:
                    print(f"  Position: {temp_title}")
                
                try:
                    time.sleep(1.5)  # Be polite to the server
                    profile_response = session.get(
                        professor_info['profile_link'], 
                        headers=headers, 
                        timeout=20,
                        verify=False
                    )
                    profile_response.encoding = 'utf-8'
                    profile_soup = BeautifulSoup(profile_response.text, 'html.parser')
                    
                    # Extract detailed information from profile page
                    professor_info['name'] = extract_professor_name(profile_soup)
                    if professor_info['name'] == 'N/A':
                        professor_info['name'] = temp_name
                    
                    professor_info['title'] = extract_professor_title(profile_soup)
                    if professor_info['title'] == 'N/A' and temp_title:
                        professor_info['title'] = temp_title
                    
                    professor_info['research_field'] = extract_research_field(profile_soup)
                    professor_info['laboratory'] = extract_lab_info(profile_soup)
                    professor_info['email'] = extract_email(profile_soup)
                    professor_info['research_interests'] = extract_research_interests(profile_soup)
                    
                    # Print status
                    print(f"  ✓ Name: {professor_info['name']}")
                    print(f"    Title: {professor_info['title']}")
                    print(f"    Field: {professor_info['research_field']}")
                    print(f"    Lab: {professor_info['laboratory']}")
                    print(f"    Email: {professor_info['email']}")
                    if professor_info['research_interests'] != 'N/A':
                        preview = professor_info['research_interests'][:150]
                        print(f"    Research: {preview}...")
                    else:
                        print(f"    Research: N/A")
                    
                except requests.RequestException as e:
                    print(f"  ✗ Network error for {temp_name}: {str(e)[:100]}")
                    professor_info['name'] = temp_name
                    professor_info['title'] = temp_title if temp_title else 'N/A'
                    professor_info['research_field'] = 'Basic Research'
                    professor_info['laboratory'] = 'N/A'
                    professor_info['email'] = 'N/A'
                    professor_info['research_interests'] = 'N/A'
                    
                except Exception as e:
                    print(f"  ✗ Error processing {temp_name}: {str(e)[:100]}")
                    professor_info['name'] = temp_name
                    professor_info['title'] = temp_title if temp_title else 'N/A'
                    professor_info['research_field'] = 'Basic Research'
                    professor_info['laboratory'] = 'N/A'
                    professor_info['email'] = 'N/A'
                    professor_info['research_interests'] = 'N/A'
            else:
                print(f"\n[{i}/{len(bio_cards)}] {temp_name} - No profile link found")
                professor_info['name'] = temp_name
                professor_info['title'] = temp_title if temp_title else 'N/A'
                professor_info['research_field'] = 'Basic Research'
                professor_info['laboratory'] = 'N/A'
                professor_info['profile_link'] = 'N/A'
                professor_info['email'] = 'N/A'
                professor_info['research_interests'] = 'N/A'
            
            professors_data.append(professor_info)
        
        return professors_data
        
    except Exception as e:
        print(f"Error scraping main page: {str(e)}")
        return professors_data

def save_to_csv(data, filename='basic_research_professors.csv'):
    """
    Save the scraped data to a CSV file
    """
    if not data:
        print("No data to save")
        return
    
    fieldnames = ['name', 'title', 'research_field', 'laboratory', 'email', 'profile_link', 'research_interests']
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    print(f"\nData saved to {filename}")

def save_to_txt(data, filename='basic_research_professors.txt'):
    """
    Save the scraped data to a text file for easy reading
    """
    if not data:
        print("No data to save")
        return
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("BASIC RESEARCH FACULTY - USTC\n")
        f.write("=" * 80 + "\n\n")
        
        for i, prof in enumerate(data, 1):
            f.write(f"{i}. {prof['name']}\n")
            f.write(f"   Title: {prof.get('title', 'N/A')}\n")
            f.write(f"   Research Field: {prof.get('research_field', 'Basic Research')}\n")
            f.write(f"   Laboratory: {prof.get('laboratory', 'N/A')}\n")
            f.write(f"   Email: {prof.get('email', 'N/A')}\n")
            f.write(f"   Profile: {prof.get('profile_link', 'N/A')}\n")
            f.write(f"   Research Interests:\n")
            
            # Format research interests with word wrap
            if prof.get('research_interests', 'N/A') != 'N/A':
                import textwrap
                wrapped = textwrap.wrap(prof['research_interests'], width=75)
                for line in wrapped[:10]:  # Limit to 10 lines for readability
                    f.write(f"      {line}\n")
                if len(wrapped) > 10:
                    f.write(f"      [...]\n")
            else:
                f.write(f"      N/A\n")
            
            f.write("-" * 80 + "\n\n")
    
    print(f"Data also saved to {filename}")

def save_to_json(data, filename='basic_research_professors.json'):
    """
    Save data to JSON format for easy integration with other systems
    """
    import json
    
    if not data:
        print("No data to save")
        return
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"Data also saved to {filename}")

def print_summary_stats(data):
    """
    Print detailed summary statistics for basic research department
    """
    if not data:
        return
    
    print("\n" + "=" * 70)
    print(" " * 20 + "DETAILED STATISTICS")
    print("=" * 70)
    
    # Count by title
    titles = {}
    for prof in data:
        title = prof.get('title', 'N/A')
        if title != 'N/A':
            # Simplify title for grouping
            if 'Professor' in title and 'Associate' not in title and 'Assistant' not in title:
                key = 'Professor'
            elif 'Associate' in title:
                key = 'Associate Professor'
            elif 'Assistant' in title:
                key = 'Assistant Professor'
            elif 'Research' in title and 'Scientist' in title:
                key = 'Research Scientist'
            elif 'Postdoc' in title or 'Post-doc' in title:
                key = 'Postdoctoral Fellow'
            elif 'Principal Investigator' in title or 'PI' in title:
                key = 'Principal Investigator'
            else:
                key = 'Other'
            
            titles[key] = titles.get(key, 0) + 1
    
    if titles:
        print("\nFaculty by Position:")
        for title, count in sorted(titles.items(), key=lambda x: x[1], reverse=True):
            print(f"  • {title}: {count}")
    
    # Count by research field
    fields = {}
    for prof in data:
        field = prof.get('research_field', 'Basic Research')
        # Split multiple fields
        for f in field.split(','):
            f = f.strip()
            fields[f] = fields.get(f, 0) + 1
    
    if len(fields) > 1:
        print("\nFaculty by Research Field:")
        for field, count in sorted(fields.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"  • {field}: {count}")
    
    # Research technique/approach keywords
    research_techniques = {
        'crispr': 0, 'sequencing': 0, 'microscopy': 0,
        'crystallography': 0, 'mass spectrometry': 0, 'flow cytometry': 0,
        'computational': 0, 'modeling': 0, 'screening': 0,
        'proteomics': 0, 'genomics': 0, 'transcriptomics': 0
    }
    
    for prof in data:
        research = prof.get('research_interests', '').lower()
        for technique in research_techniques:
            if technique in research:
                research_techniques[technique] += 1
    
    if any(research_techniques.values()):
        print("\nResearch Techniques/Approaches:")
        for technique, count in sorted(research_techniques.items(), key=lambda x: x[1], reverse=True):
            if count > 0:
                print(f"  • {technique.title()}: {count}")
    
    # Lab information
    labs_count = sum(1 for p in data if p.get('laboratory', 'N/A') != 'N/A')
    if labs_count > 0:
        print(f"\nFaculty with identified laboratories: {labs_count}")

def main():
    print("\n" + "=" * 70)
    print(" " * 15 + "USTC BASIC RESEARCH FACULTY WEB SCRAPER")
    print("=" * 70 + "\n")
    
    # Disable SSL warnings if needed (for testing only)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Scrape the data
    professors_data = scrape_basic_research_faculty()
    
    if professors_data:
        # Save to multiple formats
        save_to_csv(professors_data)
        save_to_txt(professors_data)
        save_to_json(professors_data)
        
        # Print summary
        print("\n" + "=" * 70)
        print(" " * 25 + "SCRAPING SUMMARY")
        print("=" * 70)
        print(f"Total faculty members found: {len(professors_data)}")
        print(f"Faculty with emails: {sum(1 for p in professors_data if p.get('email', 'N/A') != 'N/A')}")
        print(f"Faculty with research interests: {sum(1 for p in professors_data if p.get('research_interests', 'N/A') != 'N/A')}")
        print(f"Faculty with lab information: {sum(1 for p in professors_data if p.get('laboratory', 'N/A') != 'N/A')}")
        
        # Print detailed statistics
        print_summary_stats(professors_data)
        
        # Show sample of successfully scraped data
        successful = [p for p in professors_data if p.get('email', 'N/A') != 'N/A' and p.get('research_interests', 'N/A') != 'N/A']
        if successful:
            print("\n" + "=" * 70)
            print("Sample of successfully collected data:")
            print("=" * 70)
            for prof in successful[:3]:
                print(f"\n• {prof['name']}")
                print(f"  Title: {prof.get('title', 'N/A')}")
                print(f"  Field: {prof.get('research_field', 'Basic Research')}")
                print(f"  Lab: {prof.get('laboratory', 'N/A')}")
                print(f"  Email: {prof['email']}")
                if prof.get('research_interests', 'N/A') != 'N/A':
                    print(f"  Research preview: {prof['research_interests'][:150]}...")
    else:
        print("\n" + "=" * 70)
        print("NO DATA COLLECTED")
        print("=" * 70)
        print("\nPossible solutions:")
        print("1. Use a VPN to access the site (especially one with servers in China)")
        print("2. Save the webpage manually and process offline")
        print("3. Check if the website URL has changed")
        print("4. Try again later if the site is temporarily down")
        print("5. Use a web scraping service with proxy rotation")

if __name__ == "__main__":
    main()