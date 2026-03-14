# ChatBot-BackEnd 🤖

A powerful AI-driven chatbot backend built with Django that leverages Google's Gemini API and MongoDB for intelligent question-answering. The system automatically scrapes web content and processes PDF documents to build a comprehensive knowledge base.

## 📋 Table of Contents

- [Features](#features)
- [Installation](#installation)
- [Configuration](#configuration)
- [API Endpoints](#api-endpoints)
- [Project Structure](#project-structure)
- [Services](#services)
- [Database Schema](#database-schema)
- [Deployment](#deployment)

## ✨ Features

- **AI-Powered Q&A**: Uses Google Gemini API to generate intelligent responses
- **Vector Search**: MongoDB Atlas Vector Search for semantic similarity matching
- **Web Scraping**: Automatic scraping of TUS website course and policies pages
- **PDF Processing**: Extract text and create embeddings from PDF documents
- **Smart Chunking**: Intelligent text segmentation for better retrieval
- **Vector Embeddings**: Google's text-embedding-001 model for semantic understanding
- **Real-time Indexing**: Build and update knowledge base on demand
- **Detailed Debug Info**: Comprehensive timing and performance metrics

## 📦 Installation

### Prerequisites
- Python 3.11+
- MongoDB Atlas account with Vector Search enabled
- Google Gemini API key
- Render account (for deployment, optional)

### Local Setup

1. **Clone the repository**
```bash
git clone <https://github.com/parzanini/ChatBot-BackEnd >
cd ChatBot-BackEnd
```

2. **Create virtual environment**
```bash
python -m venv .venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # macOS/Linux
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Create `.env` file**
```env
GEMINI_API_KEY=your_gemini_api_key_here
MONGODB_URI=your_mongodb_connection_string
PDF_FOLDER_PATH=./pdfs
```

5. **Run migrations**
```bash
python manage.py migrate
```

6. **Start development server**
```bash
python manage.py runserver
```

The server will be available at `http://localhost:8000/`

## ⚙️ Configuration

Edit `core/config.py` to customize:

```python
# API Settings
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.0-flash"  # AI model
EMBEDDING_MODEL = "text-embedding-001"  # Embedding model

# Database Settings
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DATABASE = "chatbot_db"
MONGODB_COLLECTION = "knowledge_base"

# Vector Search Settings
VECTOR_INDEX_NAME = "vector_index"
MIN_VECTOR_SCORE = 0.6  # Minimum similarity threshold
TOP_K_RESULTS = 5  # Number of results to retrieve

# Web Scraping
PDF_FOLDER_PATH = os.getenv("PDF_FOLDER_PATH", "./pdfs")
SCRAPING_URLS = [
    "https://tus.ie/courses/",
    "https://tus.ie/admissions/midwest/"
]
```

## 🔌 API Endpoints

### 0. Authentication (Email + Password)

Role policy:
- `USER`: can self-sign up using `register`
- `ADMIN`: created manually in DB

#### Register

**Endpoint**: `POST /api/register/`

**Request**:
```json
{
  "email": "user@example.com",
  "name": "Ana",
  "surname": "Silva",
  "password": "strongpass123"
}
```

**Response**:
```json
{
  "success": true,
  "message": "User registered successfully.",
  "user": {
    "email": "user@example.com",
    "name": "Ana",
    "surname": "Silva",
    "role": "USER"
  }
}
```

#### Login (shared endpoint for mobile and dashboard)

**Endpoint**: `POST /api/login/`

**Request**:
```json
{
  "email": "user@example.com",
  "password": "strongpass123"
}
```

**Response**:
```json
{
  "success": true,
  "token": "<bearer_token>",
  "user": {
    "email": "user@example.com",
    "name": "Ana",
    "surname": "Silva",
    "role": "USER"
  }
}
```

#### Logout

**Endpoint**: `POST /api/logout/`

**Headers**:
- `Authorization: Bearer <token>`

**Response**:
```json
{
  "success": true,
  "message": "Logged out successfully."
}
```

### 1. Ask Chatbot a Question

**Endpoint**: `POST /api/ask/`

**Request**:
```json
{
  "query": "What courses does TUS offer?"
}
```

**Response**:
```json
{
  "answer": "TUS offers a wide range of courses including...",
  "sources": [
    {
      "title": "Bachelor of Science in Computer Science",
      "source_name": "TUS Courses",
      "url": "https://tus.ie/courses/computer-science/",
      "score": 0.8743
    }
  ],
  "debug": {
    "query": "What courses does TUS offer?",
    "matches": 5,
    "embedding_time_ms": 245,
    "vector_time_ms": 85,
    "total_time_ms": 1250,
    "top_score": 0.8743,
    "similarities": [0.8743, 0.7521, 0.6892]
  }
}
```

**Error Response**:
```json
{
  "error": "Vector search failed: ..."
}
```

### 2. Upload PDF

**Endpoint**: `POST /api/upload_pdf/`

**Request** (multipart/form-data):
- `file`: PDF file
- `source_name`: Optional custom name

**Response**:
```json
{
  "success": true,
  "message": "PDF processed successfully",
  "chunks_created": 42,
  "source_name": "Student Handbook 2025",
  "processing_time_minutes": 1.25
}
```

### 3. Index Database

**Endpoint**: `POST /api/index_database/`

**Response**:
```json
{
  "success": true,
  "message": "Database indexing completed successfully",
  "pages_indexed": 51,
  "pages_failed": 0,
  "total_pages": 51,
  "pdfs_processed": 3,
  "pdfs_failed": 0,
  "total_pdfs": 3,
  "processing_time_minutes": 5.43
}
```

### 4. Get Index Database Run History (Scrape TUS Website table)

Returns the last 20 times the `index_database` endpoint was triggered, including whether each run succeeded, how many pages and PDFs were processed, and how long it took.

**Endpoint**: `GET /api/index_database_runs/`

**Response**:
```json
{
  "success": true,
  "count": 2,
  "results": [
    {
      "id": 12,
      "created_at": "2026-03-14T10:30:00.000000+00:00",
      "success": true,
      "message": "Database indexing completed successfully",
      "error": null,
      "pages_indexed": 51,
      "pages_failed": 0,
      "total_pages": 51,
      "pdfs_processed": 3,
      "pdfs_failed": 0,
      "total_pdfs": 3,
      "processing_time_minutes": 5.43,
      "payload": { }
    },
    {
      "id": 11,
      "created_at": "2026-03-13T08:15:00.000000+00:00",
      "success": false,
      "message": null,
      "error": "Failed to index database: connection timeout",
      "pages_indexed": null,
      "pages_failed": null,
      "total_pages": null,
      "pdfs_processed": null,
      "pdfs_failed": null,
      "total_pdfs": null,
      "processing_time_minutes": 0.12,
      "payload": { }
    }
  ]
}
```

| Field | Description |
|---|---|
| `id` | Unique run ID |
| `created_at` | When the run was triggered (ISO 8601) |
| `success` | `true` if the run completed without errors |
| `message` | Success message (null on failure) |
| `error` | Error message (null on success) |
| `pages_indexed` | Website pages successfully scraped |
| `pages_failed` | Website pages that failed |
| `total_pages` | Total website pages found |
| `pdfs_processed` | PDFs from the PDFs folder successfully indexed |
| `pdfs_failed` | PDFs from the PDFs folder that failed |
| `total_pdfs` | Total PDFs found in the PDFs folder |
| `processing_time_minutes` | Total run duration in minutes |
| `payload` | Full raw payload stored at the time of the run |

---

### 5. Get Manually Uploaded PDFs (Knowledge Base Management table)

Returns all PDF documents that were uploaded via the `upload_pdf` endpoint.
Each entry represents one unique PDF, grouped by its source name, with the upload date and total chunk count.

**Endpoint**: `GET /api/manual_uploads/`

**Response**:
```json
{
  "success": true,
  "count": 2,
  "documents": [
    {
      "document_name": "Student Handbook 2025",
      "source_name": "Student Handbook 2025",
      "upload_date": "2026-03-10T14:22:00.000000+00:00",
      "file_type": "pdf",
      "file_size": null,
      "chunks_count": 42
    },
    {
      "document_name": "TUS Academic Calendar",
      "source_name": "TUS Academic Calendar",
      "upload_date": "2026-03-01T09:05:00.000000+00:00",
      "file_type": "pdf",
      "file_size": null,
      "chunks_count": 17
    }
  ]
}
```

| Field | Description |
|---|---|
| `document_name` | The name of the PDF (same as `source_name`) |
| `source_name` | The name used when the PDF was uploaded |
| `upload_date` | Earliest chunk creation date — effectively the upload date (ISO 8601) |
| `file_type` | Always `"pdf"` for manually uploaded documents |
| `file_size` | Not stored — always `null` |
| `chunks_count` | Number of text chunks the PDF was split into |

> **Note:** `file_size` is `null` because file size is not persisted in the MongoDB chunks collection. It can be added to the upload flow in the future if needed.

#### Delete a manually uploaded PDF

Deletes one PDF that was previously uploaded through the `upload_pdf` endpoint.
Only documents with `sourceType = "Manual Upload"` are affected, so PDFs indexed from the configured folder are not removed by this endpoint.

**Endpoint**: `DELETE /api/manual_uploads/`

**Request**:
```json
{
  "source_name": "Student Handbook 2025"
}
```

**Success Response**:
```json
{
  "success": true,
  "message": "Manual uploaded PDF deleted successfully.",
  "source_name": "Student Handbook 2025",
  "deleted_chunks": 42
}
```

**Not Found Response**:
```json
{
  "success": false,
  "error": "No manually uploaded PDF found with source_name 'Student Handbook 2025'."
}
```

**Validation Error Response**:
```json
{
  "success": false,
  "error": "source_name is required."
}
```

## 📁 Project Structure

```
ChatBot-BackEnd/
├── chatbotbackend/          # Django project settings
│   ├── settings.py          # Django configuration
│   ├── urls.py              # URL routing
│   ├── asgi.py              # ASGI config
│   └── wsgi.py              # WSGI config
│
├── core/                    # Main application
│   ├── views.py             # API endpoints
│   ├── config.py            # Configuration
│   ├── documents.py         # MongoDB document models
│   ├── urls.py              # App URL patterns
│   │
│   └── services/            # Business logic services
│       ├── embedding_service.py       # Vector embedding generation
│       ├── pdf_processor_service.py   # PDF text extraction & chunking
│       ├── storage_service.py         # MongoDB operations
│       ├── vector_search_service.py   # Semantic search
│       ├── chunker_service.py         # Text chunking logic
│       └── web_scraper_service.py     # Web scraping logic
│
├── requirements.txt         # Python dependencies
├── manage.py               # Django management
├── db.sqlite3              # SQLite (minimal use)
└── README.md              # This file
```

## 🗄️ Database Schema

### MongoDB Document Structure

```javascript
{
  _id: ObjectId,
  text: "Extracted text content...",
  title: "Page/Document Title",
  source_type: "pdf" | "web",
  source_name: "Student Handbook 2025",
  source_url: "https://example.com/page",
  embedding: [0.123, -0.456, 0.789, ...],  // 3072 dimensions
  chunk_index: 0,
  total_chunks: 42,
  created_at: ISODate("2026-02-21T10:30:00Z")
}
```

### Vector Index Configuration

```javascript
{
  "name": "vector_index",
  "definition": {
    "fields": [
      {
        "type": "vector",
        "path": "embedding",
        "similarity": "cosine",
        "dimensions": 3072
      }
    ]
  }
}
```

## 🚀 Deployment

### Deploy to Render

1. **Create PostgreSQL Database**
- Go to [render.com](https://render.com)
- Click **New** → **PostgreSQL**
- Choose **Free** plan (500 MB, expires after 90 days but renewable)
- Copy the **Internal Database URL** (starts with `postgresql://`)

2. **Push to GitHub**
```bash
git push origin main
```

3. **Create Web Service**
- Go to [render.com](https://render.com)
- Click **New** → **Web Service**
- Connect your GitHub repository
- Configure:
  - **Build Command**: `pip install -r requirements.txt`
  - **Start Command**: `gunicorn chatbotbackend.wsgi:application --bind 0.0.0.0:$PORT`

4. **Set Environment Variables**
Add these in your web service settings:
- `GEMINI_API_KEY`: Your Gemini API key
- `MONGODB_URI`: Your MongoDB Atlas connection string
- `DATABASE_URL`: The PostgreSQL Internal Database URL (from step 1)
- `DJANGO_SECRET_KEY`: Your secret key

5. **Run Migrations After First Deploy**
Open the **Shell** tab in your Render web service and run:
```bash
python manage.py migrate
```

## 📝 License

This project is part of the FYP (Final Year Project) at TUS.

## 👨‍💻 Author: Thiago Gomes Parzanini

Created as an academic project for chatbot development and AI integration.

---

**Last Updated**: March 14, 2026
