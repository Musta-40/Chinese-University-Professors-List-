import requests
from bs4 import BeautifulSoup
import time
import csv
from urllib.parse import urljoin

def get_main_page_data(url):
    """Extract professor names and profile links from main page"""
    professors = []
    
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Find all bio-cards
        bio_cards = soup.find_all('div', class_='bio-card')
        
        for card in bio_cards:
            professor_data = {}
            
            # Get name
            name_div = card.find('div', class_='name')
            if name_div:
                professor_data['name'] = name_div.text.strip()
            
            # Get profile link
            link_tag = card.find('a')
            if link_tag and link_tag.get('href'):
                # Handle both relative and absolute URLs
                profile_link = link_tag['href']
                if profile_link.startswith('http'):
                    professor_data['profile_link'] = profile_link
                else:
                    professor_data['profile_link'] = urljoin(url, profile_link)
            
            # Get title (might contain some info)
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
        response = requests.get(profile_url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Convert to string for text searching
        page_text = soup.get_text()
        
        # Look for email patterns
        import re
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, page_text)
        if emails:
            # Filter out common non-personal emails
            for email in emails:
                if not any(x in email.lower() for x in ['example', 'domain', 'email']):
                    details['email'] = email
                    break
        
        # Look for research interests/directions
        # Common patterns on academic pages
        research_keywords = ['research interest', 'research direction', 'research area', 
                           'research focus', 'research field', 'research topic']
        
        for keyword in research_keywords:
            # Look for headings containing these keywords
            for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'strong', 'b']):
                if keyword in heading.text.lower():
                    # Get the next sibling or parent's text
                    next_element = heading.find_next_sibling()
                    if next_element:
                        details['research_interests'] = next_element.text.strip()[:500]  # Limit length
                        break
                    # Check parent's text
                    parent = heading.parent
                    if parent:
                        text = parent.text.replace(heading.text, '').strip()
                        if text:
                            details['research_interests'] = text[:500]
                            break
            
            if details['research_interests']:
                break
        
        # Alternative: look for div/p tags that might contain research info
        if not details['research_interests']:
            for div in soup.find_all(['div', 'p']):
                text = div.text.lower()
                if 'research' in text and len(div.text) > 50:
                    details['research_interests'] = div.text.strip()[:500]
                    break
                    
    except Exception as e:
        print(f"Error fetching profile {profile_url}: {e}")
    
    return details

def crawl_professors(base_url):
    """Main function to crawl all professor data"""
    print("Starting to crawl professor data...")
    
    # Get main page data
    professors = get_main_page_data(base_url)
    print(f"Found {len(professors)} professors on main page")
    
    # Get details from each profile
    for i, prof in enumerate(professors):
        print(f"Processing {i+1}/{len(professors)}: {prof.get('name', 'Unknown')}")
        
        if prof.get('profile_link'):
            details = get_professor_details(prof['profile_link'])
            prof.update(details)
            
            # Be respectful to the server
            time.sleep(1)
    
    return professors

def save_to_csv(professors, filename='professors_data.csv'):
    """Save professor data to CSV file"""
    if not professors:
        print("No data to save")
        return
    
    fieldnames = ['name', 'title', 'email', 'profile_link', 'research_interests']
    
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        
        for prof in professors:
            # Ensure all fields exist
            for field in fieldnames:
                if field not in prof:
                    prof[field] = ''
            writer.writerow({k: prof[k] for k in fieldnames})
    
    print(f"Data saved to {filename}")

def main():
    # URL of the faculty page
    url = "https://enbiomed.ustc.edu.cn/Faculty_37974/list.htm"
    
    # Crawl the data
    professors_data = crawl_professors(url)
    
    # Display the results
    print("\n" + "="*50)
    print("CRAWLING RESULTS")
    print("="*50)
    
    for prof in professors_data:
        print(f"\nName: {prof.get('name', 'N/A')}")
        print(f"Title: {prof.get('title', 'N/A')}")
        print(f"Email: {prof.get('email', 'Not found')}")
        print(f"Profile: {prof.get('profile_link', 'N/A')}")
        print(f"Research: {prof.get('research_interests', 'Not found')[:100]}...")
    
    # Save to CSV
    save_to_csv(professors_data)

if __name__ == "__main__":
    main()