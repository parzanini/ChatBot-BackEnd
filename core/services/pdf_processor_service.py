class PDFProcessorService:
    """
    This class processes PDF files for the chatbot.

    What it does:
    1. Reads text from a PDF file
    2. Splits the text into chunks
    3. Creates embeddings for each chunk
    4. Saves everything to MongoDB

    It uses these helper components:
    - Chunker: Splits text into pieces
    - EmbeddingService: Converts text to numbers
    - KnowledgeStore: Saves to database
    """

    def __init__(self):
        """
        Set up the PDF processor.

        This creates the helper components we need.
        """
        # Create a chunker to split text
        self.chunker = Chunker()

        # Create an embedding service to convert text to numbers
        self.embedding_service = EmbeddingService()

        # Create a storage to save to database
        self.storage = KnowledgeStore()

    def extract_text(self, pdf_path):
        """
        Read all the text from a PDF file.

        Steps:
        1. Open the PDF
        2. Go through each page
        3. Extract text from each page
        4. Join all pages together

        Args:
            pdf_path: The file path to the PDF (like "C:/documents/handbook.pdf")

        Returns:
            All the text from the PDF as one long string
        """
        # List to store text from each page
        all_pages = []