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

from google import genai
from django.contrib.auth import authenticate
from django.contrib.auth.models import Group, User
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST, require_GET
from mongoengine.connection import get_db

from core import config
from core.models import AuthToken
from core.services.embedding_service import normalize_vector
from core.services.pdf_processor_service import PDFProcessorService
from core.services.storage_service import KnowledgeStore
from core.services.vector_search_service import VectorSearchService
from core.services.web_scraper_service import extract_and_process_links

# Set up Google's AI client once when the server starts
genai_client = genai.Client(api_key=config.GEMINI_API_KEY)

USER_ROLE = "USER"
ADMIN_ROLE = "ADMIN"


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
        # Connection failed! Return friendly error message
        error_message = "Sorry, the service is temporarily unavailable. Please try again shortly."
        return JsonResponse({"error": error_message}, status=500)

    # STEP 5: Make sure the collection exists
    # Get list of all collection names in the database
    collection_names = database.list_collection_names()

    # Check if our collection is in the list
    if config.MONGODB_COLLECTION not in collection_names:
        error_message = "Sorry, the service is temporarily unavailable. Please try again shortly."
        return JsonResponse({"error": error_message}, status=500)

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
        # If this fails, return friendly error message
        error_message = "Sorry, the service is temporarily unavailable. Please try again shortly."
        return JsonResponse({"error": error_message}, status=500)

    # STEP 7: Convert the question to an embedding
    try:
        # Remember start time
        embed_start_time = time.time()

        # Call Google's AI to convert the question to numbers
        embedding_result = genai_client.models.embed_content(
            model=config.EMBEDDING_MODEL,
            contents=user_query
        )

        # Get the embedding from the result
        raw_embedding = embedding_result.embeddings[0].values

        # Normalize it (make it length 1)
        query_embedding = normalize_vector(raw_embedding)

        # Calculate how long it took (in milliseconds)
        embedding_end_time = time.time()
        embedding_duration_seconds = embedding_end_time - embed_start_time
        embedding_duration_ms = int(round(embedding_duration_seconds * 1000))
        debug_info["embedding_time_ms"] = embedding_duration_ms

    except Exception as error:
        # Embedding generation failed! Return friendly error message
        error_message = "Sorry, the AI service is unavailable right now. Please try again shortly."
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
        # Search failed! Return friendly error message
        error_message = "Sorry, the search service is unavailable right now. Please try again shortly."
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

        # Return "not found" response (UC2: Insufficient Information)
        response_data = {
            "answer": "I could not find relevant information in the knowledge base. Please try rephrasing your question or contact college support for assistance.",
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
If the answer is not in the context, use the following answer: I could not find relevant information in the knowledge base. Please try rephrasing your question or contact college support for assistance.

Question:
{user_query}

Context:
{context}
"""

    # STEP 13: Ask Google's AI to generate an answer
    try:
        # Generate answer
        ai_response = genai_client.models.generate_content(
            model=config.GEMINI_MODEL,
            contents=prompt
        )

        # Get the text from the response
        if hasattr(ai_response, "text"):
            answer_text = ai_response.text.strip()
        else:
            answer_text = ""

        # Use default message if empty
        if not answer_text:
            answer_text = "No answer generated."

    except Exception as error:
        # AI call failed! Return friendly error message (NFR-R01)
        error_message = "Sorry, the AI service is unavailable right now. Please try again shortly."
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
        result = processor.process_pdf(temp_file_path, source_name,source_type ="Manual Upload")

        # STEP 7: Delete the temporary file (we don't need it anymore)
        os.unlink(temp_file_path)
        print("Temporary file deleted")

        # STEP 8: Calculate how long it took
        end_time = time.time()
        total_seconds = end_time - start_time
        total_minutes = round(total_seconds / 60, 2)

        print(f"=== PDF Upload Completed Successfully ===")
        print(f"Total processing time: {total_minutes} minutes")

        # STEP 9: Return success response
        response_data = {
            "success": True,
            "message": "PDF processed successfully",
            "chunks_created": result["chunks_created"],
            "source_name": result["source_name"],
            "processing_time_minutes": total_minutes
        }
        return JsonResponse(response_data, status=201)

    # Except block to catch errors during processing
    except Exception as error:
        print(f"Error during PDF processing: {str(error)}")
        error_msg = f"Failed to process PDF: {str(error)}"
        return JsonResponse({"success": False, "error": error_msg}, status=500)

# ------------------------------ Index Database Endpoint ------------------------------ #
@csrf_exempt  # Allow API requests without CSRF token
@require_POST  # Only accept POST requests
def index_database(request):
    """
    API Endpoint: Full database indexer.

    This endpoint reindexes the entire knowledge base by:
    1. Deleting existing PDF chunks
    2. Processing PDF files from a configured folder
    3. Scraping all configured web pages from TUS website
    4. Creating chunks from all content
    5. Generating embeddings for all chunks
    6. Saving everything to MongoDB with vector search index

    This is a complete rebuild of the knowledge base.

    How to use (example):
        POST /api/index_database/

    Returns:
        JSON with success status, pages indexed, pages failed, PDFs processed, and total time
    """
    # Remember time
    start_time = time.time()
    print("=== Database Indexing Started ===")

    try:
        # STEP 1: Delete existing PDF chunks
        print("\nSTEP 1: Deleting existing PDF chunks...")
        try:
            delete_result = KnowledgeStore().delete_by_source(source_type="pdf")
            print(f"Deleted {delete_result['deleted_count']} existing PDF chunks")
        except Exception as error:
            print(f"Warning: Failed to delete existing PDF chunks: {error}")

        # STEP 2: Process PDF files from folder
        print("\nSTEP 2: Processing PDF files from folder...")

        # Check if folder exists
        if not os.path.exists(config.PDF_FOLDER_PATH):
            error_msg = f"PDF folder does not exist: {config.PDF_FOLDER_PATH}"
            print(f"Error: {error_msg}")

            # Calculate time
            end_time = time.time()
            total_seconds = end_time - start_time
            total_minutes = round(total_seconds / 60, 2)

            return JsonResponse({
                "success": False,
                "error": error_msg,
                "processing_time_minutes": total_minutes
            }, status=500)

        # Get all PDF files from folder
        try:
            all_files = os.listdir(config.PDF_FOLDER_PATH)
        except Exception as error:
            error_msg = f"Failed to read PDF folder: {str(error)}"
            print(f"Error: {error_msg}")

            end_time = time.time()
            total_seconds = end_time - start_time
            total_minutes = round(total_seconds / 60, 2)

            return JsonResponse({
                "success": False,
                "error": error_msg,
                "processing_time_minutes": total_minutes
            }, status=500)

        # Filter for PDF files only
        pdf_files = [f for f in all_files if f.lower().endswith('.pdf')]
        total_pdfs = len(pdf_files)

        print(f"Found {total_pdfs} PDF file(s) to process")

        # Process each PDF file
        pdf_success = 0
        pdf_failures = 0
        processed_names = set()
        processor = PDFProcessorService()

        print(f"\n{'='*60}")
        print(f"Processing PDFs from: {config.PDF_FOLDER_PATH}")
        print('='*60)

        for idx, pdf_filename in enumerate(pdf_files, 1):
            # Get source name (filename without .pdf extension)
            source_name = pdf_filename[:-4] if pdf_filename.lower().endswith('.pdf') else pdf_filename

            # Skip if we already processed a file with this name
            if source_name in processed_names:
                print(f"\n[{idx}/{total_pdfs}] {pdf_filename}")
                print(f"⊗ Skipped: Duplicate filename")
                continue

            # Add to processed set
            processed_names.add(source_name)

            # Get full path to PDF file
            pdf_path = os.path.join(config.PDF_FOLDER_PATH, pdf_filename)

            print(f"\n[{idx}/{total_pdfs}] {pdf_filename}")

            try:
                # Process the PDF
                result = processor.process_pdf(
                    pdf_path=pdf_path,
                    source_name=source_name,
                    source_type="pdf"
                )

                pdf_success += 1
                print(f"✓ Success: Saved {result['chunks_created']} chunks")

            except Exception as error:
                pdf_failures += 1
                print(f"✗ Failed: {str(error)}")

        print(f"\n{'='*60}")
        print(f"PDF Processing Complete")
        print('='*60)
        print(f"Total PDFs found: {total_pdfs}")
        print(f"Successfully processed: {pdf_success}")
        print(f"Failed: {pdf_failures}")
        print('='*60)

        # STEP 3: Scrape and process website pages
        print("\nSTEP 3: Scraping website pages...")
        scrape_stats = extract_and_process_links()

        # STEP 4: Calculate total time
        end_time = time.time()
        total_seconds = end_time - start_time
        total_minutes = round(total_seconds / 60, 2)

        print(f"\n=== Database Indexing Completed Successfully ===")
        print(f"Total processing time: {total_minutes} minutes")

        # STEP 5: Return success response
        response_data = {
            "success": True,
            "message": "Database indexing completed successfully",
            "pages_indexed": scrape_stats["success_count"],
            "pages_failed": scrape_stats["error_count"],
            "total_pages": scrape_stats["total_pages"],
            "pdfs_processed": pdf_success,
            "pdfs_failed": pdf_failures,
            "total_pdfs": total_pdfs,
            "processing_time_minutes": total_minutes
        }
        return JsonResponse(response_data, status=200)

    except Exception as error:
        print(f"Error during database indexing: {str(error)}")
        error_msg = f"Failed to index database: {str(error)}"

        # Calculate time even on error
        end_time = time.time()
        total_seconds = end_time - start_time
        total_minutes = round(total_seconds / 60, 2)

        return JsonResponse({
            "success": False,
            "error": error_msg,
            "processing_time_minutes": total_minutes
        }, status=500)

@csrf_exempt
@require_GET
#This endpoint will be used to keep the backend alive on Render. It simply returns a success message.
def keep_alive(request):
    return JsonResponse({"success": True, "message": "Backend is alive!"}, status=200)

# ------------------------------ CRUD ENDPOINTS ------------------------------ #

@csrf_exempt
@require_POST
def register(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    email = str(payload.get("email", "")).strip().lower()
    name = str(payload.get("name", "")).strip()
    surname = str(payload.get("surname", "")).strip()
    password = str(payload.get("password", ""))

    if not email or not password:
        return JsonResponse({"error": "email and password are required."}, status=400)

    if len(password) < 6:
        return JsonResponse({"error": "password must have at least 6 characters."}, status=400)

    if User.objects.filter(email__iexact=email).exists() or User.objects.filter(username__iexact=email).exists():
        return JsonResponse({"error": "email is already in use."}, status=409)

    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        first_name=name,
        last_name=surname,
    )

    user_group, _ = Group.objects.get_or_create(name=USER_ROLE)
    user.groups.add(user_group)

    return JsonResponse(
        {
            "success": True,
            "message": "User registered successfully.",
            "user": {
                "email": user.email,
                "name": user.first_name,
                "surname": user.last_name,
                "role": USER_ROLE,
            },
        },
        status=201,
    )


@csrf_exempt
@require_POST
def login(request):
    try:
        payload = json.loads(request.body.decode("utf-8"))
    except Exception:
        return JsonResponse({"error": "Invalid JSON body."}, status=400)

    email = str(payload.get("email", "")).strip().lower()
    password = str(payload.get("password", ""))

    if not email or not password:
        return JsonResponse({"error": "email and password are required."}, status=400)

    user_by_email = User.objects.filter(email__iexact=email).first()

    if not user_by_email:
        return JsonResponse({"error": "Invalid credentials."}, status=401)

    authenticated_user = authenticate(request, username=user_by_email.username, password=password)
    if not authenticated_user:
        return JsonResponse({"error": "Invalid credentials."}, status=401)

    role = ADMIN_ROLE if authenticated_user.groups.filter(name=ADMIN_ROLE).exists() else USER_ROLE

    AuthToken.objects.filter(user=authenticated_user).delete()
    token = AuthToken.objects.create(user=authenticated_user)

    return JsonResponse(
        {
            "success": True,
            "token": token.key,
            "user": {
                "email": authenticated_user.email,
                "name": authenticated_user.first_name,
                "surname": authenticated_user.last_name,
                "role": role,
            },
        },
        status=200,
    )


@csrf_exempt
@require_POST
def logout(request):
    authorization = request.headers.get("Authorization", "")
    if not authorization.startswith("Bearer "):
        return JsonResponse({"error": "Missing or invalid Authorization header."}, status=401)

    token_key = authorization.split(" ", 1)[1].strip()
    if not token_key:
        return JsonResponse({"error": "Missing token."}, status=401)

    deleted_count, _ = AuthToken.objects.filter(key=token_key).delete()
    if deleted_count == 0:
        return JsonResponse({"error": "Invalid token."}, status=401)

    return JsonResponse({"success": True, "message": "Logged out successfully."}, status=200)
