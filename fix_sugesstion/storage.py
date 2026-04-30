"""
Storage helpers — local filesystem + Google Cloud Storage.

Design principles:
  • Every public function works in both local and GCS mode.
  • GCS mode is activated when settings.gcs_enabled is True.
  • Functions never raise on missing optional files; they return None / False.
  • Signed URLs are used so the frontend can fetch GCS objects directly
    without routing everything through the backend.
"""

import os
import logging
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


# ── Internal helpers ───────────────────────────────────────────────────────

def _gcs_client():
    """Return a google.cloud.storage.Client (lazy import)."""
    from google.cloud import storage  # type: ignore
    return storage.Client()


def _settings():
    from shared.config import settings
    return settings


# ── Upload ────────────────────────────────────────────────────────────────

def upload_file(
    source_path: str,
    destination_blob: str,
    bucket_name: Optional[str] = None,
    content_type: str = "application/octet-stream",
    make_public: bool = False,
) -> Optional[str]:
    """
    Upload a local file to GCS.

    Returns:
        The GCS URI ``gs://<bucket>/<blob>`` on success, or None on failure /
        when GCS is disabled.
    """
    cfg = _settings()
    bucket = bucket_name or cfg.GCS_BUCKET

    if not cfg.gcs_enabled:
        logger.debug("GCS disabled — skipping upload of %s", source_path)
        return None

    if not os.path.exists(source_path):
        logger.error("upload_file: source not found: %s", source_path)
        return None

    try:
        client = _gcs_client()
        b = client.bucket(bucket)
        blob = b.blob(destination_blob)
        blob.upload_from_filename(source_path, content_type=content_type)

        if make_public:
            blob.make_public()
            logger.info("Uploaded (public) gs://%s/%s", bucket, destination_blob)
            return blob.public_url

        uri = f"gs://{bucket}/{destination_blob}"
        logger.info("Uploaded %s → %s", source_path, uri)
        return uri

    except Exception as exc:
        logger.error("GCS upload failed for %s: %s", source_path, exc, exc_info=True)
        return None


def upload_job_file(
    job_id: str,
    local_path: str,
    sub_path: str = "",
    **kwargs,
) -> Optional[str]:
    """
    Convenience wrapper that places the file under ``jobs/<job_id>/`` in GCS.

    Args:
        job_id:     The job identifier.
        local_path: Absolute path to the local file.
        sub_path:   Extra path component, e.g. ``"clips/clip_01.mp4"``.
    """
    filename = sub_path or os.path.basename(local_path)
    blob_name = f"jobs/{job_id}/{filename}"
    return upload_file(local_path, blob_name, **kwargs)


# ── Download ──────────────────────────────────────────────────────────────

def download_file(
    blob_name: str,
    destination_path: str,
    bucket_name: Optional[str] = None,
) -> Optional[str]:
    """
    Download a GCS object to a local path.

    Returns the *destination_path* on success, or None on failure.
    """
    cfg = _settings()
    bucket = bucket_name or cfg.GCS_BUCKET

    if not cfg.gcs_enabled:
        logger.debug("GCS disabled — cannot download %s", blob_name)
        return None

    Path(destination_path).parent.mkdir(parents=True, exist_ok=True)

    try:
        client = _gcs_client()
        b = client.bucket(bucket)
        blob = b.blob(blob_name)
        blob.download_to_filename(destination_path)
        logger.info("Downloaded gs://%s/%s → %s", bucket, blob_name, destination_path)
        return destination_path

    except Exception as exc:
        logger.error("GCS download failed for %s: %s", blob_name, exc, exc_info=True)
        return None


# ── Signed URLs ───────────────────────────────────────────────────────────

def get_signed_url(
    blob_name: str,
    bucket_name: Optional[str] = None,
    expiry_seconds: Optional[int] = None,
    method: str = "GET",
) -> Optional[str]:
    """
    Generate a V4 signed URL for a GCS object.

    Returns the signed URL string, or None when GCS is disabled or on error.
    """
    cfg = _settings()
    bucket = bucket_name or cfg.GCS_BUCKET
    expiry = expiry_seconds or cfg.GCS_SIGNED_URL_EXPIRY

    if not cfg.gcs_enabled:
        return None

    try:
        client = _gcs_client()
        b = client.bucket(bucket)
        blob = b.blob(blob_name)
        url = blob.generate_signed_url(
            version="v4",
            expiration=timedelta(seconds=expiry),
            method=method,
        )
        return url

    except Exception as exc:
        logger.error("Signed URL generation failed for %s: %s", blob_name, exc, exc_info=True)
        return None


def get_job_file_url(
    job_id: str,
    filename: str,
    sub_path: str = "",
    expiry_seconds: Optional[int] = None,
) -> Optional[str]:
    """
    Return a signed URL (or None) for a file that lives under
    ``gs://<bucket>/jobs/<job_id>/<sub_path>/<filename>``.
    """
    parts = ["jobs", job_id]
    if sub_path:
        parts.append(sub_path.strip("/"))
    parts.append(filename)
    blob_name = "/".join(parts)
    return get_signed_url(blob_name, expiry_seconds=expiry_seconds)


# ── Existence check ───────────────────────────────────────────────────────

def blob_exists(blob_name: str, bucket_name: Optional[str] = None) -> bool:
    """Return True if the GCS object exists, False otherwise."""
    cfg = _settings()
    bucket = bucket_name or cfg.GCS_BUCKET

    if not cfg.gcs_enabled:
        return False

    try:
        client = _gcs_client()
        b = client.bucket(bucket)
        return b.blob(blob_name).exists()

    except Exception as exc:
        logger.error("blob_exists check failed for %s: %s", blob_name, exc)
        return False


# ── Delete ────────────────────────────────────────────────────────────────

def delete_blob(blob_name: str, bucket_name: Optional[str] = None) -> bool:
    """Delete a GCS object.  Returns True on success."""
    cfg = _settings()
    bucket = bucket_name or cfg.GCS_BUCKET

    if not cfg.gcs_enabled:
        return False

    try:
        client = _gcs_client()
        b = client.bucket(bucket)
        b.blob(blob_name).delete()
        logger.info("Deleted gs://%s/%s", bucket, blob_name)
        return True

    except Exception as exc:
        logger.error("GCS delete failed for %s: %s", blob_name, exc)
        return False


# ── Local workspace helpers ───────────────────────────────────────────────

def ensure_workspace(workspace_root: str = "workspace") -> str:
    """Create the workspace directory if it doesn't exist, return its path."""
    os.makedirs(workspace_root, exist_ok=True)
    return workspace_root


def get_job_dir(job_id: str, workspace_root: str = "workspace") -> str:
    """Return (and create) the local directory for a job."""
    job_dir = os.path.join(workspace_root, job_id)
    os.makedirs(job_dir, exist_ok=True)
    return job_dir


def local_path_for_blob(blob_name: str, workspace_root: str = "workspace") -> str:
    """
    Map a GCS blob name like ``jobs/abc123/clips/clip_01.mp4`` to a local
    path inside the workspace.  Useful for caching GCS objects locally.
    """
    # Strip the leading ``jobs/`` prefix if present
    relative = blob_name.removeprefix("jobs/")
    local = os.path.join(workspace_root, relative)
    os.makedirs(os.path.dirname(local), exist_ok=True)
    return local


# ── Upload entire job directory to GCS ───────────────────────────────────

def upload_job_directory(
    job_id: str,
    local_job_dir: str,
    extensions: tuple = (".mp4", ".json", ".srt"),
    bucket_name: Optional[str] = None,
) -> list[str]:
    """
    Walk *local_job_dir* and upload all files whose extension is in
    *extensions* to GCS under ``jobs/<job_id>/``.

    Returns list of GCS URIs that were uploaded successfully.
    """
    cfg = _settings()
    if not cfg.gcs_enabled:
        return []

    uploaded: list[str] = []

    for root, _dirs, files in os.walk(local_job_dir):
        for fname in files:
            if not any(fname.endswith(ext) for ext in extensions):
                continue

            local_file = os.path.join(root, fname)
            # Build the blob sub-path relative to the job dir
            rel = os.path.relpath(local_file, local_job_dir)
            blob_name = f"jobs/{job_id}/{rel.replace(os.sep, '/')}"

            uri = upload_file(
                local_file,
                blob_name,
                bucket_name=bucket_name,
                content_type="video/mp4" if fname.endswith(".mp4") else "application/json",
            )
            if uri:
                uploaded.append(uri)

    logger.info("Uploaded %d files for job %s to GCS", len(uploaded), job_id)
    return uploaded
