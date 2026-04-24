"""
Uploader — Stubs for YouTube and TikTok upload
"""

# TODO: Implement OAuth-based YouTube upload using google-api-python-client
# TODO: Implement TikTok upload using their API

import os


def upload_to_youtube(clip_path, metadata, credentials_path=None):
    """
    Upload a clip to YouTube Shorts.
    
    Args:
        clip_path: Path to video file
        metadata: Dict with title, description, tags
        credentials_path: Path to OAuth credentials JSON
    
    Returns:
        dict with video_id, url
    """
    # TODO: Implement with google-api-python-client
    # Steps:
    # 1. Load OAuth credentials (or run OAuth flow)
    # 2. Build YouTube API service
    # 3. Upload video with metadata
    # 4. Return video ID and URL
    raise NotImplementedError(
        "YouTube upload is not yet implemented. "
        "You can manually upload the clips from the output folder. "
        "See: https://developers.google.com/youtube/v3/guides/uploading_a_video"
    )


def upload_to_tiktok(clip_path, metadata, credentials=None):
    """
    Upload a clip to TikTok.
    
    Args:
        clip_path: Path to video file
        metadata: Dict with title, description, tags
        credentials: TikTok API credentials
    
    Returns:
        dict with video_id, url
    """
    # TODO: Implement with TikTok API
    raise NotImplementedError(
        "TikTok upload is not yet implemented. "
        "You can manually upload the clips from the output folder."
    )


def get_upload_status():
    """Return the status of upload feature implementations."""
    return {
        'youtube': {
            'implemented': False,
            'message': 'YouTube upload coming soon. Download clips and upload manually.'
        },
        'tiktok': {
            'implemented': False,
            'message': 'TikTok upload coming soon. Download clips and upload manually.'
        }
    }
