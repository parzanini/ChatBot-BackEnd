"""Views - Chatbot endpoints

This file contains the following endpoints:
1. /api/ask/              - Ask questions to the chatbot
2. /api/upload_pdf/       - Upload and process PDF files
3. /api/index_database/   - Full database indexer (web scraping + PDF folder indexing)

"""
import json
import os
import tempfile
import time

import google.generativeai as genai
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from mongoengine.connection import get_db

from core import config
from core.services.embedding_service import normalize_vector
from core.services.pdf_processor_service import PDFProcessorService
from core.services.storage_service import KnowledgeStore
from core.services.vector_search_service import VectorSearchService
from core.services.web_scraper_service import extract_and_process_links

# Set up Google's AI once when the server starts
genai.configure(api_key=config.GEMINI_API_KEY)


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
        # The JSON was invalid (not JSON, etc.)
        error_message = "Invalid JSON body. The correct format is: {\"query\": \"your question here\"}"
        return JsonResponse({"error": error_message}, status=400)

    # STEP 2: Get the user's question from the JSON
    user_query = user_request.get("query")

    # Remove spaces from beginning and end
    user_query = user_query.strip()

    # STEP 3: Gather information about the query (for debugging)

    debug_info = {
        "query": user_query,
        "collection": config.MONGODB_COLLECTION,
        "vector_index": config.VECTOR_INDEX_NAME,
        "min_vector_score": config.MIN_VECTOR_SCORE,
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
    if config.MONGODB_COLLECTION not in collection_names:
        error_message = f"Collection '{config.MONGODB_COLLECTION}' not found."
        return JsonResponse({"error": error_message}, status=404)

    # Get the collection
    collection = database[config.MONGODB_COLLECTION]

    # STEP 6: Get some stats about the collection (For admin info)
    try:
        # Count how many documents are in the collection
        debug_info["total_docs"] = collection.estimated_document_count()

        # Get list of indexes
        collection_indexes = list(collection.list_indexes())
        index_name_list = []
        for index in collection_indexes:
            name = index.get("name")
            if name:
                index_name_list.append(name)
        debug_info["index_names"] = index_name_list

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
        query_embedding = normalize_vector(raw_embedding)

        # Calculate how long it took (in milliseconds)
        embedding_end_time = time.time()
        embedding_duration_seconds = embedding_end_time - embed_start_time
        embedding_duration_ms = int(round(embedding_duration_seconds * 1000))
        debug_info["embedding_time_ms"] = embedding_duration_ms

    except Exception as error:
        # Embedding generation failed!
        error_message = f"Embedding generation failed: {error}"
        return JsonResponse({"error": error_message}, status=502)

    # STEP 8: Search for similar chunks in the database
    # Remember start time
    search_start_time = time.time()

    # Create a search service
    search_service = VectorSearchService(collection=collection)

    try:
        # Search for similar documents
        matching_docs = search_service.search(query_embedding)

        # Calculate how long it took
        vector_search_end_time = time.time()
        vector_search_duration_seconds = vector_search_end_time - search_start_time
        vector_search_duration_ms = int(round(vector_search_duration_seconds * 1000))
        debug_info["vector_time_ms"] = vector_search_duration_ms

        # Save debug info
        debug_info["candidate_count"] = len(matching_docs)

        # Get similarity scores for each document
        similarity_scores = []
        for doc in matching_docs:
            score = doc.get("score", 0.0)
            score_rounded = round(float(score), 4)
            similarity_scores.append(score_rounded)
        debug_info["similarities"] = similarity_scores

        # Get the top score if any documents found
        if len(matching_docs) > 0:
            top_doc = matching_docs[0]
            top_score = top_doc.get("score", 0.0)
            debug_info["top_score"] = round(float(top_score), 4)

        # Check if we filtered out results due to low scores
        if len(matching_docs) == 0:
            debug_info["low_score_filtered"] = True

    except Exception as error:
        # Search failed!
        error_message = f"Vector search failed: {error}"
        return JsonResponse({"error": error_message}, status=500)

    # STEP 9: Build context from the search results
    # Send this context to the AI along with the question
    context_chunks = []
    sources = []

    for document in matching_docs:
        # Get the text and title from this document
        text = document.get("text")
        title = document.get("title")
        source_url = document.get("sourceUrl")
        source_name = document.get("sourceName")

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
                "source_name": source_name,
                "url": source_url,
                "score": score_rounded
            }
            sources.append(source_info)

            # Add title to debug info
            title_for_debug = title if title else "(untitled)"
            debug_info["chunk_titles"].append(title_for_debug)

    # Save number of matches
    debug_info["matches"] = len(matching_docs)

    # STEP 10: Check if we found any relevant documents
    if len(matching_docs) == 0:
        # Calculate total time
        end_time = time.time()
        total_seconds = end_time - start_time
        total_ms = int(round(total_seconds * 1000))
        debug_info["total_time_ms"] = total_ms

        # Return "not found" response
        response_data = {
            "answer": "I could not find relevant information in the knowledge base.",
            "sources": [],
            "debug": debug_info
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
        ai_model = genai.GenerativeModel(config.GEMINI_MODEL)

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
    debug_info["total_time_ms"] = total_ms

    # Create response
    response_data = {
        "answer": answer_text,
        "sources": sources,
        "debug": debug_info
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
    2. Checks if a source with the same name already exists
    3. Saves it temporarily
    4. Processes it (extract text, create chunks, generate embeddings)
    5. Saves chunks to MongoDB
    6. Returns success or error message

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

    print("=== PDF Upload Request Started ===")

    # STEP 1: Check if a file was uploaded
    if 'file' not in request.FILES:
        # No file found! Return error
        error_msg = "No file provided. Please upload a PDF file with key 'file'."
        print(f"Error: {error_msg}")
        return JsonResponse({
            "error": error_msg
        }, status=400)

    # Get the uploaded file
    pdf_file = request.FILES['file']
    print(f"File received: {pdf_file.name}")

    # STEP 2: Make sure it's a PDF file
    # Get the filename and convert to lowercase
    filename = pdf_file.name.lower()

    # Check if it ends with .pdf
    if not filename.endswith('.pdf'):
        # Wrong file type! Return error
        error_msg = "Invalid file type. Only PDF files are accepted."
        print(f"Error: {error_msg}")
        return JsonResponse({
            "error": error_msg
        }, status=400)

    # STEP 3: Get the source name (or use filename as default)
    source_name = request.POST.get('source_name', '').strip()

    # If no source name provided, use the filename
    if not source_name:
        source_name = pdf_file.name

    print(f"Source name: {source_name}")

    # STEP 4: Check if a source with this name already exists
    print(f"Checking if source '{source_name}' already exists...")
    knowledge_store = KnowledgeStore()

    if knowledge_store.source_exists(source_type="pdf", source_name=source_name):
        error_msg = f"A source with the name '{source_name}' already exists. Please use a different name or delete the existing source first."
        print(f"Warning: {error_msg}")
        return JsonResponse({
            "success": False,
            "error": error_msg
        }, status=409)  # 409 Conflict status code

    print(f"Source '{source_name}' does not exist. Proceeding with upload.")

    # Variable to store temporary file path (so I can delete it later)
    temp_file_path = None

    try:
        # STEP 5: Save the uploaded file temporarily
        # Save it to disk before processing
        # Use a temporary file that Django will clean up later
        print("Saving temporary file...")
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')

        # Write the PDF data to the temporary file
        # PDF files can be large, so we write in chunks
        for data_chunk in pdf_file.chunks():
            temp_file.write(data_chunk)

        # Close the file and remember its path
        temp_file.close()
        temp_file_path = temp_file.name
        print(f"Temporary file saved: {temp_file_path}")

        # STEP 6: Process the PDF
        print("Starting PDF processing...")
        processor = PDFProcessorService()

        # Process the PDF (extract text, chunk, embed, save)
        result = processor.process_pdf(temp_file_path, source_name)

        # STEP 7: Delete the temporary file (we don't need it anymore)
        os.unlink(temp_file_path)
        print("Temporary file deleted")

        # STEP 8: Calculate how long it took
        end_time = time.time()
        total_seconds = end_time - start_time
        total_time = round(total_seconds, 2)

        print(f"=== PDF Upload Completed Successfully ===")
        print(f"Total processing time: {total_time} seconds")

        # STEP 9: Return success response
        response_data = {
            "success": True,
            "message": "PDF processed successfully",
            "chunks_created": result["chunks_created"],
            "source_name": result["source_name"],
            "processing_time_seconds": total_time
        }
        return JsonResponse(response_data, status=201)

    # Except block to catch errors during processing
    except Exception as error:
        print(f"Error during PDF processing: {str(error)}")
        error_msg = f"Failed to process PDF: {str(error)}"
        return JsonResponse({"success": False, "error": error_msg}, status=500)

# ------------------------------ Index Database Endpoint ------------------------------ #
@csrf_exempt  # Allow API requests without CSRF token
def index_database(request):
    """
    API Endpoint: Full database indexer.

    This endpoint reindexes the entire knowledge base by:
    1. Scraping all configured web pages from TUS website
    2. Processing PDF files from a configured folder (future feature)
    3. Creating chunks from all content
    4. Generating embeddings for all chunks
    5. Saving everything to MongoDB with vector search index

    This is a complete rebuild of the knowledge base.

    How to use (example):
        GET /api/index_database/

    Returns:
        JSON with success status, pages indexed, pages failed, and total time
    """
    # Remember time
    start_time = time.time()
    print("=== Database Indexing Started ===")

    try:
        # STEP 1: Get the list of links to scrape
        print("STEP 1: Extracting links from configured URLs...")
        scrape_stats = extract_and_process_links()

        # STEP 2: Calculate total time
        end_time = time.time()
        total_seconds = end_time - start_time
        total_time = round(total_seconds, 2)

        print(f"=== Database Indexing Completed Successfully ===")
        print(f"Total processing time: {total_time} seconds")

        # STEP 3: Return success response
        response_data = {
            "success": True,
            "message": "Database indexing completed successfully",
            "pages_indexed": scrape_stats["success_count"],
            "pages_failed": scrape_stats["error_count"],
            "total_pages": scrape_stats["total_pages"],
            "processing_time_seconds": total_time
        }
        return JsonResponse(response_data, status=200)

    except Exception as error:
        print(f"Error during database indexing: {str(error)}")
        error_msg = f"Failed to index database: {str(error)}"

        # Calculate time even on error
        end_time = time.time()
        total_seconds = end_time - start_time
        total_time = round(total_seconds, 2)

        return JsonResponse({
            "success": False,
            "error": error_msg,
            "processing_time_seconds": total_time
        }, status=500)
