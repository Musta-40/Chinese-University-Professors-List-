#!/usr/bin/env python3
"""
Complete Faculty Profile Scraper with Research Interest Inference
Extracts: Name, Email, Research Interest (from publications), Profile URL
Optimized for low-RAM systems (6GB)
"""

import os
import re
import json
import time
import logging
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import Counter
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class ResearchInterestInferencer:
    """Infer research interests from publications without AI"""
    
    def __init__(self):
        # Comprehensive research keywords database
        self.research_domains = {
            'Cancer Research': [
                'cancer', 'tumor', 'tumour', 'oncology', 'carcinoma', 'malignant', 
                'metastasis', 'chemotherapy', 'anti-tumor', 'antitumor', 'neoplasm'
            ],
            'Drug Discovery & Pharmacology': [
                'drug', 'pharmacological', 'pharmaceutical', 'compound', 'bioactive',
                'therapeutic', 'medication', 'pharmacokinetic', 'drug delivery', 'formulation'
            ],
            'Traditional Chinese Medicine': [
                'traditional chinese medicine', 'TCM', 'herbal', 'natural product',
                'ethnopharmacology', 'chinese medicine', 'medicinal plant', 'herb',
                'traditional medicine', 'phytochemical'
            ],
            'Molecular Biology': [
                'molecular', 'gene', 'protein', 'DNA', 'RNA', 'cellular', 'cell',
                'biochemical', 'pathway', 'expression', 'signaling', 'mechanism'
            ],
            'Clinical Research': [
                'clinical', 'patient', 'treatment', 'therapy', 'diagnosis', 'trial',
                'therapeutic', 'efficacy', 'safety', 'clinical trial'
            ],
            'Analytical Chemistry': [
                'HPLC', 'chromatography', 'spectrometry', 'LC-MS', 'MS/MS', 'NMR',
                'analytical', 'separation', 'determination', 'quantification', 'analysis'
            ],
            'Metabolic Diseases': [
                'diabetes', 'metabolic', 'glucose', 'insulin', 'obesity', 'lipid',
                'metabolism', 'diabetic', 'glycemic', 'metabolic syndrome'
            ],
            'Cardiovascular Research': [
                'cardiovascular', 'cardiac', 'heart', 'vascular', 'blood pressure',
                'hypertension', 'arrhythmia', 'coronary', 'myocardial'
            ],
            'Neuroscience': [
                'neural', 'brain', 'neuron', 'cognitive', 'neurodegenerative',
                'nervous system', 'neurological', 'Alzheimer', 'Parkinson'
            ],
            'Natural Products Chemistry': [
                'extraction', 'isolation', 'bioactive compound', 'phytochemical',
                'natural product', 'plant extract', 'constituent', 'secondary metabolite'
            ]
        }
        
        # Common research methods
        self.research_methods = [
            'in vitro', 'in vivo', 'cell culture', 'animal model', 'mouse model',
            'clinical trial', 'randomized controlled', 'meta-analysis', 'systematic review',
            'high-throughput screening', 'molecular docking', 'computational',
            'bioinformatics', 'proteomics', 'genomics', 'metabolomics'
        ]
        
    def infer_from_publications(self, publications: List[str]) -> str:
        """
        Infer research interests from publication titles
        
        Args:
            publications: List of publication strings
            
        Returns:
            Inferred research interests string
        """
        if not publications:
            return "Not found"
        
        # Combine all publications for analysis
        combined_text = ' '.join(publications).lower()
        
        # Count domain matches
        domain_scores = {}
        for domain, keywords in self.research_domains.items():
            score = 0
            matched_keywords = []
            for keyword in keywords:
                if keyword.lower() in combined_text:
                    score += combined_text.count(keyword.lower())
                    matched_keywords.append(keyword)
            if score > 0:
                domain_scores[domain] = (score, matched_keywords[:3])
        
        # Sort domains by score
        top_domains = sorted(domain_scores.items(), key=lambda x: x[1][0], reverse=True)[:3]
        
        # Find research methods used
        found_methods = []
        for method in self.research_methods:
            if method.lower() in combined_text:
                found_methods.append(method)
        
        # Extract specific compounds or targets mentioned multiple times
        # Look for recurring capitalized terms
        all_words = []
        for pub in publications:
            # Extract potential compound/target names (capitalized words)
            words = re.findall(r'\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b', pub)
            all_words.extend(words)
        
        # Count frequency
        word_freq = Counter(all_words)
        
        # Filter common words and get specific terms
        common_words = {
            'The', 'This', 'These', 'Study', 'Research', 'Journal', 'Analysis',
            'Effect', 'Effects', 'Investigation', 'Development', 'Application',
            'Review', 'Report', 'Case', 'Clinical', 'New', 'Novel'
        }
        
        specific_compounds = []
        for word, count in word_freq.items():
            if count >= 2 and word not in common_words and len(word) > 3:
                # Check if it might be a compound/disease/target
                if any(char.isupper() for char in word[1:]) or '-' in word or word.endswith('ase') or word.endswith('in'):
                    specific_compounds.append(word)
        
        # Build research interest description
        research_parts = []
        
        # Add main research domains
        if top_domains:
            domain_names = [domain[0] for domain in top_domains[:2]]
            research_parts.append(f"Research focuses on {', '.join(domain_names)}")
        
        # Add specific compounds/targets if found
        if specific_compounds[:3]:
            research_parts.append(f"Specific interests include {', '.join(specific_compounds[:3])}")
        
        # Add methods if found
        if found_methods[:2]:
            research_parts.append(f"Using methods such as {', '.join(found_methods[:2])}")
        
        # If nothing specific found, provide general description
        if not research_parts:
            if 'chinese' in combined_text or 'herbal' in combined_text:
                return "Research in traditional Chinese medicine and natural products"
            elif 'cancer' in combined_text or 'tumor' in combined_text:
                return "Cancer research and anti-tumor drug development"
            elif 'clinical' in combined_text:
                return "Clinical pharmaceutical research"
            else:
                return "Pharmaceutical and biomedical research"
        
        return '. '.join(research_parts)


class CompleteFacultyProfileScraper:
    """
    Complete scraper for faculty profiles
    Extracts: Name, Email, Research Interest, Profile URL
    """
    
    def __init__(self):
        self.inferencer = ResearchInterestInferencer()
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        
    def extract_name(self, soup: BeautifulSoup) -> str:
        """
        Extract faculty name from the page
        
        Priority:
        1. <h3 align="center">Name</h3>
        2. <title>Name - Department</title>
        3. Meta description
        """
        # Method 1: Check h3 with center alignment (most common in sample)
        h3_center = soup.find('h3', {'align': 'center'})
        if h3_center:
            name = h3_center.get_text(strip=True)
            if name:
                logger.debug(f"Found name in h3 center: {name}")
                return name
        
        # Method 2: Check any h3 tag
        for h3 in soup.find_all('h3'):
            text = h3.get_text(strip=True)
            # Check if it looks like a name (Chinese or English)
            if re.match(r'^[\u4e00-\u9fff]{2,4}$', text) or re.match(r'^[A-Za-z\s\.]+$', text):
                logger.debug(f"Found name in h3: {text}")
                return text
        
        # Method 3: Extract from title tag
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            # Pattern: "Name-Department" or "Name - Department"
            if '-' in title_text:
                name = title_text.split('-')[0].strip()
                if name:
                    logger.debug(f"Found name in title: {name}")
                    return name
        
        # Method 4: Check meta description
        meta_desc = soup.find('meta', {'name': 'description'})
        if meta_desc and meta_desc.get('content'):
            content = meta_desc.get('content')
            # Try to extract name from beginning
            match = re.match(r'^([\u4e00-\u9fff]{2,4})', content)
            if match:
                return match.group(1)
        
        logger.warning("Could not extract name")
        return "Unknown"
    
    def extract_email(self, soup: BeautifulSoup) -> str:
        """
        Extract email address from the page
        
        Looks for patterns like:
        - Email: xxx@xxx.edu.cn
        - 邮箱：xxx@xxx.com
        - Any email pattern in text
        """
        # Get page text
        page_text = soup.get_text()
        
        # Email patterns to search for
        email_patterns = [
            # With label
            r'(?:Email|E-mail|邮箱|电子邮箱)[：:\s]*([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})',
            # Educational emails
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.edu\.cn)',
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.edu)',
            # General email pattern
            r'([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
        ]
        
        for pattern in email_patterns:
            matches = re.findall(pattern, page_text, re.IGNORECASE)
            for match in matches:
                email = match if isinstance(match, str) else match[0]
                # Filter out generic/department emails
                if not any(x in email.lower() for x in ['student', 'department', 'office', 'admin', 'webmaster']):
                    # Additional validation
                    if '@' in email and '.' in email.split('@')[1]:
                        logger.debug(f"Found email: {email}")
                        return email
        
        logger.warning("Could not extract email")
        return "Not found"
    
    def extract_publications(self, soup: BeautifulSoup) -> List[str]:
        """
        Extract publication list from the page
        
        Looks for numbered lists or publication patterns
        """
        publications = []
        
        # Find the content area
        content_div = soup.find('div', class_='v_news_content')
        if not content_div:
            content_div = soup.find('div', class_='nwdtl_con')
        if not content_div:
            content_div = soup
        
        # Look for publication patterns
        for elem in content_div.find_all(['p', 'li']):
            text = elem.get_text(strip=True)
            
            # Pattern 1: Numbered publications (1. Author, Title, Journal, Year)
            if re.match(r'^\d+[\.KATEX_INLINE_CLOSE]\s*\w', text):
                # Remove the number
                pub = re.sub(r'^\d+[\.KATEX_INLINE_CLOSE]\s*', '', text)
                # Remove impact factor notes
                pub = re.sub(r'KATEX_INLINE_OPENIF[^)]*KATEX_INLINE_CLOSE', '', pub)
                # Remove PMID/DOI
                pub = re.sub(r'PMID:?\s*\d+', '', pub)
                pub = re.sub(r'DOI:?\s*[\S]+', '', pub)
                # Clean whitespace
                pub = ' '.join(pub.split())
                
                if len(pub) > 30:  # Reasonable length for a publication
                    publications.append(pub)
            
            # Pattern 2: Look for journal names or years as indicators
            elif any(year in text for year in ['2020', '2021', '2022', '2023', '2024']):
                if any(journal_word in text.lower() for journal_word in ['journal', 'nature', 'science', 'cell', 'medicine']):
                    # Clean the publication text
                    pub = re.sub(r'KATEX_INLINE_OPENIF[^)]*KATEX_INLINE_CLOSE', '', text)
                    pub = ' '.join(pub.split())
                    if len(pub) > 30:
                        publications.append(pub)
        
        logger.debug(f"Found {len(publications)} publications")
        return publications
    
    def scrape_profile(self, url: str) -> Dict[str, str]:
        """
        Scrape a single faculty profile
        
        Args:
            url: Profile URL
            
        Returns:
            Dictionary with name, email, research_interest, profile_link
        """
        logger.info(f"Scraping: {url}")
        
        result = {
            'name': 'Unknown',
            'email': 'Not found',
            'research_interest': 'Not found',
            'profile_link': url
        }
        
        try:
            # Fetch page
            response = self.session.get(url, timeout=15)
            response.encoding = response.apparent_encoding or 'utf-8'
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract name
            result['name'] = self.extract_name(soup)
            
            # Extract email
            result['email'] = self.extract_email(soup)
            
            # Extract publications
            publications = self.extract_publications(soup)
            
            # Infer research interests from publications
            if publications:
                result['research_interest'] = self.inferencer.infer_from_publications(publications)
                logger.info(f"Inferred research interest from {len(publications)} publications")
            else:
                result['research_interest'] = "Not found (no publications available)"
            
            logger.info(f"Successfully scraped: {result['name']}")
            
        except requests.RequestException as e:
            logger.error(f"Network error for {url}: {e}")
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
        
        return result
    
    def scrape_batch(self, urls: List[str], output_file: str = 'output.txt', 
                     json_output: bool = True, delay: float = 1.0):
        """
        Scrape multiple faculty profiles
        
        Args:
            urls: List of profile URLs
            output_file: Output text file path
            json_output: Whether to also save as JSON
            delay: Delay between requests in seconds
        """
        results = []
        total = len(urls)
        
        # Open output file
        with open(output_file, 'w', encoding='utf-8') as f:
            for i, url in enumerate(urls, 1):
                logger.info(f"Processing {i}/{total}")
                
                # Scrape profile
                profile = self.scrape_profile(url)
                results.append(profile)
                
                # Write to text file immediately
                f.write(f"Name: {profile['name']}\n")
                f.write(f"Email: {profile['email']}\n")
                f.write(f"Research interest: {profile['research_interest']}\n")
                f.write(f"Profile link: {profile['profile_link']}\n")
                f.write("-" * 50 + "\n\n")
                f.flush()
                
                # Progress update
                if i % 10 == 0:
                    logger.info(f"Progress: {i}/{total} profiles completed")
                
                # Respectful delay
                if i < total:
                    time.sleep(delay)
        
        # Save JSON if requested
        if json_output:
            json_file = output_file.replace('.txt', '.json')
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(results, f, ensure_ascii=False, indent=2)
            logger.info(f"JSON output saved to {json_file}")
        
        # Print summary
        logger.info("\n" + "="*50)
        logger.info("SCRAPING COMPLETE")
        logger.info("="*50)
        logger.info(f"Total profiles: {total}")
        logger.info(f"Profiles with names: {sum(1 for r in results if r['name'] != 'Unknown')}")
        logger.info(f"Profiles with emails: {sum(1 for r in results if r['email'] != 'Not found')}")
        logger.info(f"Profiles with research: {sum(1 for r in results if 'Not found' not in r['research_interest'])}")
        logger.info(f"Output saved to: {output_file}")
        
        return results


def main():
    """Main function with command-line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Faculty Profile Scraper with Research Interest Inference',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scraper.py --input urls.txt --output results.txt
  python scraper.py --test-url "http://example.edu.cn/faculty/profile.html"
  python scraper.py --input urls.txt --delay 2.0 --json
        """
    )
    
    parser.add_argument('--input', '-i', help='Input file containing URLs (one per line)')
    parser.add_argument('--output', '-o', default='faculty_profiles.txt', help='Output file path')
    parser.add_argument('--test-url', help='Test with a single URL')
    parser.add_argument('--json', action='store_true', help='Also save output as JSON')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests (seconds)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Create scraper instance
    scraper = CompleteFacultyProfileScraper()
    
    # Test mode
    if args.test_url:
        print(f"\nTesting with URL: {args.test_url}\n")
        result = scraper.scrape_profile(args.test_url)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    
    # Batch mode
    if args.input:
        if not os.path.exists(args.input):
            print(f"Error: Input file '{args.input}' not found")
            return
        
        # Read URLs
        with open(args.input, 'r', encoding='utf-8') as f:
            urls = [line.strip() for line in f if line.strip()]
        
        if not urls:
            print("Error: No URLs found in input file")
            return
        
        print(f"\nFound {len(urls)} URLs to process")
        print(f"Output will be saved to: {args.output}")
        print(f"Starting scraping with {args.delay}s delay between requests...\n")
        
        # Scrape profiles
        scraper.scrape_batch(urls, args.output, json_output=args.json, delay=args.delay)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()