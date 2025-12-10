class VectorSearchService:
    """
    This class searches for similar text chunks in the database.

    What it does:
    - Takes a query (like "What are the courses?")
    - Finds chunks that are similar to the query
    - Returns the most relevant chunks

    How it works:
    - Uses "vector search" which compares embeddings (lists of numbers)
    - Similar embeddings = similar meaning
    - Returns chunks sorted by similarity score
    """

    def __init__(self, collection, vector_index_name, vector_limit=5,
                 num_candidates=100, min_score=0.2):
        """
        Set up the vector search service.

        Args:
        collection: The MongoDB collection to search in
        vector_index_name: Name of the vector index (set up in MongoDB)
        vector_limit: How many results to return (default 5)
        num_candidates: How many to consider before filtering (default 100)
        min_score: Minimum similarity score to accept (default 0.2)
        """

        # Save the MongoDB collection
        self.collection = collection

        # Save the index name
        self.vector_index_name = vector_index_name

        # How many results to return
        self.vector_limit = vector_limit

        # How many candidates to consider
        self.num_candidates = num_candidates

        # Minimum score (0.0 to 1.0, where 1.0 is perfect match)
        self.min_score = min_score

    def search(self, query_embedding):
        """
        Search for chunks similar to the query.

        Steps:
        1. Build a search query (MongoDB)
        2. Run the search in MongoDB
        3. Get results with their similarity scores
        4. Filter out low scores
        5. Return the good results

        Args:
            query_embedding: The query as an embedding

        Returns:
            A list of matching chunks, each with:
                - title: The chunk's title
                - text: The chunk's content
                - score: How similar it is (0.0 to 1.0)
        """
        # STEP 1: Build the search query
        # This is a MongoDB "aggregation pipeline"
        # A MongoDB pipeline is a series of steps to process data
        pipeline = [
            {
                # Part 1: Do vector search
                "$vectorSearch": {
                    "index": self.vector_index_name,  # Which index to use
                    "path": "embedding",  # Where embeddings are stored
                    "queryVector": query_embedding,  # What I am searching for
                    "numCandidates": self.num_candidates,  # How many to consider
                    "limit": self.vector_limit  # How many to return
                }
            },
            {
                # Part 2: Choose what fields to return
                "$project": {
                    "_id": 0,  # 0 = exclude _id
                    "title": 1,  # Include title
                    "text": 1,  # Include text
                    "score": {"$meta": "vectorSearchScore"}  # Include similarity score
                }
            }
        ]
        # STEP 2: Run the search in MongoDB
        search_results = self.collection.aggregate(pipeline)