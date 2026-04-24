"""
Analyzer — GPT-4 powered highlight detection from video transcripts
"""

import json
import re
from openai import OpenAI


def parse_srt(srt_path):
    """Parse SRT subtitle file into a single transcript with timestamps."""
    if not srt_path:
        return ""

    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse SRT blocks
    blocks = re.split(r'\n\n+', content.strip())
    lines = []

    for block in blocks:
        parts = block.strip().split('\n')
        if len(parts) >= 3:
            timestamp = parts[1]
            text = ' '.join(parts[2:]).strip()
            # Clean HTML tags
            text = re.sub(r'<[^>]+>', '', text)
            if text:
                # Extract start time
                start_match = re.match(r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})', timestamp)
                if start_match:
                    start = start_match.group(1).replace(',', '.')
                    lines.append(f"[{start}] {text}")

    return '\n'.join(lines)


# ─── System Prompt ────────────────────────────────────────────────────
# Separated from user prompt for better instruction following.
# Contains persona, hard rules, and output schema.
SYSTEM_PROMPT = """You are a world-class short-form content strategist who has edited for top YouTube creators.

HARD RULES:
1. Respond ONLY with a valid JSON array. No markdown fences, no explanation, no preamble.
2. Every string value (title, hook_text, description, tags) MUST be in the SAME language as the transcript. Never translate to English unless the transcript is already in English.
3. Timestamps MUST use HH:MM:SS.mmm format and MUST align to the nearest subtitle boundary shown in the transcript — never invent timestamps between existing ones.
4. Each clip MUST start at the beginning of a sentence and end at the end of a sentence. Never cut mid-sentence.
5. Clips MUST NOT overlap in time ranges."""


def analyze_highlights(transcript, config, progress_callback=None):
    """
    Use GPT-4 to find the most engaging highlights in a transcript.
    
    Args:
        transcript: Timestamped transcript string
        config: Dict with min_duration, max_duration
        progress_callback: Optional callback(step, message, progress)
    
    Returns:
        List of highlight dicts sorted by hook_score descending
    """
    if progress_callback:
        progress_callback('analyze', 'Analyzing transcript with AI...', 20)

    client = OpenAI()

    min_dur = config.get('min_duration', 30)
    max_dur = config.get('max_duration', 90)

    user_prompt = f"""Analyze the transcript below and extract ALL viral-worthy highlights.

QUALITY GATE:
- Do NOT force a specific number of clips.
- Only include clips with hook_score >= 75.
- A boring video should yield 1-2 clips. An exceptional video can yield up to 10.

CLIP CONSTRAINTS:
- Duration: {min_dur}-{max_dur} seconds per clip.
- No overlapping time ranges.
- Start at the beginning of a complete thought/sentence.
- End at a natural conclusion — never mid-sentence.

HOOK SCORE CRITERIA (score 1-100):
- How strong are the first 3 seconds? Would a viewer stop scrolling?
- Does it open with conflict, surprise, emotion, or a bold claim?
- Score 90+: instant attention grabber ("Wait, WHAT?!")
- Score 75-89: solid hook, clearly interesting
- Below 75: skip it, not viral-worthy

OUTPUT SCHEMA (JSON array):
[
  {{
    "start_time": "HH:MM:SS.mmm",
    "end_time": "HH:MM:SS.mmm",
    "title": "emoji + eye-catching title",
    "hook_text": "1-2 sentence attention hook",
    "hook_score": 85,
    "description": "short SEO description",
    "tags": ["tag1", "tag2", "tag3"]
  }}
]

TRANSCRIPT:
{transcript}"""

    ai_provider = config.get('ai_provider', 'gpt-5.4-mini')

    if ai_provider.startswith('gemini'):
        import google.generativeai as genai
        import os
        
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is missing. Please set it to use Gemini.")
            
        genai.configure(api_key=api_key)
        
        if progress_callback:
            progress_callback('analyze', 'Waiting for Gemini response...', 25)
            
        # Initialize Gemini model
        model_name = 'gemini-1.5-pro' if 'pro' in ai_provider else 'gemini-1.5-flash'
        model = genai.GenerativeModel(model_name, system_instruction=SYSTEM_PROMPT)
        
        generation_config = genai.GenerationConfig(
            temperature=0.7,
            max_output_tokens=8000,
        )
        
        response = model.generate_content(user_prompt, generation_config=generation_config)
        response_text = response.text.strip()
    else:
        client = OpenAI()

        if progress_callback:
            progress_callback('analyze', 'Waiting for OpenAI response...', 25)
            
        model_name = ai_provider if ai_provider.startswith('gpt') else 'gpt-5.4-mini'

        args = {
            "model": model_name,
            "messages": [
                {'role': 'system', 'content': SYSTEM_PROMPT},
                {'role': 'user', 'content': user_prompt}
            ]
        }
        
        # Reasoning models and newer GPTs use max_completion_tokens
        if '5.4' in model_name or 'o1' in model_name:
            args["max_completion_tokens"] = 8000
        else:
            args["temperature"] = 0.7
            args["max_tokens"] = 8000

        response = client.chat.completions.create(**args)

        response_text = response.choices[0].message.content.strip()

    # Clean response — remove markdown code fences if present
    response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
    response_text = re.sub(r'\s*```$', '', response_text)

    try:
        highlights = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f'Failed to parse AI response as JSON: {e}\nResponse: {response_text[:500]}')

    actual_timestamps = _extract_timestamps(transcript)

    # Validate, snap, de-overlap, and sort
    valid_highlights = []
    for h in highlights:
        if not all(k in h for k in ('start_time', 'end_time', 'title')):
            continue
            
        # Snap: start snaps BACKWARD, end snaps FORWARD
        h['start_time'] = _snap_to_closest(h['start_time'], actual_timestamps, direction='backward')
        h['end_time'] = _snap_to_closest(h['end_time'], actual_timestamps, direction='forward')
        
        # Calculate duration
        start_sec = timestamp_to_seconds(h['start_time'])
        end_sec = timestamp_to_seconds(h['end_time'])
        duration = end_sec - start_sec

        if duration < min_dur * 0.8 or duration > max_dur * 1.2:
            print(f"[Analyzer] Skipping clip '{h.get('title', '?')}': duration {duration:.1f}s out of range [{min_dur*0.8:.0f}-{max_dur*1.2:.0f}]")
            continue
        
        h['duration_seconds'] = round(duration, 1)
        h.setdefault('hook_text', h['title'])
        h.setdefault('hook_score', 80)
        h.setdefault('description', '')
        h.setdefault('tags', ['shorts', 'viral'])
        valid_highlights.append(h)

    # Remove overlapping clips (keep higher hook_score)
    valid_highlights = _remove_overlaps(valid_highlights)
    
    # Sort by hook_score descending — best clips first
    valid_highlights.sort(key=lambda x: x.get('hook_score', 0), reverse=True)

    if progress_callback:
        progress_callback('analyze', f'Found {len(valid_highlights)} highlights!', 30)

    return valid_highlights


# ─── Helpers ──────────────────────────────────────────────────────────

from core.utils import timestamp_to_seconds


def _extract_timestamps(transcript_text):
    """Extract all [HH:MM:SS.mmm] timestamps from a transcript."""
    return re.findall(r'\[(\d{2}:\d{2}:\d{2}[\.,]\d{3})\]', transcript_text)


def _snap_to_closest(target_ts_str, valid_ts_list, direction='nearest'):
    """
    Snap a timestamp to the closest valid transcript boundary.
    
    Args:
        target_ts_str: The AI-generated timestamp string
        valid_ts_list: List of actual timestamps from the transcript
        direction: 'backward' (snap to <=), 'forward' (snap to >=), or 'nearest'
    """
    if not valid_ts_list or not target_ts_str:
        return target_ts_str
        
    try:
        target_sec = timestamp_to_seconds(target_ts_str)
        valid_pairs = [(ts, timestamp_to_seconds(ts)) for ts in valid_ts_list]
        
        if direction == 'backward':
            # Find the closest timestamp that is <= target
            candidates = [(ts, sec) for ts, sec in valid_pairs if sec <= target_sec]
            if not candidates:
                candidates = valid_pairs  # fallback to nearest
        elif direction == 'forward':
            # Find the closest timestamp that is >= target
            candidates = [(ts, sec) for ts, sec in valid_pairs if sec >= target_sec]
            if not candidates:
                candidates = valid_pairs  # fallback to nearest
        else:
            candidates = valid_pairs
        
        closest_ts = target_ts_str
        min_diff = float('inf')
        
        for ts, sec in candidates:
            diff = abs(target_sec - sec)
            if diff < min_diff:
                min_diff = diff
                closest_ts = ts
                
        if 0.01 < min_diff < 5.0:
            print(f"[Analyzer] Snapped {target_ts_str} -> {closest_ts} ({direction}, diff {min_diff:.2f}s)")
            return closest_ts
        elif min_diff <= 0.01:
            return closest_ts  # Exact match
            
        return target_ts_str
    except Exception as e:
        print(f"[Analyzer] Warning: Snapping failed for {target_ts_str}: {e}")
        return target_ts_str


def _remove_overlaps(highlights):
    """Remove overlapping clips, keeping the one with higher hook_score."""
    if not highlights:
        return highlights
    
    # Sort by start time first
    sorted_hl = sorted(highlights, key=lambda h: timestamp_to_seconds(h['start_time']))
    
    result = [sorted_hl[0]]
    for current in sorted_hl[1:]:
        prev = result[-1]
        prev_end = timestamp_to_seconds(prev['end_time'])
        curr_start = timestamp_to_seconds(current['start_time'])
        
        if curr_start < prev_end:
            # Overlap detected — keep the one with higher hook_score
            if current.get('hook_score', 0) > prev.get('hook_score', 0):
                print(f"[Analyzer] Overlap: keeping '{current['title']}' (score {current.get('hook_score')}) over '{prev['title']}' (score {prev.get('hook_score')})")
                result[-1] = current
            else:
                print(f"[Analyzer] Overlap: keeping '{prev['title']}' (score {prev.get('hook_score')}) over '{current['title']}' (score {current.get('hook_score')})")
        else:
            result.append(current)
    
    return result


def regenerate_clip_metadata(transcript_snippet, old_metadata, config=None):
    """
    Use GPT-4 or Gemini to regenerate metadata (title, hook, description, tags) for a specific clip's transcript.
    """
    config = config or {}
    ai_provider = config.get('ai_provider', 'gpt-5.4-mini')

    prompt = f"""You are an expert content editor specializing in viral short-form video content.

Rewrite the metadata for this specific short video clip to make it more engaging, viral, and click-worthy.
This is the spoken transcript for the clip:
"{transcript_snippet}"

Context - the PREVIOUS metadata we generated was:
Title: {old_metadata.get('title', '')}
Hook: {old_metadata.get('hook_text', '')}
Description: {old_metadata.get('description', '')}
Tags: {', '.join(old_metadata.get('tags', []))}

Generate a completely new set of metadata for this exact segment.

Provide:
1. **title** — eye-catching title with emoji (for YouTube Shorts/TikTok)
2. **hook_text** — attention-grabbing 1-2 sentence hook (read aloud at the start)
3. **description** — short SEO description
4. **tags** — array of relevant hashtags (without #)

IMPORTANT: The `title`, `hook_text`, `description`, and `tags` MUST be written in the exact same language as the spoken language in the transcript. Do NOT translate them to English if the transcript is in Indonesian or another language.

Respond ONLY with a valid JSON object matching the format below. No markdown, no explanation.

Example format:
{{
  "title": "🔥 The Secret Nobody Talks About",
  "hook_text": "You won't believe what happens next...",
  "description": "An incredible moment that changes everything",
  "tags": ["viral", "podcast", "motivation"]
}}
"""

    if ai_provider.startswith('gemini'):
        import google.generativeai as genai
        import os
        
        api_key = os.environ.get('GEMINI_API_KEY')
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY environment variable is missing. Please set it to use Gemini.")
            
        genai.configure(api_key=api_key)
        model_name = 'gemini-1.5-pro' if 'pro' in ai_provider else 'gemini-1.5-flash'
        model = genai.GenerativeModel(model_name, system_instruction='You are a viral content expert. Always respond with a valid JSON object only.')
        
        generation_config = genai.GenerationConfig(
            temperature=0.8,
            max_output_tokens=1000,
        )
        response = model.generate_content(prompt, generation_config=generation_config)
        response_text = response.text.strip()
    else:
        client = OpenAI()
        model_name = ai_provider if ai_provider.startswith('gpt') else 'gpt-5.4-mini'
        
        args = {
            "model": model_name,
            "messages": [
                {'role': 'system', 'content': 'You are a viral content expert. Always respond with a valid JSON object only.'},
                {'role': 'user', 'content': prompt}
            ]
        }

        if '5.4' in model_name or 'o1' in model_name:
            args["max_completion_tokens"] = 1000
        else:
            args["temperature"] = 0.8
            args["max_tokens"] = 1000

        response = client.chat.completions.create(**args)
        response_text = response.choices[0].message.content.strip()

    # Clean response
    response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
    response_text = re.sub(r'\s*```$', '', response_text)

    try:
        new_meta = json.loads(response_text)
    except json.JSONDecodeError as e:
        raise RuntimeError(f'Failed to parse AI response as JSON: {e}\nResponse: {response_text[:500]}')

    # Update original dict with new values
    old_metadata['title'] = new_meta.get('title', old_metadata.get('title'))
    old_metadata['hook_text'] = new_meta.get('hook_text', old_metadata.get('hook_text'))
    old_metadata['description'] = new_meta.get('description', old_metadata.get('description'))
    old_metadata['tags'] = new_meta.get('tags', old_metadata.get('tags'))

    return old_metadata
