import os
import json
import subprocess
import logging
import traceback

logger = logging.getLogger(__name__)

def render_remotion_video(
    project_dir, 
    clip_path, 
    output_path, 
    transcript, 
    caption_settings, 
    crop_params,
    progress_callback=None
):
    """
    Executes 'npx remotion render' to generate the final video with captions and cropping.
    """
    try:
        frontend_dir = os.path.join(os.getcwd(), 'frontend')
        
        # 1. Prepare Props for Remotion
        # Remotion needs absolute paths to find the video file
        abs_clip_path = os.path.abspath(clip_path)
        
        props = {
            "videoSrc": abs_clip_path,
            "transcript": transcript,
            "captionSettings": caption_settings,
            "cropX": crop_params.get('cropX', 0.5),
            "cropY": crop_params.get('cropY', 0.5),
            "zoom": crop_params.get('zoom', 1.0),
            "startSecs": crop_params.get('startSecs', 0.0),
            "captionStyle": caption_settings.get('presetId', 'classic')
        }
        
        # 2. Write props to a temp file to avoid CLI argument length limits
        props_file = os.path.join(project_dir, 'remotion_props.json')
        with open(props_file, 'w', encoding='utf-8') as f:
            json.dump(props, f)
            
        logger.info(f"[REMOTION] Props saved to {props_file}")
        if progress_callback:
            progress_callback('render', 'Memulai mesin render Remotion...', 80)

        # 3. Build Command
        # Composition ID is 'Clipper' as defined in Root.tsx
        cmd = [
            "npx", "remotion", "render", 
            "src/remotion/Root.tsx", "Clipper", 
            os.path.abspath(output_path),
            "--props", os.path.abspath(props_file),
            "--overwrite"
        ]
        
        logger.info(f"[REMOTION] Running command: {' '.join(cmd)}")
        
        # 4. Execute and stream progress
        process = subprocess.Popen(
            cmd,
            cwd=frontend_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            shell=True # Needed for npx on Windows
        )
        
        for line in process.stdout:
            # Remotion CLI outputs progress like: "Rendering... 10%"
            # We can parse this if we want exact progress
            line = line.strip()
            if "Rendering" in line and "%" in line:
                try:
                    pct_str = line.split("Rendering")[-1].split("%")[0].strip()
                    pct = int(pct_str)
                    if progress_callback:
                        # Map Remotion's 0-100% to our 80-100% range
                        mapped_pct = 80 + (pct * 0.2)
                        progress_callback('render', f'Rendering video: {pct}%', int(mapped_pct))
                except:
                    pass
            logger.debug(f"[REMOTION OUTPUT] {line}")
            
        process.wait()
        
        if process.returncode != 0:
            raise RuntimeError(f"Remotion render failed with exit code {process.returncode}")
            
        logger.info(f"[REMOTION] Successfully rendered to {output_path}")
        
        # Cleanup temp props file
        if os.path.exists(props_file):
            os.remove(props_file)
            
        return output_path
        
    except Exception as e:
        logger.error(f"[REMOTION ERROR] {str(e)}")
        traceback.print_exc()
        raise
