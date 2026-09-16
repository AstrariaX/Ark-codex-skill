import json
import re
import urllib.request
import urllib.parse


def fetch_prts_lines(operator_name):
    candidates = [operator_name]
    if "-" in operator_name:
        candidates.append(operator_name.split("-")[0])
    for name in candidates:
        page = urllib.parse.quote(f"{name}/语音记录")
        url = f"https://prts.wiki/api.php?action=parse&page={page}&prop=wikitext&format=json"
        try:
            resp = urllib.request.urlopen(url, timeout=10)
            data = json.loads(resp.read().decode("utf-8"))
        except Exception:
            continue
        text = data.get("parse", {}).get("wikitext", {}).get("*", "")
        if not text or "VoiceData" not in text:
            continue
        raw = re.findall(r"VoiceData/word\|中文\|(.*?)\}\}", text)
        results = []
        for line in raw:
            clean = re.sub(r"\{\{DrName[^}]*\}\}", "{博士}", line)
            clean = re.sub(r"\{\{DrName[^}]*$", "{博士}", clean)
            clean = clean.strip()
            if clean:
                results.append(clean)
        if results:
            return results
    return []
