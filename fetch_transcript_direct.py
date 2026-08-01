import urllib.request
import json
import re

url = "https://www.youtube.com/watch?v=8TT49tYF0FQ"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "Accept-Language": "es-ES,es;q=0.9"})
try:
    html = urllib.request.urlopen(req).read().decode('utf-8', errors='ignore')
    print("Fetched HTML length:", len(html))
    
    # Try finding captionTracks
    match = re.search(r'"captionTracks":\s*(\[.*?\])', html)
    if match:
        captions = json.loads(match.group(1))
        print("Captions found:", len(captions))
        for c in captions:
            print("Lang:", c.get("languageCode"), c.get("baseUrl"))
            cap_url = c.get("baseUrl")
            if cap_url:
                cap_req = urllib.request.Request(cap_url, headers={"User-Agent": "Mozilla/5.0"})
                cap_xml = urllib.request.urlopen(cap_req).read().decode('utf-8', errors='ignore')
                texts = re.findall(r'<text[^>]*>(.*?)</text>', cap_xml)
                clean_texts = [re.sub(r'&amp;#39;', "'", re.sub(r'&quot;', '"', t)) for t in texts]
                full_text = " ".join(clean_texts)
                print("Transcript length:", len(full_text))
                print("PREVIEW:", full_text[:1500])
                with open(r"C:\Users\Pc\.gemini\antigravity\scratch\transcript_full.txt", "w", encoding="utf-8") as f:
                    f.write(full_text)
                break
    else:
        print("No captionTracks found in watch HTML")
except Exception as e:
    print("Error:", e)
