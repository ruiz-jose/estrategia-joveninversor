import urllib.request
import json
import xml.etree.ElementTree as ET

url = "https://www.youtube.com/youtubei/v1/player"
headers = {"Content-Type": "application/json"}
payload = {
    "videoId": "8TT49tYF0FQ",
    "context": {
        "client": {
            "clientName": "ANDROID",
            "clientVersion": "19.02.34"
        }
    }
}

req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), headers=headers)
try:
    with urllib.request.urlopen(req) as response:
        res_data = response.read().decode('utf-8')
        data = json.loads(res_data)
        
        video_details = data.get("videoDetails", {})
        print("TITLE:", video_details.get("title"))
        print("AUTHOR:", video_details.get("author"))
        print("DESCRIPTION:\n", video_details.get("shortDescription"))
        
        captions = data.get("captions", {}).get("playerCaptionsTracklistRenderer", {}).get("captionTracks", [])
        print("\nFound caption tracks:", len(captions))
        for c in captions:
            print("Language:", c.get("languageCode"), "Name:", c.get("name", {}).get("runs", [{}])[0].get("text"))
            base_url = c.get("baseUrl")
            if base_url:
                try:
                    with urllib.request.urlopen(base_url) as cap_res:
                        xml_content = cap_res.read().decode('utf-8')
                        root = ET.fromstring(xml_content)
                        full_transcript = []
                        for child in root.findall('text'):
                            full_transcript.append(child.text or "")
                        transcript_text = " ".join(full_transcript)
                        print("\nTRANSCRIPT PREVIEW (first 2000 chars):\n", transcript_text[:2000])
                        with open(r"C:\Users\Pc\.gemini\antigravity\scratch\transcript.txt", "w", encoding="utf-8") as tf:
                            tf.write(transcript_text)
                        print("Saved full transcript to scratch/transcript.txt")
                        break
                except Exception as ex:
                    print("Error fetching caption XML:", ex)

except Exception as e:
    print("Error querying InnerTube:", e)
