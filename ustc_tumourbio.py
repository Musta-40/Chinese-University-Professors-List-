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
    Looking for headings like:
    - Research Interests
    - Main Research Interests and Directions
    - Research Directions
    - Research Areas
    - Research Focus
    """
    research_interests = []
    
    # Find the content div
    content_div = profile_soup.find('div', class_='content')
    
    if content_div:
        # Find all h3 tags in the content
        h3_tags = content_div.find_all('h3')
        
        for h3 in h3_tags:
            h3_text = h3.get_text(strip=True).lower()
            # Check for various research-related keywords
            if any(keyword in h3_text for keyword in [
                'research interest', 'research direction', 'main research',
                'research area', 'research focus', 'research field',
                'scientific interest', 'research topic'
            ]):
                # Get all content after this h3 until the next h3
                current = h3.find_next_sibling()
                
                while current and current.name != 'h3':
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
                    
                    current = current.find_next_sibling()
                
                break  # Found research section, stop looking
    
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
            r'email[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        ]
        
        for pattern in email_patterns:
            email_match = re.search(pattern, content_text, re.IGNORECASE)
            if email_match:
                email = email_match.group(1).strip().rstrip('/')
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
                    email = potential_email
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
                if not any(skip in e.lower() for skip in ['example.', 'email.', 'test.', 'sample.']):
                    valid_emails.append(e)
        
        if valid_emails:
            email = valid_emails[0]
    
    return email.rstrip('/')

def extract_professor_name(profile_soup):
    """
    Extract professor name from their profile page
    """
    # Look for name in div with class="name"
    name_div = profile_soup.find('div', class_='name')
    if name_div:
        return name_div.get_text(strip=True)
    
    # Fallback: look in title tag
    title_tag = profile_soup.find('title')
    if title_tag:
        title_text = title_tag.get_text(strip=True)
        # Often the title is just the professor's name
        if title_text and len(title_text) < 50 and title_text != 'Faculty':
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
    
    return 'N/A'

def scrape_tumor_biology_faculty():
    """
    Main function to scrape Tumor Biology faculty list
    """
    base_url = "https://enbiomed.ustc.edu.cn"
    list_url = "https://enbiomed.ustc.edu.cn/TumorBiology/list.htm"
    
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
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
        'Referer': 'https://enbiomed.ustc.edu.cn/SchoolofBasicMedicalScience/list.htm'
    }
    
    professors_data = []
    
    try:
        print("\nFetching Tumor Biology faculty list page...")
        response = session.get(list_url, headers=headers, timeout=20, verify=False)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all professor bio-cards
        bio_cards = soup.find_all('div', class_='bio-card')
        
        if not bio_cards:
            print("No bio-cards found. Checking page structure...")
            # Try alternative selectors if bio-card doesn't work
            bio_cards = soup.find_all('div', class_=['faculty-card', 'professor-card', 'staff-card'])
        
        print(f"Found {len(bio_cards)} professors in Tumor Biology department")
        print("=" * 70)
        
        for i, card in enumerate(bio_cards, 1):
            professor_info = {}
            
            # Extract basic info from card
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
                    
                    professor_info['email'] = extract_email(profile_soup)
                    professor_info['research_interests'] = extract_research_interests(profile_soup)
                    
                    # Print status
                    print(f"  ✓ Name: {professor_info['name']}")
                    print(f"    Title: {professor_info['title']}")
                    print(f"    Email: {professor_info['email']}")
                    if professor_info['research_interests'] != 'N/A':
                        preview = professor_info['research_interests'][:150]
                        print(f"    Research: {preview}...")
                    else:
                        print(f"    Research: N/A")
                    
                except requests.RequestException as e:
                    print(f"  ✗ Network error for {temp_name}: {str(e)}")
                    professor_info['name'] = temp_name
                    professor_info['title'] = temp_title if temp_title else 'N/A'
                    professor_info['email'] = 'N/A'
                    professor_info['research_interests'] = 'N/A'
                    
                except Exception as e:
                    print(f"  ✗ Error processing {temp_name}: {str(e)}")
                    professor_info['name'] = temp_name
                    professor_info['title'] = temp_title if temp_title else 'N/A'
                    professor_info['email'] = 'N/A'
                    professor_info['research_interests'] = 'N/A'
            else:
                print(f"\n[{i}/{len(bio_cards)}] {temp_name} - No profile link found")
                professor_info['name'] = temp_name
                professor_info['title'] = temp_title if temp_title else 'N/A'
                professor_info['profile_link'] = 'N/A'
                professor_info['email'] = 'N/A'
                professor_info['research_interests'] = 'N/A'
            
            professors_data.append(professor_info)
        
        return professors_data
        
    except Exception as e:
        print(f"Error scraping main page: {str(e)}")
        return professors_data

def save_to_csv(data, filename='tumor_biology_professors.csv'):
    """
    Save the scraped data to a CSV file
    """
    if not data:
        print("No data to save")
        return
    
    fieldnames = ['name', 'title', 'email', 'profile_link', 'research_interests']
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    print(f"\nData saved to {filename}")

def save_to_txt(data, filename='tumor_biology_professors.txt'):
    """
    Save the scraped data to a text file for easy reading
    """
    if not data:
        print("No data to save")
        return
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("TUMOR BIOLOGY FACULTY - USTC\n")
        f.write("=" * 80 + "\n\n")
        
        for i, prof in enumerate(data, 1):
            f.write(f"{i}. {prof['name']}\n")
            f.write(f"   Title: {prof['title']}\n")
            f.write(f"   Email: {prof['email']}\n")
            f.write(f"   Profile: {prof['profile_link']}\n")
            f.write(f"   Research Interests:\n")
            
            # Format research interests with word wrap
            if prof['research_interests'] != 'N/A':
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

def save_to_json(data, filename='tumor_biology_professors.json'):
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

def main():
    print("\n" + "=" * 70)
    print(" " * 15 + "USTC TUMOR BIOLOGY FACULTY WEB SCRAPER")
    print("=" * 70 + "\n")
    
    # Disable SSL warnings if needed (for testing only)
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
    
    # Scrape the data
    professors_data = scrape_tumor_biology_faculty()
    
    if professors_data:
        # Save to multiple formats
        save_to_csv(professors_data)
        save_to_txt(professors_data)
        save_to_json(professors_data)
        
        # Print summary
        print("\n" + "=" * 70)
        print(" " * 25 + "SCRAPING SUMMARY")
        print("=" * 70)
        print(f"Total professors found: {len(professors_data)}")
        print(f"Professors with emails: {sum(1 for p in professors_data if p.get('email', 'N/A') != 'N/A')}")
        print(f"Professors with research interests: {sum(1 for p in professors_data if p.get('research_interests', 'N/A') != 'N/A')}")
        
        # Show sample of successfully scraped data
        successful = [p for p in professors_data if p.get('email', 'N/A') != 'N/A' and p.get('research_interests', 'N/A') != 'N/A']
        if successful:
            print("\n" + "=" * 70)
            print("Sample of successfully collected data:")
            print("=" * 70)
            for prof in successful[:2]:
                print(f"\n• {prof['name']} ({prof['title']})")
                print(f"  Email: {prof['email']}")
                if prof['research_interests'] != 'N/A':
                    print(f"  Research preview: {prof['research_interests'][:200]}...")
    else:
        print("\n" + "=" * 70)
        print("NO DATA COLLECTED")
        print("=" * 70)
        print("\nPossible solutions:")
        print("1. Use a VPN to access the site")
        print("2. Save the webpage manually and process offline")
        print("3. Check if the website URL has changed")
        print("4. Try again later if the site is temporarily down")

if __name__ == "__main__":
    main()