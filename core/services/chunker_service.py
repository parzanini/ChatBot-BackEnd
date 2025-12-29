"""
Chunker - Splits long text into smaller pieces.

Why split text?
- AI works better with smaller pieces of text
- Easier to search and find relevant information
- Each chunk gets its own embedding (number representation)

What does this file do?
- Takes long text (like a PDF or web page)
- Splits it into chunks of about 500 characters each
- Makes sure chunks overlap a bit (so context isn't lost)
- Creates a title for each chunk
"""
import re
from langchain_text_splitters import RecursiveCharacterTextSplitter
from core import config


class Chunker:
    def __init__(self, chunk_size=None, chunk_overlap=None, separators=None):
        """
        Set up the chunker.

        Args:
            chunk_size: How many characters in each chunk (optional, uses 500 by default)
            chunk_overlap: How many characters to repeat between chunks (optional, uses 50 by default)
            separators: What to split on (optional, uses \\n\\n, \\n, ". ", " " by default)
        """
        # Use provided values or fall back to config defaults
        if chunk_size is not None:
            self.chunk_size = chunk_size
        else:
            self.chunk_size = config.CHUNK_SIZE

        if chunk_overlap is not None:
            self.chunk_overlap = chunk_overlap
        else:
            self.chunk_overlap = config.CHUNK_OVERLAP

        if separators is not None:
            self.separators = separators
        else:
            self.separators = config.CHUNK_SEPARATORS

        # Create the splitter tool from langchain
        # This does the actual work of splitting text
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            separators=self.separators
        )

    def chunk_text(self, text):
        """
        Split long text into smaller chunks.

        Steps:
        1. Check if text is empty (error if it is)
        2. Use the splitter to break text into chunks
        3. Check if we got any chunks (error if we didn't)
        4. Return the list of chunks

        Args:
            text: The long text to split

        Returns:
            A list of text chunks (each chunk is a string)
            OR {"error": "..."} if the input is invalid or splitting fails.
        """
        # Step 1: Make sure we have text to work with
        if not text:
            return {"error": "Cannot chunk empty text"}

        text_without_spaces = text.strip()
        if not text_without_spaces:
            return {"error": "Cannot chunk empty text"}

        # Step 2: Use the splitter to break text into chunks
        chunks = self.splitter.split_text(text)

        # Step 3: Make sure we got at least one chunk
        if not chunks:
            return {"error": "No chunks generated from text"}

        # Step 4: Return the chunks
        return chunks

    def chunk_with_titles(self, text):
        """
        Split text into chunks and create a title for each chunk.
        This is good because often want both the chunks and titles.

        Steps:
        1. Split the text into chunks
        2. For each chunk, create a short title
        3. Return both lists

        Args:
            text: The long text to split

        Returns:
            Two lists: (chunks, titles)
            - chunks: List of text chunks
            - titles: List of titles (same order as chunks)
        """
        # Step 1: Split the text
        chunks = self.chunk_text(text)
        if isinstance(chunks, dict) and "error" in chunks:
            return chunks

        # Step 2: Create a title for each chunk
        titles = []
        for chunk in chunks:
            title = generate_title(chunk)
            titles.append(title)

        # Step 4: Return both lists
        return chunks, titles


def generate_title(text, max_length=50):
    """
    Generate a short title from the beginning of the text.

    This extracts the first sentence or first few words to use as a title.

    Steps:
    1. Clean up the text (remove extra spaces)
    2. Find the first sentence
    3. If too long, take just the first few words
    4. Return the title

    Args:
        text: The text to create a title from
        max_length: Maximum length of the title (default 50 characters)

    Returns:
        A short title string
    """
    # Step 1: Clean up the text
    if not text:
        return "Untitled"

    # Remove extra whitespace
    cleaned = re.sub(r'\s+', ' ', text.strip())

    if not cleaned:
        return "Untitled"

    # Step 2: Try to find the first sentence
    # Look for sentence endings: . ! ?
    sentence_match = re.match(r'^[^.!?]+[.!?]', cleaned)

    if sentence_match:
        first_sentence = sentence_match.group(0).strip()
    else:
        # No sentence ending found, use the whole text
        first_sentence = cleaned

    # Step 3: If still too long, take first few words
    if len(first_sentence) > max_length:
        # Take first max_length characters and add "..."
        title = first_sentence[:max_length].strip()
        # Try to break at last space to avoid cutting words
        last_space = title.rfind(' ')
        if last_space > max_length // 2:  # Only if space is not too early
            title = title[:last_space]
        title = title + "..."
    else:
        title = first_sentence

    return title
