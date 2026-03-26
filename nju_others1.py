import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin
import re
import urllib3
import ssl

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def create_session():
    """Create a session with custom SSL settings"""
    session = requests.Session()
    
    # Custom headers to appear more like a browser
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1'
    })
    
    # Create custom SSL context
    class CustomHTTPAdapter(requests.adapters.HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ctx.set_ciphers('DEFAULT:@SECLEVEL=1')
            kwargs['ssl_context'] = ctx
            return super().init_poolmanager(*args, **kwargs)
    
    session.mount('https://', CustomHTTPAdapter())
    return session

def get_professor_list(url, session):
    """Get all professor names and profile links from the main page"""
    professors = []
    
    try:
        response = session.get(url, timeout=10, verify=False)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find all article lists that contain professor links
        article_lists = soup.find_all('ul', class_='wp_article_list')
        
        for article_list in article_lists:
            # Find all links in the list
            links = article_list.find_all('a', title=True)
            
            for link in links:
                href = link.get('href', '')
                title = link.get('title', '').strip()
                
                # Filter to get only professor links
                if href and title and len(title) <= 10:
                    # Skip if it's a navigation link
                    if '导师' not in title and '医院' not in title and '更多' not in title:
                        # Make sure we have a full URL
                        if href.startswith('/'):
                            full_url = f"https://med.nju.edu.cn{href}"
                        elif href.startswith('http'):
                            full_url = href
                        else:
                            full_url = urljoin(url, href)
                        
                        professors.append({
                            'name': title,
                            'profile_link': full_url
                        })
        
        # Also check for professor links in table format (common in this site)
        tables = soup.find_all('table', class_='wp_article_list_table')
        for table in tables:
            links = table.find_all('a', title=True)
            for link in links:
                href = link.get('href', '')
                title = link.get('title', '').strip()
                
                if href and title and len(title) <= 10:
                    if '导师' not in title and '医院' not in title:
                        if href.startswith('/'):
                            full_url = f"https://med.nju.edu.cn{href}"
                        elif href.startswith('http'):
                            full_url = href
                        else:
                            full_url = urljoin(url, href)
                        
                        professors.append({
                            'name': title,
                            'profile_link': full_url
                        })
        
    except Exception as e:
        print(f"Error fetching main page: {e}")
    
    return professors

def extract_email(text):
    """Extract email from text using regex"""
    # Common email patterns
    email_patterns = [
        r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
        r'Email[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'E-mail[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'邮箱[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'电子邮件[：:]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    ]
    
    for pattern in email_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Return the first valid-looking email
            email = matches[0] if isinstance(matches[0], str) else matches[0]
            if '@' in email:
                return email
    
    return 'N/A'

def extract_research_direction(soup):
    """Extract research direction from the professor's page"""
    research_keywords = ['研究方向', '研究领域', '研究兴趣', '主要研究方向', 'Research Interests', 'Research Direction', 'Research Areas']
    
    # Try to find research direction in various formats
    for keyword in research_keywords:
        # Look for keyword in all text elements
        for elem in soup.find_all(text=re.compile(keyword, re.IGNORECASE)):
            parent = elem.parent
            if parent:
                # Try to get the parent's parent for more context
                grandparent = parent.parent if parent.parent else parent
                full_text = grandparent.get_text(separator=' ', strip=True)
                
                if keyword in full_text:
                    # Extract text after the keyword
                    pattern = f"{keyword}[：:：\s]*(.+?)(?:研究成果|发表论文|教育背景|工作经历|联系方式|$)"
                    match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
                    if match:
                        research = match.group(1).strip()
                        # Clean up
                        research = re.sub(r'\s+', ' ', research)  # Replace multiple spaces
                        research = research.split('。')[0] if '。' in research else research  # Get first sentence
                        if research and 10 < len(research) < 500:
                            return research
    
    # Try to find in table format
    for tr in soup.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) >= 2:
            first_td = tds[0].get_text(strip=True)
            for keyword in research_keywords:
                if keyword in first_td:
                    research = tds[1].get_text(strip=True)
                    if research and 10 < len(research) < 500:
                        return research
    
    # Try div with specific classes
    for div in soup.find_all('div', class_=['content', 'article-content', 'detail-content']):
        text = div.get_text(strip=True)
        for keyword in research_keywords:
            if keyword in text:
                pattern = f"{keyword}[：:：\s]*(.+?)(?:研究成果|发表论文|教育背景|工作经历|联系方式|$)"
                match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
                if match:
                    research = match.group(1).strip()
                    research = re.sub(r'\s+', ' ', research)
                    if research and 10 < len(research) < 500:
                        return research
    
    return 'N/A'

def get_professor_details(profile_url, session):
    """Get detailed information from professor's profile page"""
    details = {
        'email': 'N/A',
        'research_direction': 'N/A'
    }
    
    try:
        response = session.get(profile_url, timeout=10, verify=False)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract email
        page_text = soup.get_text()
        details['email'] = extract_email(page_text)
        
        # Extract research direction
        details['research_direction'] = extract_research_direction(soup)
        
    except Exception as e:
        print(f"Error fetching profile {profile_url}: {e}")
    
    return details

def main():
    # URL for Model Animal Research Institute - PhD Supervisors
    base_url = "https://med.nju.edu.cn/48687/list.htm"
    
    print("Starting to crawl Model Animal Research Institute professor information...")
    print("-" * 60)
    
    # Create session with custom SSL settings
    session = create_session()
    
    # Get list of professors
    print("Fetching professor list from main page...")
    professors = get_professor_list(base_url, session)
    
    # Remove duplicates based on name
    seen_names = set()
    unique_professors = []
    for prof in professors:
        if prof['name'] not in seen_names:
            seen_names.add(prof['name'])
            unique_professors.append(prof)
    
    print(f"Found {len(unique_professors)} unique professors")
    print("-" * 60)
    
    # Get details for each professor
    results = []
    for i, prof in enumerate(unique_professors, 1):
        print(f"Processing {i}/{len(unique_professors)}: {prof['name']}")
        
        # Get professor details
        details = get_professor_details(prof['profile_link'], session)
        
        # Combine information
        professor_info = {
            'Name': prof['name'],
            'Email': details['email'],
            'Profile Link': prof['profile_link'],
            'Research Direction': details['research_direction']
        }
        
        results.append(professor_info)
        
        # Be polite to the server
        time.sleep(1)
    
    # Save to CSV
    df = pd.DataFrame(results)
    output_file = 'nju_model_animal_institute_professors.csv'
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print("-" * 60)
    print(f"Data saved to {output_file}")
    
    # Display sample results
    print("\nSample Results:")
    print("-" * 60)
    for i, result in enumerate(results[:5], 1):
        print(f"\n{i}. Professor: {result['Name']}")
        print(f"   Email: {result['Email']}")
        print(f"   Profile: {result['Profile Link']}")
        research = result['Research Direction']
        if research != 'N/A' and len(research) > 100:
            print(f"   Research: {research[:100]}...")
        else:
            print(f"   Research: {research}")
    
    # Statistics
    print("\n" + "=" * 60)
    print("STATISTICS:")
    print(f"Total professors crawled: {len(df)}")
    print(f"Professors with email: {len(df[df['Email'] != 'N/A'])}")
    print(f"Professors with research direction: {len(df[df['Research Direction'] != 'N/A'])}")
    
    return df

def crawl_multiple_pages():
    """Crawl multiple related pages if there are pagination links"""
    session = create_session()
    all_professors = []
    
    # List of URLs to crawl (add more if there are multiple pages)
    urls = [
        "https://med.nju.edu.cn/48687/list.htm",  # PhD supervisors
        "https://med.nju.edu.cn/48688/list.htm",  # Master supervisors (if exists)
    ]
    
    for url in urls:
        print(f"\nCrawling: {url}")
        try:
            professors = get_professor_list(url, session)
            all_professors.extend(professors)
            print(f"Found {len(professors)} professors on this page")
        except Exception as e:
            print(f"Error crawling {url}: {e}")
    
    # Remove duplicates
    seen = set()
    unique_professors = []
    for prof in all_professors:
        if prof['name'] not in seen:
            seen.add(prof['name'])
            unique_professors.append(prof)
    
    print(f"\nTotal unique professors found: {len(unique_professors)}")
    
    # Process each professor
    results = []
    for i, prof in enumerate(unique_professors, 1):
        print(f"Processing {i}/{len(unique_professors)}: {prof['name']}")
        details = get_professor_details(prof['profile_link'], session)
        
        professor_info = {
            'Name': prof['name'],
            'Email': details['email'],
            'Profile Link': prof['profile_link'],
            'Research Direction': details['research_direction']
        }
        results.append(professor_info)
        time.sleep(1)
    
    # Save results
    df = pd.DataFrame(results)
    df.to_csv('nju_model_animal_all_professors.csv', index=False, encoding='utf-8-sig')
    print(f"\nAll data saved to nju_model_animal_all_professors.csv")
    
    return df

if __name__ == "__main__":
    try:
        # Crawl single page
        df = main()
        
        # Uncomment to crawl multiple pages
        # df = crawl_multiple_pages()
        
    except Exception as e:
        print(f"\nError occurred: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you have installed: pip install requests beautifulsoup4 pandas urllib3")
        print("2. Check your internet connection")
        print("3. The website might be temporarily down")