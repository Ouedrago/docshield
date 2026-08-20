"""
main.py
-------
The Streamlit UI for DocShield.

This is the entry point for the application - the file a user actually
interacts with. It ties together every module we've built:
    - storage.py   → uploads the document to S3
    - ingest.py    → chunks, embeds, and indexes it in FAISS
    - security.py  → validates user input and detects PII
    - retriever.py → finds relevant chunks and gets Claude's answer

Run with: streamlit run app/main.py

Design principles for this UI:
  - Simple and honest: no fake "AI magic" aesthetics
  - Transparent: show the user what security checks ran
  - Useful for demo: the layout tells the DocShield story clearly
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import streamlit as st
from app import storage, ingest, security , logger
from app.retriever import answer_question

# -------------------------------------------------------------------
# PAGE CONFIG
# Must be the very first Streamlit call in the file - no exceptions.
# -------------------------------------------------------------------
st.set_page_config(
    page_title="DocShield",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# -------------------------------------------------------------------
# SESSION STATE INITIALISATION
# Streamlit reruns the entire script on every interaction. We use
# st.session_state (a dict that persists across reruns) to remember
# which document is currently loaded.
# -------------------------------------------------------------------
if "doc_id" not in st.session_state:
    st.session_state.doc_id = None
if "doc_name" not in st.session_state:
    st.session_state.doc_name = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "session_id" not in st.session_state:
    st.session_state.session_id = logger.generate_session_id()
# -------------------------------------------------------------------
# SIDEBAR — document upload and status
# -------------------------------------------------------------------
with st.sidebar:
    st.title("🛡️ DocShield")
    st.caption("Secure Document Intelligence")
    st.divider()

    st.subheader("📄 Upload Document")
    uploaded_file = st.file_uploader(
        "Choose a PDF file",
        type=["pdf"],
        help="Your document is stored securely in AWS S3 and never shared.",
    )

    if uploaded_file is not None:
        # Only re-ingest if this is a NEW document (different filename)
        if st.session_state.doc_name != uploaded_file.name:
            with st.spinner("Uploading and indexing your document..."):
                try:
                    # Step 1: read the file bytes from the uploader
                    pdf_bytes = uploaded_file.read()

                    # Step 2: generate a clean doc_id from the filename
                    # (strip spaces and .pdf extension for use as a
                    # filesystem-safe key)
                    doc_id = (
                        uploaded_file.name
                        .replace(".pdf", "")
                        .replace(" ", "_")
                        .lower()
                    )
                    s3_key = f"documents/{doc_id}.pdf"

                    # Step 3: upload to S3
                    storage.upload_bytes(pdf_bytes, s3_key)

                    # Step 4: ingest (chunk → embed → FAISS index)
                    os.makedirs("local_index", exist_ok=True)
                    ingest.ingest_document(s3_key=s3_key, doc_id=doc_id)

                    # Step 5: store in session state so the Q&A section
                    # knows which document to search
                    st.session_state.doc_id = doc_id
                    st.session_state.doc_name = uploaded_file.name
                    st.session_state.chat_history = []  # reset on new doc

                    st.success(f"✅ Ready: {uploaded_file.name}")

                except Exception as e:
                    st.error(f"Failed to process document: {str(e)}")
        else:
            st.success(f"✅ Loaded: {st.session_state.doc_name}")

    st.divider()

    # Security status panel - always visible, shows what's active
    st.subheader("🔒 Security Layer")
    st.markdown("""
    | Control | Status |
    |---|---|
    | Input validation | 🟢 Active |
    | PII detection | 🟢 Active |
    | Prompt injection guard | 🟢 Active |
    | Context grounding | 🟢 Active |
    """)

    st.divider()
    st.caption("Built on AWS Bedrock · Claude 3 Haiku · Titan Embeddings")
    st.caption("[View source on GitHub](https://github.com)")


# -------------------------------------------------------------------
# MAIN AREA — Q&A interface
# -------------------------------------------------------------------
st.title("Document Intelligence")

if st.session_state.doc_id is None:
    # No document loaded yet - show a clear call to action
    st.info("👈 Upload a PDF in the sidebar to get started.")

    # Show what DocShield can do while the user hasn't uploaded yet
    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("### 📄 Upload")
        st.markdown(
            "Upload any PDF — policy documents, reports, handbooks, contracts."
        )
    with col2:
        st.markdown("### 🔍 Ask")
        st.markdown(
            "Ask questions in plain English. Answers come only from your document."
        )
    with col3:
        st.markdown("### 🔒 Secure")
        st.markdown(
            "PII detection, injection guards, and audit-ready context grounding."
        )

else:
    # Document is loaded - show the Q&A interface
    st.caption(f"Document: **{st.session_state.doc_name}**")
    st.divider()

    # Show chat history (all previous Q&As in this session)
    for entry in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(entry["question"])
        with st.chat_message("assistant", avatar="🛡️"):
            st.write(entry["answer"])
            # Show security metadata as an expandable detail
            with st.expander("Security checks", expanded=False):
                st.markdown(f"**Input safe:** {entry['input_safe']}")
                st.markdown(f"**PII in question:** {entry['pii_found']}")
                if entry.get("pii_entities"):
                    st.markdown(
                        f"**PII types detected:** "
                        f"{', '.join(entry['pii_entities'])}"
                    )

    # Question input at the bottom (chat-style)
    question = st.chat_input("Ask a question about your document...")

    if question:
        # --- SECURITY CHECKS ---
        # 1. Validate for injection attempts
        is_safe, block_message = security.validate_user_input(question)

        if not is_safe:
            # Show the block but don't proceed to the LLM
            with st.chat_message("user"):
                st.write(question)
            with st.chat_message("assistant", avatar="🛡️"):
                st.warning(f"🚫 Blocked: {block_message}")

        else:
            # 2. Check for PII in the question itself
            pii_entities = security.detect_pii(question)
            pii_found = len(pii_entities) > 0
            pii_types = [e["Type"] for e in pii_entities] if pii_found else []

            # --- GET ANSWER ---
            with st.chat_message("user"):
                st.write(question)

            with st.chat_message("assistant", avatar="🛡️"):
                with st.spinner("Searching document and generating answer..."):
                    try:
                        answer = answer_question(
                            question=question,
                            doc_id=st.session_state.doc_id,
                        )
                        st.write(answer)

                        # Show security metadata
                        with st.expander("Security checks", expanded=False):
                            st.markdown("**Input safe:** ✅ No injection patterns detected")
                            pii_status = (
                                f"⚠️ Yes — types: {', '.join(pii_types)}"
                                if pii_found
                                else "✅ No PII detected"
                            )
                            st.markdown(f"**PII in question:** {pii_status}")

                        # Save to chat history
                        st.session_state.chat_history.append({
                            "question": question,
                            "answer": answer,
                            "input_safe": "✅ No injection patterns detected",
                            "pii_found": pii_status,
                            "pii_entities": pii_types,
                        })

                    except Exception as e:
                        st.error(f"Error generating answer: {str(e)}")