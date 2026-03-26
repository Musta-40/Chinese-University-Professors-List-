from bs4 import BeautifulSoup
import requests
import pandas as pd
import re
import time
import concurrent.futures
from urllib.parse import urljoin

class SJTULifeSciencesScraper:
    """
    Web scraper for SJTU School of Life Sciences that crawls individual profile pages.
    """
    
    def __init__(self):
        self.base_url = "https://life.sjtu.edu.cn"
        self.supervisors_url = "https://life.sjtu.edu.cn/en/data/list/supervisors"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        self.list_of_dicts = []
        
    def scrape_data(self):
        """
        Main method that orchestrates the two-step scraping process.
        """
        print("Step 1: Getting supervisor list and profile URLs...")
        supervisor_links = self.get_supervisor_list()
        
        if not supervisor_links:
            print("No supervisor links found. Checking page structure...")
            self.explore_page_structure()
            return self.list_of_dicts
        
        print(f"Found {len(supervisor_links)} supervisors")
        print("\nStep 2: Visiting each profile page to get details...")
        
        # Process each supervisor's profile page
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = []
            for name, url in supervisor_links:
                future = executor.submit(self.scrape_profile_page, name, url)
                futures.append(future)
                time.sleep(0.2)  # Small delay to be respectful
            
            for i, future in enumerate(concurrent.futures.as_completed(futures), 1):
                try:
                    result = future.result()
                    if result:
                        self.list_of_dicts.append(result)
                        print(f"Processed {i}/{len(supervisor_links)}: {result.get('Name', 'Unknown')}")
                except Exception as e:
                    print(f"Error processing profile: {e}")
        
        print(f"\nCompleted! Scraped {len(self.list_of_dicts)} supervisor profiles")
        return self.list_of_dicts
    
    def get_supervisor_list(self):
        """
        Gets the list of supervisors and their profile page URLs from the main page.
        """
        supervisor_links = []
        
        try:
            # Try pagination first
            page = 1
            max_pages = 20  # Safety limit
            
            while page <= max_pages:
                url = f"{self.supervisors_url}?page={page}"
                print(f"Checking page {page}...")
                
                response = self.session.get(url, timeout=15)
                if response.status_code != 200:
                    print(f"Page {page} returned status {response.status_code}")
                    break
                
                soup = BeautifulSoup(response.content, "html.parser")
                
                # Strategy 1: Look for teacher/supervisor list items with links
                found_on_page = False
                
                # Common patterns for supervisor listings
                selectors = [
                    # Try finding links within teacher/supervisor containers
                    ("div[class*='teacher']", "a"),
                    ("div[class*='supervisor']", "a"),
                    ("li[class*='teacher']", "a"),
                    ("li[class*='supervisor']", "a"),
                    ("div[class*='staff']", "a"),
                    ("div[class*='faculty']", "a"),
                    # Generic list items
                    ("ul.list", "li a"),
                    ("div.content", "a[href*='/en/']"),
                    # Table format
                    ("table", "td a"),
                    # Any link that looks like a profile
                    (None, "a[href*='teacher']"),
                    (None, "a[href*='supervisor']"),
                    (None, "a[href*='faculty']"),
                    (None, "a[href*='staff']"),
                    (None, "a[href*='/en/data/info/']"),
                ]
                
                for container_sel, link_sel in selectors:
                    if container_sel:
                        containers = soup.select(container_sel)
                        for container in containers:
                            links = container.select(link_sel) if link_sel else container.find_all("a")
                            for link in links:
                                href = link.get("href", "")
                                name = link.get_text().strip()
                                
                                if href and name and len(name) > 1:
                                    full_url = urljoin(self.base_url, href)
                                    if (name, full_url) not in supervisor_links:
                                        supervisor_links.append((name, full_url))
                                        found_on_page = True
                    else:
                        links = soup.select(link_sel)
                        for link in links:
                            href = link.get("href", "")
                            name = link.get_text().strip()
                            
                            if href and name and len(name) > 1:
                                full_url = urljoin(self.base_url, href)
                                if (name, full_url) not in supervisor_links:
                                    supervisor_links.append((name, full_url))
                                    found_on_page = True
                
                # If no supervisors found on this page and it's page 1, try different approach
                if not found_on_page and page == 1:
                    print("Trying alternative extraction methods...")
                    
                    # Look for any links with Chinese or English names
                    all_links = soup.find_all("a", href=True)
                    for link in all_links:
                        href = link.get("href", "")
                        name = link.get_text().strip()
                        
                        # Filter by URL patterns and name patterns
                        if (href and name and 
                            len(name) > 1 and len(name) < 50 and
                            ("/en/" in href or "teacher" in href or "faculty" in href) and
                            not any(skip in href.lower() for skip in ["javascript", "void", "#", ".pdf", ".doc"])):
                            
                            # Check if it looks like a name
                            if self.is_potential_name(name):
                                full_url = urljoin(self.base_url, href)
                                if (name, full_url) not in supervisor_links:
                                    supervisor_links.append((name, full_url))
                                    found_on_page = True
                
                # Check for next page
                if not found_on_page and page > 1:
                    print(f"No more supervisors found after page {page-1}")
                    break
                
                # Look for pagination controls
                has_next = False
                pagination = soup.find("div", class_=re.compile(r"pag", re.I))
                if pagination:
                    next_link = pagination.find("a", text=re.compile(r"next|下一页|>", re.I))
                    if next_link and "disabled" not in next_link.get("class", []):
                        has_next = True
                
                if not has_next and page > 1:
                    print("No next page found")
                    break
                
                page += 1
                time.sleep(0.5)  # Be respectful
                
                # If we found supervisors but no pagination, assume single page
                if found_on_page and not pagination:
                    break
                    
        except Exception as e:
            print(f"Error getting supervisor list: {e}")
        
        return supervisor_links
    
    def scrape_profile_page(self, name, url):
        """
        Scrapes individual supervisor profile page for email and research interests.
        """
        try:
            response = self.session.get(url, timeout=15)
            if response.status_code != 200:
                return {"Name": name, "Email": "", "Research Interest": "", "Profile URL": url}
            
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Extract email
            email = self.extract_email(soup)
            
            # Extract research interests
            research = self.extract_research_interests(soup)
            
            # If name not found in main list, try to extract from profile page
            profile_name = self.extract_name_from_profile(soup)
            if profile_name:
                name = profile_name
            
            return {
                "Name": name,
                "Email": email,
                "Research Interest": research,
                "Profile URL": url
            }
            
        except Exception as e:
            print(f"Error scraping profile {url}: {e}")
            return {"Name": name, "Email": "", "Research Interest": "", "Profile URL": url}
    
    def extract_email(self, soup):
        """
        Extracts email from profile page using multiple strategies.
        """
        # Strategy 1: Look for mailto links
        mailto_links = soup.find_all("a", href=re.compile(r"mailto:", re.I))
        for link in mailto_links:
            email = link.get("href", "").replace("mailto:", "").strip()
            if "@" in email:
                return email
        
        # Strategy 2: Look for email patterns in text
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        
        # Look in common email locations
        email_sections = soup.find_all(["div", "p", "span", "td"], 
                                      text=re.compile(r"email|e-mail|mail|contact", re.I))
        for section in email_sections:
            parent = section.parent if section.parent else section
            text = parent.get_text()
            emails = re.findall(email_pattern, text)
            if emails:
                return emails[0]
        
        # Strategy 3: Search entire page text
        page_text = soup.get_text()
        emails = re.findall(email_pattern, page_text)
        
        # Filter out common non-personal emails
        for email in emails:
            if not any(skip in email.lower() for skip in ['example', 'domain', 'your', 'email']):
                return email
        
        return ""
    
    def extract_research_interests(self, soup):
        """
        Extracts research interests from profile page.
        """
        research_interests = []
        
        # Keywords to look for
        research_keywords = [
            r"research\s*interest",
            r"research\s*area",
            r"research\s*field",
            r"research\s*direction",
            r"research\s*focus",
            r"research\s*topic",
            r"area.*of.*interest",
            r"field.*of.*study",
            r"专业|研究方向|研究领域|研究兴趣"  # Chinese keywords
        ]
        
        for keyword in research_keywords:
            # Find elements containing research keywords
            elements = soup.find_all(text=re.compile(keyword, re.I))
            
            for element in elements:
                parent = element.parent
                if not parent:
                    continue
                
                # Look for content after the heading
                content = ""
                
                # Check next sibling
                next_elem = parent.find_next_sibling()
                if next_elem:
                    if next_elem.name == "ul":
                        # List format
                        items = next_elem.find_all("li")
                        content = "; ".join([item.get_text().strip() for item in items])
                    elif next_elem.name in ["p", "div"]:
                        content = next_elem.get_text().strip()
                
                # Check within parent container
                if not content:
                    container = parent.parent
                    if container:
                        # Get all text after the keyword
                        full_text = container.get_text()
                        keyword_pos = full_text.lower().find(element.lower())
                        if keyword_pos != -1:
                            content = full_text[keyword_pos + len(element):].strip()
                            # Take first 500 characters or until next section
                            content = content[:500].split('\n\n')[0]
                
                if content and len(content) > 10:
                    research_interests.append(content)
        
        # Also look for div/section with class containing research
        research_divs = soup.find_all(["div", "section"], 
                                     class_=re.compile(r"research|interest", re.I))
        for div in research_divs:
            text = div.get_text().strip()
            if len(text) > 20 and len(text) < 1000:
                research_interests.append(text)
        
        # Clean and combine
        if research_interests:
            combined = "; ".join(research_interests)
            # Remove excessive whitespace
            combined = re.sub(r'\s+', ' ', combined)
            # Remove duplicate information
            combined = combined[:1000]  # Limit length
            return combined
        
        return ""
    
    def extract_name_from_profile(self, soup):
        """
        Extracts supervisor name from their profile page.
        """
        # Look for name in common locations
        selectors = [
            "h1.name",
            "h1.title",
            "h2.name",
            "div.teacher-name",
            "div.faculty-name",
            "div.profile-name",
            "h1",  # Any h1 as fallback
        ]
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                name = elem.get_text().strip()
                if self.is_potential_name(name):
                    return name
        
        return ""
    
    def is_potential_name(self, text):
        """
        Checks if text could be a person's name.
        """
        if not text or len(text) < 2 or len(text) > 100:
            return False
        
        # Skip if contains too many numbers or special characters
        if len(re.findall(r'[0-9]', text)) > 2:
            return False
        
        # Check for Chinese characters (names)
        if re.search(r'[\u4e00-\u9fff]{2,4}', text):
            return True
        
        # Check for English name patterns
        if re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)*$', text):
            return True
        
        # Check for academic titles
        if any(title in text for title in ["Prof", "Dr", "Professor"]):
            return True
        
        return False
    
    def explore_page_structure(self):
        """
        Helps debug by exploring the page structure.
        """
        try:
            response = self.session.get(self.supervisors_url)
            soup = BeautifulSoup(response.content, "html.parser")
            
            # Save for inspection
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(soup.prettify())
            
            print("\nPage structure saved to 'debug_page.html'")
            print("\nLooking for potential supervisor elements...")
            
            # Find all links
            links = soup.find_all("a", href=True)
            profile_links = []
            
            for link in links:
                href = link.get("href", "")
                text = link.get_text().strip()
                
                if text and len(text) > 1:
                    if any(pattern in href for pattern in ["/en/", "teacher", "faculty", "staff"]):
                        profile_links.append((text, href))
            
            if profile_links:
                print(f"\nFound {len(profile_links)} potential profile links:")
                for name, href in profile_links[:5]:
                    print(f"  - {name}: {href}")
            
        except Exception as e:
            print(f"Error exploring page: {e}")
    
    def dump_to_csv(self, filename="sjtu_supervisors.csv"):
        """
        Saves data to CSV file.
        """
        if self.list_of_dicts:
            df = pd.DataFrame(self.list_of_dicts)
            # Clean up the dataframe
            df = df.fillna("")
            df = df.drop_duplicates(subset=["Name"], keep="first")
            df.to_csv(filename, index=False, encoding='utf-8-sig')
            print(f"\nData saved to {filename}")
            print(f"Total records: {len(df)}")
        else:
            print("No data to save")
    
    def return_df(self):
        """
        Returns data as pandas DataFrame.
        """
        df = pd.DataFrame(self.list_of_dicts)
        if not df.empty:
            df = df.fillna("")
            df = df.drop_duplicates(subset=["Name"], keep="first")
        return df


# Main execution
if __name__ == "__main__":
    print("="*60)
    print("SJTU School of Life Sciences Supervisor Scraper")
    print("="*60)
    
    scraper = SJTULifeSciencesScraper()
    
    # Scrape data
    data = scraper.scrape_data()
    
    # Save to CSV
    scraper.dump_to_csv("sjtu_supervisors_complete.csv")
    
    # Display sample results
    df = scraper.return_df()
    if not df.empty:
        print("\n" + "="*60)
        print("Sample of scraped data:")
        print("="*60)
        
        # Show first 5 records with all details
        for i, row in df.head(5).iterrows():
            print(f"\n{i+1}. {row['Name']}")
            print(f"   Email: {row['Email']}")
            print(f"   Research: {row['Research Interest'][:100]}..." if len(row['Research Interest']) > 100 else f"   Research: {row['Research Interest']}")
            print(f"   URL: {row['Profile URL']}")
        
        print(f"\nTotal supervisors scraped: {len(df)}")
        
        # Statistics
        emails_found = df[df['Email'] != '']['Email'].count()
        research_found = df[df['Research Interest'] != '']['Research Interest'].count()
        
        print(f"Emails found: {emails_found}/{len(df)} ({emails_found*100/len(df):.1f}%)")
        print(f"Research interests found: {research_found}/{len(df)} ({research_found*100/len(df):.1f}%)")
    else:
        print("\nNo data was scraped.")
        print("Please check 'debug_page.html' for page structure.")