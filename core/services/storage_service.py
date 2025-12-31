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

        # Validate inputs
        if not chunks or not embeddings:
            return 400, {"error": "chunks and embeddings cannot be empty"}

        if len(chunks) != len(embeddings):
            return 400, {
                "error": f"Chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch"
            }

        if titles and len(titles) != len(chunks):
            return 400, {
                "error": f"Titles ({len(titles)}) and chunks ({len(chunks)}) length mismatch"
            }

        # Delete old chunks from this source
        try:
            if source_url:
                self.delete_by_source(source_url=source_url)
            else:
                self.delete_by_source(source_type=source_type, source_name=source_name)
        except Exception as error:
            return 500, {"error": f"Failed to delete old chunks: {str(error)}"}

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
            except Exception as error:
                return 500, {
                    "error": f"Failed to save chunk {i}: {str(error)}",
                    "saved_count": saved_count
                }

        return 200, {"saved_count": saved_count}

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
                deleted = KnowledgeChunk.objects(sourceUrl=source_url).delete()
            elif source_type and source_name:
                # Delete by source type and name (for PDFs)
                deleted = KnowledgeChunk.objects(
                    sourceType=source_type,
                    sourceName=source_name
                ).delete()
            else:
                raise ValueError("Must provide either source_url or both source_type and source_name")

            return {"deleted_count": deleted}
        except Exception as error:
            raise Exception(f"Failed to delete chunks: {str(error)}")


