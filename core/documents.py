from datetime import datetime, timezone

import mongoengine as me


class KnowledgeChunk(me.Document):
    """Store knowledge chunks with embeddings using MongoEngine"""

    chunkId = me.IntField(primary_key=True, required=True, db_field="chunkId")
    title = me.StringField(max_length=255, db_field="title")
    text = me.StringField(required=True, db_field="text")
    embedding = me.ListField(me.FloatField(), required=False, db_field="embedding")
    sourceType = me.StringField(max_length=20, required=True, default="pdf", db_field="sourceType")
    sourceName = me.StringField(max_length=255, required=True, db_field="sourceName")
    sourceUrl = me.StringField(max_length=500, db_field="sourceUrl")
    createdAt = me.DateTimeField(default=lambda: datetime.now(timezone.utc), db_field="createdAt")

    # Use default _id index provided by MongoDB (chunkId is primary_key -> _id).
    meta = {
        'collection': 'knowledgeChunks',
        'indexes': [
            {  # Text index for search across title and text
                'fields': ["$title", "$text"],
                'default_language': 'english'
            }
        ]
    }

    def __str__(self):
        return f"Chunk {self.chunkId}: {self.title[:50]}"
