"""
GPU Utilities â€” Detect NVIDIA GPU and provide FFmpeg/OpenCV GPU-accelerated options
"""

import subprocess
import shutil
import os

# Cache GPU detection result
_gpu_available = None


def has_nvidia_gpu():
    """Check if NVIDIA GPU is available (via nvidia-smi)."""
    global _gpu_available
    if _gpu_available is not None:
        return _gpu_available

    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name', '--format=csv,noheader'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            gpu_name = result.stdout.strip().split('\n')[0]
            print(f'[GPU] âœ… NVIDIA GPU detected: {gpu_name}')
            _gpu_available = True
        else:
            _gpu_available = False
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _gpu_available = False

    if not _gpu_available:
        print('[GPU] âŒ No NVIDIA GPU detected, using CPU encoding')

    return _gpu_available


# Cache FFmpeg encoders list
_ffmpeg_encoders = None

def get_ffmpeg_encoders():
    """Get list of available FFmpeg video encoders."""
    global _ffmpeg_encoders
    if _ffmpeg_encoders is not None:
        return _ffmpeg_encoders

    try:
        result = subprocess.run(
            ['ffmpeg', '-hide_banner', '-encoders'],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            _ffmpeg_encoders = result.stdout
        else:
            _ffmpeg_encoders = ""
    except (FileNotFoundError, subprocess.TimeoutExpired):
        _ffmpeg_encoders = ""
    
    return _ffmpeg_encoders


def get_ffmpeg_video_encode_args():
    """
    Get FFmpeg video encoding args â€” GPU-accelerated if available.
    Returns list of args for the best available encoder.
    """
    encoders = get_ffmpeg_encoders()

    # 1. Best GPU encoder (NVENC)
    if has_nvidia_gpu() and 'h264_nvenc' in encoders:
        print("[GPU] Selected encoder: h264_nvenc (NVIDIA Native)")
        return [
            '-c:v', 'h264_nvenc',
            '-preset', 'p4',          # Fast NVENC preset
            '-rc:v', 'vbr',           # Variable bitrate (stream-specific)
            '-cq:v', '23',            # Constant quality
            '-b:v', '0',              # Let CQ control quality
        ]

    # 2. Windows Media Foundation fallback (GPU - installed by Conda on Windows)
    if 'h264_mf' in encoders:
        print("[GPU] Selected encoder: h264_mf (Windows Media Foundation)")
        return [
            '-c:v', 'h264_mf',
            '-b:v', '8M',             # Constant Bitrate for 1080p (MF is safer with CBR)
        ]

    # 3. AMD AMF fallback (GPU)
    if 'h264_amf' in encoders:
        print("[GPU] Selected encoder: h264_amf (AMD Native)")
        return [
            '-c:v', 'h264_amf',
            '-quality', 'balanced',
            '-rc', 'vbr_peak',        # AMF specific VBR
        ]

    # 4. Standard CPU encoder (x264)
    if 'libx264' in encoders:
        print("[CPU] Selected encoder: libx264 (Software)")
        return [
            '-c:v', 'libx264',
            '-preset', 'fast',
            '-crf', '23',
        ]

    # 5. Last resort generic fallback
    selected = ['-c:v', 'libx264'] if 'libx264' in encoders else ['-c:v', 'h264']
    print(f"[GPU] Selected encoder: {selected[1]}")
    return selected


def get_ffmpeg_hwaccel_input_args():
    """
    Get FFmpeg hardware-accelerated decoding args.
    Returns list of args to prepend BEFORE -i input.
    """
    if has_nvidia_gpu():
        # Using 'cuda' is more specific for NVIDIA and often more stable than 'auto'
        # which might pick 'd3d11va' and crash on some Windows environments.
        return ['-hwaccel', 'cuda']
        
    return []


def get_cv2_writer_fourcc():
    """Get optimal OpenCV VideoWriter fourcc code."""
    # mp4v is universally compatible
    import cv2
    return cv2.VideoWriter_fourcc(*'mp4v')


def print_gpu_info():
    """Print GPU info for debugging."""
    if has_nvidia_gpu():
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total,memory.free,utilization.gpu',
             '--format=csv,noheader'],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            info = result.stdout.strip()
            print(f'[GPU] Info: {info}')
            return info
    return 'No GPU'


def run_gpu_diagnostics():
    """
    Perform a full GPU health check. 
    Returns (success, results_dict)
    """
    results = {
        "nvidia_gpu": has_nvidia_gpu(),
        "torch_cuda": False,
        "ffmpeg_nvenc": False,
        "ffmpeg_smoke_test": False
    }

    print("\n--- GPU Startup Diagnostics ---")
    
    # 1. Basic NVIDIA Check
    if results["nvidia_gpu"]:
        print("âœ… NVIDIA Hardware Detected")
        print_gpu_info()
    else:
        print("â Œ No NVIDIA Hardware found")

    # 2. PyTorch CUDA Check
    try:
        import torch
        results["torch_cuda"] = torch.cuda.is_available()
        if results["torch_cuda"]:
            print(f"âœ… PyTorch CUDA: Available (Device: {torch.cuda.get_device_name(0)})")
        else:
            print("âš ï¸  PyTorch CUDA: NOT AVAILABLE (Whisper will run on CPU)")
    except ImportError:
        print("â Œ PyTorch: Not installed")

    # 3. FFmpeg Encoder Check
    encoders = get_ffmpeg_encoders()
    results["ffmpeg_nvenc"] = 'h264_nvenc' in encoders
    if results["ffmpeg_nvenc"]:
        print("âœ… FFmpeg: h264_nvenc available")
    else:
        print("âš ï¸  FFmpeg: h264_nvenc NOT found (Hardware encoding disabled)")

    # 4. Smoke Test (FFmpeg encode small black frame)
    if results["ffmpeg_nvenc"]:
        print("Running FFmpeg smoke test...")
        try:
            # Create a 1-second black video using the selected encoder
            encode_args = get_ffmpeg_video_encode_args()
            test_cmd = [
                'ffmpeg', '-y', '-f', 'lavfi', '-i', 'color=c=black:s=128x128:d=1',
                *encode_args, '-f', 'mp4', 'null' if os.name == 'nt' else '/dev/null'
            ]
            subprocess.run(test_cmd, check=True, capture_output=True, timeout=10)
            results["ffmpeg_smoke_test"] = True
            print("âœ… FFmpeg Smoke Test: SUCCESS")
        except Exception as e:
            print(f"â Œ FFmpeg Smoke Test: FAILED ({e})")
            results["ffmpeg_smoke_test"] = False
    
    print("-------------------------------\n")
    return all([results["nvidia_gpu"], results["torch_cuda"], results["ffmpeg_smoke_test"]]), results
