"""Fix WF04 Code Tool node — change typeVersion from 2 to 1 for n8n v2.0.2 compatibility."""

import json

WF_PATH = 'n8n/workflows/04-plan-document.json'

with open(WF_PATH, 'r', encoding='utf-8') as f:
    wf = json.load(f)

for node in wf['nodes']:
    if node['name'] == 'Analyze Spec Tool':
        old_ver = node.get('typeVersion')
        node['typeVersion'] = 1
        print(f"✅ Fixed typeVersion: {old_ver} → 1")
        print(f"   Type: {node['type']}")
        print(f"   Params: {list(node['parameters'].keys())}")

with open(WF_PATH, 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)

# Validate
with open(WF_PATH, 'r', encoding='utf-8') as f:
    json.load(f)

print("✅ JSON valid, saved.")
