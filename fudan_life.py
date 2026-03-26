import requests
from bs4 import BeautifulSoup
import pandas as pd
import time
from urllib.parse import urljoin
import re

class FudanLifeScienceCrawler:
    def __init__(self):
        self.base_url = "https://life.fudan.edu.cn"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.professors_data = []
        
        # Department URLs based on the HTML source
        self.departments = {
            "遗传学与遗传工程系": "/ycxhycgcx_31279/list.htm",
            "生态与进化生物学系": "/styjhswxx/list.htm",
            "生物化学与生物物理学系": "/swhxyswwlxx/list.htm",
            "微生物学与免疫学系": "/wswxhmyxx/list.htm",
            "计算生物学系": "/jsswxx/list.htm",
            "生理学与神经生物学系": "/slxhsjswxx/list.htm",
            "人类遗传学与人类学系": "/rlycxyrlxx/list.htm",
            "细胞与发育生物学系": "/xbhfyswxx/list.htm"
        }
    
    def get_page(self, url):
        """Fetch a page with error handling"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.encoding = 'utf-8'
            return response.text
        except Exception as e:
            print(f"Error fetching {url}: {e}")
            return None
    
    def extract_professor_info(self, profile_url, department):
        """Extract detailed information from professor's profile page"""
        print(f"  Extracting info from: {profile_url}")
        html = self.get_page(profile_url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Initialize professor data
        professor_data = {
            'department': department,
            'name': '',
            'research_area': '',
            'email': '',
            'profile_link': profile_url
        }
        
        # Try to extract name from page title or content
        title_elem = soup.find('h2', class_='arti_title') or soup.find('h1', class_='arti_title')
        if title_elem:
            professor_data['name'] = title_elem.get_text(strip=True)
        
        # Look for article content
        content_div = soup.find('div', class_='wp_articlecontent') or soup.find('div', class_='v_news_content')
        
        if content_div:
            content_text = content_div.get_text()
            
            # Extract name if not found yet
            if not professor_data['name']:
                # Try to find name in the beginning of content
                name_patterns = [
                    r'姓名[:：]\s*([^\n]+)',
                    r'Name[:：]\s*([^\n]+)',
                    r'^([^\n，,]+)[，,]\s*(?:教授|副教授|讲师|研究员)',
                ]
                for pattern in name_patterns:
                    match = re.search(pattern, content_text, re.MULTILINE)
                    if match:
                        professor_data['name'] = match.group(1).strip()
                        break
            
            # Extract email
            email_patterns = [
                r'[Ee]-?mail[:：]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'邮箱[:：]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            ]
            for pattern in email_patterns:
                match = re.search(pattern, content_text)
                if match:
                    professor_data['email'] = match.group(1)
                    break
            
            # Extract research area
            research_patterns = [
                r'研究方向[:：]\s*([^\n]+)',
                r'Research (?:Interests?|Areas?|Focus)[:：]\s*([^\n]+)',
                r'研究领域[:：]\s*([^\n]+)',
                r'主要研究[:：]\s*([^\n]+)'
            ]
            for pattern in research_patterns:
                match = re.search(pattern, content_text, re.IGNORECASE)
                if match:
                    professor_data['research_area'] = match.group(1).strip()
                    # Clean up research area
                    professor_data['research_area'] = re.sub(r'[;；。]$', '', professor_data['research_area'])
                    break
            
            # If research area is too long, try to get first sentence or line
            if len(professor_data['research_area']) > 200:
                sentences = re.split(r'[。；;]', professor_data['research_area'])
                if sentences:
                    professor_data['research_area'] = sentences[0]
        
        # If name still not found, try from URL or page
        if not professor_data['name']:
            # Try to get from the news list title
            news_title = soup.find('title')
            if news_title:
                title_text = news_title.get_text()
                # Remove common suffixes
                professor_data['name'] = re.sub(r'-.*', '', title_text).strip()
        
        return professor_data
    
    def crawl_department(self, dept_name, dept_url):
        """Crawl all professors in a department"""
        print(f"\nCrawling department: {dept_name}")
        
        page_num = 1
        while True:
            # Construct page URL
            if page_num == 1:
                current_url = urljoin(self.base_url, dept_url)
            else:
                # Replace list.htm with list{page_num}.htm
                current_url = urljoin(self.base_url, dept_url.replace('list.htm', f'list{page_num}.htm'))
            
            print(f"  Fetching page {page_num}: {current_url}")
            html = self.get_page(current_url)
            if not html:
                break
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find professor links
            news_list = soup.find('ul', class_='news_list')
            if not news_list:
                print(f"  No news list found on page {page_num}")
                break
            
            professor_links = news_list.find_all('a')
            if not professor_links:
                print(f"  No professor links found on page {page_num}")
                break
            
            for link in professor_links:
                href = link.get('href')
                if href:
                    profile_url = urljoin(self.base_url, href)
                    
                    # Get basic info from list page
                    professor_name = link.get_text(strip=True)
                    
                    # Extract detailed info from profile page
                    professor_info = self.extract_professor_info(profile_url, dept_name)
                    
                    if professor_info:
                        # Use the name from list if profile extraction didn't find one
                        if not professor_info['name']:
                            professor_info['name'] = professor_name
                        
                        self.professors_data.append(professor_info)
                        print(f"    Added: {professor_info['name']}")
                    
                    # Be polite to the server
                    time.sleep(1)
            
            # Check if there's a next page
            paging_div = soup.find('div', id=re.compile(r'wp_paging_w\d+'))
            if paging_div:
                next_link = paging_div.find('a', class_='next')
                if next_link and 'href' in next_link.attrs and 'javascript:void(0)' not in next_link['href']:
                    page_num += 1
                else:
                    print(f"  No more pages in {dept_name}")
                    break
            else:
                break
    
    def crawl_all(self):
        """Crawl all departments"""
        print("Starting crawl of Fudan Life Sciences faculty...")
        
        for dept_name, dept_url in self.departments.items():
            self.crawl_department(dept_name, dept_url)
            time.sleep(2)  # Pause between departments
        
        print(f"\nCrawl complete! Found {len(self.professors_data)} professors")
    
    def save_to_csv(self, filename='fudan_life_sciences_faculty.csv'):
        """Save data to CSV file"""
        if self.professors_data:
            df = pd.DataFrame(self.professors_data)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"Data saved to {filename}")
        else:
            print("No data to save")
    
    def save_to_excel(self, filename='fudan_life_sciences_faculty.xlsx'):
        """Save data to Excel file"""
        if self.professors_data:
            df = pd.DataFrame(self.professors_data)
            df.to_excel(filename, index=False, engine='openpyxl')
            print(f"Data saved to {filename}")
        else:
            print("No data to save")

def main():
    # Create crawler instance
    crawler = FudanLifeScienceCrawler()
    
    # Crawl all departments
    crawler.crawl_all()
    
    # Save results
    crawler.save_to_csv()
    crawler.save_to_excel()
    
    # Display summary
    if crawler.professors_data:
        df = pd.DataFrame(crawler.professors_data)
        print("\n=== Summary ===")
        print(f"Total professors: {len(df)}")
        print("\nProfessors per department:")
        print(df['department'].value_counts())
        
        # Show sample data
        print("\n=== Sample Data (first 5 records) ===")
        print(df.head())

if __name__ == "__main__":
    main()