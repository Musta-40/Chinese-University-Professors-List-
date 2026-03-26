import requests
from bs4 import BeautifulSoup
import time
import csv
import re
from urllib.parse import urljoin

def get_main_page_data(url):
    """Extract professor names and profile links from main page"""
    professors = []
    
    try:
        # Add headers to mimic a browser request
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all bio-cards
        bio_cards = soup.find_all('div', class_='bio-card')
        
        print(f"Found {len(bio_cards)} bio-cards on the page")
        
        for card in bio_cards:
            professor_data = {}
            
            # Get name
            name_div = card.find('div', class_='name')
            if name_div:
                professor_data['name'] = name_div.text.strip()
            
            # Get profile link
            link_tag = card.find('a')
            if link_tag and link_tag.get('href'):
                profile_link = link_tag['href']
                if profile_link.startswith('http'):
                    professor_data['profile_link'] = profile_link
                else:
                    professor_data['profile_link'] = urljoin(url, profile_link)
            
            # Get title/position
            title_div = card.find('div', class_='title')
            if title_div:
                professor_data['title'] = title_div.text.strip()
            
            if professor_data.get('name') and professor_data.get('profile_link'):
                professors.append(professor_data)
                
    except Exception as e:
        print(f"Error fetching main page: {e}")
    
    return professors

def get_professor_details(profile_url):
    """Extract email and research interests from individual profile page"""
    details = {'email': '', 'research_interests': ''}
    
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(profile_url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Look for email
        # Method 1: Search in text
        page_text = soup.get_text()
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, page_text)
        
        if emails:
            # Filter out common non-personal emails and prefer .edu.cn emails
            for email in emails:
                if '@' in email and not any(x in email.lower() for x in ['example', 'domain', 'test']):
                    details['email'] = email
                    if 'ustc.edu.cn' in email:  # Prefer USTC emails
                        break
        
        # Method 2: Look for email in specific tags
        if not details['email']:
            for tag in soup.find_all(['p', 'div', 'span', 'td']):
                if tag.text and 'email' in tag.text.lower():
                    emails = re.findall(email_pattern, tag.text)
                    if emails:
                        details['email'] = emails[0]
                        break
        
        # Look for research interests/directions
        research_found = False
        
        # Method 1: Look for specific headings
        research_keywords = [
            'research interest', 'research direction', 'research area',
            'research focus', 'research field', 'current research',
            '研究方向', 'research topics', 'research'
        ]
        
        for keyword in research_keywords:
            if research_found:
                break
                
            # Check all text elements
            for element in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b', 'p', 'div']):
                if element and element.text and keyword in element.text.lower():
                    # Try to get the content after this heading
                    parent = element.parent
                    if parent:
                        # Get all text after this element
                        siblings = element.find_next_siblings()
                        if siblings:
                            research_text = ""
                            for sib in siblings[:3]:  # Get next 3 siblings
                                text = sib.text.strip()
                                if text and len(text) > 20:
                                    research_text += text + " "
                                    if len(research_text) > 100:
                                        break
                            
                            if research_text:
                                details['research_interests'] = research_text[:500]
                                research_found = True
                                break
                    
                    # Alternative: Get the next element's text
                    next_elem = element.find_next_sibling()
                    if next_elem and next_elem.text:
                        text = next_elem.text.strip()
                        if len(text) > 20:
                            details['research_interests'] = text[:500]
                            research_found = True
                            break
        
        # Method 2: Look for lists after research headings
        if not details['research_interests']:
            for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'strong']):
                if 'research' in heading.text.lower():
                    # Look for ul or ol lists after this heading
                    next_list = heading.find_next_sibling(['ul', 'ol'])
                    if next_list:
                        items = next_list.find_all('li')
                        if items:
                            research_items = [item.text.strip() for item in items[:5]]
                            details['research_interests'] = '; '.join(research_items)[:500]
                            break
                            
    except requests.exceptions.RequestException as e:
        print(f"Network error fetching profile {profile_url}: {e}")
    except Exception as e:
        print(f"Error processing profile {profile_url}: {e}")
    
    return details

def crawl_cell_biology_professors():
    """Main function to crawl Cell Biology faculty data"""
    base_url = "https://enbiomed.ustc.edu.cn/CellBiology/list.htm"
    
    print("="*60)
    print("CRAWLING CELL BIOLOGY FACULTY PAGE")
    print("="*60)
    print(f"Target URL: {base_url}\n")
    
    # Get main page data
    print("Step 1: Fetching main faculty list page...")
    professors = get_main_page_data(base_url)
    print(f"✓ Found {len(professors)} professors\n")
    
    if not professors:
        print("No professors found. Please check if the page structure has changed.")
        return []
    
    # Get details from each profile
    print("Step 2: Fetching individual professor profiles...")
    for i, prof in enumerate(professors, 1):
        print(f"[{i}/{len(professors)}] Processing: {prof.get('name', 'Unknown')}")
        
        if prof.get('profile_link'):
            details = get_professor_details(prof['profile_link'])
            prof.update(details)
            
            # Show what was found
            if details['email']:
                print(f"  ✓ Email found: {details['email']}")
            else:
                print(f"  ✗ Email not found")
                
            if details['research_interests']:
                print(f"  ✓ Research interests found ({len(details['research_interests'])} chars)")
            else:
                print(f"  ✗ Research interests not found")
            
            # Be respectful to the server
            time.sleep(1)
        else:
            print(f"  ✗ No profile link available")
    
    return professors

def save_to_csv(professors, filename='cell_biology_faculty.csv'):
    """Save professor data to CSV file"""
    if not professors:
        print("\nNo data to save")
        return
    
    fieldnames = ['name', 'title', 'email', 'profile_link', 'research_interests']
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for prof in professors:
            # Ensure all fields exist
            row_data = {}
            for field in fieldnames:
                row_data[field] = prof.get(field, '')
            writer.writerow(row_data)
    
    print(f"\n✓ Data saved to {filename}")

def save_to_json(professors, filename='cell_biology_faculty.json'):
    """Save professor data to JSON file"""
    import json
    
    if not professors:
        print("No data to save")
        return
    
    with open(filename, 'w', encoding='utf-8') as jsonfile:
        json.dump(professors, jsonfile, ensure_ascii=False, indent=2)
    
    print(f"✓ Data saved to {filename}")

def display_summary(professors):
    """Display a summary of the crawled data"""
    print("\n" + "="*60)
    print("CRAWLING SUMMARY")
    print("="*60)
    
    print(f"\nTotal professors found: {len(professors)}")
    
    # Count statistics
    with_email = sum(1 for p in professors if p.get('email'))
    with_research = sum(1 for p in professors if p.get('research_interests'))
    
    print(f"Professors with email: {with_email}/{len(professors)}")
    print(f"Professors with research interests: {with_research}/{len(professors)}")
    
    print("\n" + "-"*60)
    print("DETAILED RESULTS:")
    print("-"*60)
    
    for i, prof in enumerate(professors, 1):
        print(f"\n[{i}] {prof.get('name', 'N/A')}")
        print(f"    Title: {prof.get('title', 'N/A')}")
        print(f"    Email: {prof.get('email', 'Not found')}")
        print(f"    Profile: {prof.get('profile_link', 'N/A')}")
        
        research = prof.get('research_interests', '')
        if research:
            # Show first 150 characters of research interests
            if len(research) > 150:
                print(f"    Research: {research[:150]}...")
            else:
                print(f"    Research: {research}")
        else:
            print(f"    Research: Not found")

def main():
    """Main execution function"""
    try:
        # Crawl the data
        professors_data = crawl_cell_biology_professors()
        
        if professors_data:
            # Display summary
            display_summary(professors_data)
            
            # Save to files
            print("\n" + "="*60)
            print("SAVING DATA")
            print("="*60)
            
            save_to_csv(professors_data)
            save_to_json(professors_data)
            
            print("\n✓ Crawling completed successfully!")
        else:
            print("\n✗ No data was collected. Please check the website or script.")
            
    except KeyboardInterrupt:
        print("\n\nCrawling interrupted by user.")
    except Exception as e:
        print(f"\n✗ An error occurred: {e}")

if __name__ == "__main__":
    main()