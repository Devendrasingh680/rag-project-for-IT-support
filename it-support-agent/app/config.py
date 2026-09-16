"""
Central configuration. All API keys come from environment variables —
never hardcode keys. Copy .env.example to .env and fill in your own.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- API Keys ---
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY", "")
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

# --- Pinecone ---
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "it-support-kb")
PINECONE_CLOUD = os.getenv("PINECONE_CLOUD", "aws")
PINECONE_REGION = os.getenv("PINECONE_REGION", "us-east-1")
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"  # 384-dim, runs locally, no extra API cost
EMBEDDING_DIM = 384

# --- Groq (LLM) ---
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# --- Retrieval sufficiency logic ---
# Design decision (see README "Design Decisions" section for justification):
# We use a hybrid approach — a cheap similarity threshold as a first filter,
# and only fall back to an LLM judge when the score is in the ambiguous zone.
# This avoids paying for an LLM call on every single query while still
# catching cases where a high-similarity chunk is actually irrelevant.
SIMILARITY_CONFIDENT_THRESHOLD = 0.80   # above this: trust it, skip judge
SIMILARITY_REJECT_THRESHOLD = 0.55      # below this: don't even bother judging, go to web
TOP_K = 5

# --- App ---
APP_HOST = os.getenv("APP_HOST", "0.0.0.0")
APP_PORT = int(os.getenv("APP_PORT", "8000"))
