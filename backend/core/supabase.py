"""Supabase client factory for backend services."""

from .config import settings


def get_supabase_client():
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be configured")

    from supabase import create_client

    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
