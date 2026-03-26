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
        
        # Debug: Save the page for inspection
        with open('gulou_page.html', 'w', encoding='utf-8') as f:
            f.write(soup.prettify())
        
        # Find all article lists that contain professor links
        article_lists = soup.find_all('ul', class_='wp_article_list')
        
        for article_list in article_lists:
            # Find all links in the list
            links = article_list.find_all('a', title=True)
            
            for link in links:
                href = link.get('href', '')
                title = link.get('title', '').strip()
                
                # Filter to get only professor links
                if href and title:
                    # Skip navigation and non-professor links
                    skip_keywords = ['导师', '医院', '更多', '浏览', '栏目', '首页', '学院']
                    if not any(keyword in title for keyword in skip_keywords):
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
        
        # Also check for professor links in table format
        tables = soup.find_all('table', class_='wp_article_list_table')
        for table in tables:
            links = table.find_all('a', title=True)
            for link in links:
                href = link.get('href', '')
                title = link.get('title', '').strip()
                
                if href and title:
                    skip_keywords = ['导师', '医院', '更多', '浏览', '栏目', '首页', '学院']
                    if not any(keyword in title for keyword in skip_keywords):
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
        
        # Check for any div-based lists (some pages use different structures)
        news_lists = soup.find_all('div', class_=['news_list', 'list_content', 'article_list'])
        for news_list in news_lists:
            links = news_list.find_all('a', title=True)
            for link in links:
                href = link.get('href', '')
                title = link.get('title', '').strip()
                
                if href and title:
                    skip_keywords = ['导师', '医院', '更多', '浏览', '栏目', '首页', '学院']
                    if not any(keyword in title for keyword in skip_keywords):
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
        r'Email[：:：\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'E-mail[：:：\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'邮箱[：:：\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'电子邮件[：:：\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'电邮[：:：\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
        r'联系方式[：:：\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
    ]
    
    for pattern in email_patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        if matches:
            # Return the first valid-looking email
            if isinstance(matches[0], tuple):
                email = matches[0][0] if matches[0] else ''
            else:
                email = matches[0]
            
            if '@' in email and '.' in email.split('@')[1]:
                return email
    
    return 'N/A'

def extract_research_direction(soup):
    """Extract research direction from the professor's page"""
    research_keywords = [
        '研究方向', '研究领域', '研究兴趣', '主要研究方向', '研究内容', '专业方向',
        '临床研究方向', '科研方向', '学术方向', '专业特长',
        'Research Interests', 'Research Direction', 'Research Areas', 'Research Focus'
    ]
    
    # Method 1: Look for research direction in text
    for keyword in research_keywords:
        # Search in all text elements
        for elem in soup.find_all(text=re.compile(keyword, re.IGNORECASE)):
            parent = elem.parent
            if parent:
                # Get more context
                grandparent = parent.parent if parent.parent else parent
                full_text = grandparent.get_text(separator=' ', strip=True)
                
                if keyword in full_text:
                    # Extract text after the keyword
                    pattern = f"{keyword}[：:：\\s]*(.+?)(?:研究成果|主要成果|发表论文|教育背景|工作经历|个人简介|联系方式|获奖|专利|学术兼职|社会兼职|$)"
                    match = re.search(pattern, full_text, re.IGNORECASE | re.DOTALL)
                    if match:
                        research = match.group(1).strip()
                        # Clean up
                        research = re.sub(r'\s+', ' ', research)
                        research = re.sub(r'^\d+[\.\、]\s*', '', research)  # Remove numbering
                        research = re.sub(r'^[：:：]\s*', '', research)
                        if research and 10 < len(research) < 1000:
                            return research
    
    # Method 2: Look in table cells
    for tr in soup.find_all('tr'):
        tds = tr.find_all('td')
        if len(tds) >= 2:
            first_td = tds[0].get_text(strip=True)
            for keyword in research_keywords:
                if keyword in first_td:
                    research = tds[1].get_text(strip=True)
                    research = re.sub(r'\s+', ' ', research)
                    research = re.sub(r'^\d+[\.\、]\s*', '', research)
                    if research and 10 < len(research) < 1000:
                        return research
    
    # Method 3: Look in divs/paragraphs with specific patterns
    for elem in soup.find_all(['div', 'p', 'span', 'li']):
        text = elem.get_text(strip=True)
        for keyword in research_keywords:
            if keyword in text:
                # Try to extract content after keyword
                parts = text.split(keyword)
                if len(parts) > 1:
                    research = parts[1].strip()
                    # Get first meaningful sentence/paragraph
                    if '。' in research:
                        research = research.split('。')[0]
                    research = re.sub(r'^[：:：]\s*', '', research)
                    research = re.sub(r'\s+', ' ', research)
                    if research and 10 < len(research) < 1000:
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

def crawl_all_pages(base_url, session):
    """Crawl all pages if there's pagination"""
    all_professors = []
    page_num = 1
    max_pages = 30  # Safety limit
    
    while page_num <= max_pages:
        if page_num == 1:
            url = base_url
        else:
            # Common pagination patterns for this site
            url = base_url.replace('.htm', f'/{page_num}.htm')
        
        print(f"Checking page {page_num}...")
        
        try:
            response = session.get(url, timeout=10, verify=False)
            if response.status_code != 200:
                print(f"Page {page_num} returned status code {response.status_code}")
                break
                
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Check if there are professors on this page
            professors = get_professor_list(url, session)
            
            if not professors:
                print(f"No professors found on page {page_num}")
                break
                
            all_professors.extend(professors)
            print(f"Found {len(professors)} professors on page {page_num}")
            
            # Check if there's a next page link
            pagination = soup.find('div', class_='wp_paging')
            if pagination:
                next_link = pagination.find('a', text=re.compile('下一页|next', re.IGNORECASE))
                if not next_link or 'disabled' in str(next_link.get('class', [])):
                    print("No more pages found")
                    break
            
            page_num += 1
            time.sleep(0.5)  # Be polite
            
        except Exception as e:
            print(f"Error on page {page_num}: {e}")
            break
    
    return all_professors

def main():
    # URL for Affiliated Drum Tower Hospital - PhD Supervisors
    base_url = "https://med.nju.edu.cn/10884/list.htm"
    
    print("=" * 70)
    print("Starting to crawl Affiliated Drum Tower Hospital professor information...")
    print("附属鼓楼医院 - 博士生导师")
    print("=" * 70)
    
    # Create session with custom SSL settings
    session = create_session()
    
    # Get list of professors (check for multiple pages)
    print("\nFetching professor list...")
    professors = crawl_all_pages(base_url, session)
    
    # If no professors found from pagination, try single page
    if not professors:
        print("Trying single page fetch...")
        professors = get_professor_list(base_url, session)
    
    # Remove duplicates based on name
    seen_names = set()
    unique_professors = []
    for prof in professors:
        if prof['name'] not in seen_names:
            seen_names.add(prof['name'])
            unique_professors.append(prof)
    
    print(f"\nFound {len(unique_professors)} unique professors")
    print("-" * 70)
    
    if not unique_professors:
        print("No professors found. The page structure might have changed.")
        return None
    
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
            'Research Direction': details['research_direction'],
            'Department': '附属鼓楼医院',
            'Type': '博士生导师'
        }
        
        results.append(professor_info)
        
        # Be polite to the server
        time.sleep(1)
    
    # Save to CSV
    df = pd.DataFrame(results)
    output_file = 'nju_gulou_hospital_professors.csv'
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print("-" * 70)
    print(f"Data saved to {output_file}")
    
    # Display sample results
    print("\nSample Results:")
    print("-" * 70)
    display_count = min(5, len(results))
    for i, result in enumerate(results[:display_count], 1):
        print(f"\n{i}. Professor: {result['Name']}")
        print(f"   Department: {result['Department']}")
        print(f"   Type: {result['Type']}")
        print(f"   Email: {result['Email']}")
        print(f"   Profile: {result['Profile Link']}")
        research = result['Research Direction']
        if research != 'N/A' and len(research) > 100:
            print(f"   Research: {research[:100]}...")
        else:
            print(f"   Research: {research}")
    
    # Statistics
    print("\n" + "=" * 70)
    print("STATISTICS:")
    print(f"Total professors crawled: {len(df)}")
    print(f"Professors with email: {len(df[df['Email'] != 'N/A'])}")
    print(f"Professors with research direction: {len(df[df['Research Direction'] != 'N/A'])}")
    print("=" * 70)
    
    return df

def crawl_gulou_all():
    """Crawl both PhD and Master supervisors from Drum Tower Hospital"""
    session = create_session()
    all_results = []
    
    urls = [
        ("https://med.nju.edu.cn/10884/list.htm", "博士生导师"),
        ("https://med.nju.edu.cn/10885/list.htm", "硕士生导师"),
    ]
    
    for url, supervisor_type in urls:
        print(f"\n{'='*70}")
        print(f"Crawling {supervisor_type} from 附属鼓楼医院...")
        print(f"URL: {url}")
        print('='*70)
        
        professors = crawl_all_pages(url, session)
        
        if not professors:
            professors = get_professor_list(url, session)
        
        # Remove duplicates
        seen = set()
        unique_professors = []
        for prof in professors:
            if prof['name'] not in seen:
                seen.add(prof['name'])
                unique_professors.append(prof)
        
        print(f"Found {len(unique_professors)} unique {supervisor_type}")
        
        # Process each professor
        for i, prof in enumerate(unique_professors, 1):
            print(f"Processing {i}/{len(unique_professors)}: {prof['name']}")
            details = get_professor_details(prof['profile_link'], session)
            
            professor_info = {
                'Name': prof['name'],
                'Email': details['email'],
                'Profile Link': prof['profile_link'],
                'Research Direction': details['research_direction'],
                'Department': '附属鼓楼医院',
                'Type': supervisor_type
            }
            all_results.append(professor_info)
            time.sleep(1)
    
    # Save all results
    df = pd.DataFrame(all_results)
    df.to_csv('nju_gulou_hospital_all_professors.csv', index=False, encoding='utf-8-sig')
    print(f"\n{'='*70}")
    print(f"All data saved to nju_gulou_hospital_all_professors.csv")
    print(f"Total professors: {len(df)}")
    
    # Group by type for statistics
    for supervisor_type in df['Type'].unique():
        count = len(df[df['Type'] == supervisor_type])
        print(f"{supervisor_type}: {count}")
    
    return df

if __name__ == "__main__":
    try:
        # Crawl only PhD supervisors
        df = main()
        
        # Uncomment to crawl both PhD and Master supervisors
        # df = crawl_gulou_all()
        
    except Exception as e:
        print(f"\nError occurred: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you have installed: pip install requests beautifulsoup4 pandas urllib3")
        print("2. Check your internet connection")
        print("3. The website might be temporarily down or changed structure")