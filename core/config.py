"""
Configuration settings for the chatbot.
"""
import os

# ============================================================================
# GOOGLE GEMINI API SETTINGS
# ============================================================================

# Google API key
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Which Gemini model to use for generating answers
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

# Which model to use for creating embeddings
EMBEDDING_MODEL = "models/text-embedding-004"

# How many numbers are in each embedding (768 is standard for this model)
EMBEDDING_DIMENSIONS = 768

# How many text chunks to process at once (bigger = faster but uses more memory)
BATCH_SIZE = 32






# ============================================================================
# MONGODB DATABASE SETTINGS
# ============================================================================
# These settings control how we store and search data in MongoDB

# Which MongoDB collection to store knowledge chunks in
MONGODB_COLLECTION = os.getenv("MONGODB_COLLECTION", "knowledgeChunks")

# Name of the vector search index in MongoDB
VECTOR_INDEX_NAME = os.getenv("MONGODB_VECTOR_INDEX", "vector_index")

# How many matching chunks to return when searching
VECTOR_LIMIT = int(os.getenv("MONGODB_VECTOR_LIMIT", "5"))

# How many candidates to consider during vector search (more = slower but better)
VECTOR_NUM_CANDIDATES = int(os.getenv("MONGODB_VECTOR_CANDIDATES", "100"))

# Minimum similarity score to consider a match (0.0 to 1.0)
MIN_VECTOR_SCORE = float(os.getenv("MONGODB_MIN_VECTOR_SCORE", "0.2"))