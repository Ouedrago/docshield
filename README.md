# DocShield — Secure Document Intelligence

A RAG-powered document Q&A application built on AWS Bedrock, designed with
security as a first-class concern rather than an afterthought.

Upload a document, ask questions about it, and get answers grounded strictly
in that document's content — with PII detection, prompt injection defenses,
Bedrock Guardrails, and full audit logging built in from the foundation up.

**Status:** Phase 2 in progress — RAG pipeline, security layer, CloudWatch
logging, Bedrock Guardrails, and containerisation complete. ECS Fargate
deployment in progress.

**Live URL:** Coming in Phase 2, Step 3d (ALB + ECS service launch)

---

## Why this project exists

Most RAG demos stop at "it answers questions about my PDF." DocShield asks a
harder question: *what happens when someone tries to break it?* Every phase
of this build includes a deliberate attempt to attack what was just built,
with findings documented honestly in [`tests/attack_log.md`](tests/attack_log.md).

The result is a system where the security story is evidence-based, not
theoretical — built, broken, fixed, and documented at every step.

---

# SECTION 1 — LOCAL DEVELOPMENT

Everything in this section runs on your laptop. No cloud costs beyond
AWS API calls (Bedrock, Comprehend, S3). This is where all development
and testing happens before anything goes to production.

---

## Local architecture

```
 Browser (localhost:8501)
        │
        ▼
 Streamlit UI (app/main.py)
        │
        ├──▶ app/storage.py   ──▶  AWS S3         (document storage)
        ├──▶ app/ingest.py    ──▶  AWS Bedrock     (Titan embeddings)
        │                    ──▶  FAISS           (local disk index)
        ├──▶ app/retriever.py ──▶  AWS Bedrock     (Claude 3 Haiku)
        ├──▶ app/security.py  ──▶  AWS Comprehend  (PII detection)
        │                    ──▶  Regex filter    (injection guard)
        ├──▶ app/llm.py       ──▶  Bedrock Guardrails (semantic filter)
        └──▶ app/logger.py    ──▶  CloudWatch      (audit logs)
                                  (also logs locally to terminal)
```

**Key difference from production:**
FAISS index is saved to `local_index/` on your local disk.
Secrets come from a `.env` file, not SSM Parameter Store.

---

## Local tech stack

| Component | Technology |
|---|---|
| LLM | AWS Bedrock — Claude 3 Haiku |
| Embeddings | AWS Bedrock — Amazon Titan Embeddings V2 |
| Vector search | FAISS (saved to `local_index/` on disk) |
| Document storage | AWS S3 |
| PII detection | AWS Comprehend |
| Content filtering | AWS Bedrock Guardrails |
| Audit logging | AWS CloudWatch + local terminal |
| Secrets | `.env` file (never committed to Git) |
| UI | Streamlit |
| Language | Python 3.12 |

---

## Local project structure

```
docshield/
├── app/
│   ├── config.py       # centralised settings, loaded from .env
│   ├── llm.py          # Bedrock chat + embeddings + Guardrails
│   ├── storage.py      # S3 upload/download
│   ├── ingest.py       # PDF → chunks → embeddings → FAISS index
│   ├── retriever.py    # question → relevant chunks → grounded answer
│   ├── security.py     # PII detection + prompt injection guards
│   ├── logger.py       # structured CloudWatch audit logging
│   └── main.py         # Streamlit UI
├── tests/
│   ├── test_ingest.py
│   ├── test_security.py
│   └── attack_log.md   # every attack attempted + results + findings
├── sample_docs/
│   └── company_handbook.pdf   # synthetic test document (invented facts)
├── local_index/               # FAISS indexes saved here (gitignored)
├── make_sample_pdf.py         # generates synthetic test document
├── make_poisoned_pdf.py       # generates indirect injection test doc
├── redteam_injection.py       # direct injection bypass tests
├── redteam_llm_behavior.py    # LLM resistance tests
├── redteam_indirect_injection.py  # indirect injection tests
├── requirements.txt
└── .env                       # secrets — never committed to Git
```

---

## Running locally

```bash
# 1. Clone the repository
git clone <your-repo-url>
cd docshield

# 2. Create and activate virtual environment
python3 -m venv venv
source venv/Scripts/activate      # Windows Git Bash
# or: venv\Scripts\activate       # Windows CMD/PowerShell
# or: source venv/bin/activate    # Mac/Linux

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure AWS CLI (one-time setup)
aws configure
# Enter: Access Key ID, Secret Access Key, Region (us-east-1), output (json)

# 5. Create your .env file in the project root
# Contents:
# AWS_REGION=us-east-1
# S3_BUCKET_NAME=your-bucket-name
# BEDROCK_MODEL_ID=us.anthropic.claude-3-haiku-20240307-v1:0
# BEDROCK_EMBEDDING_MODEL=amazon.titan-embed-text-v2:0
# GUARDRAIL_ID=your-guardrail-id
# GUARDRAIL_VERSION=DRAFT

# 6. Generate the synthetic test document
python make_sample_pdf.py

# 7. Run the app
python -m streamlit run app/main.py
```

Open `http://localhost:8501` in your browser.

---

## Local prerequisites

| Requirement | Details |
|---|---|
| Python | 3.12 |
| AWS account | With Bedrock, S3, Comprehend access |
| Bedrock models | Claude 3 Haiku + Titan Embeddings V2 enabled |
| S3 bucket | Created in your AWS account |
| Bedrock Guardrail | Created in AWS console |
| AWS CLI | Configured with valid credentials |

---

## Testing locally

Run each module independently to verify it works:

```bash
# Test Bedrock connection + embeddings
python -m app.llm

# Test S3 upload/download
python -m app.storage

# Test full ingestion pipeline
python -m app.ingest

# Test RAG retrieval + answers
python -m app.retriever

# Test PII detection + injection guards
python -m app.security

# Test CloudWatch logging
python -m app.logger
```

### Security red-team tests

```bash
# Test 4: direct injection bypass attempts against regex filter
python redteam_injection.py

# Test 5: same inputs against Claude's behavior directly
python redteam_llm_behavior.py

# Test 6: indirect injection via poisoned document
python make_poisoned_pdf.py
python redteam_indirect_injection.py
```

---

## Security testing summary

| Test | What was tested | Result |
|---|---|---|
| Test 1 | Off-topic question grounding | ✅ Correctly declined |
| Test 2 | PII detection via Comprehend | ✅ NAME, EMAIL, PHONE at 100% confidence |
| Test 3 | Basic injection pattern matching | ✅ Obvious attempts caught |
| Test 4 | Adversarial rephrasing against regex | ❌ 0/9 caught by regex |
| Test 5 | Same inputs against Claude directly | ✅ 9/9 resisted by model |
| Test 6 | Indirect injection via poisoned document | ✅ All 3 techniques ignored |
| Test 7 | Bedrock Guardrails semantic filtering | ✅ Caught what regex missed |

Full findings in [`tests/attack_log.md`](tests/attack_log.md).

---

## Security architecture — defence in depth

| Layer | Control | What it catches |
|---|---|---|
| 1 | Regex filter (`security.py`) | Obvious literal injection phrases |
| 2 | Bedrock Guardrails (input) | Semantic injection, PII, denied topics |
| 3 | System prompt grounding (`llm.py`) | Model-level resistance to manipulation |
| 4 | Bedrock Guardrails (output) | Harmful content in Claude's response |
| 5 | CloudWatch audit logging | Full event trail for every interaction |

---

## Lessons learned (local development)

- **Bedrock model IDs require a regional prefix** — use
  `us.anthropic.claude-3-haiku-20240307-v1:0` not
  `anthropic.claude-3-haiku-20240307-v1:0`. AWS error message just says
  "invalid identifier" with no hint of why.
- **Regex injection detection catches 0% of deliberate rephrasings** —
  the real defense is the system-prompt grounding instruction, proven
  across Tests 1, 5, and 6. Regex is kept only as a free first-pass filter.
- **FAISS chunk count varies by document** — a fixed `chunk_size` doesn't
  guarantee a fixed number of chunks. Small variations are normal.
- **Test with invented facts, not real documents** — the synthetic test
  document uses a fictional company so correct answers can only come from
  genuine retrieval, not Claude's training knowledge.

---

---

# SECTION 2 — PRODUCTION DEPLOYMENT

Everything in this section runs on AWS. The app is containerised, deployed
on ECS Fargate, and scaled to zero when not in use to minimise cost.

---

## Production architecture

```
 Browser
    │ HTTPS
    ▼
 Route 53 (DNS)
    │
    ▼
 Application Load Balancer (HTTPS termination)
    │
    ▼
 ┌─────────────────────────────────────────┐
 │  VPC — Private Subnet                   │
 │                                         │
 │  ECS Fargate                            │
 │  DocShield container (Python 3.12-slim) │
 │  Pulled from ECR                        │
 │         │                               │
 └─────────┼───────────────────────────────┘
           │
           ├──▶ AWS S3          (document storage)
           ├──▶ AWS EFS         (FAISS index — persists across restarts)
           ├──▶ AWS Bedrock     (Claude 3 Haiku + Titan Embeddings)
           ├──▶ AWS Comprehend  (PII detection)
           ├──▶ Bedrock Guardrails (semantic input/output filtering)
           ├──▶ CloudWatch      (structured audit logs)
           └──▶ SSM Parameter Store (secrets injected at runtime)
```

**Key difference from local:**
FAISS index is mounted from EFS — survives container restarts.
Secrets come from SSM Parameter Store — never baked into the image.

---

## Production tech stack

| Component | Technology |
|---|---|
| LLM | AWS Bedrock — Claude 3 Haiku |
| Embeddings | AWS Bedrock — Amazon Titan Embeddings V2 |
| Vector search | FAISS (persisted on AWS EFS) |
| Document storage | AWS S3 |
| PII detection | AWS Comprehend |
| Content filtering | AWS Bedrock Guardrails |
| Audit logging | AWS CloudWatch Logs (`/docshield/production`) |
| Secrets | AWS SSM Parameter Store (SecureString) |
| Container registry | AWS ECR |
| Container runtime | AWS ECS Fargate |
| Index persistence | AWS EFS (`fs-0c1ed8a030f0a8831`) |
| Load balancer | AWS ALB (coming in Step 3d) |
| DNS | AWS Route 53 (optional) |

---

## Production project structure

```
docshield/
├── app/                    # same application code as local
├── Dockerfile              # production container definition
├── .dockerignore           # excludes secrets and dev files from image
├── task-definition.json    # ECS Fargate task definition
└── requirements.txt
```

---

## AWS infrastructure resources

| Resource | Value |
|---|---|
| ECR repository | `396143251711.dkr.ecr.us-east-1.amazonaws.com/docshield` |
| ECS cluster | `docshield-cluster` (us-east-1) |
| EFS file system | `fs-0c1ed8a030f0a8831` |
| IAM task role | `docshield-task-role` |
| SSM parameter — bucket | `docshield.S3_BUCKET_NAME` |
| SSM parameter — guardrail | `docshield.GUARDRAIL_ID` |
| CloudWatch log group | `/docshield/production` |
| ECS task definition | `docshield-task:1` |

---

## Building and pushing a new image

Run these whenever you make code changes and want to deploy:

```bash
# Build the image
docker build -t docshield .

# Authenticate Docker to ECR
aws ecr get-login-password --region us-east-1 | docker login \
    --username AWS \
    --password-stdin 396143251711.dkr.ecr.us-east-1.amazonaws.com

# Tag and push
docker tag docshield:latest \
    396143251711.dkr.ecr.us-east-1.amazonaws.com/docshield:latest
docker push \
    396143251711.dkr.ecr.us-east-1.amazonaws.com/docshield:latest
```

---

## Starting and stopping the service (scale to zero)

DocShield runs with `desired-count 0` by default — no charges when idle.

**Start before a demo:**
```bash
aws ecs update-service --cluster docshield-cluster \
    --service docshield-service --desired-count 1 --region us-east-1
```

**Stop after a demo:**
```bash
aws ecs update-service --cluster docshield-cluster \
    --service docshield-service --desired-count 0 --region us-east-1
```

---

## Production cost model

| State | Resource | Cost |
|---|---|---|
| Running | ECS Fargate (0.5 vCPU, 1GB) | ~$0.024/hour |
| Running | ALB | ~$0.008/hour |
| Always | ECR image storage (~700MB) | ~$0.07/month |
| Always | EFS storage (index files) | ~$0.03/month |
| Always | SSM parameters | Free |
| Always | CloudWatch logs | ~$0.50/month |
| **Stopped total** | | **~$0.10/month** |
| **Running total** | | **~$0.032/hour** |

---

## Production prerequisites

| Requirement | Status |
|---|---|
| ECR repository | ✅ Created |
| Docker image pushed | ✅ `docshield:latest` in ECR |
| ECS cluster | ✅ `docshield-cluster` active |
| EFS file system | ✅ `fs-0c1ed8a030f0a8831` |
| IAM task role | ✅ `docshield-task-role` with all permissions |
| SSM parameters | ✅ S3 bucket + Guardrail ID stored |
| Task definition | ✅ `docshield-task:1` registered |
| ECS service + ALB | ⏳ Coming in Phase 2 Step 3d |
| Live URL | ⏳ Coming in Phase 2 Step 3d |

---

## Lessons learned (production deployment)

- **Docker on Windows works best through PowerShell** — Git Bash has a
  `more` pager conflict with AWS CLI. Fix with
  `aws configure set cli_pager ""` or redirect output with `> output.json`.
- **EFS is required for FAISS persistence on ECS** — Fargate containers
  have no persistent local storage. Without EFS the FAISS index is lost
  on every container restart, forcing re-embedding of every document.
- **SSM Parameter Store over .env for production secrets** — `.env` files
  must never be baked into Docker images. SSM SecureString parameters are
  injected at runtime by ECS, keeping credentials out of the image.
- **ECR stores images even when ECS is stopped** — storage cost continues
  even at scale-zero. At ~$0.07/month for our image size, this is negligible.

---

## Roadmap

- [x] **Phase 1, Weeks 1–2:** Core RAG pipeline (Bedrock + S3 + FAISS)
- [x] **Phase 1, Week 3:** Security layer — PII detection, injection
      red-teaming, 7 documented tests in `attack_log.md`
- [x] **Phase 1, Week 4:** Streamlit UI demoed and verified locally
- [x] **Phase 2, Step 1:** CloudWatch structured audit logging
- [x] **Phase 2, Step 2:** Bedrock Guardrails — semantic filtering proven
- [x] **Phase 2, Step 3a:** Dockerfile + container tested locally
- [x] **Phase 2, Step 3b:** Docker image pushed to ECR
- [x] **Phase 2, Step 3c:** ECS cluster, EFS, IAM role, SSM, task definition
- [ ] **Phase 2, Step 3d:** ECS service + ALB + live URL
- [ ] **Phase 3:** Multi-document support, per-user access control,
      agentic multi-document synthesis
- [ ] **Phase 4 (InterviewShield):** LP evaluation engine and adaptive
      interview coaching agent

---

## License

MIT