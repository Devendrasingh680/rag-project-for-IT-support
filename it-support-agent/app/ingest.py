"""
Ingestion pipeline: reads company IT docs (markdown/txt) from sample_docs/,
chunks them by semantic unit (not fixed token windows — see README),
embeds them, and upserts into Pinecone with metadata for filtering.

Run: python -m app.ingest
"""
import os
import glob
import hashlib
from pinecone import Pinecone, ServerlessSpec
from sentence_transformers import SentenceTransformer

from app import config

DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "sample_docs")


def load_documents(docs_dir: str) -> list[dict]:
    """
    Each markdown file = one procedure/policy doc. We chunk by '## ' headers
    (sub-sections within a doc) rather than fixed token windows, because
    IT procedures lose meaning if a numbered step gets split across chunks.
    Metadata (doc_type, system) is inferred from filename convention:
        <system>__<doc_type>__<title>.md
        e.g. vpn__runbook__connection-troubleshooting.md
    """
    chunks = []
    for filepath in glob.glob(os.path.join(docs_dir, "*.md")):
        filename = os.path.basename(filepath)
        parts = filename.replace(".md", "").split("__")
        system = parts[0] if len(parts) > 0 else "general"
        doc_type = parts[1] if len(parts) > 1 else "doc"
        title = parts[2] if len(parts) > 2 else filename

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        # Split on level-2 headers to keep each chunk a coherent sub-topic
        sections = content.split("\n## ")
        for i, section in enumerate(sections):
            text = section if i == 0 else "## " + section
            text = text.strip()
            if not text or len(text) < 30:
                continue  # skip empty/trivial fragments
            chunk_id = hashlib.md5(f"{filename}-{i}".encode()).hexdigest()
            chunks.append({
                "id": chunk_id,
                "text": text,
                "metadata": {
                    "source_file": filename,
                    "system": system,
                    "doc_type": doc_type,
                    "title": title,
                    "section_index": i,
                }
            })
    return chunks


def build_index():
    if not config.PINECONE_API_KEY:
        raise RuntimeError("PINECONE_API_KEY not set. Copy .env.example to .env and fill it in.")

    pc = Pinecone(api_key=config.PINECONE_API_KEY)

    existing_indexes = [idx["name"] for idx in pc.list_indexes()]
    if config.PINECONE_INDEX_NAME not in existing_indexes:
        print(f"Creating Pinecone index '{config.PINECONE_INDEX_NAME}'...")
        pc.create_index(
            name=config.PINECONE_INDEX_NAME,
            dimension=config.EMBEDDING_DIM,
            metric="cosine",
            spec=ServerlessSpec(cloud=config.PINECONE_CLOUD, region=config.PINECONE_REGION),
        )
    else:
        print(f"Index '{config.PINECONE_INDEX_NAME}' already exists, reusing it.")

    index = pc.Index(config.PINECONE_INDEX_NAME)

    print("Loading embedding model (first run downloads ~90MB, cached after)...")
    model = SentenceTransformer(config.EMBEDDING_MODEL)

    chunks = load_documents(DOCS_DIR)
    if not chunks:
        raise RuntimeError(f"No .md files found in {DOCS_DIR}. Add company docs first.")

    print(f"Embedding {len(chunks)} chunks...")
    texts = [c["text"] for c in chunks]
    embeddings = model.encode(texts, show_progress_bar=True)

    vectors = []
    for chunk, emb in zip(chunks, embeddings):
        vectors.append({
            "id": chunk["id"],
            "values": emb.tolist(),
            "metadata": {**chunk["metadata"], "text": chunk["text"]},
        })

    print(f"Upserting {len(vectors)} vectors into Pinecone...")
    batch_size = 100
    for i in range(0, len(vectors), batch_size):
        index.upsert(vectors=vectors[i:i + batch_size])

    print("Done. Index stats:", index.describe_index_stats())


if __name__ == "__main__":
    build_index()
