import re
import json

filepath = r"C:\Users\Pc\.gemini\antigravity\brain\0a3bd275-fcb4-45be-ac32-7c8c3cbe82da\.system_generated\steps\6\content.md"

with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
    text = f.read()

print("File size:", len(text))

# Search for shortDescription
desc_match = re.search(r'"shortDescription":"(.*?)"', text)
if desc_match:
    print("DESCRIPTION:\n", desc_match.group(1).replace("\\n", "\n"))
else:
    print("No shortDescription found")

# Search for caption tracks
caption_match = re.search(r'"captionTracks":(\[.*?\])', text)
if caption_match:
    print("CAPTION TRACKS:\n", caption_match.group(1))
    try:
        tracks = json.loads(caption_match.group(1))
        for t in tracks:
            print("Track URL:", t.get("baseUrl"))
    except Exception as e:
        print("JSON parse error:", e)
else:
    print("No captionTracks found")
