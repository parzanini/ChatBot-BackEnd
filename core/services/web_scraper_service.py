"""Web Scraper Service - Extract links from web pages

This module provides functionality to extract all sub-links from a given URL.
For courses, it handles pagination by looping through sf_paged parameter.
"""

from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup


def extract_all_links():
    """
    Extract all sub-links from configured TUS URLs.

    Processes:
    - https://tus.ie/admissions/midwest/ (single page)
    - https://tus.ie/courses/ (70 paginated pages) - TUS has around 50 paginated pages for courses, but I'm using 70 to have a margin.

    Returns:
        A list of links found under each base URL
              Example: {
                  "https://tus.ie/admissions/midwest/": [...links...],
                  "https://tus.ie/courses/": [...links...]
              }
    """
    # URLs to scrape - can be extended in the future
    urls_config = [
        "https://tus.ie/admissions/midwest/",
        "https://tus.ie/courses/",
    ]

    result = {} # Store results here

    for base_url in urls_config: # Loop through each base URL
        print(f"\n{'='*60}")
        print(f"Processing: {base_url}")
        print('='*60)

        all_links = set() # Using a set to avoid duplicates
        parsed_base = urlparse(base_url) # Parse the base URL, so we can compare domains and paths
        base_domain = parsed_base.netloc  # e.g., "tus.ie"
        base_path = parsed_base.path.rstrip('/') # e.g., "/courses"

        # Determine URLs to fetch
        urls_to_fetch = []
        if base_path == "/courses":
            print(f"Pagination detected. Looping through pages 1-70...")
            for page_num in range(1, 71):
                urls_to_fetch.append(f"https://tus.ie/courses/?results-id=751&view-mode=table&sf_paged={page_num}")
        else:
            urls_to_fetch.append(base_url)

        # Fetch and extract links from all URLs
        for current_url in urls_to_fetch:
            try:
                print(f"Fetching: {current_url}")
                response = requests.get(current_url, timeout=10)
                response.raise_for_status()

                soup = BeautifulSoup(response.content, 'html.parser') # Using beautifulsoup4 to parse HTML

                for link in soup.find_all('a', href=True): # Find all anchor tags with href attribute
                    href = link['href']
                    absolute_url = urljoin(current_url, href)
                    parsed_url = urlparse(absolute_url)

                    if parsed_url.netloc == base_domain: # If the link is within the same domain, then process it
                        link_path = parsed_url.path.rstrip('/')

                        if not link_path:
                            continue

                        if link_path.startswith(base_path) and link_path != base_path: # Only sub-links under the base path
                            clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}" # Rebuild URL without fragments, that means no #section - example.com/page#section
                            if parsed_url.query:
                                clean_url += f"?{parsed_url.query}"
                            all_links.add(clean_url)

            except requests.exceptions.RequestException as error:
                print(f"Error fetching {current_url}: {error}")
            except Exception as error:
                print(f"Error processing {current_url}: {error}")

        sorted_links = sorted(list(all_links))
        result[base_url] = sorted_links
        print(f"\nFound {len(sorted_links)} unique sub-links under {base_path}")

    return result


