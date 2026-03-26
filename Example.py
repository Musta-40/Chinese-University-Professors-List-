# run_scraper.py
from faculty_scraper.FacultyScraper import FacultyScraper

# example target (repository's example)
url = "https://scbb.pkusz.edu.cn/szdw.htm"

scraper = FacultyScraper(url)
data = scraper.scrape_data()           # run main scraping routine
scraper.dump_to_csv("faculty_data.csv")  # save the results
print(f"Scraped {len(data)} records. Saved to faculty_data.csv")
