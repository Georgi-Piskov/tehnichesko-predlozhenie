# -*- coding: utf-8 -*-
"""Inspect: Pipeline Complete, Status: Complete, WF09 Store Status."""
import json

wf0 = json.load(open(r"E:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\00-orchestrator.json", encoding="utf-8"))
wf9 = json.load(open(r"E:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\09-status-api.json", encoding="utf-8"))

for n in wf0["nodes"]:
    if n["name"] in ("Pipeline Complete", "Status: Complete", "Assemble Document"):
        print("=" * 70)
        print(n["name"])
        print(json.dumps(n["parameters"], ensure_ascii=False)[:3000])

print("=" * 70)
print("WF0 connections of Pipeline Complete:", json.dumps(wf0["connections"].get("Pipeline Complete", {})))
print("WF0 connections TO Save to Google Drive: search...")
for src, c in wf0["connections"].items():
    for branch in c.get("main", []):
        for t in branch or []:
            if t["node"] == "Save to Google Drive":
                print("  from:", src)

print("=" * 70)
print("WF09 nodes:")
for n in wf9["nodes"]:
    print(" -", n["name"], "|", n["type"])
for n in wf9["nodes"]:
    if n["name"] == "Store Status":
        print("=" * 70)
        print("Store Status jsCode:")
        print(n["parameters"]["jsCode"][:2000])
print("=" * 70)
print("WF09 connections:", json.dumps(wf9["connections"], ensure_ascii=False)[:1500])
