"""Temporary fix script — repairs mangled line in app.py"""
import os

filepath = os.path.join(os.path.dirname(__file__), 'app.py')

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Find and replace the mangled line (line 1188, 0-indexed 1187)
fixed = []
for i, line in enumerate(lines):
    if 'Whisper failed' in line and '\\n' in line:
        # This is the mangled line - replace with proper multi-line code
        fixed.append('            print(f"[TRANSCRIPT] Whisper failed: {e}")\n')
        fixed.append('            words = None\n')
        fixed.append('    \n')
        fixed.append('    if not words:\n')
        fixed.append('        raise FileNotFoundError("Whisper STT failed. Ensure source video exists and OpenAI API key is set.")\n')
        print(f"Fixed mangled line {i+1}")
    else:
        fixed.append(line)

with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(fixed)

print(f"Done. Total lines: {len(fixed)}")
