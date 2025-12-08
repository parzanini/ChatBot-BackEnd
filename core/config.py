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