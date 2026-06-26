"""
storage.py
----------
Handles all communication with AWS S3.

Why this file exists:
Same principle as llm.py - we isolate all S3-specific code here.
If we ever swap S3 for a different storage backend, only this file
changes. Nothing else in the app needs to know HOW documents are
stored, only that upload_file() and read_file() exist.

S3 = "Simple Storage Service". Think of it as an infinitely scalable
folder in the cloud, organized into "buckets" (like top-level folders)
containing "objects" (the actual files/keys).
"""

import boto3
from app import config


def get_s3_client():
    """
    Creates a boto3 client for talking to S3.
    Same pattern as get_bedrock_client() in llm.py - a fresh client
    per call, authenticated automatically via your AWS CLI credentials.
    """
    return boto3.client("s3", region_name=config.AWS_REGION)


def upload_file(local_file_path: str, s3_key: str) -> str:
    """
    Uploads a local file to our S3 bucket.

    Parameters:
        local_file_path: path to the file on your computer
                         (e.g. the temp file Streamlit gives us after upload)
        s3_key: the "filename" we want to use inside the S3 bucket
                (e.g. "documents/my_report.pdf")

    Returns:
        The s3_key, so the caller knows exactly where it ended up.

    Why we separate local_file_path from s3_key:
    The name a user uploads a file with locally doesn't have to match
    how we organize it in S3. This lets us namespace files later
    (e.g. by user ID) without changing the upload logic itself.
    """
    client = get_s3_client()
    client.upload_file(local_file_path, config.S3_BUCKET_NAME, s3_key)
    return s3_key


def upload_bytes(file_bytes: bytes, s3_key: str) -> str:
    """
    Uploads raw bytes directly to S3 - no local file needed.

    This is the version we'll actually use with Streamlit, because
    Streamlit gives us an uploaded file as an in-memory object, not
    a path on disk. Writing it to disk first and then uploading would
    be unnecessary extra work and an unnecessary place for a file to
    leak sensitive data if something goes wrong.
    """
    client = get_s3_client()
    client.put_object(
        Bucket=config.S3_BUCKET_NAME,
        Key=s3_key,
        Body=file_bytes,
    )
    return s3_key


def read_file_bytes(s3_key: str) -> bytes:
    """
    Downloads a file from S3 and returns its raw bytes.

    We need this so ingest.py (which we build next) can pull the PDF
    back out of S3 in order to chunk and embed it.
    """
    client = get_s3_client()
    response = client.get_object(Bucket=config.S3_BUCKET_NAME, Key=s3_key)
    return response["Body"].read()


def list_documents(prefix: str = "documents/") -> list[str]:
    """
    Lists all document keys currently stored under a given prefix.

    Useful for building a "your uploaded documents" view in the UI
    later, and handy for debugging - you can quickly check what's
    actually in your bucket without opening the AWS console.
    """
    client = get_s3_client()
    response = client.list_objects_v2(Bucket=config.S3_BUCKET_NAME, Prefix=prefix)
    if "Contents" not in response:
        return []
    return [obj["Key"] for obj in response["Contents"]]


# --- Quick manual test ---
if __name__ == "__main__":
    # This writes a tiny test file straight to S3 as bytes,
    # then reads it back, then lists the bucket contents.
    # No local file needed - this proves upload_bytes/read_file_bytes work.
    test_key = "documents/test_upload.txt"
    test_content = b"Hello DocShield - this is a test upload."

    print(f"Uploading test file to: {test_key}")
    upload_bytes(test_content, test_key)

    print("Reading it back from S3...")
    retrieved = read_file_bytes(test_key)
    print(f"Retrieved content: {retrieved.decode('utf-8')}")

    print("\nAll documents currently in bucket:")
    for key in list_documents():
        print(f"  - {key}")