from bs4 import BeautifulSoup
import requests
import pandas as pd
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import logging

class BJMUCompleteScraper:
    """
    Complete scraper using both requests and Selenium for Beijing Medical University.
    """
    
    def __init__(self, use_selenium=True):
        self.base_url = "https://sbms.bjmu.edu.cn"
        self.supervisors_url = "https://sbms.bjmu.edu.cn/jsdw/bssds/index.htm"
        self.use_selenium = use_selenium
        self.list_of_dicts = []
        self.logger = self._setup_logger()
        
        # Regular session for requests
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
    
    def _setup_logger(self):
        """Setup logging"""
        logger = logging.getLogger("BJMUCompleteScraper")
        logger.setLevel(logging.DEBUG)
        
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        file_handler = logging.FileHandler("bjmu_complete_debug.log", encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger
    
    def scrape_with_selenium(self):
        """
        Use Selenium to handle JavaScript-rendered content.
        """
        self.logger.info("Using Selenium to scrape the page...")
        
        # Setup Chrome options
        chrome_options = Options()
        chrome_options.add_argument('--headless')  # Run in background
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_experimental_option('excludeSwitches', ['enable-logging'])
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            driver.set_page_load_timeout(30)
            
            self.logger.info(f"Loading page: {self.supervisors_url}")
            driver.get(self.supervisors_url)
            
            # Wait for the page to load
            time.sleep(5)
            
            # Try to scroll to load all content
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)
            
            # Get the page source
            page_source = driver.page_source
            
            # Save the rendered HTML
            with open("bjmu_selenium_rendered.html", "w", encoding="utf-8") as f:
                f.write(page_source)
            self.logger.info("Saved Selenium-rendered HTML to bjmu_selenium_rendered.html")
            
            # Parse with BeautifulSoup
            soup = BeautifulSoup(page_source, "html.parser")
            
            # Extract data
            self.extract_all_tables(soup)
            
            driver.quit()
            
        except Exception as e:
            self.logger.error(f"Selenium error: {e}")
            self.logger.info("Please install selenium and chromedriver: pip install selenium")
            self.logger.info("Download chromedriver from: https://chromedriver.chromium.org/")
    
    def scrape_with_requests(self):
        """
        Traditional scraping with requests library.
        """
        self.logger.info("Using requests to scrape the page...")
        
        try:
            response = self.session.get(self.supervisors_url, timeout=30)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                self.logger.error(f"Failed to load page. Status: {response.status_code}")
                return
            
            # Save raw HTML
            with open("bjmu_requests_raw.html", "w", encoding="utf-8") as f:
                f.write(response.text)
            self.logger.info("Saved raw HTML to bjmu_requests_raw.html")
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Extract data
            self.extract_all_tables(soup)
            
        except Exception as e:
            self.logger.error(f"Requests error: {e}")
    
    def extract_all_tables(self, soup):
        """
        Extract data from ALL tables on the page.
        """
        self.logger.info("Extracting data from tables...")
        
        # Find ALL tables
        all_tables = soup.find_all("table")
        self.logger.info(f"Found {len(all_tables)} table(s) on the page")
        
        for table_idx, table in enumerate(all_tables):
            self.logger.info(f"Processing table {table_idx + 1}...")
            
            # Get all rows including those in tbody, thead, tfoot
            all_rows = []
            
            # Direct tr elements
            direct_rows = table.find_all("tr", recursive=False)
            all_rows.extend(direct_rows)
            
            # Rows in tbody
            tbodies = table.find_all("tbody")
            for tbody in tbodies:
                tbody_rows = tbody.find_all("tr")
                all_rows.extend(tbody_rows)
            
            # Rows in thead
            theads = table.find_all("thead")
            for thead in theads:
                thead_rows = thead.find_all("tr")
                all_rows.extend(thead_rows)
            
            # If no rows found with above methods, get all tr recursively
            if not all_rows:
                all_rows = table.find_all("tr")
            
            self.logger.info(f"Table {table_idx + 1} has {len(all_rows)} rows")
            
            if len(all_rows) < 2:
                continue
            
            # Process header row
            header_row = all_rows[0]
            headers = []
            header_cells = header_row.find_all(["th", "td"])
            
            for cell in header_cells:
                header_text = cell.get_text().strip()
                header_text = re.sub(r'\s+', ' ', header_text)
                headers.append(header_text)
            
            self.logger.debug(f"Headers: {headers}")
            
            # Find column indices
            indices = self.find_column_indices(headers)
            
            # If this looks like our target table
            if indices['name'] >= 0:
                self.logger.info(f"This appears to be the supervisor table!")
                
                # Process ALL data rows
                for row_idx, row in enumerate(all_rows[1:], 1):
                    cells = row.find_all(["td", "th"])
                    
                    if len(cells) > indices['name']:
                        supervisor = self.extract_supervisor_from_row(cells, indices)
                        
                        if supervisor and supervisor['Name']:
                            # Check for duplicates
                            if not any(s['Name'] == supervisor['Name'] for s in self.list_of_dicts):
                                self.list_of_dicts.append(supervisor)
                                self.logger.debug(f"Row {row_idx}: Added {supervisor['Name']}")
                
                self.logger.info(f"Extracted {len(self.list_of_dicts)} supervisors from this table")
    
    def find_column_indices(self, headers):
        """
        Find the indices of important columns.
        """
        indices = {
            'name': -1,
            'gender': -1,
            'title': -1,
            'discipline': -1,
            'research': -1,
            'note': -1
        }
        
        for i, header in enumerate(headers):
            header_lower = header.lower()
            
            if any(x in header for x in ['姓名', '姓 名', 'name']):
                indices['name'] = i
            elif any(x in header for x in ['性别', 'gender']):
                indices['gender'] = i
            elif any(x in header for x in ['职称', 'title', '职 称']):
                indices['title'] = i
            elif any(x in header for x in ['学科', '专业', 'discipline', 'major']):
                indices['discipline'] = i
            elif any(x in header for x in ['研究', 'research']):
                indices['research'] = i
            elif any(x in header for x in ['备注', 'note', 'remark']):
                indices['note'] = i
        
        return indices
    
    def extract_supervisor_from_row(self, cells, indices):
        """
        Extract supervisor data from a table row.
        """
        supervisor = {
            'Name': '',
            'Gender': '',
            'Title': '',
            'Discipline/Major': '',
            'Research Direction': '',
            'Email': '',
            'Note': ''
        }
        
        # Extract name
        if indices['name'] >= 0 and indices['name'] < len(cells):
            name_cell = cells[indices['name']]
            
            # Check for link
            name_link = name_cell.find("a")
            if name_link:
                supervisor['Name'] = name_link.get_text().strip()
                href = name_link.get("href", "")
                if href:
                    supervisor['Profile URL'] = href if href.startswith("http") else self.base_url + "/" + href.lstrip("/")
            else:
                supervisor['Name'] = name_cell.get_text().strip()
            
            # Clean name
            supervisor['Name'] = re.sub(r'\s+', ' ', supervisor['Name'])
            supervisor['Name'] = supervisor['Name'].replace('\n', '').replace('\r', '').replace('\t', '')
        
        # Skip if invalid name
        if not supervisor['Name'] or len(supervisor['Name']) < 2 or len(supervisor['Name']) > 20:
            return None
        
        # Skip if contains invalid characters
        if not re.search(r'[\u4e00-\u9fff]|[a-zA-Z]', supervisor['Name']):
            return None
        
        # Extract other fields
        if indices['gender'] >= 0 and indices['gender'] < len(cells):
            supervisor['Gender'] = cells[indices['gender']].get_text().strip()
        
        if indices['title'] >= 0 and indices['title'] < len(cells):
            supervisor['Title'] = cells[indices['title']].get_text().strip()
            supervisor['Title'] = re.sub(r'\s+', ' ', supervisor['Title'])
        
        if indices['discipline'] >= 0 and indices['discipline'] < len(cells):
            supervisor['Discipline/Major'] = cells[indices['discipline']].get_text().strip()
            supervisor['Discipline/Major'] = re.sub(r'\s+', ' ', supervisor['Discipline/Major'])
        
        if indices['research'] >= 0 and indices['research'] < len(cells):
            supervisor['Research Direction'] = cells[indices['research']].get_text().strip()
            supervisor['Research Direction'] = re.sub(r'\s+', ' ', supervisor['Research Direction'])
        
        if indices['note'] >= 0 and indices['note'] < len(cells):
            supervisor['Note'] = cells[indices['note']].get_text().strip()
        
        return supervisor
    
    def scrape_data(self):
        """
        Main method to scrape all data.
        """
        self.logger.info("="*60)
        self.logger.info("Starting comprehensive scraping...")
        self.logger.info("="*60)
        
        if self.use_selenium:
            try:
                self.scrape_with_selenium()
            except:
                self.logger.info("Selenium failed, falling back to requests...")
                self.scrape_with_requests()
        else:
            self.scrape_with_requests()
        
        # If still not enough data, try alternative methods
        if len(self.list_of_dicts) < 100:
            self.logger.info("Not enough data found. Trying alternative extraction...")
            self.alternative_extraction()
        
        self.logger.info(f"="*60)
        self.logger.info(f"Total supervisors extracted: {len(self.list_of_dicts)}")
        self.logger.info(f"="*60)
        
        return self.list_of_dicts
    
    def alternative_extraction(self):
        """
        Alternative method to extract data if main method fails.
        """
        self.logger.info("Trying alternative extraction methods...")
        
        try:
            response = self.session.get(self.supervisors_url, timeout=30)
            response.encoding = 'utf-8'
            
            # Try different parsers
            for parser in ['html.parser', 'lxml', 'html5lib']:
                try:
                    self.logger.info(f"Trying parser: {parser}")
                    soup = BeautifulSoup(response.content, parser)
                    
                    # Find all text that looks like names
                    all_text = soup.get_text()
                    lines = all_text.split('\n')
                    
                    for line in lines:
                        line = line.strip()
                        
                        # Check if it looks like a name (2-4 Chinese characters)
                        if re.match(r'^[\u4e00-\u9fff]{2,4}$', line):
                            if not any(s['Name'] == line for s in self.list_of_dicts):
                                self.list_of_dicts.append({
                                    'Name': line,
                                    'Gender': '',
                                    'Title': '',
                                    'Discipline/Major': '',
                                    'Research Direction': '',
                                    'Email': '',
                                    'Note': ''
                                })
                    
                except Exception as e:
                    self.logger.debug(f"Parser {parser} failed: {e}")
                    continue
                    
        except Exception as e:
            self.logger.error(f"Alternative extraction failed: {e}")
    
    def dump_to_csv(self, filename="bjmu_all_158_supervisors.csv"):
        """
        Save data to CSV file.
        """
        if self.list_of_dicts:
            df = pd.DataFrame(self.list_of_dicts)
            
            # Clean data
            for col in df.columns:
                if col in df.columns:
                    df[col] = df[col].apply(lambda x: str(x).strip() if pd.notna(x) else '')
            
            # Remove duplicates
            df = df.drop_duplicates(subset=['Name'], keep='first')
            
            # Sort by name
            df = df.sort_values('Name')
            
            # Save to CSV
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            
            print(f"\n{'='*60}")
            print(f"EXTRACTION COMPLETE")
            print(f"{'='*60}")
            print(f"Total unique supervisors: {len(df)}")
            print(f"Data saved to: {filename}")
            
            # Statistics
            for col in ['Gender', 'Title', 'Discipline/Major', 'Research Direction', 'Email']:
                if col in df.columns:
                    non_empty = df[df[col] != ''][col].count()
                    print(f"{col}: {non_empty}/{len(df)} ({non_empty*100/len(df):.1f}% filled)")
            
            # Show sample
            print(f"\n{'='*60}")
            print("First 10 supervisors:")
            print(f"{'='*60}")
            for i, row in df.head(10).iterrows():
                print(f"{i+1}. {row['Name']}")
                if row.get('Discipline/Major'):
                    print(f"   Discipline: {row['Discipline/Major']}")
                if row.get('Research Direction'):
                    research = row['Research Direction']
                    print(f"   Research: {research[:60]}..." if len(research) > 60 else f"   Research: {research}")
            
            return df
        else:
            print("No data extracted!")
            return pd.DataFrame()


# Alternative: Direct HTML parsing approach
def direct_html_parse():
    """
    Direct approach: Download and parse the HTML manually.
    """
    print("="*60)
    print("Direct HTML Parsing Approach")
    print("="*60)
    
    url = "https://sbms.bjmu.edu.cn/jsdw/bssds/index.htm"
    
    # Download the page
    response = requests.get(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    })
    response.encoding = 'utf-8'
    
    # Save raw HTML
    with open("bjmu_raw.html", "w", encoding="utf-8") as f:
        f.write(response.text)
    
    print("Raw HTML saved to bjmu_raw.html")
    print("Please open this file and check the table structure.")
    
    # Parse with BeautifulSoup
    soup = BeautifulSoup(response.text, 'html.parser')
    
    # Find all table cells with Chinese names
    supervisors = []
    
    # Method 1: Find all cells in tables
    for table in soup.find_all('table'):
        for row in table.find_all('tr'):
            cells = row.find_all(['td', 'th'])
            
            row_data = []
            for cell in cells:
                text = cell.get_text().strip()
                text = re.sub(r'\s+', ' ', text)
                row_data.append(text)
            
            # If this row has data (not header)
            if row_data and len(row_data) > 1:
                # Check if second column looks like a name
                if len(row_data) > 1 and re.match(r'^[\u4e00-\u9fff]{2,4}$', row_data[1]):
                    supervisor = {
                        'Discipline/Major': row_data[0] if len(row_data) > 0 else '',
                        'Name': row_data[1] if len(row_data) > 1 else '',
                        'Gender': row_data[2] if len(row_data) > 2 else '',
                        'Title': row_data[3] if len(row_data) > 3 else '',
                        'Research Direction': row_data[4] if len(row_data) > 4 else '',
                        'Note': row_data[5] if len(row_data) > 5 else ''
                    }
                    supervisors.append(supervisor)
    
    if supervisors:
        df = pd.DataFrame(supervisors)
        df = df.drop_duplicates(subset=['Name'], keep='first')
        df.to_csv("bjmu_direct_parse.csv", index=False, encoding='utf-8-sig')
        print(f"Found {len(df)} supervisors using direct parsing")
        print(f"Data saved to bjmu_direct_parse.csv")
        return df
    else:
        print("No supervisors found with direct parsing")
        return None


# Main execution
if __name__ == "__main__":
    print("="*60)
    print("Beijing Medical University - Complete Supervisor Extraction")
    print("="*60)
    print("\nTrying multiple methods to extract all 158 supervisors...")
    
    # Method 1: Comprehensive scraper
    print("\n1. Using comprehensive scraper...")
    scraper = BJMUCompleteScraper(use_selenium=False)  # Set to True if you have Selenium installed
    data = scraper.scrape_data()
    df1 = scraper.dump_to_csv("bjmu_method1.csv")
    
    # Method 2: Direct HTML parsing
    print("\n2. Using direct HTML parsing...")
    df2 = direct_html_parse()
    
    print("\n" + "="*60)
    print("IMPORTANT DEBUGGING STEPS:")
    print("="*60)
    print("1. Check 'bjmu_raw.html' to see the actual HTML structure")
    print("2. Check 'bjmu_complete_debug.log' for detailed extraction logs")
    print("3. If you have Selenium installed, set use_selenium=True")
    print("4. The actual table might be very long - scroll through bjmu_raw.html")
    print("\nIf still having issues, please share the bjmu_raw.html file content")