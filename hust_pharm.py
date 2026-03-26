from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import re
import os

class FacultyProfileScraper:
    def __init__(self):
        self.driver = self.setup_driver()
        self.faculty_data = []
        
    def setup_driver(self):
        """Setup Chrome driver"""
        options = webdriver.ChromeOptions()
        options.add_argument('--log-level=3')
        options.add_experimental_option('excludeSwitches', ['enable-logging'])
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        # Uncomment for headless
        # options.add_argument('--headless')
        
        return webdriver.Chrome(options=options)
    
    def extract_email(self, page_text):
        """Extract email from page text"""
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, page_text)
        
        for email in emails:
            if '@' in email and not any(x in email.lower() for x in ['example', 'test', 'email']):
                return email
        return "Not found"
    
    def extract_research_focus(self, driver):
        """Extract research focus with multiple strategies"""
        research_text = ""
        
        # Strategy 1: Look for common research section patterns in Chinese pages
        research_selectors = [
            # Common class names and IDs for research sections
            "div.research-field",
            "div.research-direction", 
            "div.research-interest",
            "div.research_field",
            "div.field",
            "div[class*='research']",
            "div[class*='direction']",
            
            # Table cells that might contain research info
            "td:has(> strong:contains('研究方向'))",
            "td:has(> b:contains('研究方向'))",
            
            # Divs with specific text
            "div:contains('研究方向')",
            "div:contains('研究领域')",
            "div:contains('研究兴趣')",
            "div:contains('主要研究方向')",
        ]
        
        # Try CSS selectors first
        for selector in research_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for elem in elements:
                    text = elem.text.strip()
                    if text and len(text) > 20:
                        research_text = text
                        break
                if research_text:
                    break
            except:
                continue
        
        # Strategy 2: Look for research keywords and get the content after them
        if not research_text:
            research_keywords = [
                '研究方向', '研究领域', '研究兴趣', '主要研究方向', 
                'Research Direction', 'Research Field', 'Research Interest',
                'Research Focus', 'Research Areas', '科研方向'
            ]
            
            page_text = driver.find_element(By.TAG_NAME, "body").text
            
            for keyword in research_keywords:
                if keyword in page_text:
                    # Split by keyword and get the content after it
                    parts = page_text.split(keyword)
                    if len(parts) > 1:
                        # Get the text after the keyword
                        after_text = parts[1]
                        
                        # Clean and extract meaningful content
                        # Stop at next section keywords
                        stop_keywords = [
                            '教育经历', '工作经历', '代表性论文', '科研项目',
                            '获奖情况', '联系方式', '个人简介', '教学',
                            'Education', 'Work Experience', 'Publications',
                            'Awards', 'Contact', 'Teaching', '主讲课程'
                        ]
                        
                        for stop_word in stop_keywords:
                            if stop_word in after_text:
                                after_text = after_text.split(stop_word)[0]
                        
                        # Get first 500 characters or until line breaks
                        lines = after_text.strip().split('\n')
                        research_lines = []
                        
                        for line in lines[:10]:  # Get up to 10 lines
                            line = line.strip()
                            if line and not any(stop in line for stop in stop_keywords):
                                research_lines.append(line)
                            if len(' '.join(research_lines)) > 500:
                                break
                        
                        research_text = ' '.join(research_lines)
                        if research_text:
                            break
        
        # Strategy 3: Try XPath for more complex structures
        if not research_text:
            xpath_patterns = [
                "//strong[contains(text(),'研究方向')]/following-sibling::text()",
                "//b[contains(text(),'研究方向')]/following-sibling::text()",
                "//span[contains(text(),'研究方向')]/following-sibling::*",
                "//div[contains(text(),'研究方向')]/following-sibling::*",
                "//p[contains(text(),'研究方向')]/following-sibling::*",
                "//td[contains(text(),'研究方向')]/following-sibling::td",
                "//*[contains(text(),'研究方向')]/parent::*/following-sibling::*[1]",
            ]
            
            for xpath in xpath_patterns:
                try:
                    elements = driver.find_elements(By.XPATH, xpath)
                    for elem in elements[:3]:
                        text = elem.text.strip() if hasattr(elem, 'text') else str(elem).strip()
                        if text and len(text) > 10:
                            research_text += " " + text
                    if research_text:
                        break
                except:
                    continue
        
        # Strategy 4: If still no research found, try personal profile
        if not research_text:
            profile_keywords = ['个人简介', '简介', '个人介绍', 'Personal Profile', 'Biography']
            
            for keyword in profile_keywords:
                if keyword in page_text:
                    parts = page_text.split(keyword)
                    if len(parts) > 1:
                        # Get first 500 characters after the keyword
                        profile_text = parts[1][:500].strip()
                        if profile_text:
                            research_text = f"[From Personal Profile] {profile_text}"
                            break
        
        # Clean up the extracted text
        if research_text:
            # Remove the keyword itself if it's at the beginning
            for keyword in ['研究方向', '研究领域', '研究兴趣']:
                if research_text.startswith(keyword):
                    research_text = research_text[len(keyword):].strip()
                    if research_text.startswith(':') or research_text.startswith('：'):
                        research_text = research_text[1:].strip()
            
            # Remove excessive whitespace
            research_text = ' '.join(research_text.split())
            
            # Limit length
            if len(research_text) > 1000:
                research_text = research_text[:1000] + "..."
        
        return research_text if research_text else "Not found"
    
    def scrape_faculty_page(self, url, name):
        """Scrape individual faculty page"""
        print(f"\nScraping: {name}")
        print(f"URL: {url}")
        
        faculty_info = {
            'name': name,
            'url': url,
            'email': 'Not found',
            'research': 'Not found'
        }
        
        try:
            self.driver.get(url)
            # Wait for page to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(2)  # Additional wait for dynamic content
            
            # Get page text for email extraction
            page_text = self.driver.find_element(By.TAG_NAME, "body").text
            
            # Extract email
            faculty_info['email'] = self.extract_email(page_text)
            
            # Extract research focus
            faculty_info['research'] = self.extract_research_focus(self.driver)
            
            print(f"  Email: {faculty_info['email']}")
            print(f"  Research: {faculty_info['research'][:100]}..." if faculty_info['research'] != 'Not found' else "  Research: Not found")
            
        except Exception as e:
            print(f"  Error: {str(e)}")
        
        return faculty_info
    
    def save_to_txt(self, filename='faculty_data.txt'):
        """Save data to text file"""
        with open(filename, 'w', encoding='utf-8') as f:
            f.write("="*80 + "\n")
            f.write("HUST FACULTY INFORMATION\n")
            f.write("="*80 + "\n\n")
            
            # Statistics
            total = len(self.faculty_data)
            with_email = sum(1 for f in self.faculty_data if f['email'] != 'Not found')
            with_research = sum(1 for f in self.faculty_data if f['research'] != 'Not found')
            
            f.write(f"Total Faculty: {total}\n")
            f.write(f"With Email: {with_email}\n")
            f.write(f"With Research Info: {with_research}\n")
            f.write("="*80 + "\n\n")
            
            # Individual faculty data
            for i, faculty in enumerate(self.faculty_data, 1):
                f.write(f"#{i}. {faculty['name']}\n")
                f.write("-"*40 + "\n")
                f.write(f"Profile URL: {faculty['url']}\n")
                f.write(f"Email: {faculty['email']}\n")
                f.write(f"\nResearch Focus/Direction:\n")
                f.write(f"{faculty['research']}\n")
                f.write("\n" + "="*80 + "\n\n")
    
    def run(self):
        """Main execution"""
        faculty_list = [
            ("Gan Lu", "http://faculty.hust.edu.cn/ganlu7/zh_CN/index.htm"),
            ("Hu Jun", "http://faculty.hust.edu.cn/hujun0718/zh_CN/index.htm"),
            ("Li Wei", "http://faculty.hust.edu.cn/LIWEI/zh_CN/index.htm"),
            ("Li Zifu", "http://faculty.hust.edu.cn/lizifu/zh_CN/index.htm"),
            ("Liu Wei", "http://faculty.hust.edu.cn/liuwei17/zh_CN/index.htm"),
            ("Luo Liang", "http://faculty.hust.edu.cn/liangluo/zh_CN/index.htm"),
            ("Luo Zhiqiang", "http://faculty.hust.edu.cn/luozhiqiang/zh_CN/index.htm"),
            ("Wang Chenhui", "http://faculty.hust.edu.cn/wangchenhui/zh_CN/index.htm"),
            ("Yang Xiangliang", "http://faculty.hust.edu.cn/yangxiangliang/zh_CN/index.htm"),
            ("Zhang Chun", "http://faculty.hust.edu.cn/zhangchun2/zh_CN/index.htm"),
            ("Zhang Peijing", "http://faculty.hust.edu.cn/zhangpeijing/zh_CN/index.htm"),
            ("Zhang Yan", "http://faculty.hust.edu.cn/zhangyan11/zh_CN/index.htm"),
            ("Zhao Yanbing", "http://faculty.hust.edu.cn/zhaoyanbing/zh_CN/index.htm"),
            ("Zhu Yanhong", "http://faculty.hust.edu.cn/zhuyanhong/zh_CN/index.htm"),
            ("Du Qing", "http://faculty.hust.edu.cn/duqing1/zh_CN/index.htm"),
            ("Jiang Xinnong", "http://faculty.hust.edu.cn/jiangxinnong/zh_CN/index.htm"),
            ("Meng Fanling", "http://faculty.hust.edu.cn/mengfanling/zh_CN/index.htm"),
            ("Weng Jun", "http://faculty.hust.edu.cn/wengjun1/zh_CN/index.htm"),
            ("Yang Hai", "http://faculty.hust.edu.cn/yanghai/zh_CN/index.htm"),
            ("Yong Tuying", "http://faculty.hust.edu.cn/yongtuying1/zh_CN/index.htm"),
            ("Tian Sidan", "http://faculty.hust.edu.cn/tiansidan1/zh_CN/index.htm"),
            ("Faculty Member", "http://life.hust.edu.cn/info/1072/4785.htm")
        ]
        
        print("Starting faculty scraping...")
        print(f"Total to scrape: {len(faculty_list)}")
        print("="*50)
        
        for name, url in faculty_list:
            faculty_info = self.scrape_faculty_page(url, name)
            self.faculty_data.append(faculty_info)
            time.sleep(2)  # Rate limiting
        
        # Save results
        self.save_to_txt('faculty_data.txt')
        
        print("\n" + "="*50)
        print("Scraping completed!")
        print(f"Results saved to: faculty_data.txt")
        
        # Print summary
        total = len(self.faculty_data)
        with_email = sum(1 for f in self.faculty_data if f['email'] != 'Not found')
        with_research = sum(1 for f in self.faculty_data if f['research'] != 'Not found')
        
        print(f"\nSummary:")
        print(f"  Total scraped: {total}")
        print(f"  With email: {with_email}")
        print(f"  With research: {with_research}")
        
        self.driver.quit()

# Alternative approach using more specific element inspection
def alternative_scraper():
    """Alternative scraping approach with debug mode"""
    
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    import time
    import re
    
    options = webdriver.ChromeOptions()
    options.add_argument('--log-level=3')
    options.add_experimental_option('excludeSwitches', ['enable-logging'])
    driver = webdriver.Chrome(options=options)
    
    # Test with one URL first
    test_url = "http://faculty.hust.edu.cn/ganlu7/zh_CN/index.htm"
    
    driver.get(test_url)
    time.sleep(3)
    
    print("\n=== DEBUG MODE ===")
    print(f"Testing URL: {test_url}\n")
    
    # Try to find all text containing research keywords
    body = driver.find_element(By.TAG_NAME, "body")
    page_text = body.text
    
    # Look for research sections
    print("Looking for research sections...")
    research_keywords = ['研究方向', '研究领域', '研究兴趣', '主要研究']
    
    for keyword in research_keywords:
        if keyword in page_text:
            print(f"\nFound keyword: {keyword}")
            index = page_text.find(keyword)
            # Get 500 characters after the keyword
            context = page_text[index:index+500]
            print(f"Context: {context[:200]}...")
    
    # Try to find by common HTML structures
    print("\n\nTrying different selectors:")
    
    test_selectors = [
        ("Table cells with research", "td"),
        ("Divs with class", "div[class*='col']"),
        ("Paragraphs", "p"),
        ("List items", "li")
    ]
    
    for desc, selector in test_selectors:
        elements = driver.find_elements(By.CSS_SELECTOR, selector)
        for elem in elements:
            text = elem.text.strip()
            if any(kw in text for kw in research_keywords):
                print(f"\n{desc}: Found research content")
                print(f"Text: {text[:200]}...")
                break
    
    driver.quit()
    print("\n=== END DEBUG ===\n")

def main():
    print("HUST Faculty Information Scraper")
    print("="*50)
    
    # Uncomment to run debug mode first
    # alternative_scraper()
    
    # Run main scraper
    scraper = FacultyProfileScraper()
    scraper.run()

if __name__ == "__main__":
    main()