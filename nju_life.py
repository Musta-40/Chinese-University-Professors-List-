import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException
import re

def crawl_professor_page(driver, url):
    """Extract research direction from individual professor page"""
    try:
        driver.get(url)
        time.sleep(2)
        
        research_direction = ""
        try:
            content = driver.find_element(By.CLASS_NAME, "wp-column-news-text").text
            pattern = r'研究方向[：:]\s*(.*?)(?:\n|$)'
            match = re.search(pattern, content)
            if match:
                research_direction = match.group(1).strip()
            else:
                if '研究方向' in content:
                    lines = content.split('\n')
                    for i, line in enumerate(lines):
                        if '研究方向' in line:
                            if '：' in line or ':' in line:
                                research_direction = line.split('：')[-1].split(':')[-1].strip()
                            elif i + 1 < len(lines):
                                research_direction = lines[i + 1].strip()
                            break
        except:
            pass
            
        return research_direction
    except Exception as e:
        print(f"Error crawling professor page {url}: {e}")
        return ""

def setup_driver():
    """Setup Chrome driver with automatic ChromeDriver management"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')  # Run in background
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--window-size=1920,1080')
    
    # Automatically download and setup ChromeDriver
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def crawl_nju_life_faculty():
    """Main crawling function"""
    driver = setup_driver()
    professors_data = []
    
    try:
        url = "https://life.nju.edu.cn/szdw/list.htm"
        driver.get(url)
        
        print("Waiting for page to load...")
        time.sleep(5)
        
        categories = [
            ("教学科研", "career_1"),
            ("专职科研", "career_2"),
            ("跨学科博导", "career_3")
        ]
        
        for category_name, career_class in categories:
            print(f"\nProcessing category: {category_name}")
            
            try:
                faculty_list = driver.find_element(By.CLASS_NAME, career_class)
                professor_items = faculty_list.find_elements(By.TAG_NAME, "li")
                
                print(f"Found {len(professor_items)} professors in {category_name}")
                
                for item in professor_items:
                    try:
                        professor_info = {
                            "category": category_name,
                            "name": "",
                            "department": "",
                            "email": "",
                            "profile_link": "",
                            "research_direction": ""
                        }
                        
                        link_element = item.find_element(By.TAG_NAME, "a")
                        professor_info["name"] = link_element.text.strip()
                        
                        profile_link = link_element.get_attribute("href")
                        if profile_link:
                            if not profile_link.startswith("http"):
                                profile_link = "https://life.nju.edu.cn" + profile_link
                            professor_info["profile_link"] = profile_link
                        
                        print(f"Processing: {professor_info['name']}")
                        
                        if professor_info["profile_link"]:
                            driver.execute_script("window.open('');")
                            driver.switch_to.window(driver.window_handles[-1])
                            
                            research_direction = crawl_professor_page(driver, professor_info["profile_link"])
                            professor_info["research_direction"] = research_direction
                            
                            try:
                                page_text = driver.find_element(By.TAG_NAME, "body").text
                                email_match = re.search(r'[\w\.-]+@[\w\.-]+\.[\w]+', page_text)
                                if email_match:
                                    professor_info["email"] = email_match.group()
                            except:
                                pass
                            
                            driver.close()
                            driver.switch_to.window(driver.window_handles[0])
                            time.sleep(1)
                        
                        professors_data.append(professor_info)
                        
                    except Exception as e:
                        print(f"Error processing professor: {e}")
                        continue
                        
            except NoSuchElementException:
                print(f"Category {category_name} not found")
                continue
                
    except Exception as e:
        print(f"Error during crawling: {e}")
    finally:
        driver.quit()
    
    return professors_data

def save_to_csv(professors_data, filename="nju_life_faculty.csv"):
    """Save data to CSV file"""
    if professors_data:
        df = pd.DataFrame(professors_data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"\nData saved to {filename}")
        print(f"Total professors collected: {len(professors_data)}")
        return df
    else:
        print("No data collected")
        return None

def main():
    print("Starting NJU Life Sciences Faculty crawling...")
    print("ChromeDriver will be automatically downloaded if needed...")
    
    professors_data = crawl_nju_life_faculty()
    df = save_to_csv(professors_data)
    
    if df is not None:
        print("\nSample of collected data:")
        print(df.head())
        print("\nStatistics:")
        print(f"Total professors: {len(df)}")
        print(f"Professors by category:")
        print(df['category'].value_counts())

if __name__ == "__main__":
    main()