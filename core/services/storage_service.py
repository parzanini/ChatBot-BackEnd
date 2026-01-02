import time
from mongoengine.connection import get_db
from core.documents import KnowledgeChunk


class KnowledgeStore:
    """
    This class saves and manages text chunks in MongoDB.

    What it does:
    - Saves chunks with their embeddings
    - Remembers where each chunk came from (PDF file or website)
    - Deletes old chunks before saving new ones (prevents duplicates)
    - Creates unique IDs for each chunk
    """

    def __init__(self, db_client=None):
        if db_client is None:
            db_client = get_db()
        self.db_client = db_client

    def save_chunks(self, chunks, embeddings, source_type, source_name,
                    titles=None, source_url=None):
        """
        Save text chunks and their embeddings to MongoDB.

        Returns:
            tuple: (status_code, response_dict)
                - (200, {"saved_count": int})
                - (400, {"error": str})
                - (500, {"error": str})
        """
        print(f"Starting to save chunks for source: {source_name} (type: {source_type})")
        print(f"Number of chunks to save: {len(chunks)}")

        # Validate inputs
        if not chunks or not embeddings:
            error_msg = "chunks and embeddings cannot be empty"
            print(f"Error: {error_msg}")
            return 400, {"error": error_msg}

        if len(chunks) != len(embeddings):
            error_msg = f"Chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch"
            print(f"Error: {error_msg}")
            return 400, {"error": error_msg}

        if titles and len(titles) != len(chunks):
            error_msg = f"Titles ({len(titles)}) and chunks ({len(chunks)}) length mismatch"
            print(f"Error: {error_msg}")
            return 400, {"error": error_msg}

        # Delete old chunks from this source
        # If delete fails due to connection error, continue anyway and save new chunks
        try:
            if source_url:
                print(f"Deleting old chunks for URL: {source_url}")
                self.delete_by_source(source_url=source_url)
            else:
                print(f"Deleting old chunks for source: {source_name}")
                self.delete_by_source(source_type=source_type, source_name=source_name)
            print("Successfully deleted old chunks")
        except Exception as error:
            # Log the error but don't fail - continue to save chunks
            print(f"Warning: Failed to delete old chunks: {str(error)}")
            # Continue processing instead of returning error

        # Save each chunk
        saved_count = 0
        for i in range(len(chunks)):
            try:
                unique_id = int(time.time() * 1000000) + i
                chunk_object = KnowledgeChunk(
                    chunkId=unique_id,
                    title=titles[i] if titles else None,
                    text=chunks[i],
                    embedding=list(embeddings[i]),
                    sourceType=source_type,
                    sourceName=source_name,
                    sourceUrl=source_url
                )
                chunk_object.save()
                saved_count += 1
                print(f"Successfully saved chunk {i} with ID {unique_id}")
            except Exception as error:
                error_msg = f"Failed to save chunk {i}: {str(error)}"
                print(f"Error: {error_msg}")
                return 500, {
                    "error": error_msg,
                    "saved_count": saved_count
                }

        print(f"Successfully saved {saved_count} chunks for source: {source_name}")
        return 200, {"saved_count": saved_count}

    def source_exists(self, source_type=None, source_name=None, source_url=None):
        """
        Check if a source already exists in the database.

        Args:
            source_type: Type of source ("pdf" or "website")
            source_name: Name of the source (like "Student Handbook" or "TUS Homepage")
            source_url: URL of the source (for websites)

        Returns:
            bool: True if source exists, False otherwise
        """
        try:
            if source_url:
                # Check by URL (for web scraping)
                exists = KnowledgeChunk.objects(sourceUrl=source_url).first()
            elif source_type and source_name:
                # Check by source type and name (for PDFs)
                exists = KnowledgeChunk.objects(
                    sourceType=source_type,
                    sourceName=source_name
                ).first()
            else:
                print("Warning: source_exists called without proper parameters")
                return False

            if exists:
                print(f"Source exists: {source_name if source_name else source_url}")
                return True
            else:
                print(f"Source does not exist: {source_name if source_name else source_url}")
                return False
        except Exception as error:
            print(f"Error checking if source exists: {str(error)}")
            return False

    def delete_by_source(self, source_type=None, source_name=None, source_url=None):
        """
        Delete all chunks from a specific source.

        This is used to remove old chunks before saving new ones from the same source
        (prevents duplicates and stale data).

        Args:
            source_type: Type of source ("pdf" or "website")
            source_name: Name of the source (like "Student Handbook" or "TUS Homepage")
            source_url: URL of the source (for websites)

        Returns:
            dict: {"deleted_count": number of chunks deleted}

        Raises:
            ValueError: If parameters are invalid
        """
        try:
            if source_url:
                # Delete by URL (for web scraping)
                print(f"Deleting chunks for URL: {source_url}")
                deleted = KnowledgeChunk.objects(sourceUrl=source_url).delete()
            elif source_type and source_name:
                # Delete by source type and name (for PDFs)
                print(f"Deleting chunks for source: {source_name}")
                deleted = KnowledgeChunk.objects(
                    sourceType=source_type,
                    sourceName=source_name
                ).delete()
            else:
                error_msg = "Must provide either source_url or both source_type and source_name"
                print(f"Error: {error_msg}")
                raise ValueError(error_msg)

            print(f"Successfully deleted {deleted} chunks")
            return {"deleted_count": deleted}
        except Exception as error:
            error_msg = f"Failed to delete chunks: {str(error)}"
            print(f"Error: {error_msg}")
            raise Exception(error_msg)

