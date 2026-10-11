import os
from dotenv import load_dotenv

load_dotenv()

CONN_SA = os.getenv("CONN_SA")
CONN_PG = os.getenv("CONN_PG")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL")
CHAT_MODEL = os.getenv("CHAT_MODEL")
COLLECTION_NAME = os.getenv("COLLECTION_NAME")