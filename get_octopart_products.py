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
MAX_WORKERS = 8

def fetch_and_parse_sitemap(url, headless_mode=True):
    """
    Worker function: Launches a browser, fetches a sitemap URL, waits for it to load,
    parses the content, and returns a list of URLs.
    """
    options = uc.ChromeOptions()
    if headless_mode:
        options.add_argument('--headless')
        
    driver = None
    try:
        driver = uc.Chrome(options=options)
        driver.get(url)
        
        # --- MODIFIED: Increased timeout to 4 minutes (240 seconds) ---
        wait = WebDriverWait(driver, 240)
        wait.until(EC.presence_of_element_located((By.TAG_NAME, "loc")))
        
        page_content = driver.page_source

        # Parse the content directly in the worker
        if not page_content:
            return []
        soup = BeautifulSoup(page_content, 'lxml')
        loc_tags = soup.find_all('loc')
        return [tag.text for tag in loc_tags]

    except TimeoutException:
        # --- ADDED: Better error logging ---
        # This will now show up in the GitHub Actions log if a specific URL fails.
        print(f"\n[WORKER TIMEOUT] Timed out waiting for content on: {url}")
        return []
    except Exception as e:
        print(f"\n[WORKER ERROR] An unexpected error occurred for {url}: {e}")
        return []
    finally:
        if driver:
            driver.quit()

# --- Main execution block ---
if __name__ == "__main__":
    start_time = time.time()
    
    # --- Step 1: Fetch the main sitemap index (with a VISIBLE browser) ---
    print("--- Step 1: Fetching main sitemap index (visible browser in virtual display) ---")
    # Using a list comprehension to get the result from the single call
    sub_sitemaps = fetch_and_parse_sitemap(SITEMAP_INDEX_URL, headless_mode=False)
    
    if not sub_sitemaps:
        print("\nCRITICAL ERROR: Script failed to retrieve or parse the main sitemap index.")
        exit()
        
    print(f"-> Success! Found {len(sub_sitemaps)} sub-sitemap URLs.")
    
    all_product_urls = set()

    # --- Step 2: Concurrently process all sub-sitemaps (in HEADLESS mode) ---
    print(f"\n--- Step 2: Processing {len(sub_sitemaps)} sub-sitemaps with {MAX_WORKERS} workers ---")
    
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_url = {executor.submit(fetch_and_parse_sitemap, url, headless_mode=True): url for url in sub_sitemaps}
        
        for future in tqdm(as_completed(future_to_url), total=len(sub_sitemaps), desc="Processing Sitemaps"):
            try:
                urls_from_sitemap = future.result()
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
