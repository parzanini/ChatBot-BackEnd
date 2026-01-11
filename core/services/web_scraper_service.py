"""Web Scraper Service - Extract links from web pages

This module provides functionality to extract all sub-links from a given URL.
"""

from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup


# URLs to scrape for sub-links
URLS_TO_SCRAPE = [
    "https://tus.ie/admissions/midwest/",
    "https://tus.ie/courses/",
]


def extract_links(url):
    """
    Extract all sub-links from a given URL.

    This function:
    1. Fetches the web page
    2. Parses the HTML
    3. Extracts all href attributes
    4. Filters to internal links only (same domain)
    5. Filters to only sub-links under the requested path
    6. Removes duplicates
    7. Returns a sorted list of URLs

    Args:
        url (str): The starting URL (e.g., "https://tus.ie/courses/")

    Returns:
        list: Array of sub-links found on the page.
              Only returns links under the same path, not sibling pages.
              Returns empty list if page cannot be fetched.
    """
    try:
        # Parse the base URL to get the domain and path
        parsed_base = urlparse(url)
        base_domain = parsed_base.netloc  # e.g., "tus.ie"
        base_path = parsed_base.path.rstrip('/')  # e.g., "/courses" (remove trailing slash)

        # Fetch the web page with timeout
        print(f"Fetching page: {url}")
        response = requests.get(url, timeout=10)
        response.raise_for_status()  # Raise error if status code is not 200

        # Parse the HTML content
        soup = BeautifulSoup(response.content, 'html.parser')

        # Find all <a> tags
        links = set()  # Use set to automatically remove duplicates
        for link in soup.find_all('a', href=True):
            href = link['href']

            # Convert relative URLs to absolute URLs
            absolute_url = urljoin(url, href)

            # Parse the absolute URL
            parsed_url = urlparse(absolute_url)

            # Only include links from the same domain
            if parsed_url.netloc == base_domain:
                # Get the path and remove trailing slash for comparison
                link_path = parsed_url.path.rstrip('/')

                # Only include if the link path starts with the base path
                # and is not the base path itself
                # This ensures we only get sub-links, not sibling pages
                if link_path.startswith(base_path) and link_path != base_path:
                    # Remove fragment identifiers (e.g., #section)
                    clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                    if parsed_url.query:
                        clean_url += f"?{parsed_url.query}"

                    links.add(clean_url)

        # Convert set to sorted list
        sorted_links = sorted(list(links))

        print(f"Found {len(sorted_links)} unique sub-links under {base_path}")
        return sorted_links

    except requests.exceptions.RequestException as error:
        # Network or HTTP error
        print(f"Error fetching URL: {error}")
        return []

    except Exception as error:
        # Any other error
        print(f"Error extracting links: {error}")
        return []


def extract_all_configured_links():
    """
    Extract all sub-links from all configured URLs in URLS_TO_SCRAPE.

    Returns:
        dict: Dictionary with URL as key and list of links as value.
              Example: {
                  "https://tus.ie/admissions/midwest/": [...links...],
                  "https://tus.ie/courses/": [...links...]
              }
    """
    all_links = {}

    for url in URLS_TO_SCRAPE:
        print(f"\nProcessing: {url}")
        links = extract_links(url)
        all_links[url] = links

    return all_links


