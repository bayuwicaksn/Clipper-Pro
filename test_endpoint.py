import requests
import json

url = "http://localhost:5000/api/caption_composition/b4513ed7"
payload = {
    "transcript": [{"word": "test", "start": 0.5, "end": 1.0}],
    "caption_settings": {"presetId": "default", "fontSize": 100},
    "aspect_ratio": "9:16"
}

resp = requests.post(url, json=payload)
print(f"Status: {resp.status_code}")
if resp.status_code != 200:
    print(f"Body: {resp.text}")
else:
    print(f"Content-Type: {resp.headers.get('content-type')}")
    print(f"Body starts with: {resp.text[:100]}")
