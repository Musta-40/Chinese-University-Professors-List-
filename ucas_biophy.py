import re
import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import logging
from typing import Dict, List, Optional, Tuple
import json

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('scraping_log.txt'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class UniversityFacultyScraper:
    def __init__(self, driver_path: Optional[str] = None, headless: bool = True):
        """
        Initialize the scraper with Selenium WebDriver
        
        Args:
            driver_path: Path to chromedriver executable (optional if in PATH)
            headless: Run browser in headless mode
        """
        self.driver = self._setup_driver(driver_path, headless)
        self.failed_urls = []
        self.extracted_data = []
        
    def _setup_driver(self, driver_path: Optional[str], headless: bool) -> webdriver.Chrome:
        """Setup Chrome WebDriver with appropriate options"""
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        if driver_path:
            service = Service(driver_path)
            return webdriver.Chrome(service=service, options=chrome_options)
        else:
            return webdriver.Chrome(options=chrome_options)
    
    def extract_js_variables(self, page_source: str) -> Dict[str, str]:
        """
        Extract JavaScript variables from page source
        
        Args:
            page_source: HTML page source
            
        Returns:
            Dictionary with extracted variables
        """
        extracted = {
            'name': '',
            'email': '',
            'research_interest_raw': ''
        }
        
        try:
            # Extract name (en_xm variable)
            name_pattern = r'var\s+en_xm\s*=\s*"([^"]*)"'
            name_match = re.search(name_pattern, page_source)
            if name_match:
                extracted['name'] = name_match.group(1).strip()
            
            # Extract email (dzyj variable)
            email_pattern = r'var\s+dzyj\s*=\s*"([^"]*)"'
            email_match = re.search(email_pattern, page_source)
            if email_match:
                extracted['email'] = email_match.group(1).strip()
            
            # Extract research interest (en_yjfx variable) - handle multi-line
            research_pattern = r'var\s+en_yjfx\s*=\s*"(.*?)"(?:\s*;|\s*\n)'
            research_match = re.search(research_pattern, page_source, re.DOTALL)
            if research_match:
                extracted['research_interest_raw'] = research_match.group(1)
                
        except Exception as e:
            logger.error(f"Error extracting JS variables: {str(e)}")
            
        return extracted
    
    def clean_research_interest(self, html_content: str) -> str:
        """
        Clean and extract research interest text from HTML content
        
        Args:
            html_content: Raw HTML content from en_yjfx variable
            
        Returns:
            Cleaned research interest text
        """
        if not html_content:
            return ""
        
        try:
            # Unescape HTML entities
            html_content = html_content.replace('\\"', '"').replace('\\/', '/')
            html_content = html_content.replace('\\n', '\n').replace('\\t', '\t')
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Remove style and script tags
            for tag in soup(['style', 'script']):
                tag.decompose()
            
            # Define possible start markers (case-insensitive)
            start_markers = [
                'research direction',
                'research interests',
                'research interest',
                'research areas',
                'research interests/areas',
                'research interests\/areas'
            ]
            
            # Find the start of research content
            text_content = ""
            found_start = False
            
            # Try to find any element containing the start markers
            for element in soup.find_all(['p', 'div', 'strong', 'b', 'h1', 'h2', 'h3', 'h4']):
                element_text = element.get_text().strip().lower()
                
                if not found_start:
                    for marker in start_markers:
                        if marker in element_text:
                            found_start = True
                            # Get all siblings after this element
                            for sibling in element.find_next_siblings():
                                sibling_text = sibling.get_text().strip()
                                # Stop at next major section
                                if any(stop in sibling_text.lower() for stop in 
                                      ['representative works', 'publications', 'education', 
                                       'awards', 'homepage', 'employment']):
                                    break
                                if sibling_text:
                                    text_content += sibling_text + " "
                            break
            
            # If no start marker found, extract all text
            if not text_content:
                text_content = soup.get_text()
            
            # Clean up the text
            text_content = re.sub(r'\s+', ' ', text_content)  # Normalize whitespace
            text_content = re.sub(r'：|:', ': ', text_content)  # Normalize colons
            
            # Remove the header itself if it's at the beginning
            for marker in start_markers:
                pattern = re.compile(f'^.*?{re.escape(marker)}.*?[:：]?\s*', re.IGNORECASE)
                text_content = pattern.sub('', text_content, count=1)
            
            return text_content.strip()
            
        except Exception as e:
            logger.error(f"Error cleaning research interest: {str(e)}")
            return html_content  # Return raw content as fallback
    
    def scrape_single_url(self, url: str, retry_count: int = 3) -> Dict[str, str]:
        """
        Scrape a single URL for faculty information
        
        Args:
            url: URL to scrape
            retry_count: Number of retries on failure
            
        Returns:
            Dictionary with extracted data
        """
        result = {
            'url': url,
            'name': '',
            'email': '',
            'research_interest': '',
            'status': 'failed'
        }
        
        for attempt in range(retry_count):
            try:
                logger.info(f"Scraping URL (attempt {attempt + 1}): {url}")
                
                # Load the page
                self.driver.get(url)
                
                # Wait for JavaScript to execute
                time.sleep(3)  # Basic wait
                
                # Try to wait for specific elements
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.ID, "name"))
                    )
                except:
                    pass  # Element might not exist in all pages
                
                # Get page source
                page_source = self.driver.page_source
                
                # Extract JavaScript variables
                js_data = self.extract_js_variables(page_source)
                
                # If JS extraction failed, try fallback methods
                if not js_data['name']:
                    try:
                        name_element = self.driver.find_element(By.ID, "name")
                        js_data['name'] = name_element.text.strip()
                    except:
                        pass
                
                if not js_data['email']:
                    try:
                        email_element = self.driver.find_element(By.ID, "dzyj")
                        js_data['email'] = email_element.text.strip()
                    except:
                        pass
                
                if not js_data['research_interest_raw']:
                    try:
                        research_element = self.driver.find_element(By.ID, "yjfx")
                        js_data['research_interest_raw'] = research_element.get_attribute('innerHTML')
                    except:
                        pass
                
                # Update result
                result['name'] = js_data['name']
                result['email'] = js_data['email']
                result['research_interest'] = self.clean_research_interest(
                    js_data['research_interest_raw']
                )
                
                # Validate extraction
                if result['name'] or result['email']:
                    result['status'] = 'success'
                    logger.info(f"Successfully extracted data for: {result['name']}")
                    break
                else:
                    logger.warning(f"No data extracted from {url}, attempt {attempt + 1}")
                    
            except Exception as e:
                logger.error(f"Error scraping {url} (attempt {attempt + 1}): {str(e)}")
                if attempt == retry_count - 1:
                    result['status'] = f'error: {str(e)}'
        
        return result
    
    def scrape_urls(self, urls: List[str], save_interval: int = 10) -> pd.DataFrame:
        """
        Scrape multiple URLs
        
        Args:
            urls: List of URLs to scrape
            save_interval: Save progress every N URLs
            
        Returns:
            DataFrame with all extracted data
        """
        total_urls = len(urls)
        
        for idx, url in enumerate(urls, 1):
            logger.info(f"Processing {idx}/{total_urls}: {url}")
            
            # Scrape the URL
            data = self.scrape_single_url(url)
            self.extracted_data.append(data)
            
            # Track failed URLs
            if data['status'] != 'success':
                self.failed_urls.append(url)
            
            # Save progress periodically
            if idx % save_interval == 0:
                self.save_progress(f"progress_backup_{idx}.csv")
            
            # Add small delay to avoid overwhelming the server
            time.sleep(1)
        
        # Create DataFrame
        df = pd.DataFrame(self.extracted_data)
        return df
    
    def save_progress(self, filename: str):
        """Save current progress to file"""
        if self.extracted_data:
            df = pd.DataFrame(self.extracted_data)
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            logger.info(f"Progress saved to {filename}")
    
    def save_results(self, df: pd.DataFrame, filename: str = "faculty_data.xlsx"):
        """
        Save results to Excel file with multiple sheets
        
        Args:
            df: DataFrame with extracted data
            filename: Output filename
        """
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # All data
            df.to_excel(writer, sheet_name='All Data', index=False)
            
            # Successfully extracted
            success_df = df[df['status'] == 'success']
            success_df.to_excel(writer, sheet_name='Successful', index=False)
            
            # Failed extractions
            failed_df = df[df['status'] != 'success']
            if not failed_df.empty:
                failed_df.to_excel(writer, sheet_name='Failed', index=False)
            
            # Summary statistics
            summary = pd.DataFrame({
                'Metric': ['Total URLs', 'Successful', 'Failed', 'Success Rate'],
                'Value': [
                    len(df),
                    len(success_df),
                    len(failed_df),
                    f"{len(success_df)/len(df)*100:.2f}%"
                ]
            })
            summary.to_excel(writer, sheet_name='Summary', index=False)
        
        logger.info(f"Results saved to {filename}")
    
    def close(self):
        """Close the WebDriver"""
        if self.driver:
            self.driver.quit()
            logger.info("WebDriver closed")

def main():
    """Main execution function"""
    
    # Load your URLs (replace with your actual URLs)
    urls = [
        # Add your 106 URLs here
        # Example:
        # "http://example.edu.cn/faculty/professor1",
        # "http://example.edu.cn/faculty/professor2",
        # ...
    ]
    
    # Or load from a file
    # with open('urls.txt', 'r') as f:
    #     urls = [line.strip() for line in f if line.strip()]
    
    # Initialize scraper
    scraper = UniversityFacultyScraper(headless=True)
    
    try:
        # Scrape all URLs
        df = scraper.scrape_urls(urls, save_interval=10)
        
        # Save results
        scraper.save_results(df, "faculty_data.xlsx")
        
        # Save failed URLs for re-processing
        if scraper.failed_urls:
            with open('failed_urls.txt', 'w') as f:
                for url in scraper.failed_urls:
                    f.write(f"{url}\n")
            logger.info(f"Failed URLs saved to failed_urls.txt")
        
        # Print summary
        print("\n" + "="*50)
        print("SCRAPING SUMMARY")
        print("="*50)
        print(f"Total URLs processed: {len(df)}")
        print(f"Successful extractions: {len(df[df['status'] == 'success'])}")
        print(f"Failed extractions: {len(df[df['status'] != 'success'])}")
        print(f"Success rate: {len(df[df['status'] == 'success'])/len(df)*100:.2f}%")
        
    finally:
        scraper.close()

if __name__ == "__main__":
    main()