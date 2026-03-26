import requests
from bs4 import BeautifulSoup
import json
import time
import re
from urllib.parse import urljoin

def scrape_faculty_profile(profile_url):
    """
    Scrape detailed information from a faculty member's profile page
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(profile_url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        profile_info = {}
        
        # Find the main content area
        content = soup.find('div', class_='wp_articlecontent')
        if not content:
            content = soup.find('div', class_='v_news_content')
        if not content:
            # Try alternative content container
            content = soup.find('div', class_='Article_Content')
        
        if content:
            # Get all text content
            text_content = content.get_text()
            
            # Extract email using regex patterns
            email_patterns = [
                r'[Ee]-?mail[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'Email[:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'([a-zA-Z0-9._%+-]+@fudan\.edu\.cn)',
                r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            ]
            
            for pattern in email_patterns:
                email_match = re.search(pattern, text_content)
                if email_match:
                    profile_info['email'] = email_match.group(1)
                    break
            
            # Extract phone number
            phone_patterns = [
                r'[Tt]el[:\s]*([+\d\s-]+)',
                r'[Pp]hone[:\s]*([+\d\s-]+)',
                r'电话[:\s]*([+\d\s-]+)',
                r'办公电话[:\s]*([+\d\s-]+)'
            ]
            
            for pattern in phone_patterns:
                phone_match = re.search(pattern, text_content)
                if phone_match:
                    profile_info['phone'] = phone_match.group(1).strip()
                    break
            
            # Extract office/address
            office_patterns = [
                r'[Oo]ffice[:\s]*([^\n]+)',
                r'[Aa]ddress[:\s]*([^\n]+)',
                r'办公室[:\s]*([^\n]+)'
            ]
            
            for pattern in office_patterns:
                office_match = re.search(pattern, text_content)
                if office_match:
                    profile_info['office'] = office_match.group(1).strip()
                    break
            
            # Look for structured data in tables or definition lists
            tables = content.find_all('table')
            for table in tables:
                rows = table.find_all('tr')
                for row in rows:
                    cells = row.find_all(['td', 'th'])
                    if len(cells) >= 2:
                        label = cells[0].get_text().strip().lower()
                        value = cells[1].get_text().strip()
                        
                        if 'email' in label or 'e-mail' in label:
                            profile_info['email'] = value
                        elif 'phone' in label or 'tel' in label:
                            profile_info['phone'] = value
                        elif 'office' in label or 'address' in label:
                            profile_info['office'] = value
            
            # Try to find email in any <a href="mailto:..."> tags
            mailto_links = soup.find_all('a', href=re.compile(r'^mailto:'))
            if mailto_links and 'email' not in profile_info:
                email = mailto_links[0]['href'].replace('mailto:', '')
                profile_info['email'] = email
        
        return profile_info
    
    except Exception as e:
        print(f"Error scraping profile {profile_url}: {str(e)}")
        return {}

def scrape_faculty_page(url):
    """
    Scrape faculty information from a single listing page
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        faculty_list = []
        
        # Find all faculty entries
        faculty_items = soup.find_all('li', class_='news left clearfix')
        
        for item in faculty_items:
            faculty_info = {}
            
            # Extract name and profile link
            name_link = item.find('a', title=True)
            if name_link:
                faculty_info['name'] = name_link.get('title', '').strip()
                profile_url = name_link.get('href', '')
                if profile_url:
                    faculty_info['profile_url'] = urljoin('https://ibs.fudan.edu.cn', profile_url)
                else:
                    faculty_info['profile_url'] = ''
            
            # Extract image URL
            img_tag = item.find('img')
            if img_tag:
                img_url = img_tag.get('src', '')
                if img_url:
                    faculty_info['image_url'] = urljoin('https://ibs.fudan.edu.cn', img_url)
                else:
                    faculty_info['image_url'] = ''
            
            # Extract credentials and research area
            text_content = item.find('dl', class_='left you')
            if text_content:
                text_lines = text_content.get_text(separator='\n').strip().split('\n')
                text_lines = [line.strip() for line in text_lines if line.strip()]
                
                if len(text_lines) > 0:
                    degree_line = text_lines[0].replace(faculty_info.get('name', ''), '').strip()
                    faculty_info['degree'] = degree_line
                
                if len(text_lines) > 1:
                    faculty_info['research_area'] = text_lines[-1].strip()
                else:
                    faculty_info['research_area'] = ''
            
            if faculty_info.get('name'):
                faculty_list.append(faculty_info)
        
        return faculty_list
    
    except Exception as e:
        print(f"Error scraping {url}: {str(e)}")
        return []

def scrape_all_faculty_with_details():
    """
    Scrape all faculty pages and their individual profiles for complete information
    """
    base_url = "https://ibs.fudan.edu.cn/ibsen/waculty1/"
    all_faculty = []
    
    # First, get all faculty from listing pages
    print("Phase 1: Scraping faculty listing pages...")
    print("-" * 50)
    
    # Page 1
    print("Scraping listing page 1...")
    page1_url = base_url + "list.htm"
    faculty_page1 = scrape_faculty_page(page1_url)
    all_faculty.extend(faculty_page1)
    print(f"Found {len(faculty_page1)} faculty members on page 1")
    
    time.sleep(1)
    
    # Page 2
    print("Scraping listing page 2...")
    page2_url = base_url + "list2.htm"
    faculty_page2 = scrape_faculty_page(page2_url)
    all_faculty.extend(faculty_page2)
    print(f"Found {len(faculty_page2)} faculty members on page 2")
    
    print(f"\nTotal faculty found: {len(all_faculty)}")
    
    # Phase 2: Visit each faculty profile to get detailed information
    print("\nPhase 2: Scraping individual faculty profiles for emails and details...")
    print("-" * 50)
    
    for i, faculty in enumerate(all_faculty, 1):
        if faculty.get('profile_url'):
            print(f"[{i}/{len(all_faculty)}] Scraping profile for {faculty.get('name', 'Unknown')}...")
            
            # Get detailed profile information
            profile_details = scrape_faculty_profile(faculty['profile_url'])
            
            # Merge profile details with existing faculty info
            faculty.update(profile_details)
            
            # Show email if found
            if faculty.get('email'):
                print(f"  ✓ Email found: {faculty['email']}")
            else:
                print(f"  ✗ Email not found")
            
            # Be respectful to the server
            time.sleep(0.5)
    
    return all_faculty

def save_to_json(data, filename='faculty_data_complete.json'):
    """
    Save the scraped data to a JSON file
    """
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Data saved to {filename}")

def save_to_csv(data, filename='faculty_data_complete.csv'):
    """
    Save the scraped data to a CSV file
    """
    import csv
    
    if not data:
        print("No data to save")
        return
    
    # Define the order of fields for better readability
    preferred_order = ['name', 'email', 'degree', 'research_area', 'phone', 'office', 'profile_url', 'image_url']
    
    # Get all unique keys from the data
    all_keys = set()
    for item in data:
        all_keys.update(item.keys())
    
    # Order fields: preferred fields first, then any remaining fields
    remaining_keys = sorted(list(all_keys - set(preferred_order)))
    fieldnames = [field for field in preferred_order if field in all_keys] + remaining_keys
    
    with open(filename, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)
    print(f"Data saved to {filename}")

def print_summary(data):
    """
    Print a summary of the scraped data
    """
    print("\n" + "=" * 50)
    print("SCRAPING SUMMARY")
    print("=" * 50)
    
    total = len(data)
    with_email = sum(1 for f in data if f.get('email'))
    with_phone = sum(1 for f in data if f.get('phone'))
    with_office = sum(1 for f in data if f.get('office'))
    
    print(f"Total faculty members: {total}")
    print(f"Profiles with email: {with_email} ({with_email/total*100:.1f}%)")
    print(f"Profiles with phone: {with_phone} ({with_phone/total*100:.1f}%)")
    print(f"Profiles with office: {with_office} ({with_office/total*100:.1f}%)")
    
    print("\nSample of scraped data (first 5 entries with emails):")
    sample_count = 0
    for faculty in data:
        if faculty.get('email') and sample_count < 5:
            print(f"\n{sample_count + 1}. {faculty.get('name', 'Unknown')}")
            print(f"   Email: {faculty.get('email', 'N/A')}")
            print(f"   Degree: {faculty.get('degree', 'N/A')}")
            print(f"   Research: {faculty.get('research_area', 'N/A')}")
            if faculty.get('phone'):
                print(f"   Phone: {faculty.get('phone', 'N/A')}")
            if faculty.get('office'):
                print(f"   Office: {faculty.get('office', 'N/A')}")
            sample_count += 1

def main():
    """
    Main function to run the scraper
    """
    print("Starting Complete Faculty Scraper (with email extraction)...")
    print("=" * 50)
    
    # Scrape all faculty data including profile details
    faculty_data = scrape_all_faculty_with_details()
    
    if faculty_data:
        # Save to JSON
        save_to_json(faculty_data)
        
        # Save to CSV
        save_to_csv(faculty_data)
        
        # Print summary
        print_summary(faculty_data)
    else:
        print("No data was scraped. Please check the website or your connection.")

if __name__ == "__main__":
    main()