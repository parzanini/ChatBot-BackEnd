"""
Chunker - Splits long text into smaller pieces for the chatbot.

- AI works better with smaller pieces of text
- Easier to search and find relevant information
- Each chunk gets its own embedding (number representation)

- Takes long text (like a PDF or web page)
- Splits it into chunks of about 1000 characters each
- Chunks overlap so context isn't lost
- Creates a title for each chunk
"""
import re
from langchain_text_splitters import RecursiveCharacterTextSplitter
from core import config


class Chunker:
    def __init__(self):
        """
        Set up the chunker with default settings from config.

        Default settings:
        - chunk_size: 1000 characters per chunk
        - chunk_overlap: 100 characters overlap between chunks
        - separators: Split on paragraphs (\\n\\n), lines (\\n), sentences (". "), or words (" ")
        """
        # Create the splitter tool from langchain
        # This does the actual work of splitting text
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=config.CHUNK_SIZE,
            chunk_overlap=config.CHUNK_OVERLAP,
            separators=config.CHUNK_SEPARATORS
        )

    def chunk_text(self, text):
        """
        Split long text into smaller chunks with titles.

        All chunks get the same keyword title with different numbers:
        - "Computing with AI – BSc (Hons) [1/49]"
        - "Computing with AI – BSc (Hons) [2/49]"
        ...and so on

        Args:
            text: The long text to split

        Returns:
            (chunks, titles) - Two lists of the same length
            OR {"error": "..."} if text is empty
        """
        # Step 1: Check if text is empty
        if not text or not text.strip():
            return {"error": "Cannot chunk empty text"}

        # Step 2: Extract keywords from the beginning
        # This keyword will be reused for ALL chunk titles
        keywords = self._extract_keywords(text)

        # Step 3: Split text into chunks (using langchain splitter)
        chunks = self.splitter.split_text(text)

        if not chunks:
            return {"error": "No chunks generated from text"}

        # Step 4: Create titles for all chunks
        # Same keywords + different numbers: [1/49], [2/49], [3/49], etc.
        total_chunks = len(chunks)
        titles = [f"{keywords} [{i+1}/{total_chunks}]" for i in range(total_chunks)]

        # Step 5: Return chunks and titles
        return chunks, titles

    def _extract_keywords(self, text, max_len=60):
        """
        Extract keywords from the beginning of the text.

        Example: "Computing with AI – BSc (Hons)" from the first few lines

        Returns: A string (max 60 chars) to use for all chunk titles
        """
        # Handle empty text
        if not text:
            return "Untitled Document"

        # Get first 500 characters and split into lines
        first_part = text[:500]
        lines = [line.strip() for line in first_part.split('\n') if line.strip()]

        if not lines:
            return "Untitled Document"

        # Check first 5 lines for a good heading
        for line in lines[:5]:
            # Remove extra spaces: "  Hello   World " -> "Hello World"
            clean_line = re.sub(r'\s+', ' ', line)

            # Skip if line is too short (less than 10 characters)
            if len(clean_line) < 10:
                continue

            # Skip if line has only numbers/symbols (like "123" or "---")
            if re.match(r'^[\d\s.\-]+$', clean_line):
                continue

            # This line looks good then Use it as keywords
            # Shorten if longer than max_len (60 characters)
            if len(clean_line) > max_len:
                # Truncate to max_len
                shortened = clean_line[:max_len]

                # Find last space to avoid cutting words in half
                last_space_position = shortened.rfind(' ')

                # Cut at last space (if it's not too early in the text)
                if last_space_position > max_len // 2:
                    shortened = shortened[:last_space_position]

                return shortened + "..."

            # Line is short enough, return as-is
            return clean_line

        # No good heading found, use first 60 characters as fallback
        fallback = re.sub(r'\s+', ' ', text.strip())

        if len(fallback) > max_len:
            shortened = fallback[:max_len]
            last_space_position = shortened.rfind(' ')

            if last_space_position > max_len // 2:
                shortened = shortened[:last_space_position]

            return shortened + "..."

        return fallback
