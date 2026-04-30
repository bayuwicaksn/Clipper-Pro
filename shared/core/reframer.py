"""
Compatibility wrapper for the reframer module.
Redirects to the modular implementation in shared/core/reframer/.
"""

from .reframer.service import reframe_clip
from .reframer.scenes import detect_scenes
from .reframer.tracking import get_face_center_x

__all__ = ['reframe_clip', 'detect_scenes', 'get_face_center_x']
