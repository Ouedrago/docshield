"""
retriever.py
------------
Takes a user's QUESTION and finds the most relevant chunks from a
document's FAISS index.

This is the "Retrieval" half of RAG. ingest.py already did the hard
work of turning the document into searchable vectors - this file is
what makes that searchable on demand, every time someone asks something.

The flow:
    user question -> embed the question -> search FAISS index
    -> get back the N closest chunks -> return them as context
"""

import time
from app import logger
import numpy as np
from app import ingest, llm



def retrieve_relevant_chunks(question: str, doc_id: str, top_k: int = 3) -> list[str]:
    """
    Finds the chunks most relevant to a user's question.

    Parameters:
        question: what the user typed in
        doc_id: which document's index to search (matches the doc_id
                used in ingest_document())
        top_k: how many chunks to return. 3 is a reasonable starting
               point - enough context to answer most questions, not
               so much that we drown Claude in irrelevant text or
               blow through token limits.

    Returns:
        A list of the top_k most relevant chunk strings, ordered by
        relevance (closest match first).

    Why we embed the QUESTION the same way we embedded the chunks:
    FAISS can only compare vectors to other vectors. To find chunks
    "similar in meaning" to the question, the question itself has to
    become a vector using the EXACT SAME embedding model. If we used
    a different model here than we used in ingest.py, the vectors
    would live in different "meaning spaces" and comparing them would
    be meaningless - like comparing a distance in miles to a distance
    in kilograms.
    """
    # Load the FAISS index and chunks we saved during ingestion
    index, chunks = ingest.load_index(doc_id)

    # Embed the question using the SAME Titan model used for the chunks
    question_embedding = llm.get_embedding(question)
    question_vector = np.array([question_embedding]).astype("float32")

    # FAISS search: returns two things -
    #   distances = how far each match is (lower = more similar)
    #   indices = WHICH chunks those are (their position in our list)
    distances, indices = index.search(question_vector, top_k)

    # indices is a 2D array (because FAISS supports searching multiple
    # questions at once) - we only searched one question, so we take
    # row [0] to get our actual list of chunk positions.
    relevant_chunks = [chunks[i] for i in indices[0]]

    return relevant_chunks


def answer_question(question: str, doc_id: str,
                    session_id: str = "local") -> str:
    start = time.time()

    relevant_chunks = retrieve_relevant_chunks(question, doc_id)
    context = "\n---\n".join(relevant_chunks)
    answer = llm.ask_claude(question=question, context=context)

    latency_ms = int((time.time() - start) * 1000)
    logger.log_query(
        session_id=session_id,
        doc_id=doc_id,
        question=question,
        chunks_retrieved=len(relevant_chunks),
        latency_ms=latency_ms,
    )
    return answer


# --- Quick manual test ---
if __name__ == "__main__":
    test_questions = [
        "When was the company founded and who founded it?",
        "How many days of annual leave do employees get?",
        "What is the maximum expense I can claim without approval?",
        "What is the capital of France?",  # deliberately OFF-TOPIC test
    ]

    for q in test_questions:
        print(f"\nQ: {q}")
        answer = answer_question(q, doc_id="company_handbook")
        print(f"A: {answer}")