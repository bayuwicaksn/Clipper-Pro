"""
Pipeline â€” Orchestrates all processing modules in sequence
"""

import os
import json
import traceback
from datetime import datetime
from .analyzer import timestamp_to_seconds


class Pipeline:
    """
    Full video-to-clips pipeline orchestrator.
    
    Steps:
    1. Download video + subtitles
    2. Analyze transcript for highlights
    3. Clip segments
    4. Reframe to portrait (9:16)
    5. Generate hooks (optional)
    6. Generate captions (optional)
    7. Save metadata
    """

    def __init__(self, job_dir, config, progress_callback=None):
        from .utils import pipeline_logger as logger
        self.logger = logger
        self.job_dir = job_dir
        self.config = config
        self.progress = progress_callback or (lambda *a, **k: None)
        # New layout: per-clip dirs under clips/
        self.clips_root = os.path.join(job_dir, 'clips')
        os.makedirs(self.clips_root, exist_ok=True)
        # Keep legacy output_dir for backward compat in export
        self.output_dir = os.path.join(job_dir, 'output')

    def _clip_dir(self, clip_index):
        """Return and ensure the per-clip directory exists."""
        d = os.path.join(self.clips_root, f'clip_{clip_index + 1:02d}')
        os.makedirs(d, exist_ok=True)
        os.makedirs(os.path.join(d, 'segments'), exist_ok=True)
        os.makedirs(os.path.join(d, 'exports'), exist_ok=True)
        return d

    def run(self):
        """Execute the full pipeline. Returns list of clip metadata dicts."""
        clips_result = []

        try:
            # â”€â”€â”€ GPU Detection â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            from .gpu_utils import print_gpu_info, has_nvidia_gpu
            if has_nvidia_gpu():
                self.progress('download', 'GPU detected! Using hardware-accelerated encoding', 3)
                self.logger.info("GPU detected! Using hardware-accelerated encoding")
                print_gpu_info()
            else:
                self.progress('download', 'No GPU detected, using CPU encoding', 3)
                self.logger.info("No GPU detected, using CPU encoding")

            # â”€â”€â”€ Step 1: Download â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            self.progress('download', 'Establishing connection with YouTube...', 5)
            from .downloader import download_video
            dl = download_video(
                self.config['url'],
                self.job_dir,
                progress_callback=self.progress
            )
            video_path = dl['video_path']
            video_metadata = dl['metadata']

            # â”€â”€â”€ Step 2: Analyze â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            self.progress('analyze', 'AI is preparing transcript...', 20)
            from .analyzer import analyze_highlights
            from .utils import get_source_transcript

            transcript_path = os.path.join(self.job_dir, 'source_transcript.json')
            if os.path.exists(transcript_path):
                self.progress('analyze', 'Transcript cache found, skipping transcription...', 25)
            else:
                self.progress('analyze', 'Generating precise word-level timestamps with Whisper...', 25)
            
            _, words = get_source_transcript(
                self.job_dir, 
                provider=self.config.get('transcription_provider', 'openai-whisper'),
                progress_callback=self.progress
            )
            
            # Convert word list to the string format expected by analyze_highlights
            transcript_lines = []
            current_line = []
            last_ts = -1
            
            for w in words:
                ts = int(w['start'])
                if ts != last_ts and current_line:
                    from .utils import seconds_to_timestamp_simple
                    ts_str = seconds_to_timestamp_simple(last_ts)
                    transcript_lines.append(f"[{ts_str}] {' '.join(current_line)}")
                    current_line = []
                current_line.append(w['word'])
                last_ts = ts
            
            if current_line:
                from .utils import seconds_to_timestamp_simple
                transcript_lines.append(f"[{seconds_to_timestamp_simple(last_ts)}] {' '.join(current_line)}")
            
            transcript = '\n'.join(transcript_lines)

            self.progress('analyze', 'Scanning transcript for viral segments...', 40)
            highlights = analyze_highlights(
                transcript,
                self.config,
                progress_callback=self.progress
            )

            if not highlights:
                self.progress('error', 'No highlights found in the video.', 0)
                return []

            self.progress('analyze', f'Success! Found {len(highlights)} potential viral clips.', 70)

            # â”€â”€â”€ Deferred Rendering â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            # Instead of physical clipping here, we just save metadata.
            self.progress('analyze', 'Mapping segments and preparing metadata...', 85)
            
            for i, h in enumerate(highlights):
                clip_data = {
                    'clip_index': i,
                    'filename': f'clip_{i+1:02d}_master.mp4', # Expected final filename
                    'title': h.get('title', f'Clip {i+1}'),
                    'hook_text': h.get('hook_text', ''),
                    'start_time': h.get('start_time', ''),
                    'end_time': h.get('end_time', ''),
                    'duration_seconds': h.get('duration_seconds', 0),
                    'description': h.get('description', ''),
                    'tags': h.get('tags', []),
                    'has_hook': self.config.get('enable_hook', True),
                    'has_captions': self.config.get('enable_captions', True),
                    'auto_background_enabled': True,
                    'extract': h.get('extract', '') # Store transcript extract
                }
                clips_result.append(clip_data)

            # ————————————————————————————————————————————————————————————————————————
            self.progress('finalize', 'Finalizing project workspace...', 95)
            self._save_metadata(clips_result, video_metadata)

            self.progress('done', 'Pipeline complete! Click clips to start editing.', 100)

        except Exception as e:
            self.logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
            self.progress('error', f'Pipeline failed: {str(e)}', 0)
            raise

        return clips_result

    def export_single_clip(self, highlight, custom_start=None, custom_end=None, 
                           custom_crop_x=None, segments=None, aspect_ratio='9:16', 
                           auto_background_enabled=True, delegate_captions=False,
                           export_id=None):
        """
        Export a single clip with full processing.
        If delegate_captions=True, it will skip caption rendering and return metadata for worker_node.
        """
        import time
        index = highlight.get('clip_index', 0)
        total = 1 # We are doing single export
        base_name = highlight.get('filename', f'clip_{index+1:02d}.mp4').replace('.mp4', '')
        
        # If export_id is provided, make the filename unique to avoid overwriting
        clip_name = f"{base_name}_{export_id}" if export_id else base_name
        
        # Ensure workspace subdirs exist
        temp_dir = os.path.join(self.job_dir, 'clips', f'clip_{index+1:02d}', 'segments', f'run_{int(time.time())}')
        os.makedirs(temp_dir, exist_ok=True)

        # Output folder for final exports
        exports_dir = os.path.join(self.job_dir, 'clips', f'clip_{index+1:02d}', 'exports')
        os.makedirs(exports_dir, exist_ok=True)
        
        # Path for the reframed (but potentially not captioned) result
        # We use exports_dir for the intermediate reframed file if delegating
        if delegate_captions:
            reframed_path = os.path.join(exports_dir, f'{clip_name}_reframed.mp4')
        else:
            reframed_path = os.path.join(temp_dir, f'{clip_name}_reframed.mp4')
            
        current_path = os.path.join(self.job_dir, 'source.mp4') # Start from source

        # â”€â”€â”€ Step 1: Clipping + Reframing (Always done on GPU) â”€â”€â”€
        self.progress('clip', f'Clipping precision segment...', 10)
        from .reframer import reframe_clip
        
        # Determine start/end times
        from shared.utils.helpers import timestamp_to_seconds
        
        start_time = custom_start if custom_start is not None else highlight.get('start_time', 0)
        end_time = custom_end if custom_end is not None else highlight.get('end_time', 0)
        
        # Ensure they are floats (seconds)
        if isinstance(start_time, str): start_time = timestamp_to_seconds(start_time)
        if isinstance(end_time, str): end_time = timestamp_to_seconds(end_time)
        
        # Note: reframer will handle the actual ffmpeg call
        reframe_clip(
            current_path, reframed_path, 
            mode='mediapipe', 
            progress_callback=self.progress,
            clip_index=index, total_clips=total,
            custom_crop_x=custom_crop_x,
            segments=segments,
            aspect_ratio=aspect_ratio,
            auto_background_enabled=auto_background_enabled,
            start_time=start_time,
            end_time=end_time
        )

        if os.path.exists(reframed_path) and os.path.getsize(reframed_path) > 0:
            current_path = reframed_path

        # If we are delegating, stop here and return the path
        if delegate_captions:
            self.logger.info(f"[Pipeline] Reframing complete. Delegating captions to Node worker.")
            return {
                "video_path": current_path,
                "status": "ready_for_captions",
                "export_path": os.path.join(exports_dir, f"{clip_name}_final.mp4"),
                "clip_name": clip_name
            }

        # â”€â”€â”€ Step 2: Hook intro (optional TTS + blurred intro) â”€â”€â”€
        return self._process_single_clip(current_path, highlight, index, total, aspect_ratio, temp_dir)

    def _process_single_clip(self, raw_clip_path, highlight, index, total, aspect_ratio='9:16', work_dir=None):
        """Process a single clip through reframe â†’ captions â†’ hook (all FFmpeg-native)."""
        clip_dir = self._clip_dir(index)
        exports_dir = os.path.join(clip_dir, 'exports')
        os.makedirs(exports_dir, exist_ok=True)
        
        # Use work_dir for intermediate files, fall back to exports if none provided
        temp_dir = work_dir or exports_dir
        os.makedirs(temp_dir, exist_ok=True)
        
        clip_name = f'clip_{index+1:02d}'

        current_path = raw_clip_path

        # â”€â”€â”€ Step 1: Reframe (16:9 â†’ 9:16 portrait crop) â”€â”€â”€â”€â”€â”€â”€â”€â”€
        self.progress('reframe', f'Reframing clip to portrait...', 40)
        reframed_path = os.path.join(temp_dir, f'{clip_name}_reframed.mp4')

        from .reframer import reframe_clip

        segments = highlight.get('segments')
        custom_crop_x = highlight.get('custom_crop_x')
        auto_background_enabled = highlight.get('auto_background_enabled', True)

        reframe_clip(
            raw_clip_path, reframed_path,
            mode=self.config.get('reframe_mode', 'opencv'),
            progress_callback=self.progress,
            clip_index=index, total_clips=total,
            custom_crop_x=custom_crop_x,
            segments=segments,
            aspect_ratio=aspect_ratio,
            auto_background_enabled=auto_background_enabled
        )

        if os.path.exists(reframed_path) and os.path.getsize(reframed_path) > 0:
            current_path = reframed_path

        # â”€â”€â”€ Step 2: Hook intro (optional TTS + blurred intro) â”€â”€â”€
        if self.config.get('enable_hook', True) and highlight.get('hook_text'):
            self.progress('hook', f'Generating hook intro...', 55)
            hooked_path = os.path.join(temp_dir, f'{clip_name}_hooked.mp4')
            try:
                from .hook_generator import generate_hook
                generate_hook(
                    current_path, highlight['hook_text'], hooked_path,
                    config=self.config, progress_callback=self.progress,
                    clip_index=index, total_clips=total
                )
                if os.path.exists(hooked_path) and os.path.getsize(hooked_path) > 0:
                    current_path = hooked_path
            except Exception as e:
                self.logger.warning(f"Hook generation failed (non-fatal): {e}")

        # â”€â”€â”€ Step 3: Captions (HyperFrames composition + GSAP) â”€â”€â”€â”€
        caption_settings = self.config.get('caption_settings', {})
        if self.config.get('enable_captions', True) and caption_settings.get('presetId') != 'none':
            self.progress('caption', f'Generating caption composition...', 70)
            captioned_path = os.path.join(temp_dir, f'{clip_name}_final.mp4')

            # Prepare word-level transcript mapped to clip-local time
            custom_words = None
            transcript_words = highlight.get('transcript', [])
            
            # Fallback: Try to load from source_transcript.json if missing in metadata
            if not transcript_words:
                transcript_path = os.path.join(self.job_dir, "source_transcript.json")
                if os.path.exists(transcript_path):
                    try:
                        with open(transcript_path, 'r', encoding='utf-8') as f:
                            data = json.load(f)
                            # Handle different transcription formats (list or dict with 'words' key)
                            if isinstance(data, list):
                                transcript_words = data
                            elif isinstance(data, dict):
                                transcript_words = data.get('words', [])
                        self.logger.info(f"[Pipeline] Loaded {len(transcript_words)} words from source_transcript.json for mapping")
                    except Exception as e:
                        self.logger.warning(f"[Pipeline] Failed to load source_transcript.json: {e}")

            if transcript_words:
                clip_start = timestamp_to_seconds(highlight.get('start_time', '00:00:00'))
                clip_end = timestamp_to_seconds(highlight.get('end_time', '00:00:00'))
                
                custom_words = []
                for w in transcript_words:
                    w_start = w.get('start', 0)
                    w_end = w.get('end', 0)
                    
                    # Only include words within the clip range
                    if w_start >= clip_start and w_end <= clip_end:
                        local_start = w_start - clip_start
                        local_end = w_end - clip_start
                        custom_words.append({
                            'word': w.get('word', w.get('text', '')),
                            'start': max(0, local_start),
                            'end': max(0, local_end)
                        })
                
                self.logger.info(f"[Pipeline] Mapped {len(custom_words)} words for clip duration.")

            caption_success = False
            caption_settings = self.config.get('caption_settings', {})

            # Try HyperFrames composition-based rendering first
            if custom_words and caption_settings.get('presetId') != 'none':
                self.logger.info(f"[Pipeline] ðŸŽ¨ ACTIVATING HYPERFRAMES (Premium Rendering)...")
                try:
                    from .caption_composition import generate_caption_composition, render_composition

                    # Parse video dimensions from aspect ratio
                    ar = self.config.get('aspect_ratio', '9:16')
                    try:
                        parts = [float(x) for x in ar.split(':')]
                        video_w = 1080 if parts[0] < parts[1] else 1920
                        video_h = 1920 if parts[0] < parts[1] else 1080
                    except Exception:
                        video_w, video_h = 1080, 1920

                    # Generate HTML composition
                    composition_path = os.path.join(temp_dir, f'{clip_name}_caption.html')
                    generate_caption_composition(
                        video_src=current_path,
                        output_html=composition_path,
                        words=custom_words,
                        settings=caption_settings,
                        video_w=video_w,
                        video_h=video_h,
                    )

                    # Render composition to transparent MOV (Hybrid Approach)
                    self.progress('caption', f'Rendering captions (Hybrid Overlay)...', 80)
                    overlay_mov_path = os.path.join(temp_dir, f'{clip_name}_overlay.mov')
                    render_composition(composition_path, overlay_mov_path)

                    if os.path.exists(overlay_mov_path) and os.path.getsize(overlay_mov_path) > 0:
                        # Step 4: Composite the transparent captions over the reframed video
                        self.progress('caption', f'Compositing hybrid final video...', 85)
                        from .caption_composition import composite_transparent_captions
                        composite_transparent_captions(current_path, overlay_mov_path, captioned_path)
                        
                        if os.path.exists(captioned_path) and os.path.getsize(captioned_path) > 0:
                            caption_success = True
                            self.logger.info(f"[Pipeline] Hybrid HyperFrames caption render successful")
                    
                    # Cleanup composition HTML and overlay MOV
                    try:
                        if os.path.exists(composition_path): os.remove(composition_path)
                        if os.path.exists(overlay_mov_path): os.remove(overlay_mov_path)
                    except Exception:
                        pass

                except Exception as e:
                    self.logger.warning(f"[Pipeline] HyperFrames caption failed, falling back to ASS: {e}")

            # Fallback: old ASS-based caption burning
            if not caption_success:
                self.progress('caption', f'Burning captions (fallback)...', 80)
                from .caption_generator import generate_captions
                generate_captions(
                    current_path, captioned_path,
                    config=self.config,
                    progress_callback=self.progress,
                    clip_index=index, total_clips=total,
                    custom_words=custom_words
                )

            if os.path.exists(captioned_path) and os.path.getsize(captioned_path) > 0:
                current_path = captioned_path
        else:
            # No captions â€” just copy to final location
            import shutil
            captioned_path = os.path.join(temp_dir, f'{clip_name}_final.mp4')
            shutil.copy(current_path, captioned_path)
            current_path = captioned_path

        self.progress('finalize', 'Video render complete!', 98)

        # Rename to clean final name with timestamp to prevent overwriting
        import time
        ts = int(time.time())
        final_filename = f'{clip_name}_v{ts}.mp4'
        master_path = os.path.join(exports_dir, final_filename)
        if current_path != master_path:
            if os.path.exists(master_path):
                os.remove(master_path)
            os.rename(current_path, master_path)

        # Cleanup intermediate files (ignore errors if locked by Windows)
        for suffix in ['_raw', '_reframed', '_hooked', '_final']:
            temp = os.path.join(exports_dir, f'{clip_name}{suffix}.mp4')
            if os.path.exists(temp) and temp != master_path:
                try:
                    os.remove(temp)
                except Exception:
                    pass

        return {
            'filename': final_filename,
            'title': highlight.get('title', f'Clip {index+1}'),
            'hook_text': highlight.get('hook_text', ''),
            'start_time': highlight.get('start_time', ''),
            'end_time': highlight.get('end_time', ''),
            'duration_seconds': highlight.get('duration_seconds', 0),
            'description': highlight.get('description', ''),
            'tags': highlight.get('tags', []),
            'has_hook': self.config.get('enable_hook', True),
            'has_captions': self.config.get('enable_captions', True),
            'auto_background_enabled': highlight.get('auto_background_enabled', True),
        }

    def _save_metadata(self, clips, video_metadata):
        """Save metadata JSON for each clip and the session."""
        session_data = {
            'video': video_metadata,
            'config': self.config,
            'created_at': datetime.now().isoformat(),
            'clips': clips,
        }
        # Save session.json at project root (new layout)
        with open(os.path.join(self.job_dir, 'session.json'), 'w', encoding='utf-8') as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)

        # Save per-clip meta.json inside each clip's directory
        for clip in clips:
            clip_dir = self._clip_dir(clip['clip_index'])
            meta_path = os.path.join(clip_dir, 'meta.json')
            with open(meta_path, 'w', encoding='utf-8') as f:
                json.dump(clip, f, indent=2, ensure_ascii=False)
