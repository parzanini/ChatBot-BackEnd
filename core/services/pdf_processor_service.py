import pdfplumber
from concurrent.futures import (ThreadPoolExecutor, TimeoutError as FuturesTimeoutError)

from core.services.chunker_service import Chunker
from core.services.embedding_service import EmbeddingService
from core.services.storage_service import KnowledgeStore


class PDFProcessorService:
    """
    This class processes PDF files for the chatbot.

    What it does:
    1. Reads text from a PDF file
    2. Splits the text into chunks
    3. Creates embeddings for each chunk
    4. Saves everything to MongoDB

    It uses these helper components:
    - Chunker: Splits text into pieces
    - EmbeddingService: Converts text to numbers
    - KnowledgeStore: Saves to database
    """

    def __init__(self):
        """
        Set up the PDF processor.

        This creates the helper components we need.
        """
        # Create a chunker to split text
        self.chunker = Chunker()

        # Create an embedding service to convert text to numbers
        self.embedding_service = EmbeddingService()

        # Create a storage to save to database
        self.storage = KnowledgeStore()

    def extract_text(self, pdf_path, page_timeout=5):
        """
        Read all the text from a PDF file with timeout protection.

        Steps:
        1. Open the PDF
        2. Go through each page with timeout protection
        3. Extract text from each page
        4. Join all pages together

        Args:
            pdf_path: The file path to the PDF (like "C:/documents/handbook.pdf")
            page_timeout: Maximum seconds to spend extracting text from one page (default: 5)

        Returns:
            All the text from the PDF as one long string

        Raises:
            ValueError: If the PDF cannot be opened or processed
        """
        # List to store text from each page
        all_pages = []

        try:
            # Open the PDF file
            with pdfplumber.open(pdf_path) as pdf:
                total_pages = len(pdf.pages)

                # Go through each page
                for page_num, page in enumerate(pdf.pages, 1):
                    page_text = ''

                    try:
                        # Extract text with timeout using ThreadPoolExecutor
                        with ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(page.extract_text)
                            try:
                                page_text = future.result(timeout=page_timeout)
                            except FuturesTimeoutError:
                                print(f"Warning: Page {page_num} extraction timed out after {page_timeout}s, skipping")
                                page_text = ''

                    except Exception as page_error:
                        print(f"Warning: Failed to extract text from page {page_num}: {str(page_error)}")
                        page_text = ''

                    # If page has no text, use empty string
                    if page_text is None:
                        page_text = ''

                    # Remove extra spaces at beginning and end
                    page_text = page_text.strip()

                    # Add this page's text to list
                    all_pages.append(page_text)

            # Join all pages with double newline between them
            all_text = "\n\n".join(all_pages)
            return all_text

        except Exception as error:
            raise ValueError(f"Failed to open or process PDF: {str(error)}")

    def process_pdf(self, pdf_path, source_name):
        """
        Process a PDF file from start to finish.

        This is the main method that does everything:
        1. Read text from the PDF
        2. Split it into chunks
        3. Create embeddings
        4. Save to database

        Steps explained:
        - Extract all text from the PDF
        - Make sure it's not empty
        - Split into small chunks with titles
        - Convert chunks to embeddings (numbers)
        - Save everything to MongoDB
        - Return summary

        Args:
            pdf_path: Where the PDF file is located
            source_name: A friendly name for this PDF (like "Student Handbook 2025")

        Returns:
            A dictionary with:
            - chunks_created: How many chunks were saved
            - source_name: The name you provided

        Raises:
            ValueError: If the PDF is empty or can't be processed
        """

        # STEP 1: Extract all text from the PDF
        text = self.extract_text(pdf_path)

        # Make sure There is some text
        text_without_spaces = text.strip()
        if not text_without_spaces:
            raise ValueError("PDF appears to be empty or contains no text we can read.")

        # STEP 2: Split text into chunks and create titles
        chunks, titles = self.chunker.chunk_with_titles(text)

        num_chunks = len(chunks)

        # STEP 3: Generate embeddings for all chunks
        # This converts each chunk into a list of numbers
        embeddings = self.embedding_service.embed_chunks(chunks)

        # STEP 4: Save everything to MongoDB
        chunks_saved = self.storage.save_chunks(
            chunks=chunks,
            embeddings=embeddings,
            source_type="pdf",
            source_name=source_name,
            titles=titles,
            source_url=None  # PDFs don't have URLs
        )

        # STEP 5: Return summary
        result = {
            "chunks_created": chunks_saved,
            "source_name": source_name
        }
        return result


