import math

def _get_mouth_aspect_ratio(landmarks, width, height):
    """
    Calculate Mouth Aspect Ratio (MAR) to determine how wide the mouth is open.
    Using standard MediaPipe FaceMesh inner lip indices:
    Upper inner lip: 13, Lower inner lip: 14
    Left mouth corner: 61, Right mouth corner: 291
    """
    p13 = landmarks[13]
    p14 = landmarks[14]
    p61 = landmarks[61]
    p291 = landmarks[291]
    
    # Calculate vertical distance
    v_dist = math.hypot((p14.x - p13.x) * width, (p14.y - p13.y) * height)
    # Calculate horizontal distance
    h_dist = math.hypot((p291.x - p61.x) * width, (p291.y - p61.y) * height)
    
    if h_dist == 0:
        return 0
    return v_dist / h_dist

def _find_face_center(landmarks, width):
    """Find the approximate horizontal center of the face."""
    x_coords = [lm.x for lm in landmarks]
    cx = (min(x_coords) + max(x_coords)) / 2.0
    return int(cx * width)
