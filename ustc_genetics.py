import requests
from bs4 import BeautifulSoup
import time
import csv
import json
import re
from urllib.parse import urljoin
from datetime import datetime

class GeneticsFacultyCrawler:
    """Crawler for USTC Genetics Faculty Page"""
    
    def __init__(self):
        self.base_url = "https://enbiomed.ustc.edu.cn/Genetics/list.htm"
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        self.professors = []
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        
    def get_main_page_data(self):
        """Extract professor names and profile links from main page"""
        professors = []
        
        try:
            print(f"Fetching main page: {self.base_url}")
            response = self.session.get(self.base_url, timeout=15)
            response.raise_for_status()
            response.encoding = 'utf-8'  # Ensure proper encoding
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find all bio-cards
            bio_cards = soup.find_all('div', class_='bio-card')
            
            if not bio_cards:
                # Try alternative selectors if bio-card not found
                print("No bio-cards found, trying alternative selectors...")
                # Look for faculty list items
                faculty_items = soup.find_all('div', class_=['faculty-item', 'professor-card', 'staff-item'])
                if faculty_items:
                    bio_cards = faculty_items
            
            print(f"Found {len(bio_cards)} faculty cards on the page")
            
            for card in bio_cards:
                professor_data = {}
                
                # Get name - try multiple selectors
                name = None
                for selector in ['div.name', 'h3', 'h4', '.faculty-name', '.professor-name']:
                    name_elem = card.select_one(selector)
                    if name_elem:
                        name = name_elem.text.strip()
                        break
                
                if not name:
                    # Try getting text from anchor tag
                    link = card.find('a')
                    if link and link.text:
                        name = link.text.strip()
                
                if name:
                    professor_data['name'] = name
                
                # Get profile link
                link_tag = card.find('a')
                if link_tag and link_tag.get('href'):
                    profile_link = link_tag['href']
                    if profile_link.startswith('http'):
                        professor_data['profile_link'] = profile_link
                    else:
                        professor_data['profile_link'] = urljoin(self.base_url, profile_link)
                
                # Get title/position
                title = None
                for selector in ['div.title', '.faculty-title', '.position', 'p']:
                    title_elem = card.select_one(selector)
                    if title_elem:
                        title_text = title_elem.text.strip()
                        if title_text and title_text != name:  # Make sure it's not the name again
                            title = title_text
                            break
                
                if title:
                    professor_data['title'] = title
                
                # Get department info if available
                dept_elem = card.select_one('.department, .dept')
                if dept_elem:
                    professor_data['department'] = dept_elem.text.strip()
                
                if professor_data.get('name') and professor_data.get('profile_link'):
                    professors.append(professor_data)
                    
        except requests.exceptions.RequestException as e:
            print(f"Network error fetching main page: {e}")
        except Exception as e:
            print(f"Error parsing main page: {e}")
            import traceback
            traceback.print_exc()
        
        return professors
    
    def extract_email(self, soup, text):
        """Extract email from soup or text"""
        email = ''
        
        # Email regex pattern
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        
        # Method 1: Search in entire text
        emails = re.findall(email_pattern, text)
        if emails:
            # Prefer USTC emails
            for e in emails:
                if 'ustc.edu.cn' in e.lower():
                    return e
            # Return first valid email if no USTC email found
            for e in emails:
                if not any(x in e.lower() for x in ['example', 'domain', 'test', 'email@']):
                    return e
        
        # Method 2: Look for email in specific contexts
        email_contexts = [
            'email:', 'e-mail:', 'mail:', 'contact:', 
            '邮箱:', '电子邮件:', '联系方式:'
        ]
        
        for context in email_contexts:
            if context in text.lower():
                # Find text after the context word
                idx = text.lower().index(context)
                snippet = text[idx:idx+100]
                emails = re.findall(email_pattern, snippet)
                if emails:
                    return emails[0]
        
        # Method 3: Look in mailto links
        mailto_links = soup.find_all('a', href=re.compile(r'^mailto:'))
        if mailto_links:
            email = mailto_links[0]['href'].replace('mailto:', '').strip()
            if '@' in email:
                return email.split('?')[0]  # Remove any query parameters
        
        return email
    
    def extract_research_interests(self, soup, text):
        """Extract research interests from soup or text"""
        research = ''
        
        # Research keywords to look for
        research_keywords = [
            'research interest', 'research direction', 'research area',
            'research focus', 'research field', 'current research',
            'research topic', 'research work', 'scientific interest',
            'area of expertise', 'research program', 'research project',
            '研究方向', '研究兴趣', '研究领域', '主要研究'
        ]
        
        # Method 1: Look for research sections
        for keyword in research_keywords:
            # Case-insensitive search
            pattern = re.compile(keyword, re.IGNORECASE)
            
            # Search in headings
            for heading in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'strong', 'b']):
                if heading.text and pattern.search(heading.text):
                    # Get content after heading
                    content = []
                    
                    # Check next siblings
                    for sibling in heading.find_next_siblings()[:5]:
                        if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5']:
                            break  # Stop at next heading
                        
                        text_content = sibling.text.strip()
                        if text_content:
                            # Check if it's a list
                            if sibling.name in ['ul', 'ol']:
                                items = sibling.find_all('li')
                                for item in items[:10]:  # Limit to 10 items
                                    content.append(f"• {item.text.strip()}")
                            else:
                                content.append(text_content)
                    
                    if content:
                        research = '\n'.join(content)[:1000]  # Limit length
                        if len(research) > 50:  # Make sure we have substantial content
                            return research
            
            # Search in divs/sections
            for div in soup.find_all(['div', 'section']):
                if div.text and pattern.search(div.text):
                    # Extract the research content
                    lines = div.text.split('\n')
                    for i, line in enumerate(lines):
                        if pattern.search(line):
                            # Get next few lines as research description
                            research_lines = []
                            for j in range(i+1, min(i+10, len(lines))):
                                line_text = lines[j].strip()
                                if line_text and len(line_text) > 10:
                                    research_lines.append(line_text)
                            
                            if research_lines:
                                research = '\n'.join(research_lines)[:1000]
                                if len(research) > 50:
                                    return research
        
        # Method 2: Look for numbered or bulleted lists after research keyword
        research_sections = soup.find_all(text=re.compile(r'research|研究', re.IGNORECASE))
        for section in research_sections:
            parent = section.parent
            if parent:
                next_list = parent.find_next_sibling(['ul', 'ol'])
                if next_list:
                    items = next_list.find_all('li')
                    if items:
                        research_items = [f"• {item.text.strip()}" for item in items[:10]]
                        research = '\n'.join(research_items)[:1000]
                        if len(research) > 50:
                            return research
        
        return research
    
    def get_professor_details(self, profile_url):
        """Extract email and research interests from individual profile page"""
        details = {
            'email': '',
            'research_interests': '',
            'phone': '',
            'office': ''
        }
        
        try:
            print(f"  → Fetching profile: {profile_url}")
            response = self.session.get(profile_url, timeout=15)
            response.raise_for_status()
            response.encoding = 'utf-8'
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Get page text
            page_text = soup.get_text()
            
            # Extract email
            details['email'] = self.extract_email(soup, page_text)
            
            # Extract research interests
            details['research_interests'] = self.extract_research_interests(soup, page_text)
            
            # Extract phone number (optional)
            phone_pattern = r'(?:phone|tel|电话)[:\s]*([+\d\s\-KATEX_INLINE_OPENKATEX_INLINE_CLOSE]+)'
            phone_match = re.search(phone_pattern, page_text, re.IGNORECASE)
            if phone_match:
                details['phone'] = phone_match.group(1).strip()
            
            # Extract office location (optional)
            office_pattern = r'(?:office|room|办公室)[:\s]*([^\n]{3,50})'
            office_match = re.search(office_pattern, page_text, re.IGNORECASE)
            if office_match:
                details['office'] = office_match.group(1).strip()
                
        except requests.exceptions.RequestException as e:
            print(f"  ✗ Network error: {e}")
        except Exception as e:
            print(f"  ✗ Error processing profile: {e}")
        
        return details
    
    def crawl(self):
        """Main crawling function"""
        print("\n" + "="*70)
        print(" GENETICS FACULTY CRAWLER - USTC ")
        print("="*70)
        print(f"Target: {self.base_url}")
        print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70 + "\n")
        
        # Step 1: Get main page data
        print("STEP 1: Fetching faculty list...")
        print("-"*40)
        self.professors = self.get_main_page_data()
        
        if not self.professors:
            print("✗ No professors found on the main page.")
            return
        
        print(f"✓ Found {len(self.professors)} professors\n")
        
        # Step 2: Get individual profiles
        print("STEP 2: Fetching individual profiles...")
        print("-"*40)
        
        for i, prof in enumerate(self.professors, 1):
            print(f"\n[{i}/{len(self.professors)}] {prof.get('name', 'Unknown')}")
            
            if prof.get('profile_link'):
                details = self.get_professor_details(prof['profile_link'])
                prof.update(details)
                
                # Display what was found
                status = []
                if details['email']:
                    status.append(f"✓ Email: {details['email']}")
                else:
                    status.append("✗ Email: Not found")
                
                if details['research_interests']:
                    status.append(f"✓ Research: {len(details['research_interests'])} chars")
                else:
                    status.append("✗ Research: Not found")
                
                for s in status:
                    print(f"  {s}")
                
                # Rate limiting
                time.sleep(1)
            else:
                print("  ✗ No profile link available")
        
        return self.professors
    
    def save_to_csv(self, filename='genetics_faculty.csv'):
        """Save data to CSV file"""
        if not self.professors:
            return
        
        fieldnames = ['name', 'title', 'department', 'email', 'phone', 'office', 
                     'profile_link', 'research_interests']
        
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for prof in self.professors:
                row = {field: prof.get(field, '') for field in fieldnames}
                writer.writerow(row)
        
        print(f"\n✓ CSV saved: {filename}")
    
    def save_to_json(self, filename='genetics_faculty.json'):
        """Save data to JSON file"""
        if not self.professors:
            return
        
        with open(filename, 'w', encoding='utf-8') as jsonfile:
            json.dump(self.professors, jsonfile, ensure_ascii=False, indent=2)
        
        print(f"✓ JSON saved: {filename}")
    
    def save_to_html(self, filename='genetics_faculty.html'):
        """Save data to HTML file for easy viewing"""
        if not self.professors:
            return
        
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Genetics Faculty - USTC</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f5f5f5;
        }
        h1 {
            color: #333;
            border-bottom: 3px solid #0066cc;
            padding-bottom: 10px;
        }
        .professor-card {
            background: white;
            border-radius: 8px;
            padding: 20px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .professor-name {
            font-size: 1.4em;
            font-weight: bold;
            color: #0066cc;
            margin-bottom: 10px;
        }
        .professor-title {
            color: #666;
            margin-bottom: 15px;
            font-style: italic;
        }
        .info-row {
            margin: 8px 0;
            display: flex;
            align-items: flex-start;
        }
        .info-label {
            font-weight: bold;
            min-width: 120px;
            color: #555;
        }
        .info-value {
            flex: 1;
            color: #333;
        }
        .research-interests {
            background: #f9f9f9;
            padding: 10px;
            border-left: 3px solid #0066cc;
            margin-top: 10px;
            white-space: pre-line;
        }
        a {
            color: #0066cc;
            text-decoration: none;
        }
        a:hover {
            text-decoration: underline;
        }
        .timestamp {
            text-align: center;
            color: #999;
            margin-top: 30px;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <h1>Genetics Faculty - USTC</h1>
    <p>Total: """ + str(len(self.professors)) + """ professors</p>
"""
        
        for prof in self.professors:
            html += f"""
    <div class="professor-card">
        <div class="professor-name">{prof.get('name', 'N/A')}</div>
        <div class="professor-title">{prof.get('title', '')}</div>
        """
            
            if prof.get('department'):
                html += f"""
        <div class="info-row">
            <span class="info-label">Department:</span>
            <span class="info-value">{prof['department']}</span>
        </div>"""
            
            if prof.get('email'):
                html += f"""
        <div class="info-row">
            <span class="info-label">Email:</span>
            <span class="info-value"><a href="mailto:{prof['email']}">{prof['email']}</a></span>
        </div>"""
            
            if prof.get('phone'):
                html += f"""
        <div class="info-row">
            <span class="info-label">Phone:</span>
            <span class="info-value">{prof['phone']}</span>
        </div>"""
            
            if prof.get('office'):
                html += f"""
        <div class="info-row">
            <span class="info-label">Office:</span>
            <span class="info-value">{prof['office']}</span>
        </div>"""
            
            if prof.get('profile_link'):
                html += f"""
        <div class="info-row">
            <span class="info-label">Profile:</span>
            <span class="info-value"><a href="{prof['profile_link']}" target="_blank">View Profile</a></span>
        </div>"""
            
            if prof.get('research_interests'):
                html += f"""
        <div class="info-row">
            <span class="info-label">Research:</span>
            <span class="info-value">
                <div class="research-interests">{prof['research_interests']}</div>
            </span>
        </div>"""
            
            html += """
    </div>"""
        
        html += f"""
    <div class="timestamp">Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
</body>
</html>"""
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(html)
        
        print(f"✓ HTML saved: {filename}")
    
    def display_summary(self):
        """Display summary of crawled data"""
        print("\n" + "="*70)
        print(" CRAWLING SUMMARY ")
        print("="*70)
        
        total = len(self.professors)
        with_email = sum(1 for p in self.professors if p.get('email'))
        with_research = sum(1 for p in self.professors if p.get('research_interests'))
        with_phone = sum(1 for p in self.professors if p.get('phone'))
        with_office = sum(1 for p in self.professors if p.get('office'))
        
        print(f"\nTotal professors: {total}")
        print(f"With email: {with_email}/{total} ({with_email*100//total if total else 0}%)")
        print(f"With research info: {with_research}/{total} ({with_research*100//total if total else 0}%)")
        print(f"With phone: {with_phone}/{total} ({with_phone*100//total if total else 0}%)")
        print(f"With office: {with_office}/{total} ({with_office*100//total if total else 0}%)")
        
        print("\n" + "-"*70)
        print(" FACULTY LIST ")
        print("-"*70)
        
        for i, prof in enumerate(self.professors, 1):
            print(f"\n{i}. {prof.get('name', 'N/A')}")
            if prof.get('title'):
                print(f"   Position: {prof['title']}")
            if prof.get('email'):
                print(f"   Email: {prof['email']}")
            if prof.get('research_interests'):
                research = prof['research_interests']
                if len(research) > 100:
                    print(f"   Research: {research[:100]}...")
                else:
                    print(f"   Research: {research}")

def main():
    """Main execution function"""
    try:
        # Create crawler instance
        crawler = GeneticsFacultyCrawler()
        
        # Run the crawler
        crawler.crawl()
        
        # Display summary
        crawler.display_summary()
        
        # Save data in multiple formats
        print("\n" + "="*70)
        print(" SAVING DATA ")
        print("="*70)
        
        crawler.save_to_csv()
        crawler.save_to_json()
        crawler.save_to_html()
        
        print("\n" + "="*70)
        print(" ✓ CRAWLING COMPLETED SUCCESSFULLY ")
        print("="*70)
        
    except KeyboardInterrupt:
        print("\n\n⚠ Crawling interrupted by user.")
    except Exception as e:
        print(f"\n\n✗ Fatal error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()