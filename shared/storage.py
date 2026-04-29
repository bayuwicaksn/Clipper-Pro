"""Shared Cloud Storage helpers."""

from pathlib import Path


def upload_file(bucket_name: str, source_path: str, destination_blob: str) -> str:
    from google.cloud import storage

    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(destination_blob)
    blob.upload_from_filename(source_path)
    return f"gs://{bucket_name}/{destination_blob}"


def download_file(bucket_name: str, blob_name: str, destination_path: str) -> str:
    from google.cloud import storage

    Path(destination_path).parent.mkdir(parents=True, exist_ok=True)
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.download_to_filename(destination_path)
    return destination_path
