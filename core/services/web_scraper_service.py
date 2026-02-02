"""Web Scraper Service - Extract links from web pages

This module provides functionality to extract all sub-links from a given URL.
For courses, it handles pagination by looping through sf_paged parameter in TUS Website.
"""

from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup
from core.services.chunker_service import Chunker
from core.services.embedding_service import EmbeddingService
from core.services.storage_service import KnowledgeStore


def extract_and_process_links():
    """
    Extract and process all course links from TUS website.

    This method handles the complete flow:
    1. Fetch pages from configured URLs (supports pagination)
    2. Extract all course links from each page
    3. Deduplicate links
    4. Process each course page (extract, chunk, embed, save)
    5. Print progress and results

    To add more URLs, just add them to the urls_to_scrape array below.

    Returns:
        dict: Contains statistics about the scraping operation
            - "success_count": Number of pages successfully processed
            - "error_count": Number of pages that failed to process
            - "total_pages": Total number of unique pages found
    """
    # Remove existing website chunks before scraping to avoid stale data
    try:
        KnowledgeStore().delete_by_source(source_type="website")
        print("Existing website chunks deleted successfully.")
    except Exception as error:
        print(f"Warning: Failed to delete existing website chunks: {error}")

    # Configure URLs to scrape (add more as needed)
    urls_to_scrape = [
        {
            "url": "https://tus.ie/courses/",
            "paginated": True,
            "max_pages": 70,
            "base_path": "/courses"
        },
        {
            "url": "https://tus.ie/admissions/midwest/",
            "paginated": False,
            "base_path": "/admissions/midwest"
        }
        # Add more URLs here as needed, for example:
    ]

    print(f"\n{'*'*60}")
    print(f"Starting TUS Web Scraper")
    print('*'*60)
    print(f"Configured to scrape {len(urls_to_scrape)} URL(s)")

    all_links = set()
    base_domain = "tus.ie"

    # Process each configured URL
    for config in urls_to_scrape:
        url = config["url"]
        paginated = config["paginated"]
        base_path = config["base_path"]

        print(f"\n{'='*60}")
        print(f"Processing: {url}")
        if paginated:
            print(f"Pagination: YES (up to {config['max_pages']} pages)")
        else:
            print(f"Pagination: NO (single page)")
        print('='*60)

        # Determine which pages to fetch
        pages_to_fetch = []
        if paginated:
            max_pages = config.get("max_pages", 70)
            for page_num in range(1, max_pages + 1):
                pages_to_fetch.append({
                    "url": f"{url}?results-id=751&view-mode=table&sf_paged={page_num}",
                    "page_num": page_num
                })
        else:
            pages_to_fetch.append({"url": url, "page_num": 1})

        # Fetch and extract links from all pages
        for page_info in pages_to_fetch:
            page_url = page_info["url"]
            page_num = page_info["page_num"]

            try:
                if paginated:
                    print(f"Fetching page {page_num}...", end=" ")
                else:
                    print(f"Fetching page...", end=" ")
                # Get the page content, timeout after 10 seconds
                response = requests.get(page_url, timeout=10)
                response.raise_for_status()
                soup = BeautifulSoup(response.content, 'html.parser')

                # Extract all links from this page using href attributes
                page_links = 0
                for link in soup.find_all('a', href=True):
                    href = link['href']
                    absolute_url = urljoin(page_url, href)
                    parsed_url = urlparse(absolute_url)

                    # Only process links within the same domain and base path
                    if parsed_url.netloc == base_domain:
                        link_path = parsed_url.path.rstrip('/') # Remove trailing slash

                        if link_path and link_path.startswith(base_path) and link_path != base_path: # Exclude the base path itself
                            clean_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                            if parsed_url.query:
                                clean_url += f"?{parsed_url.query}"
                            all_links.add(clean_url)
                            page_links += 1

                print(f"Found {page_links} links")

            except requests.exceptions.RequestException as error:
                print(f"Error: {error}")
            except Exception as error:
                print(f"Error: {error}")

    # Process all discovered course pages
    sorted_links = sorted(list(all_links))
    print(f"\n{'='*60}")
    print(f"Found {len(sorted_links)} unique course pages to process")
    print('='*60)

    success_count = 0
    error_count = 0

    for idx, course_url in enumerate(sorted_links, 1):
        print(f"\n[{idx}/{len(sorted_links)}] {course_url}")
        status_code, response = process_course_page(course_url)

        if status_code == 200:
            success_count += 1
            print(f"✓ Success: Saved {response.get('saved_count', 0)} chunks")
        else:
            error_count += 1
            print(f"✗ Failed: {response.get('error', 'Unknown error')}")

    # Final summary
    print(f"\n{'='*60}")
    print(f"Processing Complete")
    print('='*60)
    print(f"Total courses found: {len(sorted_links)}")
    print(f"Successfully processed: {success_count}")
    print(f"Failed: {error_count}")
    print('='*60)

    # Return statistics
    return {
        "success_count": success_count,
        "error_count": error_count,
        "total_pages": len(sorted_links)
    }


def process_course_page(url):
    """
    Process a course page: fetch, extract, chunk, embed, and save to database.

    This method handles the complete flow:
    1. Fetch the course page HTML
    2. Extract course title from h1 tag
    3. Extract content from maincontent div
    4. Split content into chunks
    5. Create embeddings for each chunk
    6. Generate chunk titles with course name
    7. Save to MongoDB with URL as source

    Args:
        url: The course page URL to process

    Returns:
        tuple: (status_code, response)
            - (200, {"saved_count": int})
            - (400, {"error": str})
    """
    print(f"\n{'='*60}")
    print(f"Processing course page: {url}")
    print('='*60)

    try:
        # Fetch the page once
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')

        # Extract course title from h1 tag
        h1 = soup.find('h1')
        course_title = h1.get_text(strip=True) if h1 else "Unknown Course"
        print(f"Course title: {course_title}")

        # Extract content from maincontent (can be main tag or div tag)
        maincontent = soup.find(id='maincontent')
        if not maincontent:
            error_msg = f"Could not find maincontent element in {url}"
            print(f"Error: {error_msg}")
            return 400, {"error": error_msg}

        # Remove script and style tags
        for tag in maincontent(['script', 'style']):
            tag.decompose()

        # Get clean text
        content = "\n".join(maincontent.stripped_strings) # Join all text with newlines
        if not content:
            error_msg = f"No content extracted from {url}"
            print(f"Error: {error_msg}")
            return 400, {"error": error_msg}

        # Chunk the content
        chunker = Chunker()
        result = chunker.chunk_text(content)

        if isinstance(result, dict) and "error" in result:
            error_msg = f"Failed to chunk content: {result['error']}"
            print(f"Error: {error_msg}")
            return 400, {"error": error_msg}

        chunks, titles = result
        print(f"Created {len(chunks)} chunks")

        # Create embeddings
        # IMPORTANT: Pass titles to improve retrieval accuracy
        embedding_service = EmbeddingService()
        embeddings = embedding_service.embed_chunks(chunks, titles=titles)

        if isinstance(embeddings, dict) and "error" in embeddings:
            error_msg = f"Failed to create embeddings: {embeddings['error']}"
            print(f"Error: {error_msg}")
            return 400, {"error": error_msg}


        # Save to database
        storage = KnowledgeStore()
        status_code, response_data = storage.save_chunks(
            chunks=chunks,
            embeddings=embeddings,
            source_type="website",
            source_name=course_title,
            titles=titles,
            source_url=url
        )

        return status_code, response_data

    except requests.exceptions.RequestException as e:
        error_msg = f"Failed to fetch {url}: {str(e)}"
        print(f"Error: {error_msg}")
        return 400, {"error": error_msg}
    except Exception as e:
        error_msg = f"Error processing {url}: {str(e)}"
        print(f"Error: {error_msg}")
        return 500, {"error": error_msg}
