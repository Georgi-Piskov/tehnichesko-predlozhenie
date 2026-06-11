# -*- coding: utf-8 -*-
"""Фаза 2: CORS заключване на WF09 Status API — * → https://proceno.net."""
import json

p = r"E:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\09-status-api.json"
ORIGIN = "https://proceno.net"

wf = json.load(open(p, encoding="utf-8"))
changed = 0
for n in wf["nodes"]:
    params = n.get("parameters", {})
    entries = (params.get("options", {}).get("responseHeaders", {}) or {}).get("entries", [])
    for e in entries:
        if e.get("name") == "Access-Control-Allow-Origin" and e.get("value") == "*":
            e["value"] = ORIGIN
            changed += 1
            print(f"  {n['name']}: CORS -> {ORIGIN}")

json.dump(wf, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
json.load(open(p, encoding="utf-8"))  # validate
print(f"OK: {changed} headers updated")
