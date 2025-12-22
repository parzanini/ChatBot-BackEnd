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

        def __init__(self, model=None, dimensions=None, batch_size=None):
            """
            Set up the embedding service.

            Args:
                model: Which AI model to use
                dimensions: How many numbers in each embedding
                batch_size: How many texts to process at once
            """
            # Use provided values or fall back to config defaults
            if model is not None:
                self.model = model
            else:
                self.model = config.EMBEDDING_MODEL

            if dimensions is not None:
                self.dimensions = dimensions
            else:
                self.dimensions = config.EMBEDDING_DIMENSIONS

            if batch_size is not None:
                self.batch_size = batch_size
            else:
                self.batch_size = config.BATCH_SIZE

            # Create an empty cache (dictionary) to store embeddings
            # Key = text hash, Value = embedding (list of numbers)
            self._cache = {}

            # Set up connection to Google's AI
            if config.GEMINI_API_KEY:
                genai.configure(api_key=config.GEMINI_API_KEY)


    @staticmethod
    def normalize_vector(values):
        """
        Make a list of numbers have a total length of 1.

        Why? This makes comparing different vectors more accurate.
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