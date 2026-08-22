"""
config.py
---------
Centralized configuration for DocShield.

Why this file exists:
All settings (region, bucket name, model IDs) live in ONE place.
If we ever need to change the AWS region or swap models, we change
it here once instead of hunting through every file.

We load secrets/config from environment variables (.env file) rather
than hardcoding them. This is a basic but important security practice -
it means this file is 100% safe to commit to GitHub, because it
contains no actual secrets, just the *names* of where to find them.
"""

import os
from dotenv import load_dotenv

# load_dotenv() reads the .env file in your project root and makes
# its values available via os.environ / os.getenv()
load_dotenv()


# --- AWS basics ---
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME")

# --- Bedrock model IDs ---
# These are AWS's specific identifiers for each model.
# Haiku = fast + cheap, good for most of our RAG answering.
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
BEDROCK_EMBEDDING_MODEL = os.getenv("BEDROCK_EMBEDDING_MODEL", "amazon.titan-embed-text-v2:0")

GUARDRAIL_ID = os.getenv("GUARDRAIL_ID", "2pwx8xq1k2vp")
GUARDRAIL_VERSION = os.getenv("GUARDRAIL_VERSION", "DRAFT")

# --- Model generation settings ---
# max_tokens: the maximum length of the model's answer
# temperature: 0 = focused/deterministic, 1 = creative/random
# For a document Q&A tool, we want LOW temperature - we want accurate
# answers grounded in the document, not creative ones.
MAX_TOKENS = 1000
TEMPERATURE = 0.1

# --- Validation on import ---
# This runs the moment another file does `from app import config`.
# If S3_BUCKET_NAME is missing, we fail LOUD and EARLY instead of
# failing confusingly later when we try to actually use it.
if not S3_BUCKET_NAME:
    raise ValueError(
        "S3_BUCKET_NAME is not set. Did you create a .env file? "
        "Check the setup checklist, step 6."
    )