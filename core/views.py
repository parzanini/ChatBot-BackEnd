"""Views - Chatbot endpoints

This file contains the following endpoints:
1. /api/ask/         - Ask questions to the chatbot
2. /api/upload_pdf/  - Upload and process PDF files
3. /api/scrape_url/  - Scrape and process web pages

"""
import json
import logging
import os
import tempfile
import time

import google.generativeai as genai
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from mongoengine.connection import get_db


# Create your views here.

# Set up Google's AI once when the server starts
genai.configure(api_key=config.GEMINI_API_KEY)


@csrf_exempt  # Allow API requests without CSRF token
@require_POST  # Only accept POST requests
def ask(request):
    """
    API Endpoint: Ask the chatbot a question.

    This is the main chatbot endpoint. It:
    1. Receives a question from the user
    2. Converts the question to an embedding (list of numbers)
    3. Searches the database for similar content
    4. Sends the question + similar content to Google's AI
    5. Returns the AI's answer

    How to use (example):
        POST /api/ask/
        JSON body: {"query": "What courses does TUS offer?"}

    Returns:
        JSON with the answer and source documents
    """
    # Remember when we started (for timing)
    start_time = time.time()

    # STEP 1: Parse the JSON body
    # The request body contains JSON like: {"query": "What are the courses?"}
    try:
        # Read the request body as text
        request_body = request.body.decode("utf-8")

        # Parse it as JSON (convert text to Python dictionary)
        payload = json.loads(request_body)

    except Exception:
        # The JSON was invalid (malformed, not JSON, etc.)
        error_message = "Invalid JSON body. The correct format is: {\"query\": \"your question here\"}"
        return JsonResponse({"error": error_message}, status=400)