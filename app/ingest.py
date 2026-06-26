"""
ingest.py
---------
Turns a raw PDF into a searchable FAISS index.

This is the core of the "R" in RAG (Retrieval Augmented Generation).
The pipeline is:

    PDF bytes -> extract raw text -> split into chunks
              -> embed each chunk -> store in FAISS index

We then save that FAISS index to disk so we don't have to re-embed
the same document every single time someone asks a question - only
once, when the document is first uploaded.
"""

import io
import pickle
from pypdf import PdfReader
import numpy as np
import faiss

from app import storage, llm


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Pulls all the raw text out of a PDF's pages and joins it together.

    pypdf reads the PDF page by page. We join everything into one
    big string for now - the chunking step (next function) is what
    actually breaks it into manageable, meaningful pieces.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    full_text = ""
    for page in reader.pages:
        full_text += page.extract_text() + "\n"
    return full_text


def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list[str]:
    """
    Splits a long piece of text into smaller overlapping chunks.

    Parameters:
        chunk_size: roughly how many characters per chunk
        overlap: how many characters each chunk repeats from the
                 previous one

    Why chunks need to be SMALL:
    Embedding models work best on focused pieces of text, not entire
    documents. A chunk that's "too big" mixes multiple ideas together
    and its embedding becomes a blurry average that matches almost
    nothing well.

    Why chunks need to OVERLAP:
    Imagine a sentence describing something important gets cut exactly
    in half between two chunks. Without overlap, neither chunk alone
    fully captures that idea. The overlap means important sentences
    near a chunk boundary usually appear *complete* in at least one
    chunk.

    This is a simple, naive chunker (fixed character count). It's
    perfectly fine for Phase 1. In a later phase we could upgrade to
    smarter chunking that respects paragraph/sentence boundaries -
    that's a good "what I'd improve next" line for your README.
    """
    chunks = []
    start = 0
    text_length = len(text)

    while start < text_length:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        # Move forward by (chunk_size - overlap), not chunk_size,
        # so consecutive chunks share a bit of text at the boundary.
        start += chunk_size - overlap

    return chunks


def build_index(chunks: list[str]) -> tuple[faiss.Index, list[str]]:
    """
    Embeds every chunk and builds a FAISS index for fast similarity search.

    FAISS (Facebook AI Similarity Search) is a library specifically
    built for searching through large numbers of vectors quickly.
    Think of it as a search engine, but for "meaning" instead of
    keywords.

    Returns both:
        - the FAISS index itself (for searching)
        - the original list of chunks (so when FAISS tells us
          "chunk #7 is the best match", we can look up what
          chunk #7 actually SAYS)
    """
    print(f"Embedding {len(chunks)} chunks...")
    embeddings = []
    for i, chunk in enumerate(chunks):
        embedding = llm.get_embedding(chunk)
        embeddings.append(embedding)
        print(f"  Embedded chunk {i + 1}/{len(chunks)}")

    # FAISS needs a numpy array of float32 numbers, not a plain Python list
    embeddings_array = np.array(embeddings).astype("float32")

    # IndexFlatL2 = the simplest FAISS index type. It does an exact
    # search by measuring straight-line ("Euclidean") distance between
    # vectors. It's not the fastest option for millions of documents,
    # but for a single uploaded PDF it's more than fast enough, and
    # it's the easiest to understand and debug. We can swap to a
    # faster approximate index later if needed.
    dimension = embeddings_array.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings_array)

    return index, chunks


def save_index(index: faiss.Index, chunks: list[str], doc_id: str):
    """
    Saves the FAISS index and its matching chunks to local disk.

    Why save chunks separately alongside the index:
    FAISS only stores the NUMBERS (embeddings). It has no idea what
    text those numbers came from. We use Python's pickle module to
    save the original chunk text in the same order, so we can match
    "vector #3" back to "the actual sentence that vector represents".

    For Phase 1 we save to local disk. In Phase 3 we'll look at
    persisting this in S3 instead, so it survives across deployments.
    """
    faiss.write_index(index, f"local_index/{doc_id}.faiss")
    with open(f"local_index/{doc_id}_chunks.pkl", "wb") as f:
        pickle.dump(chunks, f)


def load_index(doc_id: str) -> tuple[faiss.Index, list[str]]:
    """
    Loads a previously saved FAISS index and its chunks back from disk.
    """
    index = faiss.read_index(f"local_index/{doc_id}.faiss")
    with open(f"local_index/{doc_id}_chunks.pkl", "rb") as f:
        chunks = pickle.load(f)
    return index, chunks


def ingest_document(s3_key: str, doc_id: str):
    """
    The full pipeline, start to finish:
    S3 -> extract text -> chunk -> embed -> FAISS index -> save to disk

    This is the ONE function the rest of the app calls. Everything
    above this is internal plumbing - main.py will just call
    ingest_document() and not need to know HOW any of it works.
    """
    print(f"Fetching {s3_key} from S3...")
    pdf_bytes = storage.read_file_bytes(s3_key)

    print("Extracting text...")
    text = extract_text_from_pdf(pdf_bytes)
    print(f"Extracted {len(text)} characters")

    print("Chunking text...")
    chunks = chunk_text(text)
    print(f"Created {len(chunks)} chunks")

    index, chunks = build_index(chunks)

    import os
    os.makedirs("local_index", exist_ok=True)
    save_index(index, chunks, doc_id)
    print(f"Index saved as local_index/{doc_id}.faiss")

    return index, chunks


# --- Quick manual test ---
if __name__ == "__main__":
    # First, upload our sample PDF to S3 (if not already there)
    with open("sample_docs/company_handbook.pdf", "rb") as f:
        pdf_bytes = f.read()

    test_s3_key = "documents/company_handbook.pdf"
    storage.upload_bytes(pdf_bytes, test_s3_key)
    print(f"Uploaded sample PDF to {test_s3_key}\n")

    # Now run the full ingestion pipeline on it
    ingest_document(s3_key=test_s3_key, doc_id="company_handbook")