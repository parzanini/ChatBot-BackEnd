"""Views - Chatbot endpoints

This file contains the following endpoints:
1. /api/ask/         - Ask questions to the chatbot
2. /api/upload_pdf/  - Upload and process PDF files
3. /api/scrape_url/  - Scrape and process web pages

"""
import json
import tempfile
import time

import google.generativeai as genai
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from mongoengine.connection import get_db

from core import config
from core.services.embedding_service import EmbeddingService
from core.services.vector_search_service import VectorSearchService

# Create your views here.

# Set up Google's AI once when the server starts
genai.configure(api_key=config.GEMINI_API_KEY)

# Load settings from config file (easier to change in one place)
MODEL_NAME = config.GEMINI_MODEL
COLLECTION = config.MONGODB_COLLECTION
VECTOR_INDEX_NAME = config.VECTOR_INDEX_NAME
VECTOR_LIMIT = config.VECTOR_LIMIT
VECTOR_NUM_CANDIDATES = config.VECTOR_NUM_CANDIDATES
MIN_VECTOR_SCORE = config.MIN_VECTOR_SCORE

# ------------------------------ Ask Endpoint ------------------------------ #
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
    # Remember when time started
    start_time = time.time()

    # STEP 1: Parse the JSON body
    # The request body contains JSON like: {"query": "What are the courses?"}
    try:
        # Read the request body as text
        request_body = request.body.decode("utf-8")

        # Parse it as JSON (convert text to Python dictionary)
        user_request = json.loads(request_body)

    except Exception:
        # The JSON was invalid (malformed, not JSON, etc.)
        error_message = "Invalid JSON body. The correct format is: {\"query\": \"your question here\"}"
        return JsonResponse({"error": error_message}, status=400)

    # STEP 2: Get the user's question from the JSON
    user_query = user_request.get("query")

    # Remove spaces from beginning and end
    user_query = user_query.strip()

    # STEP 3: Gather information about the query (Admin only)

    adm_info = {
        "query": user_query,
        "collection": COLLECTION,
        "vector_index": VECTOR_INDEX_NAME,
        "min_vector_score": MIN_VECTOR_SCORE,
        "matches": 0,
        "index_names": [],
        "total_docs": None,
        "embedding_time_ms": None,
        "vector_time_ms": None,
        "candidate_count": 0,
        "similarities": [],
        "chunk_titles": [],
        "low_score_filtered": False,
        "top_score": None
    }

    # STEP 4: Connect to MongoDB database
    try:
        # Get database connection (configured in Django settings)
        database = get_db()

    except Exception as error:
        # Connection failed!
        error_message = f"MongoDB connection failed: {error}"
        return JsonResponse({"error": error_message}, status=500)

    # STEP 5: Make sure the collection exists
    # Get list of all collection names in the database
    collection_names = database.list_collection_names()

    # Check if our collection is in the list
    if COLLECTION not in collection_names:
        error_message = f"Collection '{COLLECTION}' not found."
        return JsonResponse({"error": error_message}, status=404)

    # Get the collection
    collection = database[COLLECTION]

    # STEP 6: Get some stats about the collection (For admin info)
    try:
        # Count how many documents are in the collection
        adm_info["total_docs"] = collection.estimated_document_count()

        # Get list of indexes
        all_indexes = list(collection.list_indexes())
        index_names = []
        for index in all_indexes:
            name = index.get("name")
            if name:
                index_names.append(name)
        adm_info["index_names"] = index_names

    except Exception as error:
        # If this fails,
        error_message = f"Failed to get collection stats: {error}"
        return JsonResponse({"error": error_message}, status=500)

    # STEP 7: Convert the question to an embedding
    try:
        # Remember start time
        embed_start_time = time.time()

        # Call Google's AI to convert the question to numbers
        embedding_result = genai.embed_content(
            model=config.EMBEDDING_MODEL,
            content=user_query,
            task_type="retrieval_query"
        )

        # Get the embedding from the result
        raw_embedding = embedding_result['embedding']

        # Normalize it (make it length 1)
        query_embedding = EmbeddingService.normalize_vector(raw_embedding)

        # Calculate how long it took (in milliseconds)
        embed_end_time = time.time()
        embed_duration_seconds = embed_end_time - embed_start_time
        embed_duration_ms = int(round(embed_duration_seconds * 1000))
        adm_info["embedding_time_ms"] = embed_duration_ms

    except Exception as error:
        # Embedding generation failed!
        error_message = f"Embedding generation failed: {error}"
        return JsonResponse({"error": error_message}, status=502)

    # STEP 8: Search for similar chunks in the database
    # Remember start time
    search_start_time = time.time()

    # Create a search service
    search_service = VectorSearchService(
        collection=collection,
        vector_index_name=VECTOR_INDEX_NAME,
        vector_limit=VECTOR_LIMIT,
        num_candidates=VECTOR_NUM_CANDIDATES,
        min_score=MIN_VECTOR_SCORE
    )

    try:
        # Search for similar documents
        matching_docs = search_service.search(query_embedding)

        # Calculate how long it took
        search_end_time = time.time()
        search_duration_seconds = search_end_time - search_start_time
        search_duration_ms = int(round(search_duration_seconds * 1000))
        adm_info["vector_time_ms"] = search_duration_ms

        # Save debug info
        adm_info["candidate_count"] = len(matching_docs)

        # Get similarity scores for each document
        similarity_scores = []
        for doc in matching_docs:
            score = doc.get("score", 0.0)
            score_rounded = round(float(score), 4)
            similarity_scores.append(score_rounded)
        adm_info["similarities"] = similarity_scores

        # Get the top score (if we have results)
        if len(matching_docs) > 0:
            top_doc = matching_docs[0]
            top_score = top_doc.get("score", 0.0)
            adm_info["top_score"] = round(float(top_score), 4)

        # Check if we filtered out results due to low scores
        if len(matching_docs) == 0:
            adm_info["low_score_filtered"] = True

    except Exception as error:
        # Search failed!
        error_message = f"Vector search failed: {error}"
        return JsonResponse({"error": error_message}, status=500)

    # STEP 9: Build context from the search results
    # We'll send this context to the AI along with the question
    context_chunks = []
    sources = []

    for document in matching_docs:
        # Get the text and title from this document
        text = document.get("text")
        title = document.get("title")

        # Use empty string if missing
        if not text:
            text = ""
        if not title:
            title = ""

        # Only include documents that have text
        if text:
            # Limit text to 800 characters to keep it reasonable
            text_excerpt = text[:800]

            # Format as "Title: ...\nText: ..."
            formatted_chunk = f"Title: {title}\nText: {text_excerpt}"
            context_chunks.append(formatted_chunk)

            # Add to sources list (to return to user)
            score = document.get("score", 0.0)
            score_rounded = round(float(score), 4)
            source_info = {
                "title": title,
                "score": score_rounded
            }
            sources.append(source_info)

            # Add title to debug info
            title_for_debug = title if title else "(untitled)"
            adm_info["chunk_titles"].append(title_for_debug)

    # Save number of matches
    adm_info["matches"] = len(matching_docs)

    # STEP 10: Check if we found any relevant documents
    if len(matching_docs) == 0:
        # Calculate total time
        end_time = time.time()
        total_seconds = end_time - start_time
        total_ms = int(round(total_seconds * 1000))
        adm_info["total_time_ms"] = total_ms

        # Return "not found" response
        response_data = {
            "answer": "I could not find relevant information in the knowledge base.",
            "sources": [],
            "debug": adm_info
        }

        return JsonResponse(response_data, status=200)

    # STEP 11: Combine all context chunks into one big string
    # Join them with "---" separator
    context = "\n\n---\n\n".join(context_chunks)

    # STEP 12: Create a prompt for Google's AI
    # This tells the AI what to do
    prompt = f"""You are a helpful assistant. Use the provided context to answer the user's question.
If the answer is not in the context, state that you do not have enough information.

Question:
{user_query}

Context:
{context}
"""

    # STEP 13: Ask Google's AI to generate an answer
    try:
        # Create AI model
        ai_model = genai.GenerativeModel(MODEL_NAME)

        # Generate answer
        ai_response = ai_model.generate_content(prompt)

        # Get the text from the response
        if hasattr(ai_response, "text"):
            answer_text = ai_response.text.strip()
        else:
            answer_text = ""

        # Use default message if empty
        if not answer_text:
            answer_text = "No answer generated."

    except Exception as error:
        # AI call failed!
        error_message = f"Gemini AI call failed: {error}"
        return JsonResponse({"error": error_message}, status=502)

    # STEP 14: Calculate total time and prepare response
    end_time = time.time()
    total_seconds = end_time - start_time
    total_ms = int(round(total_seconds * 1000))
    adm_info["total_time_ms"] = total_ms

    # Create response
    response_data = {
        "answer": answer_text,
        "sources": sources,
        "debug": adm_info
    }

    # STEP 15: Return the response
    return JsonResponse(response_data, status=200)

# ------------------------------ PDF Upload Endpoint ------------------------------ #

@csrf_exempt  # Allow requests without CSRF token (for APIs)
@require_POST  # Only accept POST requests (not GET, PUT, etc.)
def upload_pdf(request):
    """
    API Endpoint: Upload and process a PDF file.

    What this does:
    1. Receives a PDF file from the user
    2. Saves it temporarily
    3. Processes it (extract text, create chunks, generate embeddings)
    4. Saves chunks to MongoDB
    5. Returns success or error message

    How to use (example):
        POST /api/upload_pdf/
        Form data:
        - file: (the PDF file)
        - source_name: "Student Handbook 2025" (optional)

    Returns:
        JSON with success status and number of chunks created
    """
    # Remember when we started (to calculate how long this takes)
    start_time = time.time()

    # STEP 1: Check if a file was uploaded
    if 'file' not in request.FILES:
        # No file found! Return error
        return JsonResponse({
            "error": "No file provided. Please upload a PDF file with key 'file'."
        }, status=400)

    # Get the uploaded file
    pdf_file = request.FILES['file']

    # STEP 2: Make sure it's a PDF file
    # Get the filename and convert to lowercase
    filename = pdf_file.name.lower()

    # Check if it ends with .pdf
    if not filename.endswith('.pdf'):
        # Wrong file type! Return error
        return JsonResponse({
            "error": "Invalid file type. Only PDF files are accepted."
        }, status=400)

    # STEP 3: Get the source name (or use filename as default)
    source_name = request.POST.get('source_name', '').strip()

    # If no source name provided, use the filename
    if not source_name:
        source_name = pdf_file.name

    # Variable to store temporary file path (so I can delete it later)
    temp_file_path = None

    try:
        # STEP 4: Save the uploaded file temporarily
        # We need to save it to disk before processing
        # Use a temporary file that Django will clean up later
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')