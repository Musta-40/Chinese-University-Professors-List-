import requests
from bs4 import BeautifulSoup
import csv
import re
from urllib.parse import urljoin
import time

def get_professor_details(url):
    """Scrape email and research direction from individual professor page"""
    try:
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Initialize default values
        email = "Not found"
        research_direction = "Not found"
        
        # Extract email using regex pattern
        email_pattern = r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"
        email_match = re.search(email_pattern, response.text)
        if email_match:
            email = email_match.group(0)
        
        # Extract research direction from specific section
        research_section = soup.find('p', class_='bt', string=re.compile(r'研究方向|研究领域'))
        if research_section:
            next_p = research_section.find_next_sibling('p', class_='txt')
            if next_p:
                research_direction = next_p.get_text(strip=True)
        
        return email, research_direction
    
    except Exception as e:
        print(f"Error scraping {url}: {str(e)}")
        return "Error", "Error"

def scrape_professors():
    base_url = "https://pharm.sjtu.edu.cn"
    target_url = f"{base_url}/bdjs/p2.html"
    professors = []
    
    try:
        # Fetch main page
        response = requests.get(target_url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find professor list container
        professor_list = soup.find('ul', class_='kt_lb')
        if not professor_list:
            return []
        
        # Extract professor data
        for li in professor_list.find_all('li'):
            link = li.find('a')
            if not link:
                continue
                
            # Extract basic info
            profile_path = link.get('href')
            profile_url = urljoin(base_url, profile_path)
            
            img_div = li.find('div', class_='imgk')
            img_src = img_div.find('img').get('src') if img_div and img_div.find('img') else None
            image_url = urljoin(base_url, img_src) if img_src else None
            
            name_div = li.find('div', class_='txtk')
            name = name_div.find('b').text.strip() if name_div and name_div.find('b') else "Unknown"
            
            # Get detailed info
            email, research_direction = get_professor_details(profile_url)
            
            professors.append({
                'name': name,
                'profile_url': profile_url,
                'image_url': image_url,
                'email': email,
                'research_direction': research_direction
            })
            
            # Be polite - delay between requests
            time.sleep(1)
        
        return professors
        
    except Exception as e:
        print(f"Error during scraping: {e}")
        return []

def save_to_csv(professors, filename='professors.csv'):
    """Save professor data to CSV file"""
    with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
        fieldnames = ['name', 'email', 'research_direction', 'profile_url', 'image_url']
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        writer.writeheader()
        for prof in professors:
            writer.writerow(prof)

if __name__ == "__main__":
    print("Starting scrape...")
    professors = scrape_professors()
    
    if professors:
        print(f"\nFound {len(professors)} professors")
        save_to_csv(professors)
        print("Data saved to professors.csv")
        
        # Print sample data
        print("\nSample data:")
        for i, prof in enumerate(professors[:3], 1):
            print(f"\nProfessor {i}:")
            print(f"Name: {prof['name']}")
            print(f"Email: {prof['email']}")
            print(f"Research: {prof['research_direction']}")
            print(f"Profile: {prof['profile_url']}")
    else:
        print("No professors found")