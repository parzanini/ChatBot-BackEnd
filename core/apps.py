# Django AppConfig for chatbotapp that connects to MongoDB using MongoEngine.
import logging
from django.apps import AppConfig
from django.conf import settings
_mongo_connected = False


class ChatbotappConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chatbotapp'

    def ready(self):
        """Connect to MongoDB using MongoEngine once at startup."""
        global _mongo_connected
        if _mongo_connected:
            return
        logger = logging.getLogger(__name__)
        try:
            import mongoengine
        except ImportError as imp_err:
            logger.error("MongoEngine not installed: %s", imp_err)
            return
        try:
            db_name = getattr(settings, 'MONGODB_DB_NAME', 'Chatbot')
            uri = getattr(settings, 'MONGODB_URI', None)
            if not uri or '<' in str(uri) or '>' in str(uri):
                logger.error("MONGODB_URI is not configured correctly. Set a real connection string in your environment (.env or service vars).")
                return
            mongoengine.connect(
                db=db_name,
                host=uri,
                uuidRepresentation='standard',
            )
            _mongo_connected = True
            logger.info("MongoEngine connected to %s", db_name)
        except Exception as exc:  # broad so we don't crash startup
            logger.error("MongoEngine connection failed: %s", exc)
