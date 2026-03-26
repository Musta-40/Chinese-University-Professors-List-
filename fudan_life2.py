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
    
    def extract_professor_info(self, profile_url, professor_name, department):
        """Extract only required information from professor's profile page"""
        html = self.get_page(profile_url)
        if not html:
            return None
        
        soup = BeautifulSoup(html, 'html.parser')
        
        # Initialize professor data with what we already know
        professor_data = {
            'name': professor_name,
            'department': department,
            'email': '',
            'research_direction': '',
            'profile_link': profile_url
        }
        
        # Look for article content
        content_div = soup.find('div', class_='wp_articlecontent') or soup.find('div', class_='v_news_content')
        
        if content_div:
            content_text = content_div.get_text()
            
            # Extract email (电子邮箱)
            email_patterns = [
                r'电子邮箱[:：]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'[Ee]-?mail[:：]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
                r'邮箱[:：]\s*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            ]
            
            for pattern in email_patterns:
                match = re.search(pattern, content_text)
                if match:
                    professor_data['email'] = match.group(1).strip()
                    break
            
            # If no email found with patterns, try to find any email in the content
            if not professor_data['email']:
                email_general = re.search(r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})', content_text)
                if email_general:
                    professor_data['email'] = email_general.group(1).strip()
            
            # Extract research direction (研究方向)
            research_patterns = [
                r'研究方向[:：]\s*([^\n]+?)(?=\n|$|电子邮箱|个人简介|代表性论文)',
                r'研究领域[:：]\s*([^\n]+?)(?=\n|$|电子邮箱|个人简介|代表性论文)',
                r'主要研究方向[:：]\s*([^\n]+?)(?=\n|$|电子邮箱|个人简介|代表性论文)',
            ]
            
            for pattern in research_patterns:
                match = re.search(pattern, content_text, re.IGNORECASE | re.DOTALL)
                if match:
                    research = match.group(1).strip()
                    # Clean up the research direction text
                    research = re.sub(r'[;；。]$', '', research)
                    # Remove any trailing punctuation
                    research = research.rstrip('.,;；。，')
                    professor_data['research_direction'] = research
                    break
        
        return professor_data
    
    def crawl_department(self, dept_name, dept_url):
        """Crawl all professors in a department"""
        print(f"\nCrawling department: {dept_name}")
        
        page_num = 1
        professors_in_dept = 0
        
        while True:
            # Construct page URL
            if page_num == 1:
                current_url = urljoin(self.base_url, dept_url)
            else:
                current_url = urljoin(self.base_url, dept_url.replace('list.htm', f'list{page_num}.htm'))
            
            print(f"  Page {page_num}...")
            html = self.get_page(current_url)
            if not html:
                break
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # Find professor links
            news_list = soup.find('ul', class_='news_list')
            if not news_list:
                break
            
            professor_links = news_list.find_all('a')
            if not professor_links:
                break
            
            for link in professor_links:
                href = link.get('href')
                if href:
                    profile_url = urljoin(self.base_url, href)
                    professor_name = link.get_text(strip=True)
                    
                    # Extract info from profile page
                    professor_info = self.extract_professor_info(profile_url, professor_name, dept_name)
                    
                    if professor_info:
                        self.professors_data.append(professor_info)
                        professors_in_dept += 1
                        print(f"    ✓ {professor_name}")
                    
                    # Small delay to be polite to the server
                    time.sleep(0.5)
            
            # Check if there's a next page
            paging_div = soup.find('div', id=re.compile(r'wp_paging_w\d+'))
            if paging_div:
                next_link = paging_div.find('a', class_='next')
                if next_link and 'href' in next_link.attrs and 'javascript:void(0)' not in next_link['href']:
                    page_num += 1
                else:
                    break
            else:
                break
        
        print(f"  Found {professors_in_dept} professors in {dept_name}")
    
    def crawl_all(self):
        """Crawl all departments"""
        print("=" * 50)
        print("Starting crawl of Fudan Life Sciences faculty")
        print("=" * 50)
        
        for dept_name, dept_url in self.departments.items():
            self.crawl_department(dept_name, dept_url)
            time.sleep(1)  # Pause between departments
        
        print("\n" + "=" * 50)
        print(f"Crawl complete! Total professors found: {len(self.professors_data)}")
        print("=" * 50)
    
    def save_to_csv(self, filename='fudan_professors.csv'):
        """Save data to CSV file"""
        if self.professors_data:
            df = pd.DataFrame(self.professors_data)
            # Reorder columns for better readability
            df = df[['name', 'department', 'email', 'research_direction', 'profile_link']]
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"\n✓ Data saved to {filename}")
        else:
            print("No data to save")
    
    def save_to_excel(self, filename='fudan_professors.xlsx'):
        """Save data to Excel file"""
        if self.professors_data:
            df = pd.DataFrame(self.professors_data)
            # Reorder columns for better readability
            df = df[['name', 'department', 'email', 'research_direction', 'profile_link']]
            
            # Create Excel writer with formatting
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                df.to_excel(writer, sheet_name='Professors', index=False)
                
                # Auto-adjust columns width
                worksheet = writer.sheets['Professors']
                for column in worksheet.columns:
                    max_length = 0
                    column = [cell for cell in column]
                    for cell in column:
                        try:
                            if len(str(cell.value)) > max_length:
                                max_length = len(str(cell.value))
                        except:
                            pass
                    adjusted_width = min(max_length + 2, 50)
                    worksheet.column_dimensions[column[0].column_letter].width = adjusted_width
            
            print(f"✓ Data saved to {filename}")
        else:
            print("No data to save")
    
    def display_summary(self):
        """Display a summary of the collected data"""
        if self.professors_data:
            df = pd.DataFrame(self.professors_data)
            
            print("\n" + "=" * 50)
            print("SUMMARY")
            print("=" * 50)
            print(f"Total professors: {len(df)}")
            print(f"Professors with email: {df['email'].str.len().gt(0).sum()}")
            print(f"Professors with research direction: {df['research_direction'].str.len().gt(0).sum()}")
            
            print("\nProfessors per department:")
            print("-" * 30)
            dept_counts = df['department'].value_counts()
            for dept, count in dept_counts.items():
                print(f"  {dept}: {count}")
            
            print("\nSample data (first 5 records):")
            print("-" * 30)
            sample_df = df.head()[['name', 'department', 'email']]
            for idx, row in sample_df.iterrows():
                print(f"  {row['name']} | {row['department']} | {row['email'] if row['email'] else 'No email'}")

def main():
    # Create crawler instance
    crawler = FudanLifeScienceCrawler()
    
    try:
        # Crawl all departments
        crawler.crawl_all()
        
        # Save results
        crawler.save_to_csv()
        crawler.save_to_excel()
        
        # Display summary
        crawler.display_summary()
        
    except KeyboardInterrupt:
        print("\n\nCrawling interrupted by user")
        if crawler.professors_data:
            print("Saving collected data...")
            crawler.save_to_csv('fudan_professors_partial.csv')
            crawler.save_to_excel('fudan_professors_partial.xlsx')
            print("Partial data saved")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
        if crawler.professors_data:
            print("Saving collected data...")
            crawler.save_to_csv('fudan_professors_partial.csv')
            crawler.save_to_excel('fudan_professors_partial.xlsx')
            print("Partial data saved")

if __name__ == "__main__":
    main()