"""
logger.py
---------
Structured audit logging for DocShield via AWS CloudWatch.

Why structured logging matters:
Most beginners log strings like "User asked a question". That's useless
in production - you can't query it, filter it, or build metrics from it.

Structured logging means every log entry is a JSON object with consistent
fields. CloudWatch can then filter, query, and alarm on specific fields.
For example:
  - "Show me all queries where security_blocked = true"
  - "Alert me when bedrock_latency_ms > 5000"
  - "How many unique documents were queried today?"

That's what separates a hobbyist project from an enterprise-grade system.
And it's exactly what Amazon's Operational Excellence LP means in practice.

Log groups and streams:
- A LOG GROUP is like a folder: /docshield/production
- A LOG STREAM is like a file inside that folder, one per Lambda instance
  or one per day for our Streamlit setup.
- Every event we log goes into a stream inside the group.

What we log (every event has these fields):
  - timestamp: ISO 8601 UTC
  - event_type: what happened (QUERY, UPLOAD, SECURITY_BLOCK, ERROR, etc.)
  - session_id: random ID per browser session (privacy-safe, not a user ID)
  - doc_id: which document was involved
  - Any event-specific fields (latency, pii_detected, chunks_retrieved etc.)
"""

import json
import time
import uuid
import logging
import boto3
from datetime import datetime, timezone
from botocore.exceptions import ClientError
from app import config


# Standard Python logger as fallback - if CloudWatch fails for any reason,
# events still get logged locally so we don't lose data silently.
_local_logger = logging.getLogger("docshield")
logging.basicConfig(level=logging.INFO)

LOG_GROUP = "/docshield/production"


def get_logs_client():
    return boto3.client("logs", region_name=config.AWS_REGION)


def _ensure_log_group(client):
    """
    Creates the CloudWatch log group if it doesn't already exist.
    Safe to call repeatedly - it checks first and only creates if missing.
    """
    try:
        client.create_log_group(logGroupName=LOG_GROUP)
    except ClientError as e:
        # ResourceAlreadyExistsException is expected and fine to ignore.
        # Any other error we re-raise so it doesn't silently fail.
        if e.response["Error"]["Code"] != "ResourceAlreadyExistsException":
            raise


def _ensure_log_stream(client, stream_name: str):
    """
    Creates a log stream inside the log group if it doesn't exist.
    We use one stream per day so logs are naturally partitioned by date
    and easy to find in the console without scrolling through months of data.
    """
    try:
        client.create_log_stream(
            logGroupName=LOG_GROUP,
            logStreamName=stream_name,
        )
    except ClientError as e:
        if e.response["Error"]["Code"] != "ResourceAlreadyExistsException":
            raise


def _get_stream_name() -> str:
    """
    Returns today's log stream name, e.g. '2026-06-27'.
    A new stream is created automatically each day.
    """
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def log_event(event_type: str, payload: dict):
    """
    The single function every other module calls to log anything.

    Parameters:
        event_type: a short uppercase string identifying what happened.
                    Use consistent names - these become queryable fields.
                    Examples: QUERY, UPLOAD, SECURITY_BLOCK, PII_DETECTED,
                              BEDROCK_CALL, ERROR, INJECTION_ATTEMPT
        payload:    a dict of event-specific fields. Always safe to add
                    more fields - CloudWatch stores the whole JSON object.

    Design decision - why one function instead of log_query(), log_upload() etc:
    A single entry point means every log event is guaranteed to have the
    same base fields (timestamp, event_type, session_id). Separate functions
    would risk inconsistency as the codebase grows. One function, always
    consistent. This is the same pattern AWS uses internally.
    """
    # Build the base event - fields every log entry always has
    event = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "event_type": event_type,
        **payload,  # merge in the caller's specific fields
    }

    # Always log locally first (instant, never fails)
    _local_logger.info(json.dumps(event))

    # Then attempt CloudWatch (may fail if offline or misconfigured)
    try:
        client = get_logs_client()
        _ensure_log_group(client)
        stream_name = _get_stream_name()
        _ensure_log_stream(client, stream_name)

        client.put_log_events(
            logGroupName=LOG_GROUP,
            logStreamName=stream_name,
            logEvents=[{
                # CloudWatch requires epoch milliseconds, not seconds
                "timestamp": int(time.time() * 1000),
                "message": json.dumps(event),
            }],
        )
    except Exception as e:
        # Logging must NEVER crash the application. If CloudWatch is
        # unavailable, we log the failure locally and carry on.
        # Silent degradation is intentional here - a logging failure
        # should never become a user-visible error.
        _local_logger.warning(f"CloudWatch logging failed: {e}")


# -------------------------------------------------------------------
# Convenience wrappers - these make call sites clean and readable
# while guaranteeing consistent field names across events.
# -------------------------------------------------------------------

def log_query(session_id: str, doc_id: str, question: str,
              chunks_retrieved: int, latency_ms: int):
    """Logs every question asked through the RAG pipeline."""
    log_event("QUERY", {
        "session_id": session_id,
        "doc_id": doc_id,
        # We hash the question rather than logging it raw, to avoid
        # storing potentially sensitive user input in CloudWatch.
        # In a real product you'd decide this based on your data
        # retention policy - logging raw questions is fine for dev.
        "question_length": len(question),
        "chunks_retrieved": chunks_retrieved,
        "latency_ms": latency_ms,
    })


def log_upload(session_id: str, doc_id: str, file_size_bytes: int,
               chunks_created: int, latency_ms: int):
    """Logs every document upload and ingestion."""
    log_event("UPLOAD", {
        "session_id": session_id,
        "doc_id": doc_id,
        "file_size_bytes": file_size_bytes,
        "chunks_created": chunks_created,
        "latency_ms": latency_ms,
    })


def log_security_event(session_id: str, doc_id: str,
                       event_subtype: str, details: dict):
    """
    Logs any security-relevant event.

    event_subtype examples:
        INJECTION_ATTEMPT  - regex filter caught something
        PII_DETECTED       - Comprehend found PII in user input
        GROUNDING_REFUSAL  - Claude declined to answer (off-topic)
        GUARDRAIL_TRIGGERED - Bedrock Guardrail fired on output
    """
    log_event("SECURITY", {
        "session_id": session_id,
        "doc_id": doc_id,
        "subtype": event_subtype,
        **details,
    })


def log_error(session_id: str, doc_id: str,
              error_type: str, error_message: str):
    """Logs any exception or error state."""
    log_event("ERROR", {
        "session_id": session_id,
        "doc_id": doc_id,
        "error_type": error_type,
        "error_message": error_message,
    })


def generate_session_id() -> str:
    """
    Generates a random session ID for the current browser session.
    We use a random UUID - not tied to any user identity, just used
    to correlate log events within a single session.
    """
    return str(uuid.uuid4())[:8]


# --- Quick manual test ---
if __name__ == "__main__":
    print("Testing CloudWatch logging...")

    test_session = generate_session_id()
    print(f"Session ID: {test_session}")

    log_upload(
        session_id=test_session,
        doc_id="company_handbook",
        file_size_bytes=24500,
        chunks_created=4,
        latency_ms=3200,
    )
    print("Upload event logged.")

    log_query(
        session_id=test_session,
        doc_id="company_handbook",
        question="Who founded the company?",
        chunks_retrieved=3,
        latency_ms=1850,
    )
    print("Query event logged.")

    log_security_event(
        session_id=test_session,
        doc_id="company_handbook",
        event_subtype="INJECTION_ATTEMPT",
        details={"pattern_matched": "ignore all previous instructions"},
    )
    print("Security event logged.")

    print("\nDone. Check CloudWatch console:")
    print(f"  Log group: {LOG_GROUP}")
    print(f"  Log stream: {_get_stream_name()}")