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
        
        # Additional options
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Set user agent
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
        
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
        
        self.driver.implicitly_wait(10)
    
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
    
    def scrape_multiple_urls(self, urls_file="urls.txt", output_dir="scraped_data", 
                           combine_output=False, wait_between=2):
        """
        Scrape multiple URLs from a text file
        
        Args:
            urls_file: Path to text file containing URLs
            output_dir: Directory to save scraped data
            combine_output: If True, combine all results in one file
            wait_between: Seconds to wait between scraping each URL
        """
        
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
            print(f"\n[{i}/{len(urls)}] Scraping: {url}")
            log_f.write(f"[{i}/{len(urls)}] URL: {url}\n")
            
            try:
                # Generate output filename based on URL
                parsed_url = urlparse(url)
                safe_filename = re.sub(r'[^\w\s-]', '_', parsed_url.netloc + parsed_url.path)
                safe_filename = re.sub(r'[-\s]+', '-', safe_filename)[:100]  # Limit filename length
                
                if not combine_output:
                    output_file = os.path.join(output_dir, f"{i:03d}_{safe_filename}.txt")
                else:
                    output_file = None
                
                # Scrape the URL
                success = self.scrape_single_url(url, output_file, combined_f if combine_output else None, i)
                
                if success:
                    self.successful_urls.append(url)
                    log_f.write(f"  Status: SUCCESS\n")
                    print(f"  ✓ Successfully scraped")
                else:
                    self.failed_urls.append(url)
                    log_f.write(f"  Status: FAILED\n")
                    print(f"  ✗ Failed to scrape")
                
                # Wait between requests to avoid being blocked
                if i < len(urls):
                    print(f"  Waiting {wait_between} seconds before next request...")
                    time.sleep(wait_between)
                    
            except Exception as e:
                print(f"  ✗ Error: {str(e)}")
                log_f.write(f"  Status: ERROR - {str(e)}\n")
                self.failed_urls.append(url)
                
                # Try to recover by restarting the driver
                try:
                    self.restart_driver()
                except:
                    pass
            
            log_f.write("\n")
        
        # Close combined output file if used
        if combine_output:
            combined_f.close()
            print(f"\nCombined output saved to: {combined_file}")
        
        # Write summary to log
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
        
        # Save failed URLs to a separate file for retry
        if self.failed_urls:
            failed_file = os.path.join(output_dir, "failed_urls.txt")
            with open(failed_file, 'w', encoding='utf-8') as f:
                for url in self.failed_urls:
                    f.write(f"{url}\n")
            print(f"Failed URLs saved to: {failed_file}")
    
    def scrape_single_url(self, url, output_file=None, combined_f=None, url_index=None):
        """
        Scrape a single URL
        
        Args:
            url: URL to scrape
            output_file: Individual output file path
            combined_f: Combined output file handle (if combining results)
            url_index: Index of the URL (for labeling)
        
        Returns:
            Boolean indicating success
        """
        try:
            # Load the URL
            self.driver.get(url)
            
            # Wait for page to load
            WebDriverWait(self.driver, 20).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Additional wait for dynamic content
            time.sleep(2)
            
            # Try to scroll for lazy-loaded content
            self.scroll_page()
            
            # Get page source
            page_source = self.driver.page_source
            soup = BeautifulSoup(page_source, 'html.parser')
            
            # Extract content
            content = self.extract_content(soup, url, url_index)
            
            # Save to individual file
            if output_file:
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            # Add to combined file
            if combined_f:
                combined_f.write("\n\n" + "="*70 + "\n")
                combined_f.write(f"URL #{url_index}: {url}\n")
                combined_f.write("="*70 + "\n")
                combined_f.write(content)
                combined_f.write("\n")
            
            return True
            
        except TimeoutException:
            print(f"  Timeout loading: {url}")
            return False
        except Exception as e:
            print(f"  Error scraping: {str(e)}")
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
        
        # Extract headings
        content.append("HEADINGS:")
        content.append("-"*30)
        for i in range(1, 7):
            headings = soup.find_all(f'h{i}')
            if headings:
                content.append(f"\nH{i} Tags:")
                for heading in headings[:10]:  # Limit to first 10
                    text = heading.get_text().strip()
                    if text:
                        content.append(f"  • {text}")
        content.append("")
        
        # Extract navigation menu
        content.append("\nNAVIGATION MENU:")
        content.append("-"*30)
        menu_items = soup.find_all('a', class_=['menu-link', 'sub-link', 'nav-link'])
        for item in menu_items[:30]:  # Limit to first 30
            text = item.get_text(strip=True)
            href = item.get('href', 'No link')
            if text:
                content.append(f"• {text} -> {href}")
        
        # Extract main content area (customize based on common patterns)
        content.append("\nMAIN CONTENT:")
        content.append("-"*30)
        
        # Look for common content containers
        main_content = soup.find('main') or soup.find('article') or soup.find('div', class_=['content', 'main-content', 'col_news_con'])
        
        if main_content:
            # Extract text from main content
            text = main_content.get_text(separator='\n', strip=True)
            # Clean up the text
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            content.extend(lines[:100])  # Limit to first 100 lines
        
        # Extract tables
        content.append("\nTABLES:")
        content.append("-"*30)
        tables = soup.find_all('table')
        for i, table in enumerate(tables[:5], 1):  # Limit to first 5 tables
            content.append(f"\nTable {i}:")
            rows = table.find_all('tr')
            for row in rows[:20]:  # Limit rows
                cells = row.find_all(['td', 'th'])
                row_data = [cell.get_text(strip=True) for cell in cells]
                if row_data:
                    content.append(" | ".join(row_data))
        
        # Extract all links
        content.append("\nALL LINKS:")
        content.append("-"*30)
        links = soup.find_all('a', href=True)
        unique_links = {}
        for link in links:
            href = link.get('href')
            text = link.get_text(strip=True)
            if href and text and text not in unique_links:
                unique_links[text] = href
        
        for text, href in list(unique_links.items())[:50]:  # Limit to first 50
            content.append(f"{text} -> {href}")
        
        # Extract images
        content.append("\nIMAGES:")
        content.append("-"*30)
        images = soup.find_all('img')
        for i, img in enumerate(images[:20], 1):  # Limit to first 20
            src = img.get('src', 'N/A')
            alt = img.get('alt', 'No alt text')
            content.append(f"{i}. {alt} -> {src}")
        
        return '\n'.join(content)
    
    def scroll_page(self):
        """Scroll the page to load lazy-loaded content"""
        try:
            # Scroll down in steps
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            viewport_height = self.driver.execute_script("return window.innerHeight")
            
            current_position = 0
            while current_position < total_height:
                self.driver.execute_script(f"window.scrollTo(0, {current_position});")
                current_position += viewport_height
                time.sleep(0.5)  # Small delay for content to load
            
            # Scroll back to top
            self.driver.execute_script("window.scrollTo(0, 0);")
            
        except Exception as e:
            pass  # Ignore scroll errors
    
    def restart_driver(self):
        """Restart the WebDriver (useful for recovery from errors)"""
        print("  Restarting WebDriver...")
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
                print("WebDriver closed")
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
    print("Initializing scraper...")
    scraper = MultiURLScraper(headless=True)  # Set to False to see browser
    
    try:
        # Scrape all URLs from the file
        scraper.scrape_multiple_urls(
            urls_file="urls.txt",           # File containing URLs
            output_dir="scraped_data",      # Output directory
            combine_output=False,            # Set True to combine all results
            wait_between=2                   # Seconds to wait between URLs
        )
        
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user")
    except Exception as e:
        print(f"\nError: {str(e)}")
    finally:
        # Always close the driver
        scraper.close()

if __name__ == "__main__":
    # Install required packages:
    # pip install selenium beautifulsoup4 webdriver-manager
    
    main()