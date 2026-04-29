"""
Pipeline — Orchestrates all processing modules in sequence
"""

import os
import json
import traceback
from datetime import datetime
from core.analyzer import timestamp_to_seconds


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
        from core.utils import pipeline_logger as logger
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
            # ─── GPU Detection ──────────────────────────────────────
            from core.gpu_utils import print_gpu_info, has_nvidia_gpu
            if has_nvidia_gpu():
                self.progress('download', 'GPU detected! Using hardware-accelerated encoding', 3)
                self.logger.info("GPU detected! Using hardware-accelerated encoding")
                print_gpu_info()
            else:
                self.progress('download', 'No GPU detected, using CPU encoding', 3)
                self.logger.info("No GPU detected, using CPU encoding")

            # ─── Step 1: Download ────────────────────────────────────
            self.progress('download', 'Establishing connection with YouTube...', 5)
            from core.downloader import download_video
            dl = download_video(
                self.config['url'],
                self.job_dir,
                progress_callback=self.progress
            )
            video_path = dl['video_path']
            video_metadata = dl['metadata']

            # ─── Step 2: Analyze ─────────────────────────────────────
            self.progress('analyze', 'AI is preparing transcript...', 20)
            from core.analyzer import analyze_highlights
            from core.utils import get_source_transcript

            transcript_path = os.path.join(self.job_dir, 'source_transcript.json')
            if os.path.exists(transcript_path):
                self.progress('analyze', 'Transcript cache found, skipping transcription...', 25)
            else:
                self.progress('analyze', 'Generating precise word-level timestamps with Whisper...', 25)
            
            _, words = get_source_transcript(self.job_dir, provider=self.config.get('transcription_provider', 'openai-whisper'))
            
            # Convert word list to the string format expected by analyze_highlights
            transcript_lines = []
            current_line = []
            last_ts = -1
            
            for w in words:
                ts = int(w['start'])
                if ts != last_ts and current_line:
                    from core.utils import seconds_to_timestamp_simple
                    ts_str = seconds_to_timestamp_simple(last_ts)
                    transcript_lines.append(f"[{ts_str}] {' '.join(current_line)}")
                    current_line = []
                current_line.append(w['word'])
                last_ts = ts
            
            if current_line:
                from core.utils import seconds_to_timestamp_simple
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

            # ─── Deferred Rendering ──────────────────────────────────
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

            # ─── Step 7: Save metadata ───────────────────────────────
            self.progress('finalize', 'Finalizing project workspace...', 95)
            self._save_metadata(clips_result, video_metadata)

            self.progress('done', 'Pipeline complete! Click clips to start editing.', 100)

        except Exception as e:
            self.logger.error(f"Pipeline failed: {str(e)}", exc_info=True)
            self.progress('error', f'Pipeline failed: {str(e)}', 0)
            raise

        return clips_result

    def export_single_clip(self, clip_metadata, custom_start=None, custom_end=None, custom_crop_x=None, segments=None, clip_index=None, aspect_ratio='9:16'):
        """Run the actual rendering pipeline for a single tweaked clip."""
        segments_dir = None
        try:
            self.progress('clip', 'Clipping precision segment...', 10)
            
            video_path = os.path.join(self.job_dir, 'source.mp4')
            if not os.path.exists(video_path):
                for f in os.listdir(self.job_dir):
                    if f.endswith('.mp4') and not os.path.isdir(os.path.join(self.job_dir, f)):
                        video_path = os.path.join(self.job_dir, f)
                        break
            
            if custom_start: clip_metadata['start_time'] = custom_start
            if custom_end: clip_metadata['end_time'] = custom_end
            if custom_crop_x is not None: clip_metadata['custom_crop_x'] = custom_crop_x
            if segments: clip_metadata['segments'] = segments
            clip_metadata['auto_background_enabled'] = clip_metadata.get('auto_background_enabled', True)

            # Determine which clip index to use for directory
            idx = clip_index if clip_index is not None else clip_metadata.get('clip_index', 0)
            clip_dir = self._clip_dir(idx)

            # Use a unique segments subdirectory per export to avoid Windows file locks
            import time as _time
            export_ts = int(_time.time())
            segments_dir = os.path.join(clip_dir, 'segments', f'run_{export_ts}')

            from core.clipper import clip_segments
            raw_clips = clip_segments(
                video_path, [clip_metadata], segments_dir,
                progress_callback=None
            )
            
            if not raw_clips:
                raise RuntimeError("Clipping failed.")
                
            raw_clip_path = raw_clips[0]
            
            final_data = self._process_single_clip(
                raw_clip_path, clip_metadata, idx, 1,
                aspect_ratio=aspect_ratio,
                work_dir=segments_dir
            )
            
            # Cleanup temporary segments directory
            if segments_dir:
                try:
                    import shutil
                    shutil.rmtree(segments_dir, ignore_errors=True)
                except Exception:
                    pass

            self.progress('done', 'Export finished.', 100)
            return final_data
            
        except Exception as e:
            traceback.print_exc()
            # Cleanup on error too
            if segments_dir:
                try:
                    import shutil
                    shutil.rmtree(segments_dir, ignore_errors=True)
                except Exception:
                    pass
            self.progress('error', f'Export failed: {str(e)}', 0)
            raise

    def _process_single_clip(self, raw_clip_path, highlight, index, total, aspect_ratio='9:16', work_dir=None):
        """Process a single clip through reframe → captions → hook (all FFmpeg-native)."""
        clip_dir = self._clip_dir(index)
        exports_dir = os.path.join(clip_dir, 'exports')
        os.makedirs(exports_dir, exist_ok=True)
        
        # Use work_dir for intermediate files, fall back to exports if none provided
        temp_dir = work_dir or exports_dir
        os.makedirs(temp_dir, exist_ok=True)
        
        clip_name = f'clip_{index+1:02d}'

        current_path = raw_clip_path

        # ─── Step 1: Reframe (16:9 → 9:16 portrait crop) ─────────
        self.progress('reframe', f'Reframing clip to portrait...', 40)
        reframed_path = os.path.join(temp_dir, f'{clip_name}_reframed.mp4')

        from core.reframer import reframe_clip

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

        # ─── Step 2: Hook intro (optional TTS + blurred intro) ───
        if self.config.get('enable_hook', True) and highlight.get('hook_text'):
            self.progress('hook', f'Generating hook intro...', 55)
            hooked_path = os.path.join(temp_dir, f'{clip_name}_hooked.mp4')
            try:
                from core.hook_generator import generate_hook
                generate_hook(
                    current_path, highlight['hook_text'], hooked_path,
                    config=self.config, progress_callback=self.progress,
                    clip_index=index, total_clips=total
                )
                if os.path.exists(hooked_path) and os.path.getsize(hooked_path) > 0:
                    current_path = hooked_path
            except Exception as e:
                self.logger.warning(f"Hook generation failed (non-fatal): {e}")

        # ─── Step 3: Captions (HyperFrames composition + GSAP) ────
        if self.config.get('enable_captions', True):
            self.progress('caption', f'Generating caption composition...', 70)
            captioned_path = os.path.join(temp_dir, f'{clip_name}_final.mp4')

            # Prepare word-level transcript mapped to clip-local time
            custom_words = None
            transcript_words = highlight.get('transcript', [])
            if transcript_words:
                clip_start = timestamp_to_seconds(highlight.get('start_time', '00:00:00'))
                custom_words = []
                for w in transcript_words:
                    local_start = w.get('start', 0) - clip_start
                    local_end = w.get('end', 0) - clip_start
                    if local_end > 0:
                        custom_words.append({
                            'word': w.get('word', w.get('text', '')),
                            'start': max(0, local_start),
                            'end': max(0, local_end)
                        })

            caption_success = False
            caption_settings = self.config.get('caption_settings', {})

            # Try HyperFrames composition-based rendering first
            if custom_words and caption_settings.get('presetId') != 'none':
                try:
                    from core.caption_composition import generate_caption_composition, render_composition

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
                        from core.caption_composition import composite_transparent_captions
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
                from core.caption_generator import generate_captions
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
            # No captions — just copy to final location
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
