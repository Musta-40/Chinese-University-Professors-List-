import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import re

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

def extract_email_from_text(text):
    """Extract email from text using regex"""
    email_pattern = r'[\w\.-]+@[\w\.-]+\.[\w]+'
    match = re.search(email_pattern, text)
    return match.group() if match else ""

def crawl_professor_details(driver, profile_url):
    """Visit individual professor page to extract email and research field"""
    professor_details = {
        "email": "",
        "research_field": ""
    }
    
    try:
        # Open in new tab
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        driver.get(profile_url)
        time.sleep(2)
        
        # Try to find the main content area
        try:
            # Look for content in various possible containers
            content_selectors = [
                "wp-column-news-text",
                "col_news_con",
                "news_content",
                "article-content",
                "content"
            ]
            
            page_text = ""
            for selector in content_selectors:
                try:
                    element = driver.find_element(By.CLASS_NAME, selector)
                    page_text = element.text
                    if page_text:
                        break
                except:
                    continue
            
            # If no specific content area found, get entire body text
            if not page_text:
                page_text = driver.find_element(By.TAG_NAME, "body").text
            
            # Extract email
            professor_details["email"] = extract_email_from_text(page_text)
            
            # Extract research field/direction
            # Look for common patterns in English pages
            research_patterns = [
                r'Research (?:Field|Direction|Interest|Area)[s]?[：:]\s*(.*?)(?:\n|$)',
                r'Research[：:]\s*(.*?)(?:\n|$)',
                r'Field[s]? of Research[：:]\s*(.*?)(?:\n|$)',
                r'Research Focus[：:]\s*(.*?)(?:\n|$)'
            ]
            
            for pattern in research_patterns:
                match = re.search(pattern, page_text, re.IGNORECASE)
                if match:
                    professor_details["research_field"] = match.group(1).strip()
                    break
            
            # If no pattern match, look for section headers
            if not professor_details["research_field"]:
                lines = page_text.split('\n')
                for i, line in enumerate(lines):
                    if any(keyword in line.lower() for keyword in ['research field', 'research direction', 
                                                                    'research interest', 'research area', 
                                                                    'research focus']):
                        # Get the next non-empty line
                        for j in range(i+1, min(i+5, len(lines))):
                            if lines[j].strip():
                                professor_details["research_field"] = lines[j].strip()
                                break
                        break
        
        except Exception as e:
            print(f"Error extracting details from professor page: {e}")
        
    except Exception as e:
        print(f"Error accessing professor page {profile_url}: {e}")
    
    finally:
        # Close tab and switch back
        driver.close()
        driver.switch_to.window(driver.window_handles[0])
    
    return professor_details

def crawl_nju_life_faculty_english():
    """Main function to crawl the English faculty page"""
    driver = setup_driver()
    professors_data = []
    
    try:
        url = "https://life.nju.edu.cn/lifeen/13591/list.htm"
        print(f"Navigating to: {url}")
        driver.get(url)
        
        # Wait for dynamic content to load
        print("Waiting for page to load...")
        time.sleep(5)
        
        # Try to find faculty list - check multiple possible selectors
        faculty_found = False
        
        # Method 1: Look for news list items
        try:
            # Wait for the dynamic content to load
            wait = WebDriverWait(driver, 10)
            
            # Check if there's a faculty list in the fws_search area
            search_area = driver.find_element(By.CLASS_NAME, "fws_search")
            
            # Look for list items with faculty information
            faculty_items = search_area.find_elements(By.TAG_NAME, "li")
            
            if not faculty_items:
                # Try finding links directly
                faculty_items = search_area.find_elements(By.TAG_NAME, "a")
            
            print(f"Found {len(faculty_items)} potential faculty items")
            
            for item in faculty_items:
                try:
                    professor_info = {
                        "name": "",
                        "email": "",
                        "research_field": "",
                        "profile_link": ""
                    }
                    
                    # Try to extract link and name
                    link_element = None
                    
                    if item.tag_name == "a":
                        link_element = item
                    else:
                        # If it's a list item, find the link within
                        try:
                            link_element = item.find_element(By.TAG_NAME, "a")
                        except:
                            # Skip if no link found
                            continue
                    
                    if link_element:
                        # Extract name
                        name_text = link_element.text.strip()
                        if name_text and not name_text.isdigit():  # Filter out page numbers
                            professor_info["name"] = name_text
                        else:
                            continue
                        
                        # Extract profile link
                        profile_link = link_element.get_attribute("href")
                        if profile_link:
                            if not profile_link.startswith("http"):
                                profile_link = "https://life.nju.edu.cn" + profile_link
                            professor_info["profile_link"] = profile_link
                        
                        print(f"Processing: {professor_info['name']}")
                        
                        # Visit individual page for more details
                        if professor_info["profile_link"] and "javascript" not in professor_info["profile_link"].lower():
                            details = crawl_professor_details(driver, professor_info["profile_link"])
                            professor_info["email"] = details["email"]
                            professor_info["research_field"] = details["research_field"]
                            time.sleep(1)  # Be respectful to the server
                        
                        # Only add if we have a valid name
                        if professor_info["name"]:
                            professors_data.append(professor_info)
                            faculty_found = True
                
                except Exception as e:
                    print(f"Error processing faculty item: {e}")
                    continue
        
        except Exception as e:
            print(f"Error finding faculty list with method 1: {e}")
        
        # Method 2: Check if there's pagination or different layout
        if not faculty_found:
            print("Trying alternative extraction method...")
            
            # Look for any links that might be faculty profiles
            all_links = driver.find_elements(By.CSS_SELECTOR, "a[href*='/lifeen/']")
            
            for link in all_links:
                try:
                    link_text = link.text.strip()
                    link_href = link.get_attribute("href")
                    
                    # Filter for likely faculty names (avoid navigation links, etc.)
                    if (link_text and 
                        len(link_text) > 3 and 
                        not any(skip in link_text.upper() for skip in ['HOME', 'ABOUT', 'FACULTY', 'RESEARCH', 
                                                                        'EVENTS', 'JOIN', '中文版', 'NEXT', 
                                                                        'PREVIOUS', 'PAGE']) and
                        '/lifeen/' in link_href and
                        '.htm' in link_href):
                        
                        professor_info = {
                            "name": link_text,
                            "email": "",
                            "research_field": "",
                            "profile_link": link_href if link_href.startswith("http") else "https://life.nju.edu.cn" + link_href
                        }
                        
                        print(f"Found potential faculty: {professor_info['name']}")
                        
                        # Visit page for details
                        if "javascript" not in professor_info["profile_link"].lower():
                            details = crawl_professor_details(driver, professor_info["profile_link"])
                            professor_info["email"] = details["email"]
                            professor_info["research_field"] = details["research_field"]
                            time.sleep(1)
                        
                        professors_data.append(professor_info)
                        faculty_found = True
                
                except Exception as e:
                    continue
        
        # Check for pagination
        try:
            # Look for page navigation
            page_nav = driver.find_elements(By.CSS_SELECTOR, ".news_pages a, .pagination a, .wp-paging a")
            if page_nav:
                print(f"Found pagination with {len(page_nav)} pages")
                # You would need to iterate through pages here
                # This is a simplified version - you'd need to handle page navigation properly
        except:
            pass
        
        if not faculty_found:
            print("Warning: No faculty data found. The page structure might have changed.")
            print("Attempting to capture page structure for debugging...")
            
            # Debug: Print page structure
            try:
                page_source = driver.page_source
                if "Professor" in page_source or "Dr." in page_source:
                    print("Faculty mentions found in page source, but couldn't extract structured data")
                else:
                    print("No obvious faculty data in page source")
            except:
                pass
    
    except Exception as e:
        print(f"Error during crawling: {e}")
    
    finally:
        driver.quit()
    
    return professors_data

def save_to_csv(professors_data, filename="nju_life_faculty_english.csv"):
    """Save the collected data to a CSV file"""
    if professors_data:
        df = pd.DataFrame(professors_data)
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"\nData saved to {filename}")
        print(f"Total professors collected: {len(professors_data)}")
        return df
    else:
        print("No data collected")
        return None

def save_to_excel(professors_data, filename="nju_life_faculty_english.xlsx"):
    """Save the collected data to an Excel file"""
    if professors_data:
        df = pd.DataFrame(professors_data)
        df.to_excel(filename, index=False, engine='openpyxl')
        print(f"Data also saved to {filename}")
        return df
    return None

def main():
    print("="*60)
    print("NJU Life Sciences Faculty Crawler (English Version)")
    print("="*60)
    print("\nStarting crawl...")
    print("Note: This will take some time as it visits individual faculty pages")
    print("-"*60)
    
    # Install required packages reminder
    print("\nMake sure you have installed required packages:")
    print("pip install selenium pandas webdriver-manager openpyxl")
    print("-"*60)
    
    # Crawl the website
    professors_data = crawl_nju_life_faculty_english()
    
    # Save to both CSV and Excel
    df = save_to_csv(professors_data)
    save_to_excel(professors_data)
    
    # Display results
    if df is not None:
        print("\n" + "="*60)
        print("CRAWLING COMPLETED")
        print("="*60)
        
        print("\nSample of collected data:")
        print("-"*60)
        print(df.head(10).to_string())
        
        print("\n" + "-"*60)
        print("Statistics:")
        print(f"Total professors collected: {len(df)}")
        
        # Show some basic statistics
        if len(df) > 0:
            print(f"Professors with email addresses: {df['email'].str.len().gt(0).sum()}")
            print(f"Professors with research fields: {df['research_field'].str.len().gt(0).sum()}")
            print(f"Professors with profile links: {df['profile_link'].str.len().gt(0).sum()}")
    else:
        print("\n" + "="*60)
        print("NO DATA COLLECTED")
        print("="*60)
        print("Possible reasons:")
        print("1. The website structure might have changed")
        print("2. The content might be loaded differently")
        print("3. Network connection issues")
        print("\nPlease check the website manually and adjust the script if needed")

if __name__ == "__main__":
    main()