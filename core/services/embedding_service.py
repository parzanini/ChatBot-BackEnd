"""
Embedding Service - Converts text into numbers that AI can understand.

What are embeddings?
- They are lists of numbers that represent the meaning of text
- Similar text has similar numbers
- This lets us find related content by comparing numbers

What does this file do?
- Converts text chunks into embeddings using Google's AI
"""
import math
import google.generativeai as genai

from core import config


class EmbeddingService:
    """Service to create embeddings using Google Gemini API.

        What it does:
        1. Takes text as input
        2. Calls Google's AI to convert it to numbers
        3. Saves the result in memory so we don't need to call the API again
        4. Returns the numbers
        """

    def __init__(self):
        """
        Set up the embedding service.
        """
        self.model = config.EMBEDDING_MODEL
        self.dimensions = config.EMBEDDING_DIMENSIONS
        self.batch_size = config.BATCH_SIZE
        self._cache = {}
        genai.configure(api_key=config.GEMINI_API_KEY)


    def embed_single(self, text, task_type="retrieval_document"):
        """
        Convert one piece of text into an embedding (list of numbers).

        Steps:
        1. Check if we already processed this text (cache)
        2. If yes, return the saved result
        3. If no, call Google's AI to convert it
        4. Save the result for next time
        5. Return the embedding

        Args:
            text: The text to convert
            task_type: What we're using this for (usually "retrieval_document")

        Returns:
            A list of numbers (the embedding)
        """
        # Step 1: Check if we've already processed this text
        if text in self._cache:
            return self._cache[text]
        try:
            # Call Google's AI to convert text to numbers
            result = genai.embed_content(
                model=self.model,
                content=text,
                task_type=task_type
            )

            # Get the embedding from the result
            raw_embedding = result['embedding']

            # Step 4: Normalize it (make all embeddings the same "size")
            normalized_embedding = normalize_vector(raw_embedding)

            # Step 5: Save it in the cache for next time
            self._cache[text] = normalized_embedding

            # Step 6: Return the embedding
            return normalized_embedding
        except Exception as e:
            # Return error information
            return {"error": str(e)}

    def embed_chunks(self, chunks, titles=None, task_type="retrieval_document"):
        """
        Convert multiple pieces of text into embeddings.
        This processes each chunk one at a time.

        Steps:
        1. Create an empty list to store all embeddings
        2. Go through each chunk one by one
        3. If title exists, prepend it to the chunk for better context
        4. Convert each chunk to an embedding
        5. Add the embedding to our list
        6. Return the complete list

        Args:
            chunks: A list of text chunks to convert
            titles: Optional list of titles (same length as chunks). If provided, titles
                   are prepended to chunks before embedding for better retrieval accuracy.
            task_type: What this is for (usually "retrieval_document")

        Returns:
            A list of embeddings (each embedding is a list of numbers)
        """
        # Step 1: Create empty list to collect all embeddings
        all_embeddings = []

        # Step 2: Process each chunk one by one
        chunk_number = 0
        for i, chunk in enumerate(chunks):
            # Every 10 chunks, print progress
            if chunk_number > 0 and chunk_number % 10 == 0:
                print(f"Embedding chunk {chunk_number}...")

            # Step 3: Prepare text for embedding (include title if available)
            if titles and i < len(titles):
                # Prepend title to chunk for better semantic context
                # This helps retrieval find the right chunks when users ask specific questions
                # Example: "Computing with AI – BSc (Hons)\n\nContact Details: Carol Rainsford..."
                text_to_embed = f"{titles[i]}\n\n{chunk}"
            else:
                # No title available, just use the chunk
                text_to_embed = chunk

            # Step 4: Convert this text to an embedding
            embedding = self.embed_single(text_to_embed, task_type=task_type)

            # Step 5: Add it to our list
            all_embeddings.append(embedding)

            chunk_number = chunk_number + 1

        # Step 6: Log some stats
        total_chunks = len(chunks)
        with_titles = "YES" if titles else "NO"
        print(f"Embedded {total_chunks} chunks (titles included: {with_titles})")

        # Step 7: Return all the embeddings
        return all_embeddings

    def clear_cache(self):
        # Delete all saved embeddings from memory.
        self._cache.clear()

    def get_cache_stats(self):
        """
        Get information about the cache.

        Returns:
            - How many embeddings are cached
            - Which model is being used
            - How many dimensions in each embedding
            - The batch size setting
        """
        stats = {
            "cached_items": len(self._cache),
            "model": self.model,
            "dimensions": self.dimensions,
            "batch_size": self.batch_size
        }
        return stats

    @staticmethod
    def normalize_vector(values):
        """
        This is a helper method to normalize a vector.It just calls the standalone function.
        By doing this, I can call it as a method of the EmbeddingService class.
        """
        return normalize_vector(values)


def normalize_vector(values):
    """
    Make a list of numbers have a total length of 1.

    This makes comparing different vectors more accurate.
    It's like converting all measurements to the same scale.

    How it works:
    1. Square each number and add them up
    2. Take the square root (this gives us the "length")
    3. Divide each number by the length

    Example:
        [3, 4] becomes [0.6, 0.8] because sqrt(3² + 4²) = 5

    Args:
        values: A list of numbers (the vector)

    Returns:
        A new list of numbers with length = 1
    """
    # Step 1: Square each number and add them up
    squared_sum = 0.0
    for value in values:
        number = float(value) if value else 0.0
        squared_sum = squared_sum + (number * number)

    # Step 2: Get the length (magnitude) by taking square root
    length = math.sqrt(squared_sum)

    # Step 3: If length is zero, return all zeros (avoid division by zero)
    if length == 0:
        return [0.0 for _ in values]

    # Step 4: Divide each number by the length
    normalized = []
    for value in values:
        number = float(value) if value else 0.0
        normalized.append(number / length)

    return normalized
