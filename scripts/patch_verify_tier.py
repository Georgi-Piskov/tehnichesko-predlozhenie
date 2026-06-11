# -*- coding: utf-8 -*-
"""Patch: Verify Access — добавя tier === 'business' към проверката."""
import json

p = r"E:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\00-orchestrator.json"
wf = json.load(open(p, encoding="utf-8"))
for n in wf["nodes"]:
    if n["name"] == "Verify Access":
        old = "var authorized = role === 'admin' || role === 'business';"
        new = ("var tier = (p && p.tier) ? String(p.tier) : '';\n"
               "var authorized = role === 'admin' || role === 'business' || tier === 'business';")
        assert old in n["parameters"]["jsCode"], "old string not found"
        n["parameters"]["jsCode"] = n["parameters"]["jsCode"].replace(old, new)
json.dump(wf, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
json.load(open(p, encoding="utf-8"))  # validate
print("OK")
