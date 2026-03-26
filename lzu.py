from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from bs4 import BeautifulSoup
import time
import re
import os
from datetime import datetime
from urllib.parse import urlparse

class MultiURLScraper:
    def __init__(self, driver_path=None, headless=True):
        """
        Initialize the web scraper with Selenium WebDriver
        
        Args:
            driver_path: Path to chromedriver executable (optional if in PATH)
            headless: Run browser in headless mode (no GUI)
        """
        self.driver = None
        self.setup_driver(driver_path, headless)
        self.failed_urls = []
        self.successful_urls = []
        
    def setup_driver(self, driver_path, headless):
        """Setup Chrome WebDriver with options"""
        
        chrome_options = Options()
        
        if headless:
            chrome_options.add_argument("--headless")
        
        # Additional options for better performance and compatibility
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # IMPORTANT: Use 'normal' or 'eager' page load strategy for full page load
        chrome_options.page_load_strategy = 'normal'  # Wait for full page load
        
        # Don't disable JavaScript as the site might need it
        # chrome_options.add_argument("--disable-javascript")
        
        # Set user agent
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Initialize WebDriver
        try:
            if driver_path:
                service = Service(driver_path)
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
            else:
                # Try with webdriver-manager
                from webdriver_manager.chrome import ChromeDriverManager
                service = Service(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except:
            # Fallback to system ChromeDriver
            self.driver = webdriver.Chrome(options=chrome_options)
        
        # Set longer timeouts for slow sites
        self.driver.set_page_load_timeout(300)  # 5 minutes timeout
        self.driver.implicitly_wait(60)  # 60 seconds implicit wait
    
    def wait_for_complete_page_load(self, url, timeout=180):
        """
        Comprehensive wait strategy to ensure page is fully loaded
        """
        print(f"  ⏳ Waiting for page to fully load (up to {timeout} seconds)...")
        start_time = time.time()
        
        try:
            # Step 1: Initial page load
            self.driver.get(url)
            
            # Step 2: Wait for document ready state
            WebDriverWait(self.driver, 60).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
            print(f"  ✓ Document ready state: complete")
            
            # Step 3: Wait for body to exist and have content
            body = WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            print(f"  ✓ Body element found")
            
            # Step 4: Wait for specific content indicators (customize based on the site)
            content_found = False
            content_selectors = [
                (By.CLASS_NAME, "col_news_con"),
                (By.CLASS_NAME, "news_list"),
                (By.CLASS_NAME, "list"),
                (By.CLASS_NAME, "content"),
                (By.CLASS_NAME, "main-content"),
                (By.CSS_SELECTOR, "ul.news"),
                (By.CSS_SELECTOR, "div.news"),
                (By.CSS_SELECTOR, ".col_news_list"),
                (By.CSS_SELECTOR, "[class*='news']"),
                (By.CSS_SELECTOR, "[class*='content']"),
                (By.CSS_SELECTOR, "[class*='list']"),
                (By.TAG_NAME, "article"),
                (By.TAG_NAME, "main")
            ]
            
            for selector_type, selector_value in content_selectors:
                try:
                    element = WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((selector_type, selector_value))
                    )
                    if element:
                        print(f"  ✓ Content container found: {selector_value}")
                        content_found = True
                        break
                except:
                    continue
            
            # Step 5: Progressive wait - check if content is still loading
            print(f"  ⏳ Checking if content is still loading...")
            previous_page_source = ""
            stable_count = 0
            max_wait_cycles = 40  # Maximum 20 cycles of 3 seconds each = 60 seconds
            
            for i in range(max_wait_cycles):
                time.sleep(3)  # Wait 3 seconds between checks
                current_page_source = self.driver.page_source
                
                # Check if page content has stabilized
                if len(current_page_source) == len(previous_page_source):
                    stable_count += 1
                    if stable_count >= 3:  # Content stable for 9 seconds
                        print(f"  ✓ Page content stabilized")
                        break
                else:
                    stable_count = 0  # Reset if content changed
                    print(f"  ⏳ Content still loading... ({len(current_page_source)} bytes)")
                
                previous_page_source = current_page_source
                
                # Check if we have enough content
                if len(current_page_source) > 10000:  # At least 10KB of content
                    soup = BeautifulSoup(current_page_source, 'html.parser')
                    text_content = soup.get_text(strip=True)
                    if len(text_content) > 500:  # At least 500 characters of text
                        print(f"  ✓ Sufficient content loaded ({len(text_content)} characters)")
                        break
            
            # Step 6: Wait for AJAX/XHR requests to complete
            try:
                self.driver.execute_script("""
                    var callback = arguments[arguments.length - 1];
                    var xhr_count = 0;
                    var interval = setInterval(function() {
                        if (typeof jQuery !== 'undefined' && jQuery.active == 0) {
                            clearInterval(interval);
                            callback(true);
                        } else if (typeof jQuery === 'undefined') {
                            clearInterval(interval);
                            callback(true);
                        }
                        xhr_count++;
                        if (xhr_count > 20) {  // Maximum 20 seconds wait for AJAX
                            clearInterval(interval);
                            callback(true);
                        }
                    }, 1000);
                """)
                print(f"  ✓ AJAX requests completed")
            except:
                pass  # Site might not use jQuery/AJAX
            
            # Step 7: Final wait to ensure everything is loaded
            time.sleep(5)
            
            # Step 8: Try scrolling to trigger lazy loading
            print(f"  ⏳ Scrolling to load any lazy content...")
            self.scroll_page_slowly()
            
            # Step 9: Final check for content
            final_page_source = self.driver.page_source
            elapsed_time = time.time() - start_time
            
            print(f"  ✅ Page load completed in {elapsed_time:.2f} seconds")
            print(f"  📊 Page size: {len(final_page_source)} bytes")
            
            return True
            
        except TimeoutException as e:
            elapsed_time = time.time() - start_time
            print(f"  ⚠️ Page load timeout after {elapsed_time:.2f} seconds")
            print(f"  ⚠️ Attempting to extract partial content...")
            return False
        except Exception as e:
            print(f"  ❌ Error during page load: {str(e)}")
            return False
    
    def scroll_page_slowly(self):
        """Scroll the page slowly to trigger lazy loading"""
        try:
            # Get page height
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            viewport_height = self.driver.execute_script("return window.innerHeight")
            
            # Scroll in steps
            current_position = 0
            step = viewport_height // 2  # Scroll half viewport at a time
            
            while current_position < total_height:
                # Scroll to next position
                self.driver.execute_script(f"window.scrollTo(0, {current_position});")
                time.sleep(1)  # Wait for content to load
                
                # Update current position
                current_position += step
                
                # Check if page height increased (new content loaded)
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height > total_height:
                    total_height = new_height
            
            # Scroll to bottom
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Scroll back to top
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
        except Exception as e:
            print(f"  ⚠️ Scroll error: {str(e)}")
    
    def read_urls_from_file(self, file_path="urls.txt"):
        """Read URLs from a text file"""
        urls = []
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                for line in f:
                    url = line.strip()
                    # Skip empty lines and comments (lines starting with #)
                    if url and not url.startswith('#'):
                        urls.append(url)
            
            print(f"Found {len(urls)} URLs to scrape")
            return urls
        except FileNotFoundError:
            print(f"Error: File '{file_path}' not found")
            return []
        except Exception as e:
            print(f"Error reading file: {str(e)}")
            return []
    
    def scrape_single_url(self, url, output_file=None, combined_f=None, url_index=None):
        """
        Scrape a single URL with comprehensive wait strategy
        """
        try:
            print(f"  🌐 Navigating to URL...")
            
            # Use the comprehensive wait strategy
            page_loaded = self.wait_for_complete_page_load(url, timeout=180)
            
            if not page_loaded:
                print(f"  ⚠️ Page may not be fully loaded, but attempting to extract available content...")
            
            # Get page source after all waiting is done
            page_source = self.driver.page_source
            
            # Check if we got meaningful content
            if len(page_source) < 1000:
                print(f"  ❌ Insufficient content retrieved ({len(page_source)} bytes)")
                # Try one more time with a refresh
                print(f"  🔄 Attempting page refresh...")
                self.driver.refresh()
                time.sleep(10)
                page_source = self.driver.page_source
                
                if len(page_source) < 1000:
                    print(f"  ❌ Still insufficient content after refresh")
                    return False
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract content
            content = self.extract_content(soup, url, url_index)
            
            # Check if we extracted meaningful content
            if len(content) < 200:
                print(f"  ⚠️ Very little content extracted")
                return False
            
            # Save to individual file
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"  💾 Saved to: {output_file}")
            
            # Add to combined file
            if combined_f:
                combined_f.write("\n\n" + "="*70 + "\n")
                combined_f.write(f"URL #{url_index}: {url}\n")
                combined_f.write("="*70 + "\n")
                combined_f.write(content)
                combined_f.write("\n")
            
            return True
            
        except Exception as e:
            print(f"  ❌ Error scraping: {str(e)}")
            return False
    
    def extract_content(self, soup, url, url_index=None):
        """Extract content from BeautifulSoup object"""
        
        content = []
        
        # Header
        content.append("="*50)
        content.append("WEB SCRAPING RESULTS")
        if url_index:
            content.append(f"URL #{url_index}")
        content.append(f"URL: {url}")
        content.append(f"Scraped at: {datetime.now()}")
        content.append("="*50 + "\n")
        
        # Extract title
        title = soup.find('title')
        if title:
            content.append(f"PAGE TITLE: {title.get_text().strip()}")
            content.append("-"*30 + "\n")
        
        # Extract meta description
        meta_desc = soup.find('meta', attrs={'name': 'description'})
        if meta_desc:
            content.append("META DESCRIPTION:")
            content.append(meta_desc.get('content', 'N/A'))
            content.append("")
        
        # Try to find the main content area more specifically
        content.append("\nMAIN CONTENT AREA:")
        content.append("-"*30)
        
        # Look for news list specifically (based on the website structure)
        main_content_selectors = [
            {'class': 'col_news_con'},
            {'class': 'col_news_list'},
            {'class': 'news_list'},
            {'class': 'wp_news_article_list'},
            {'id': 'newslist'},
            {'class': re.compile('news', re.I)},
            {'class': re.compile('list', re.I)},
            {'class': re.compile('content', re.I)}
        ]
        
        main_content = None
        for selector in main_content_selectors:
            main_content = soup.find(['div', 'ul', 'section', 'main'], selector)
            if main_content:
                print(f"  ✓ Found main content with selector: {selector}")
                break
        
        if main_content:
            # Extract all links and text from the main content
            items = main_content.find_all(['li', 'article', 'div'], recursive=True)
            for idx, item in enumerate(items[:100], 1):  # Limit to 100 items
                link = item.find('a')
                if link:
                    text = link.get_text(strip=True)
                    href = link.get('href', '')
                    if text:
                        content.append(f"{idx}. {text}")
                        if href:
                            content.append(f"   Link: {href}")
                        
                        # Look for date
                        date_elem = item.find(['span', 'time'], class_=re.compile('date|time', re.I))
                        if date_elem:
                            content.append(f"   Date: {date_elem.get_text(strip=True)}")
        else:
            # Fallback: Extract all text
            content.append("Could not find specific content area, extracting all text:")
            all_text = soup.get_text(separator='\n', strip=True)
            lines = [line.strip() for line in all_text.split('\n') if line.strip()]
            content.extend(lines[:500])
        
        # Extract all headings
        content.append("\n\nALL HEADINGS:")
        content.append("-"*30)
        for i in range(1, 7):
            headings = soup.find_all(f'h{i}')
            if headings:
                content.append(f"\nH{i} Tags:")
                for heading in headings[:20]:
                    text = heading.get_text().strip()
                    if text:
                        content.append(f"  • {text}")
        
        # Extract all links
        content.append("\n\nALL LINKS ON PAGE:")
        content.append("-"*30)
        all_links = soup.find_all('a', href=True)
        unique_links = {}
        for link in all_links:
            text = link.get_text(strip=True)
            href = link.get('href', '')
            if text and href and text not in unique_links:
                unique_links[text] = href
        
        for idx, (text, href) in enumerate(list(unique_links.items())[:200], 1):
            content.append(f"{idx}. {text} -> {href}")
        
        return '\n'.join(content)
    
    def scrape_multiple_urls(self, urls_file="urls.txt", output_dir="scraped_data", 
                           combine_output=False, wait_between=5):
        """Scrape multiple URLs from a text file"""
        
        # Create output directory if it doesn't exist
        os.makedirs(output_dir, exist_ok=True)
        
        # Read URLs from file
        urls = self.read_urls_from_file(urls_file)
        
        if not urls:
            print("No URLs to scrape")
            return
        
        # Create combined output file if requested
        if combine_output:
            combined_file = os.path.join(output_dir, f"combined_output_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            combined_f = open(combined_file, 'w', encoding='utf-8')
        
        # Create log file
        log_file = os.path.join(output_dir, f"scraping_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        log_f = open(log_file, 'w', encoding='utf-8')
        log_f.write(f"Scraping started at: {datetime.now()}\n")
        log_f.write(f"Total URLs to scrape: {len(urls)}\n")
        log_f.write("="*50 + "\n\n")
        
        # Scrape each URL
        for i, url in enumerate(urls, 1):
            print(f"\n{'='*60}")
            print(f"[{i}/{len(urls)}] Processing: {url}")
            print(f"{'='*60}")
            log_f.write(f"[{i}/{len(urls)}] URL: {url}\n")
            
            try:
                # Generate output filename based on URL
                parsed_url = urlparse(url)
                safe_filename = re.sub(r'[^\w\s-]', '_', parsed_url.netloc + parsed_url.path)
                safe_filename = re.sub(r'[-\s]+', '-', safe_filename)[:100]
                
                if not combine_output:
                    output_file = os.path.join(output_dir, f"{i:03d}_{safe_filename}.txt")
                else:
                    output_file = None
                
                # Scrape the URL
                success = self.scrape_single_url(url, output_file, combined_f if combine_output else None, i)
                
                if success:
                    self.successful_urls.append(url)
                    log_f.write(f"  Status: SUCCESS\n")
                    print(f"  ✅ Successfully scraped")
                else:
                    self.failed_urls.append(url)
                    log_f.write(f"  Status: FAILED\n")
                    print(f"  ❌ Failed to scrape")
                
                # Wait between requests
                if i < len(urls):
                    print(f"\n  ⏳ Waiting {wait_between} seconds before next request...")
                    time.sleep(wait_between)
                    
            except Exception as e:
                print(f"  ❌ Error: {str(e)}")
                log_f.write(f"  Status: ERROR - {str(e)}\n")
                self.failed_urls.append(url)
            
            log_f.write("\n")
        
        # Close combined output file if used
        if combine_output:
            combined_f.close()
            print(f"\nCombined output saved to: {combined_file}")
        
        # Write summary
        log_f.write("\n" + "="*50 + "\n")
        log_f.write("SCRAPING SUMMARY\n")
        log_f.write("="*50 + "\n")
        log_f.write(f"Completed at: {datetime.now()}\n")
        log_f.write(f"Total URLs: {len(urls)}\n")
        log_f.write(f"Successful: {len(self.successful_urls)}\n")
        log_f.write(f"Failed: {len(self.failed_urls)}\n\n")
        
        if self.failed_urls:
            log_f.write("Failed URLs:\n")
            for url in self.failed_urls:
                log_f.write(f"  - {url}\n")
        
        log_f.close()
        
        # Print summary
        print("\n" + "="*50)
        print("SCRAPING COMPLETED")
        print("="*50)
        print(f"Total URLs: {len(urls)}")
        print(f"Successful: {len(self.successful_urls)}")
        print(f"Failed: {len(self.failed_urls)}")
        print(f"\nLog file: {log_file}")
        
        # Save failed URLs
        if self.failed_urls:
            failed_file = os.path.join(output_dir, "failed_urls.txt")
            with open(failed_file, 'w', encoding='utf-8') as f:
                for url in self.failed_urls:
                    f.write(f"{url}\n")
            print(f"Failed URLs saved to: {failed_file}")
    
    def restart_driver(self):
        """Restart the WebDriver"""
        print("  🔄 Restarting WebDriver...")
        try:
            self.driver.quit()
        except:
            pass
        time.sleep(2)
        self.setup_driver(None, True)
    
    def close(self):
        """Close the WebDriver"""
        if self.driver:
            try:
                self.driver.quit()
                print("✅ WebDriver closed")
            except:
                pass

def main():
    """Main function"""
    
    # Create a sample urls.txt file if it doesn't exist
    if not os.path.exists("urls.txt"):
        print("Creating sample urls.txt file...")
        with open("urls.txt", "w", encoding="utf-8") as f:
            f.write("# Add your URLs here, one per line\n")
            f.write("# Lines starting with # are ignored\n")
            f.write("http://bme.seu.edu.cn/englishweb/7841/list.htm\n")
            f.write("http://bme.seu.edu.cn/englishweb/7840/list.htm\n")
            f.write("http://bme.seu.edu.cn/englishweb/7842/list.htm\n")
        print("Sample urls.txt created. Please add your URLs to this file.")
    
    # Initialize scraper
    print("\n🚀 Initializing Web Scraper...")
    print("📝 Note: This scraper will wait for pages to fully load before extracting content")
    print("⏱️  Each page may take 1-3 minutes for slow-loading sites\n")
    
    # Set headless=False to see what's happening in the browser
    scraper = MultiURLScraper(headless=False)
    
    try:
        # Scrape all URLs from the file
        scraper.scrape_multiple_urls(
            urls_file="urls.txt",           # File containing URLs
            output_dir="scraped_data",      # Output directory
            combine_output=False,            # Set True to combine all results
            wait_between=5                   # Seconds to wait between URLs
        )
        
    except KeyboardInterrupt:
        print("\n\n⚠️ Scraping interrupted by user")
    except Exception as e:
        print(f"\n❌ Error: {str(e)}")
    finally:
        # Always close the driver
        scraper.close()

if __name__ == "__main__":
    # Install required packages:
    # pip install selenium beautifulsoup4 webdriver-manager
    
    main()