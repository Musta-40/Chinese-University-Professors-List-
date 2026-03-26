import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin
import re
import urllib3
import ssl

# Disable SSL warnings (not recommended for production, but okay for scraping)
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

def get_professor_list_from_html():
    """Parse professors from the HTML you provided"""
    professors = []
    
    # Based on the HTML structure you provided, let me extract the professors directly
    professor_data = [
        ('蔡平强', 'https://med.nju.edu.cn/cpq/main.htm'),
        ('陈鑫', 'https://med.nju.edu.cn/ca/1f/c10880a772639/page.htm'),
        ('付婷婷', 'https://med.nju.edu.cn/ftt/main.htm'),
        ('方雷', 'https://med.nju.edu.cn/fl1/main.htm'),
        ('郭保生', 'https://med.nju.edu.cn/gbs/main.htm'),
        ('高千', 'https://med.nju.edu.cn/2c/3d/c10880a207933/page.htm'),
        ('何克磊', 'https://med.nju.edu.cn/hkl/main.htm'),
        ('侯亚义', 'https://med.nju.edu.cn/2c/3b/c10880a207931/page.htm'),
        ('洪浩', 'https://med.nju.edu.cn/82/c4/c10880a492228/page.htm'),
        ('胡一桥', 'https://med.nju.edu.cn/hyq/main.htm'),
        ('韩晓冬', 'https://med.nju.edu.cn/ad/4b/c10880a306507/page.htm'),
        ('黄志强', 'https://med.nju.edu.cn/hzq/main.htm'),
        ('黄颖钰', 'https://med.nju.edu.cn/hyy_62080/main.htm'),
        ('金玉', 'https://med.nju.edu.cn/2d/23/c10880a208163/page.htm'),
        ('李冬梅', 'https://med.nju.edu.cn/ldm1/main.htm'),
        ('李宽钰', 'https://med.nju.edu.cn/lky1/main.htm'),
        ('李尔广', 'https://med.nju.edu.cn/2c/39/c10880a207929/page.htm'),
        ('倪海波', 'https://med.nju.edu.cn/nhb2/main.htm'),
        ('吴俊华', 'https://med.nju.edu.cn/wjh/main.htm'),
        ('吴喜林', 'https://med.nju.edu.cn/wxl/main.htm'),
        ('吴稚伟', 'https://med.nju.edu.cn/2c/35/c10880a207925/page.htm'),
        ('吴锦慧', 'https://med.nju.edu.cn/wjh11/main.htm'),
        ('王勇', 'https://med.nju.edu.cn/wy1/main.htm'),
        ('王亚平', 'https://med.nju.edu.cn/ac/de/c10880a306398/page.htm'),
        ('王婷婷', 'https://med.nju.edu.cn/wtt1/main.htm'),
        ('王宏伟', 'https://med.nju.edu.cn/2c/3e/c10880a207934/page.htm'),
        ('魏继武', 'https://med.nju.edu.cn/2c/36/c10880a207926/page.htm'),
        ('薛璐璐', 'https://med.nju.edu.cn/xll/main.htm'),
        ('岳春燕', 'https://med.nju.edu.cn/ca/20/c10880a772640/page.htm'),
        ('杨中州', 'https://med.nju.edu.cn/yzz1/main.htm'),
        ('杨敬平', 'https://med.nju.edu.cn/yjp1/main.psp'),
        ('袁阿虎', 'https://med.nju.edu.cn/yah1/main.htm'),
        ('周游', 'https://med.nju.edu.cn/zy/main.htm'),
        ('朱敏生', 'https://med.nju.edu.cn/82/c2/c10880a492226/page.htm'),
        ('朱昱敏', 'https://med.nju.edu.cn/zym/main.htm'),
        ('赵越', 'https://med.nju.edu.cn/zy2/main.htm'),
    ]
    
    for name, url in professor_data:
        professors.append({
            'name': name,
            'profile_link': url
        })
    
    return professors

def extract_email(text):
    """Extract email from text using regex"""
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    emails = re.findall(email_pattern, text)
    return emails[0] if emails else 'N/A'

def extract_research_direction(soup):
    """Extract research direction from the professor's page"""
    research_keywords = ['研究方向', '研究领域', '研究兴趣', 'Research']
    
    # Try to find research direction in various formats
    for keyword in research_keywords:
        # Look for keyword in text
        for elem in soup.find_all(text=re.compile(keyword)):
            parent = elem.parent
            if parent:
                # Get the text after the keyword
                full_text = parent.get_text(strip=True)
                if keyword in full_text:
                    # Extract text after the keyword
                    parts = full_text.split(keyword)
                    if len(parts) > 1:
                        research = parts[1].strip()
                        # Clean up the text
                        research = research.split('。')[0]  # Get first sentence
                        research = research.replace('：', '').replace(':', '').strip()
                        if research and len(research) < 500:  # Reasonable length
                            return research
    
    # Try to find in table format
    for td in soup.find_all('td'):
        text = td.get_text(strip=True)
        for keyword in research_keywords:
            if keyword in text:
                next_td = td.find_next_sibling('td')
                if next_td:
                    research = next_td.get_text(strip=True)
                    if research and len(research) < 500:
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
    print("Starting to crawl professor information...")
    print("-" * 50)
    
    # Create session with custom SSL settings
    session = create_session()
    
    # Get list of professors from hardcoded data
    print("Using professor list from provided HTML...")
    professors = get_professor_list_from_html()
    
    print(f"Found {len(professors)} professors")
    print("-" * 50)
    
    # Get details for each professor
    results = []
    for i, prof in enumerate(professors, 1):
        print(f"Processing {i}/{len(professors)}: {prof['name']}")
        
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
    output_file = 'nju_medical_professors.csv'
    df.to_csv(output_file, index=False, encoding='utf-8-sig')
    print("-" * 50)
    print(f"Data saved to {output_file}")
    
    # Display sample results
    print("\nSample Results:")
    print("-" * 50)
    for i, result in enumerate(results[:5], 1):
        print(f"\n{i}. Professor: {result['Name']}")
        print(f"   Email: {result['Email']}")
        print(f"   Profile: {result['Profile Link']}")
        research = result['Research Direction']
        if research != 'N/A' and len(research) > 100:
            print(f"   Research: {research[:100]}...")
        else:
            print(f"   Research: {research}")
    
    return df

# Alternative: Using Selenium if requests still fails
def main_with_selenium():
    """Alternative method using Selenium for better SSL handling"""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    
    print("Using Selenium method...")
    
    # Setup Chrome options
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in background
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--ignore-certificate-errors')
    chrome_options.add_argument('--disable-web-security')
    
    # Initialize driver
    driver = webdriver.Chrome(options=chrome_options)
    
    results = []
    professors = get_professor_list_from_html()
    
    for i, prof in enumerate(professors, 1):
        print(f"Processing {i}/{len(professors)}: {prof['name']}")
        
        try:
            driver.get(prof['profile_link'])
            time.sleep(2)  # Wait for page to load
            
            # Get page source
            soup = BeautifulSoup(driver.page_source, 'html.parser')
            page_text = soup.get_text()
            
            # Extract information
            professor_info = {
                'Name': prof['name'],
                'Email': extract_email(page_text),
                'Profile Link': prof['profile_link'],
                'Research Direction': extract_research_direction(soup)
            }
            
            results.append(professor_info)
            
        except Exception as e:
            print(f"Error processing {prof['name']}: {e}")
            results.append({
                'Name': prof['name'],
                'Email': 'N/A',
                'Profile Link': prof['profile_link'],
                'Research Direction': 'N/A'
            })
    
    driver.quit()
    
    # Save results
    df = pd.DataFrame(results)
    df.to_csv('nju_medical_professors_selenium.csv', index=False, encoding='utf-8-sig')
    print(f"Data saved to nju_medical_professors_selenium.csv")
    
    return df

if __name__ == "__main__":
    try:
        # Try the requests method first
        df = main()
    except Exception as e:
        print(f"\nRequests method failed: {e}")
        print("\nTo use Selenium as alternative, install:")
        print("pip install selenium")
        print("And download ChromeDriver from: https://chromedriver.chromium.org/")
        print("\nThen uncomment and run:")
        print("# df = main_with_selenium()")
    
    print(f"\nTotal professors: {len(df) if 'df' in locals() else 0}")