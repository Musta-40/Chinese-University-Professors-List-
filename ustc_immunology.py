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

def scrape_with_fallback():
    """
    Alternative: Scrape using saved HTML file
    """
    print("\n" + "=" * 70)
    print("ALTERNATIVE METHOD: Using saved HTML")
    print("=" * 70)
    print("\nSince the website is not accessible, you can:")
    print("1. Save the webpage manually")
    print("2. Use a VPN to access the site")
    print("3. Use the following script with saved HTML files")
    
    return """
# Alternative script for offline/saved HTML processing

import os
from bs4 import BeautifulSoup
import csv

def process_saved_html(list_html_file, professor_html_folder):
    '''
    Process saved HTML files
    
    Args:
        list_html_file: Path to the saved main list HTML file
        professor_html_folder: Folder containing individual professor HTML files
    '''
    professors_data = []
    
    # Read the main list page
    with open(list_html_file, 'r', encoding='utf-8') as f:
        soup = BeautifulSoup(f.read(), 'html.parser')
    
    bio_cards = soup.find_all('div', class_='bio-card')
    print(f"Found {len(bio_cards)} professors in saved HTML")
    
    for card in bio_cards:
        professor_info = {}
        
        # Extract name from card
        name_elem = card.find('div', class_='name')
        professor_info['name'] = name_elem.text.strip() if name_elem else 'N/A'
        
        # Try to find corresponding professor HTML file
        professor_file = os.path.join(professor_html_folder, f"{professor_info['name'].replace(' ', '_')}.html")
        
        if os.path.exists(professor_file):
            with open(professor_file, 'r', encoding='utf-8') as f:
                prof_soup = BeautifulSoup(f.read(), 'html.parser')
            
            # Extract details from professor page
            professor_info['email'] = extract_email_from_soup(prof_soup)
            professor_info['research_interests'] = extract_research_from_soup(prof_soup)
        
        professors_data.append(professor_info)
    
    return professors_data

# Usage:
# data = process_saved_html('immunology_list.html', 'professor_pages/')
"""

def extract_research_interests(profile_soup):
    """
    Extract research interests from the professor's profile page
    """
    research_interests = []
    
    # Find the content div
    content_div = profile_soup.find('div', class_='content')
    
    if content_div:
        # Find all h3 tags in the content
        h3_tags = content_div.find_all('h3')
        
        for h3 in h3_tags:
            h3_text = h3.get_text(strip=True).lower()
            if any(keyword in h3_text for keyword in ['research interest', 'research direction', 'main research']):
                current = h3.find_next_sibling()
                
                while current and current.name != 'h3':
                    if current.name == 'p':
                        text = current.get_text(strip=True)
                        if text and len(text) > 10:
                            research_interests.append(text)
                    elif current.name in ['ol', 'ul']:
                        list_items = current.find_all('li')
                        for li in list_items:
                            li_text = li.get_text(strip=True)
                            if li_text:
                                research_interests.append(li_text)
                    
                    current = current.find_next_sibling()
                
                break
    
    if research_interests:
        return ' '.join(research_interests)
    
    return 'N/A'

def extract_email(profile_soup):
    """
    Extract email address from the professor's profile page
    """
    email = 'N/A'
    
    content_div = profile_soup.find('div', class_='content')
    
    if content_div:
        content_text = content_div.get_text()
        email_pattern = r'Email[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        email_match = re.search(email_pattern, content_text, re.IGNORECASE)
        
        if email_match:
            email = email_match.group(1).strip().rstrip('/')
            return email
    
    # Fallback to mailto links
    mailto_links = profile_soup.find_all('a', href=re.compile(r'^mailto:'))
    if mailto_links:
        for link in mailto_links:
            email_href = link.get('href', '')
            if email_href.startswith('mailto:'):
                potential_email = email_href.replace('mailto:', '').strip()
                if '@' in potential_email and '.' in potential_email.split('@')[1]:
                    email = potential_email
                    break
    
    return email.rstrip('/')

def scrape_faculty_list():
    """
    Main scraping function with better error handling
    """
    # Correct URL (note: was 38310, not 38318)
    base_url = "https://enbiomed.ustc.edu.cn"
    list_url = "https://enbiomed.ustc.edu.cn/Immunology_38310/list.htm"
    
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
        print("\n5. As a last resort, save the HTML pages manually and process offline")
        
        print(scrape_with_fallback())
        return []
    
    # Create session with retries
    session = create_session_with_retries()
    
    # Enhanced headers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0'
    }
    
    professors_data = []
    
    try:
        print("\nFetching main faculty list page...")
        response = session.get(list_url, headers=headers, timeout=20)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        bio_cards = soup.find_all('div', class_='bio-card')
        print(f"Found {len(bio_cards)} professors")
        
        for i, card in enumerate(bio_cards, 1):
            professor_info = {}
            
            name_elem = card.find('div', class_='name')
            professor_info['name'] = name_elem.text.strip() if name_elem else 'N/A'
            
            profile_link_elem = card.find('a')
            if profile_link_elem and profile_link_elem.get('href'):
                professor_info['profile_link'] = urljoin(base_url, profile_link_elem['href'])
                
                print(f"\n[{i}/{len(bio_cards)}] Processing {professor_info['name']}...")
                
                try:
                    time.sleep(2)  # Longer delay to be safe
                    profile_response = session.get(professor_info['profile_link'], headers=headers, timeout=20)
                    profile_response.encoding = 'utf-8'
                    profile_soup = BeautifulSoup(profile_response.text, 'html.parser')
                    
                    # Extract information
                    title_div = profile_soup.find('div', class_='title')
                    professor_info['title'] = title_div.get_text(strip=True) if title_div else 'N/A'
                    professor_info['email'] = extract_email(profile_soup)
                    professor_info['research_interests'] = extract_research_interests(profile_soup)
                    
                    print(f"  ✓ Email: {professor_info['email']}")
                    
                except Exception as e:
                    print(f"  ✗ Error: {str(e)}")
                    professor_info['title'] = 'N/A'
                    professor_info['email'] = 'N/A'
                    professor_info['research_interests'] = 'N/A'
            else:
                professor_info['profile_link'] = 'N/A'
                professor_info['title'] = 'N/A'
                professor_info['email'] = 'N/A'
                professor_info['research_interests'] = 'N/A'
            
            professors_data.append(professor_info)
        
        return professors_data
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return professors_data

def save_to_csv(data, filename='immunology_professors.csv'):
    """Save data to CSV"""
    if not data:
        print("No data to save")
        return
    
    fieldnames = ['name', 'title', 'email', 'profile_link', 'research_interests']
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    
    print(f"\nData saved to {filename}")

def main():
    print("\n" + "=" * 70)
    print(" " * 20 + "USTC IMMUNOLOGY FACULTY WEB SCRAPER")
    print("=" * 70 + "\n")
    
    # Try proxies if direct connection fails
    print("Attempting to connect to the website...")
    
    professors_data = scrape_faculty_list()
    
    if professors_data:
        save_to_csv(professors_data)
        print(f"\nSuccessfully scraped {len(professors_data)} professors")
    else:
        print("\nNo data could be scraped. Please check the troubleshooting tips above.")

if __name__ == "__main__":
    main()