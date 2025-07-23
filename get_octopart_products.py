import time
import os
from tqdm import tqdm

# HTML/XML parsing
from bs4 import BeautifulSoup

# The stealthy chromedriver
import undetected_chromedriver as uc

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

# Concurrency
from concurrent.futures import ThreadPoolExecutor, as_completed

# --- Configuration ---
SITEMAP_INDEX_URL = 'https://octopart.com/product-sitemap-index.xml'
OUTPUT_FILE = 'octopart_product_urls.txt'
# Number of concurrent browsers to run. 
# 8 is a good starting point. Adjust based on your PC's performance.
MAX_WORKERS = 8

def fetch_page_with_uc(url, headless_mode=True):
    """
    Uses undetected_chromedriver to fetch page content.
    Can run in either headless (invisible) or headful (visible) mode.
    """
    options = uc.ChromeOptions()
    if headless_mode:
        options.add_argument('--headless')
        
    driver = None
    try:
        driver = uc.Chrome(options=options)
        driver.get(url)
        
        # Wait up to 60 seconds for a <loc> tag to appear.
        wait = WebDriverWait(driver, 60)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "loc")))
        
        page_content = driver.page_source
        return page_content

    except Exception:
        # If any error occurs (timeout, etc.), it will fail gracefully for this one URL.
        return None
    finally:
        if driver:
            driver.quit()

def parse_urls_from_sitemap_content(page_content):
    """Parses page content to extract URLs from <loc> tags."""
    if not page_content:
        return []
    try:
        soup = BeautifulSoup(page_content, 'lxml')
        loc_tags = soup.find_all('loc')
        return [tag.text for tag in loc_tags]
    except Exception:
        return []

# --- Main execution block ---
if __name__ == "__main__":
    start_time = time.time()
    
    # --- Step 1: Fetch the main sitemap index (with a VISIBLE browser to be safe) ---
    print("--- Step 1: Fetching main sitemap index (visible browser) ---")
    index_page_content = fetch_page_with_uc(SITEMAP_INDEX_URL, headless_mode=False)
    
    if not index_page_content:
        print("\nCRITICAL ERROR: Script failed to retrieve the main sitemap index.")
        print("This could be a network issue or a change in the website's protection.")
        exit()
        
    sub_sitemaps = parse_urls_from_sitemap_content(index_page_content)
    
    if not sub_sitemaps:
        print("Page was retrieved, but no sub-sitemap URLs (<loc> tags) were found.")
        exit()

    print(f"-> Success! Found {len(sub_sitemaps)} sub-sitemap URLs.")
    
    all_product_urls = set()

    # --- Step 2: Concurrently process all sub-sitemaps (in HEADLESS mode for speed) ---
    print(f"\n--- Step 2: Processing {len(sub_sitemaps)} sub-sitemaps with {MAX_WORKERS} workers ---")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        # Submit subsequent, easier requests in headless mode
        future_to_url = {executor.submit(fetch_page_with_uc, url, headless_mode=True): url for url in sub_sitemaps}
        
        for future in tqdm(as_completed(future_to_url), total=len(sub_sitemaps), desc="Processing Sitemaps"):
            try:
                sitemap_content = future.result()
                urls_from_sitemap = parse_urls_from_sitemap_content(sitemap_content)
                if urls_from_sitemap:
                    all_product_urls.update(urls_from_sitemap)
            except Exception as e:
                print(f"A task generated an exception: {e}")

    # --- Step 3: Save the final results ---
    print(f"\nAll sitemaps processed. Found {len(all_product_urls):,} unique product URLs.")
    print(f"Saving results to '{OUTPUT_FILE}'...")
    
    sorted_urls = sorted(list(all_product_urls))
    
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        for url in sorted_urls:
            f.write(url + '\n')
            
    end_time = time.time()

    print("\n" + "="*40)
    print("        Extraction Complete!")
    print("="*40)
    print(f"Total unique product URLs found: {len(sorted_urls):,}")
    print(f"Results saved to '{OUTPUT_FILE}'.")
    print(f"Total time taken: {end_time - start_time:.2f} seconds.")
    print("="*40)
