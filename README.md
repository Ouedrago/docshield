# DocShield — Secure Document Intelligence

A RAG-powered document Q&A application built on AWS Bedrock, designed with
security as a first-class concern rather than an afterthought.

Upload a document, ask questions about it, and get answers grounded strictly
in that document's content — with PII detection, prompt injection defenses,
and full audit logging layered in as the project matures through its phases.

**Status:** Phase 1 in progress — core RAG pipeline complete and verified.

---

## Why this project exists

Most RAG demos stop at "it answers questions about my PDF." DocShield asks a
harder question: *what happens when someone tries to break it?* Every phase
of this build includes a deliberate attempt to attack what was just built,
with findings documented in [`tests/attack_log.md`](tests/attack_log.md).

---

## Architecture (Phase 1)

```
 User (Streamlit UI)
        │
        ▼
 AWS API Gateway  ──▶  AWS Lambda (orchestration)
                              │
                ┌─────────────┼─────────────┐
                ▼             ▼             ▼
            AWS S3      AWS Bedrock      FAISS
         (documents)   (Claude 3 Haiku  (vector
                        + Titan Embed)   search)
                              │
                              ▼
                        AWS CloudWatch
                       (logs & metrics)
```

**Data flow:** a document is uploaded to S3 → text is extracted and split
into overlapping chunks → each chunk is embedded via Amazon Titan → vectors
are stored in a local FAISS index → a user's question is embedded the same
way → FAISS returns the most relevant chunks → those chunks (and only those)
are passed to Claude 3 Haiku as context → Claude answers strictly from that
context.

---

## Tech stack

| Layer | Technology |
|---|---|
| LLM | AWS Bedrock — Claude 3 Haiku |
| Embeddings | AWS Bedrock — Amazon Titan Embeddings V2 |
| Vector search | FAISS (local, `IndexFlatL2`) |
| Document storage | AWS S3 |
| PDF parsing | `pypdf` |
| UI | Streamlit |
| Language | Python 3 |

---

## Project structure

```
docshield/
├── app/
│   ├── config.py       # centralized settings, loaded from .env
│   ├── llm.py           # Bedrock chat + embedding calls
│   ├── storage.py        # S3 upload/download
│   ├── ingest.py         # PDF → chunks → embeddings → FAISS index
│   ├── retriever.py     # question → relevant chunks → grounded answer
│   └── security.py       # PII detection + prompt injection guards (Phase 1, Week 3)
├── tests/
│   ├── test_ingest.py
│   ├── test_security.py
│   └── attack_log.md     # every attack attempted, what happened, what was fixed
├── sample_docs/
│   └── company_handbook.pdf   # synthetic test document with invented facts
├── make_sample_pdf.py    # generates the sample document above
├── requirements.txt
└── README.md
```

---

## Security design decisions

- **The real defense against prompt injection is the system prompt, not
  pattern matching — and we proved this, not just assumed it.**
  `security.py` includes a regex-based filter for known injection
  phrasings, but red-team testing showed it catches 0% of deliberately
  rephrased attempts (synonyms, roleplay framing, non-English text,
  character spacing — see `tests/attack_log.md`, Test 4). The actual
  boundary that held in every single one of those same tests was the
  system-prompt grounding instruction in `llm.py`, which generalizes far
  beyond literal phrase matching (Test 5). The regex filter is kept as a
  free, zero-latency first pass for lazy attempts, but is explicitly
  *not* relied upon as the real security control.
- **PII detection via AWS Comprehend**, not regex. Comprehend correctly
  identified names, emails, and phone numbers at 100% confidence in
  testing (`tests/attack_log.md`, Test 2) — catching cases like names
  that have no fixed pattern, which regex alone would miss.
- **Context-only grounding.** The system prompt in `llm.py` instructs
  the model to answer only from supplied context, decline plainly when
  an answer isn't present, and treat retrieved context as data rather
  than instructions. Verified against both off-topic questions (Test 1)
  and 9 adversarial injection attempts (Test 5).
- **No hardcoded secrets.** All AWS configuration is loaded from a local
  `.env` file (excluded via `.gitignore`) through `config.py`, which
  fails loudly and immediately if required settings are missing.

---

## Testing & results

A synthetic test document (`sample_docs/company_handbook.pdf`) was created
with entirely invented facts about a fictional company, specifically so
correct answers could only come from genuine retrieval — not from anything
Claude could plausibly know already.

| Question | Result |
|---|---|
| "When was the company founded and who founded it?" | ✅ Correct — retrieved and answered from document |
| "How many days of annual leave do employees get?" | ✅ Correct — retrieved and answered from document |
| "What is the maximum expense I can claim without approval?" | ✅ Correct — retrieved and answered from document |
| "What is the capital of France?" (deliberately off-topic) | ✅ Correctly declined: *"I cannot find that information in the document."* |

The fourth test is the most important one. A RAG system that quietly
answers off-topic questions using general knowledge looks impressive in a
demo but is unreliable and unsafe in practice — it means there's no real
guarantee answers come from the source document at all. DocShield held the
boundary correctly here.

Full details, including future adversarial/security testing, are logged in
[`tests/attack_log.md`](tests/attack_log.md).

---

## Lessons learned

- **Bedrock model IDs for Claude often require a region-prefixed inference
  profile** (e.g. `us.anthropic.claude-3-haiku-20240307-v1:0`, not just
  `anthropic.claude-3-haiku-20240307-v1:0`) — even though AWS's error
  message just says "invalid identifier" with no indication of why. Fixed
  by adding the regional prefix matching `AWS_REGION`.
- **Chunk count varies slightly by document and extraction quirks.**
  A fixed `chunk_size` doesn't guarantee a fixed number of chunks — small
  variations in extracted text length are normal and not a bug.

---

## Setup & running locally

```bash
# 1. Clone and enter the project
git clone <your-repo-url>
cd docshield

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure AWS CLI (one-time, if not already done)
aws configure

# 5. Create your .env file (see .env.example) with:
#    AWS_REGION, S3_BUCKET_NAME, BEDROCK_MODEL_ID, BEDROCK_EMBEDDING_MODEL

# 6. Generate the sample test document
python make_sample_pdf.py

# 7. Run the ingestion pipeline on the sample document
python -m app.ingest

# 8. Ask it questions
python -m app.retriever
```

**Prerequisites:** an AWS account with Bedrock model access enabled for
Claude 3 Haiku and Titan Embeddings V2, and an S3 bucket created in advance.

---

## Roadmap

- [x] **Phase 1, Weeks 1–2:** Core RAG pipeline (Bedrock + S3 + FAISS)
- [ ] **Phase 1, Week 3:** PII detection (AWS Comprehend) + prompt injection
      red-teaming, documented in `attack_log.md`
- [ ] **Phase 1, Week 4:** Streamlit UI, deployment to AWS Lambda + API
      Gateway, CloudWatch logging, live URL
- [ ] **Phase 2:** Multi-document support, per-user access control, query
      audit trail
- [ ] **Phase 3:** Agentic capabilities — multi-document synthesis and
      autonomous report drafting

---

## License

MIT