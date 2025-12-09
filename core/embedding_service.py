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

class EmbeddingService:
    """Service to create embeddings using Google Gemini API."""

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