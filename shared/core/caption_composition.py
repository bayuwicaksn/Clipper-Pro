"""
Caption Composition Generator â€” HyperFrames HTML + GSAP
Generates a single HTML composition file that renders identically
in both the browser preview (<hyperframes-player>) and export (npx hyperframes render).

Replaces the ASS subtitle approach with a unified rendering engine.
"""

import os
import re
import json
import logging

logger = logging.getLogger('pipeline')

# â”€â”€ Auto-Highlight Keyword Patterns â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
# Synced between frontend and backend
GREEN_REGEX  = r"(?i)^(sukses|kaya|uang|viral|trending|presiden|milyar|triliun|cuan|profit|untung|berhasil)"
YELLOW_REGEX = r"(?i)^(penting|rahasia|masalah|solusi|gila|keren|tips|trik|cara|fakta|bukti|seru|menarik|wow)"


def generate_caption_composition(
    video_src,
    output_html,
    words,
    settings,
    video_w=1080,
    video_h=1920,
    preview_mode=False,
):
    """
    Generate a HyperFrames HTML composition with GSAP word-by-word karaoke captions.
    
    Args:
        video_src: Path or URL to the reframed video (used as background layer)
        output_html: Output path for the composition HTML file
        words: List of {'word': str, 'start': float, 'end': float} dicts
        settings: Caption settings dict from the editor
        video_w: Video width in pixels
        video_h: Video height in pixels
        preview_mode: If True, generates transparent bg, no video, with postMessage controller
    """
    if not words:
        logger.warning("[Caption] No words provided, skipping composition generation.")
        return None

    os.makedirs(os.path.dirname(output_html), exist_ok=True)
    
    # Standardize output to index.html for HyperFrames/Remotion directory mode
    work_dir = os.path.dirname(output_html)
    standard_input = os.path.join(work_dir, "index.html")


    # â”€â”€ Extract settings with defaults â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    font_name       = settings.get('fontName') or 'Montserrat'
    font_size       = settings.get('fontSize')
    if font_size is None: font_size = 100
    
    font_weight     = settings.get('fontWeight') or 'Black'
    is_italic       = bool(settings.get('isItalic', False))
    is_underline    = bool(settings.get('isUnderline', False))
    is_uppercase    = bool(settings.get('isUppercase', True))

    primary_color   = settings.get('primaryColor') or '#FFFFFF'
    outline_color   = settings.get('outlineColor') or '#000000'
    outline_width   = settings.get('outlineWidth')
    if outline_width is None: outline_width = 8
    
    highlight_green = settings.get('highlightColor1') or '#04f827'
    highlight_yellow= settings.get('highlightColor2') or '#fffd03'

    shadow_enabled  = bool(settings.get('shadowEnabled', True))
    shadow_color    = settings.get('shadowColor') or '#000000'
    shadow_x        = settings.get('shadowOffsetX')
    if shadow_x is None: shadow_x = 2
    shadow_y        = settings.get('shadowOffsetY')
    if shadow_y is None: shadow_y = 2
    shadow_blur     = settings.get('shadowBlur')
    if shadow_blur is None: shadow_blur = 2

    auto_highlight  = bool(settings.get('autoHighlight', True))
    line_limit      = 2 # Hardcoded default
    
    caption_x       = settings.get('captionX')
    if caption_x is None: caption_x = 0.5
    caption_y       = settings.get('captionY')
    if caption_y is None: caption_y = 0.82
    caption_width   = settings.get('captionWidth')
    if caption_width is None: caption_width = 85
    
    style_type      = (settings.get('styleType') or 'classic').lower()

    # â”€â”€ Font weight mapping â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    css_font_weight = 900 if font_weight in ['Black', 'Heavy'] else (
        700 if font_weight == 'Bold' else (500 if font_weight == 'Medium' else 400)
    )

    # â”€â”€ Responsive Scaling (vh) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # We use vh (viewport height) so the text scales proportionally whether
    # rendered in a 300x533 preview iframe or a 1080x1920 headless browser.
    # The reference height is the dynamic video height (e.g. 1920).
    ref_height = float(video_h)
    
    font_size_vh = (font_size / ref_height) * 100
    
    # Stroke width is proportional to font size. outline_width 8 = 0.8% of font height.
    # Matches legacy CustomCaptions logic: (fontSize * outlineWidth) / 1000
    stroke_width_vh = font_size_vh * (outline_width / 1000.0)
    
    # Shadow sizes conversion (scaled proportionally, assuming default 2px relative to a 100px font)
    # So shadow_x of 2 means 2% of the font size
    shadow_x_vh = font_size_vh * (shadow_x / 100.0)
    shadow_y_vh = font_size_vh * (shadow_y / 100.0)
    shadow_blur_vh = font_size_vh * (shadow_blur / 100.0)

    shadow_css = f"{shadow_x_vh}vh {shadow_y_vh}vh {shadow_blur_vh}vh {shadow_color}" if shadow_enabled else "none"

    # â”€â”€ Compute total duration from words â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    total_duration = max(w['end'] for w in words) if words else 1
    # Add small buffer
    total_duration = round(total_duration + 0.5, 2)

    # â”€â”€ Intelligent Word Chunking (CapCut Style) â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # CapCut splits by:
    # 1. Speech pauses (> 0.4s between words)
    # 2. Punctuation (sentence ends)
    # 3. Visual width constraint (if text exceeds max allowed lines)
    
    # Estimate visual width
    # In a 1080px wide reference scale, font_size represents exact pixels.
    char_width_ratio = 0.7 if is_uppercase else 0.55
    char_width_px = font_size * char_width_ratio
    space_width_px = font_size * 0.3
    
    # Calculate container width capacity in pixels
    # Fallback to 1080 baseline if video_w is weird
    base_w = video_w if video_w else 1080
    max_line_width_px = base_w * (caption_width / 100.0)
    # Total visual capacity is max_line width * number of allowed lines
    # We use a 5% safety buffer so it doesn't clip exactly at the edge
    safe_line_width_px = max_line_width_px * 0.95
    max_chunk_width_px = safe_line_width_px * line_limit

    chunks = []
    current_chunk = []
    current_width_px = 0.0

    for idx, w in enumerate(words):
        txt = w['word'].strip()
        if not txt:
            continue
        
        # Original text for punctuation check
        raw_txt = txt
        if is_uppercase:
            txt = txt.upper()
            
        word_width_px = (len(txt) * char_width_px)
        
        force_break = False
        
        if current_chunk:
            prev_w = current_chunk[-1]
            pause_duration = w['start'] - prev_w['end']
            
            # 1. Break on long pause (> 0.4 seconds)
            if pause_duration > 0.4:
                force_break = True
                
            # 2. Break on end of sentence punctuation from previous word
            if prev_w['raw_word'].rstrip()[-1] in ['.', '!', '?', ',']:
                force_break = True
                
            # 3. Break if adding this word exceeds the visual width capacity of the chunk
            if (current_width_px + space_width_px + word_width_px) > max_chunk_width_px:
                force_break = True
                
        if force_break and current_chunk:
            chunks.append(current_chunk)
            current_chunk = []
            current_width_px = 0.0
            
        current_chunk.append({
            'word': txt,
            'start': round(w['start'], 3),
            'end': round(w['end'], 3),
            'raw_word': raw_txt
        })
        
        # Add to current width (plus space if not first word)
        current_width_px += word_width_px + (space_width_px if len(current_chunk) > 1 else 0)

    if current_chunk:
        chunks.append(current_chunk)

    # â”€â”€ Determine animation parameters â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    is_intense = style_type in ['explosive', 'hype', 'vibrant']
    is_bouncy = style_type in ['explosive', 'hype', 'vibrant', 'model', 'fast']

    scale_active = 1.25 if is_bouncy else 1.10
    y_offset = -12 if is_bouncy else -4
    anim_duration = 0.15  # seconds
    future_opacity = 0.6 if is_intense else 0.8

    # â”€â”€ Build HTML elements for each page/chunk â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    page_elements = []
    gsap_animations = []
    word_counter = 0

    for chunk_idx, chunk in enumerate(chunks):
        chunk_start = chunk[0]['start']
        chunk_end = chunk[-1]['end']
        chunk_duration = round(chunk_end - chunk_start, 3)
        page_id = f"page-{chunk_idx}"

        # Build word spans
        word_spans = []
        for w_idx, w in enumerate(chunk):
            wid = f"w-{word_counter}"
            word_counter += 1

            # Determine static color for keywords
            is_green = auto_highlight and bool(re.match(GREEN_REGEX, w['word'], re.IGNORECASE))
            is_yellow = auto_highlight and bool(re.match(YELLOW_REGEX, w['word'], re.IGNORECASE))

            # Determine static color (always primary color when not active)
            static_color = primary_color
            word_spans.append(f'    <span id="{wid}" class="cw" style="color:{static_color}">{w["word"]}</span>')

            # GSAP animation for this word becoming active
            # Use highlightColor2 if it's a yellow keyword, otherwise Color 1 (default highlight)
            active_color = highlight_yellow if is_yellow else highlight_green
            gsap_animations.append(
                f'  tl.to("#{wid}", {{ color: "{active_color}", scale: {scale_active}, y: {y_offset}, duration: {anim_duration}, ease: "back.out(1.7)" }}, {w["start"]});'
            )
            # Restore to primary color when done
            gsap_animations.append(
                f'  tl.to("#{wid}", {{ color: "{primary_color}", scale: 1, y: 0, duration: {anim_duration} }}, {w["end"]});'
            )

            # 2. Glow effect for intense styles
            if is_intense and shadow_enabled:
                gsap_animations.append(
                    f'  tl.to("#{wid}", {{ textShadow: "{shadow_x}px {shadow_y}px {shadow_blur}px {shadow_color}, 0 0 15px {active_color}", duration: {anim_duration} }}, {w["start"]});'
                )

            # 3. Rotation for intense styles
            if is_intense:
                rot = -4 if w_idx % 2 == 0 else 4
                gsap_animations.append(
                    f'  tl.to("#{wid}", {{ rotation: {rot}, duration: {anim_duration} }}, {w["start"]});'
                )
                gsap_animations.append(
                    f'  tl.to("#{wid}", {{ rotation: 0, duration: 0.1 }}, {w["end"]});'
                )

            # 4. Highlight OFF: restore original color, reset scale
            restore_color = static_color  # Restore to keyword color or primary
            gsap_animations.append(
                f'  tl.to("#{wid}", {{ color: "{restore_color}", scale: 1, y: 0, duration: 0.1, ease: "power2.out" }}, {w["end"]});'
            )

            # 5. Restore shadow
            if is_intense and shadow_enabled:
                gsap_animations.append(
                    f'  tl.to("#{wid}", {{ textShadow: "{shadow_css}", duration: 0.1 }}, {w["end"]});'
                )

        words_html = "\n".join(word_spans)

        page_elements.append(f"""  <div id="{page_id}" class="clip caption-page"
       data-start="{chunk_start}" data-duration="{chunk_duration}" data-track-index="1"
       style="position:absolute; left:{caption_x * 100}%; top:{caption_y * 100}%;
              transform:translate(-50%,-50%); text-align:center; width:{caption_width}%;
              line-height:1.0; text-wrap:balance;">
{words_html}
  </div>""")

    # â”€â”€ Future word opacity â€” set initial opacity for non-first words in each chunk
    for chunk_idx, chunk in enumerate(chunks):
        word_offset = sum(len(chunks[i]) for i in range(chunk_idx))
        for w_idx, w in enumerate(chunk):
            if w_idx > 0:
                wid = f"w-{word_offset + w_idx}"
                # Dim future words, brighten when their page starts
                gsap_animations.insert(0,
                    f'  gsap.set("#{wid}", {{ opacity: {future_opacity} }});'
                )
                gsap_animations.append(
                    f'  tl.to("#{wid}", {{ opacity: 1, duration: 0.1 }}, {w["start"]});'
                )

    # â”€â”€ Escape video path for HTML â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    # Use relative path if possible, or just the filename
    video_filename = os.path.basename(video_src) if video_src else "reframed.mp4"

    # Always transparent background for hybrid rendering / preview
    # HyperFrames/Remotion will detect the transparent body and render alpha channel
    bg_color = 'transparent'

    # Video element â€” we now remove this for the hybrid approach in export mode
    # so the engine only renders the captions as a transparent layer.
    video_html = ''
    
    # We only include the video element in preview_mode (editor) if we want 
    # to see it in the iframe, but actually CustomPreview.jsx has its own video layer.
    # So we keep it empty to ensure we never accidentally render a background in the engine.
    if preview_mode:
        pass


    # Preview controller script (postMessage-based time sync)
    preview_controller = ''
    if preview_mode:
        preview_controller = """
    // Preview controller â€” driven by parent via postMessage
    const pages = document.querySelectorAll('.caption-page');
    const pageData = Array.from(pages).map(p => ({
      el: p,
      start: parseFloat(p.dataset.start),
      duration: parseFloat(p.dataset.duration)
    }));

    function seekTo(timeSec) {
      // Show/hide pages based on time
      pageData.forEach(({ el, start, duration }) => {
        const end = start + duration;
        el.style.display = (timeSec >= start && timeSec < end) ? '' : 'none';
      });
      // Drive GSAP timeline
      tl.seek(timeSec);
    }

    // Listen for seek commands from parent
    window.addEventListener('message', (e) => {
      if (e.data && e.data.type === 'seek') {
        seekTo(e.data.time);
      }
    });

    // Hide all pages initially
    pageData.forEach(({ el }) => { el.style.display = 'none'; });

    // Signal ready to parent
    window.parent.postMessage({ type: 'caption-ready', duration: tl.duration() }, '*');
"""

    # â”€â”€ Compose full HTML â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    pages_html = "\n\n".join(page_elements)
    gsap_js = "\n".join(gsap_animations)

    html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Anton&family=Bangers&family=Bebas+Neue&family=Montserrat:wght@800;900&family=Oswald:wght@700&family=Roboto:wght@700;900&display=swap" rel="stylesheet">
  <style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    html, body {{ overflow: hidden; background: {bg_color}; }}

    .caption-page {{
      pointer-events: none;
      z-index: 50;
      perspective: 1000px;
    }}

    .cw {{
      font-family: "{font_name}", sans-serif;
      font-size: {font_size_vh}vh;
      font-weight: {css_font_weight};
      font-style: {"italic" if is_italic else "normal"};
      text-decoration: {"underline" if is_underline else "none"};
      -webkit-text-stroke: {stroke_width_vh}vh {outline_color};
      text-shadow: {shadow_css};
      display: inline-block;
      margin: 0 0.8vh;
      {"text-transform: uppercase;" if is_uppercase else ""}
      transform-origin: center center;
      will-change: transform, color, opacity;
    }}
  </style>
</head>
<body>
<div id="root" data-composition-id="captions"
     data-start="0" data-duration="{total_duration}" data-width="{video_w}" data-height="{video_h}">

{video_html}

  <!-- Caption Pages -->
{pages_html}

  <!-- GSAP Animation Engine -->
  <script src="https://cdn.jsdelivr.net/npm/gsap@3/dist/gsap.min.js"></script>
  <script>
    const tl = gsap.timeline({{ paused: true }});

{gsap_js}

    window.__timelines = window.__timelines || {{}};
    window.__timelines["captions"] = tl;
{preview_controller}
  </script>
</div>
</body>
</html>"""

    with open(output_html, 'w', encoding='utf-8') as f:
        f.write(html)

    file_size = os.path.getsize(output_html) if os.path.exists(output_html) else 0
    logger.info(f"[Caption] HyperFrames composition created: {output_html} ({file_size} bytes, {len(chunks)} pages, {word_counter} words)")
    return output_html


def render_composition(composition_path, output_path, fps=30):
    """
    Render a HyperFrames composition to MP4 using the CLI.
    """
    import subprocess
    import shutil

    if not os.path.exists(composition_path):
        raise FileNotFoundError(f"Composition not found: {composition_path}")

    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Standardize: HyperFrames/Remotion works best if the input is a directory with index.html
    # We rename our temporary HTML to index.html within its segment folder
    work_dir = os.path.dirname(composition_path)
    standard_input = os.path.join(work_dir, "index.html")
    
    if os.path.basename(composition_path) != "index.html":
        if os.path.exists(standard_input):
            os.remove(standard_input)
        shutil.copy2(composition_path, standard_input)

    # Remove existing output to avoid prompts
    if os.path.exists(output_path):
        try:
            os.remove(output_path)
        except Exception:
            pass

    # Hybrid Approach: Render as transparent MOV (ProRes 4444)
    # Flags: --workers auto (concurrency), --quality draft (speed), --format mov (alpha)
    cmd = f'npx -y hyperframes render --input . --output "{os.path.basename(output_path)}" --fps {fps} --gpu --workers auto --quality draft --format mov'

    logger.info(f"[Caption] Rendering composition: {cmd} (CWD: {work_dir})")

    try:
        result = subprocess.run(
            cmd, 
            capture_output=True, 
            text=True, 
            timeout=300,
            cwd=work_dir,
            shell=os.name == 'nt'
        )
        if result.returncode != 0:
            logger.error(f"[Caption] HyperFrames render failed: {result.stderr}")
            raise RuntimeError(f"HyperFrames render failed: {result.stderr}")
        
        logger.info(f"[Caption] Render complete: {output_path}")
        return output_path
    except subprocess.TimeoutExpired:
        raise RuntimeError("HyperFrames render timed out after 300 seconds")


def composite_transparent_captions(base_video_path, overlay_mov_path, output_path):
    """
    Composite a transparent .mov (ProRes 4444) on top of an MP4 using GPU acceleration.
    """
    import subprocess
    
    if not os.path.exists(base_video_path) or not os.path.exists(overlay_mov_path):
        raise FileNotFoundError("Base video or overlay MOV not found")

    # Try GPU (NVENC) first, fallback to CPU (libx264)
    for codec, args in [
        ('h264_nvenc', ['-preset', 'p4', '-rc:v', 'vbr', '-cq:v', '23']),
        ('libx264', ['-preset', 'fast', '-crf', '21'])
    ]:
        cmd = [
            'ffmpeg', '-y',
            '-i', base_video_path,
            '-i', overlay_mov_path,
            '-filter_complex', '[0:v][1:v]overlay=0:0',
            '-c:v', codec,
            *args,
            '-pix_fmt', 'yuv420p',
            '-c:a', 'copy',
            output_path
        ]
        
        try:
            logger.info(f"[Caption] Hybrid Compositing with {codec}: {' '.join(cmd)}")
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            return output_path
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else str(e)
            logger.warning(f"[Caption] Hybrid Compositing with {codec} failed: {error_msg}")
            if codec == 'libx264':
                raise RuntimeError(f"Failed to composite captions: {error_msg}")
    
    return output_path

