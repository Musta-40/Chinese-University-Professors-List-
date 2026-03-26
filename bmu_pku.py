from bs4 import BeautifulSoup
import requests
import pandas as pd
import re
import time
import concurrent.futures
from urllib.parse import urljoin
import logging

class BJMUPharmacyScraper:
    """
    Web scraper for Beijing Medical University School of Pharmaceutical Sciences doctoral supervisors.
    """
    
    def __init__(self):
        self.base_url = "https://sps.bjmu.edu.cn"
        self.supervisors_url = "https://sps.bjmu.edu.cn/szdw/bssds/index.htm"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        self.list_of_dicts = []
        self.logger = self._setup_logger()
    
    def _setup_logger(self):
        """
        Sets up logging for the scraper.
        """
        logger = logging.getLogger("BJMUPharmacyScraper")
        logger.setLevel(logging.INFO)
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        
        # File handler
        file_handler = logging.FileHandler("bjmu_scraper.log", encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        return logger
    
    def scrape_data(self):
        """
        Main method to scrape all supervisor data.
        """
        self.logger.info("Starting BJMU Pharmacy supervisor scraping...")
        
        # Step 1: Get all supervisors from the main page
        supervisors_by_dept = self.get_supervisors_list()
        
        if not supervisors_by_dept:
            self.logger.error("No supervisors found on the main page")
            return self.list_of_dicts
        
        total_supervisors = sum(len(supervisors) for supervisors in supervisors_by_dept.values())
        self.logger.info(f"Found {total_supervisors} supervisors across {len(supervisors_by_dept)} departments")
        
        # Step 2: Visit each supervisor's profile page to get details
        self.logger.info("Visiting individual profile pages...")
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
            futures = []
            
            for department, supervisors in supervisors_by_dept.items():
                for name, url in supervisors:
                    future = executor.submit(self.scrape_supervisor_profile, name, url, department)
                    futures.append(future)
                    time.sleep(0.3)  # Be respectful to the server
            
            for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
                try:
                    result = future.result()
                    if result:
                        self.list_of_dicts.append(result)
                        self.logger.info(f"Processed {i}/{total_supervisors}: {result.get('Name', 'Unknown')}")
                except Exception as e:
                    self.logger.error(f"Error processing profile: {e}")
        
        self.logger.info(f"Scraping completed. Total profiles scraped: {len(self.list_of_dicts)}")
        return self.list_of_dicts
    
    def get_supervisors_list(self):
        """
        Gets all supervisors from the main listing page, organized by department.
        
        Returns:
            dict: Dictionary with department names as keys and list of (name, url) tuples as values
        """
        supervisors_by_dept = {}
        
        try:
            response = self.session.get(self.supervisors_url, timeout=15)
            response.encoding = 'utf-8'  # Ensure proper Chinese encoding
            
            if response.status_code != 200:
                self.logger.error(f"Failed to load main page. Status code: {response.status_code}")
                return supervisors_by_dept
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Save HTML for debugging
            with open("bjmu_main_page.html", "w", encoding="utf-8") as f:
                f.write(soup.prettify())
            
            # Find all department sections
            department_sections = soup.find_all("div", class_="dWrap_title02")
            
            for dept_section in department_sections:
                # Get department name
                dept_name_elem = dept_section.find("h3")
                if not dept_name_elem:
                    continue
                
                department = dept_name_elem.get_text().strip()
                
                # Find the next sibling which should contain the supervisor list
                list_section = dept_section.find_next_sibling("div", class_="dList02")
                
                if list_section:
                    supervisors = []
                    
                    # Find all supervisor links
                    supervisor_items = list_section.find_all("li")
                    
                    for item in supervisor_items:
                        link = item.find("a")
                        if link:
                            name = link.get_text().strip()
                            href = link.get("href", "")
                            
                            # Handle relative URLs
                            if href:
                                if href.startswith("http"):
                                    full_url = href
                                else:
                                    # Handle relative paths
                                    full_url = urljoin(self.supervisors_url, href)
                                
                                supervisors.append((name, full_url))
                    
                    if supervisors:
                        supervisors_by_dept[department] = supervisors
                        self.logger.info(f"Department '{department}': {len(supervisors)} supervisors")
            
            # Alternative extraction if the above doesn't work
            if not supervisors_by_dept:
                self.logger.info("Trying alternative extraction method...")
                
                # Look for the main content div
                content_div = soup.find("div", id="p01") or soup.find("div", class_="dWrap02")
                
                if content_div:
                    current_dept = "Unknown Department"
                    
                    for element in content_div.find_all(["h3", "li"]):
                        if element.name == "h3":
                            current_dept = element.get_text().strip()
                            if current_dept not in supervisors_by_dept:
                                supervisors_by_dept[current_dept] = []
                        elif element.name == "li":
                            link = element.find("a")
                            if link:
                                name = link.get_text().strip()
                                href = link.get("href", "")
                                if href:
                                    full_url = urljoin(self.supervisors_url, href) if not href.startswith("http") else href
                                    supervisors_by_dept[current_dept].append((name, full_url))
            
        except Exception as e:
            self.logger.error(f"Error getting supervisors list: {e}")
        
        return supervisors_by_dept
    
    def scrape_supervisor_profile(self, name, url, department):
        """
        Scrapes individual supervisor profile page for email and research interests.
        
        Args:
            name (str): Supervisor's name
            url (str): URL of the supervisor's profile page
            department (str): Department name
            
        Returns:
            dict: Supervisor information including email and research interests
        """
        try:
            # Handle special cases where URL might be the main page
            if url == self.supervisors_url or "index.htm" in url and name not in url:
                self.logger.warning(f"Skipping invalid profile URL for {name}")
                return {
                    "Name": name,
                    "Department": department,
                    "Email": "",
                    "Research Interest": "",
                    "Profile URL": url
                }
            
            response = self.session.get(url, timeout=15)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                self.logger.warning(f"Failed to load profile for {name}. Status: {response.status_code}")
                return {
                    "Name": name,
                    "Department": department,
                    "Email": "",
                    "Research Interest": "",
                    "Profile URL": url
                }
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Extract email
            email = self.extract_email(soup)
            
            # Extract research interests
            research = self.extract_research_interests(soup)
            
            # Try to get more accurate name from profile page
            profile_name = self.extract_name_from_profile(soup)
            if profile_name:
                name = profile_name
            
            return {
                "Name": name,
                "Department": department,
                "Email": email,
                "Research Interest": research,
                "Profile URL": url
            }
            
        except Exception as e:
            self.logger.error(f"Error scraping profile for {name}: {e}")
            return {
                "Name": name,
                "Department": department,
                "Email": "",
                "Research Interest": "",
                "Profile URL": url
            }
    
    def extract_email(self, soup):
        """
        Extracts email from profile page.
        """
        # Strategy 1: Look for mailto links
        mailto_links = soup.find_all("a", href=re.compile(r"mailto:", re.I))
        for link in mailto_links:
            email = link.get("href", "").replace("mailto:", "").strip()
            if "@" in email and "bjmu.edu.cn" in email:
                return email
        
        # Strategy 2: Look for email patterns in text
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        # Look for email in common locations
        email_keywords = ["email", "e-mail", "邮箱", "邮件", "电子邮件", "Email", "E-mail", "联系方式"]
        
        for keyword in email_keywords:
            elements = soup.find_all(text=re.compile(keyword, re.I))
            for elem in elements:
                parent = elem.parent if hasattr(elem, 'parent') else None
                if parent:
                    text = parent.get_text()
                    emails = re.findall(email_pattern, text)
                    for email in emails:
                        if "bjmu.edu.cn" in email or "pku.edu.cn" in email:
                            return email
        
        # Strategy 3: Search entire page
        page_text = soup.get_text()
        emails = re.findall(email_pattern, page_text)
        
        # Prefer institutional emails
        for email in emails:
            if "bjmu.edu.cn" in email or "pku.edu.cn" in email:
                return email
        
        # Return any email found
        return emails[0] if emails else ""
    
    def extract_research_interests(self, soup):
        """
        Extracts research interests from profile page.
        """
        research_interests = []
        
        # Chinese and English keywords for research interests
        keywords = [
            "研究方向", "研究领域", "研究兴趣", "主要研究", "研究内容",
            "Research Interest", "Research Area", "Research Field", 
            "Research Direction", "Research Focus", "Research Topics"
        ]
        
        for keyword in keywords:
            # Find elements containing the keyword
            elements = soup.find_all(text=re.compile(keyword, re.I))
            
            for element in elements:
                parent = element.parent if hasattr(element, 'parent') else None
                if not parent:
                    continue
                
                # Look for content after the keyword
                content = ""
                
                # Check next sibling
                next_elem = parent.find_next_sibling()
                if next_elem:
                    if next_elem.name == "ul":
                        items = next_elem.find_all("li")
                        content = "；".join([item.get_text().strip() for item in items])
                    elif next_elem.name in ["p", "div", "td"]:
                        content = next_elem.get_text().strip()
                
                # Check within the same container
                if not content:
                    # Get parent's parent for broader context
                    container = parent.parent
                    if container:
                        full_text = container.get_text()
                        # Extract text after the keyword
                        keyword_pos = full_text.find(element)
                        if keyword_pos != -1:
                            content = full_text[keyword_pos + len(element):].strip()
                            # Clean up and limit length
                            content = re.sub(r'\s+', ' ', content)[:500]
                
                if content and len(content) > 10:
                    research_interests.append(content)
        
        # Also look for divs/sections with research-related classes
        research_sections = soup.find_all(["div", "section", "td"], 
                                         class_=re.compile(r"research|研究", re.I))
        for section in research_sections:
            text = section.get_text().strip()
            if len(text) > 20 and len(text) < 1000:
                # Remove the keyword from the beginning if present
                for keyword in keywords:
                    if text.startswith(keyword):
                        text = text[len(keyword):].strip()
                        break
                if text:
                    research_interests.append(text)
        
        # Clean and combine
        if research_interests:
            # Remove duplicates and combine
            unique_interests = []
            for interest in research_interests:
                if interest not in unique_interests:
                    unique_interests.append(interest)
            
            combined = "；".join(unique_interests)
            # Clean up
            combined = re.sub(r'\s+', ' ', combined)
            combined = combined[:1000]  # Limit total length
            return combined
        
        return ""
    
    def extract_name_from_profile(self, soup):
        """
        Extracts supervisor name from their profile page.
        """
        # Look for name in common locations
        selectors = [
            ("h1", {}),
            ("h2", {}),
            ("div", {"class": re.compile(r"name|title|姓名")}),
            ("span", {"class": re.compile(r"name|title")}),
            ("td", {"class": re.compile(r"name")}),
        ]
        
        for tag, attrs in selectors:
            elements = soup.find_all(tag, attrs)
            for elem in elements:
                text = elem.get_text().strip()
                # Check if it looks like a Chinese name (2-4 characters)
                if re.match(r'^[\u4e00-\u9fff]{2,4}$', text):
                    return text
                # Check if it's formatted like "姓名：XXX"
                if "姓名" in text or "名字" in text:
                    name = re.sub(r'.*[姓名|名字][：:]\s*', '', text).strip()
                    if name and len(name) < 10:
                        return name
        
        return ""
    
    def dump_to_csv(self, filename="bjmu_pharmacy_supervisors.csv"):
        """
        Saves data to CSV file.
        """
        if self.list_of_dicts:
            df = pd.DataFrame(self.list_of_dicts)
            # Sort by department and name
            if 'Department' in df.columns:
                df = df.sort_values(['Department', 'Name'])
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            self.logger.info(f"Data saved to {filename}")
            
            # Print statistics
            total = len(df)
            emails_found = df[df['Email'] != '']['Email'].count()
            research_found = df[df['Research Interest'] != '']['Research Interest'].count()
            
            print(f"\n=== Statistics ===")
            print(f"Total supervisors: {total}")
            print(f"Emails found: {emails_found}/{total} ({emails_found*100/total:.1f}%)")
            print(f"Research interests found: {research_found}/{total} ({research_found*100/total:.1f}%)")
            
            if 'Department' in df.columns:
                print(f"\n=== By Department ===")
                dept_counts = df['Department'].value_counts()
                for dept, count in dept_counts.items():
                    print(f"{dept}: {count} supervisors")
        else:
            self.logger.warning("No data to save")
    
    def return_df(self):
        """
        Returns data as pandas DataFrame.
        """
        df = pd.DataFrame(self.list_of_dicts)
        if not df.empty and 'Department' in df.columns:
            df = df.sort_values(['Department', 'Name'])
        return df


# Main execution
if __name__ == "__main__":
    print("="*60)
    print("Beijing Medical University School of Pharmaceutical Sciences")
    print("Doctoral Supervisors Scraper")
    print("="*60)
    
    scraper = BJMUPharmacyScraper()
    
    # Scrape data
    data = scraper.scrape_data()
    
    # Save to CSV
    scraper.dump_to_csv("bjmu_pharmacy_supervisors.csv")
    
    # Display sample results
    df = scraper.return_df()
    if not df.empty:
        print("\n" + "="*60)
        print("Sample of scraped data (first 5 records):")
        print("="*60)
        
        for i, row in df.head(5).iterrows():
            print(f"\n{i+1}. {row.get('Name', 'N/A')}")
            print(f"   Department: {row.get('Department', 'N/A')}")
            print(f"   Email: {row.get('Email', 'Not found')}")
            research = row.get('Research Interest', '')
            if research:
                print(f"   Research: {research[:100]}..." if len(research) > 100 else f"   Research: {research}")
            else:
                print(f"   Research: Not found")
            print(f"   URL: {row.get('Profile URL', 'N/A')}")
    else:
        print("\nNo data was scraped.")