# -*- coding: utf-8 -*-
"""Fix: HTTP timeout 10 мин е по-кратък от реалното време на WF04 (10-13+ мин)
→ orchestrator retry-ва успешни стъпки. Вдигаме на 25 мин за всички pipeline ноди."""
import json

p = r"E:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\00-orchestrator.json"
NEW_TIMEOUT = 1500000  # 25 мин

wf = json.load(open(p, encoding="utf-8"))
changed = []
for n in wf["nodes"]:
    opts = n.get("parameters", {}).get("options", {})
    if opts.get("timeout") == 600000:
        opts["timeout"] = NEW_TIMEOUT
        changed.append(n["name"])

json.dump(wf, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
json.load(open(p, encoding="utf-8"))
print("Updated to 25 min:", changed)
