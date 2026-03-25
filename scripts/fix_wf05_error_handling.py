"""
Fix WF05: Add onError and retryOnFail to chainLlm node so errors produce valid JSON.

Problem: When the LLM API fails (timeout, token limit, etc.), WF05 crashes and 
returns HTML error page instead of JSON. WF00 gets "Invalid JSON in response body".

Fix: Add onError: "continueRegularOutput" so errors pass to Format Output code node,
which already has error handling logic that returns a proper JSON error response.
Also add retryOnFail with 2 attempts.
"""

import json

WF_PATH = 'n8n/workflows/05-write-section.json'

with open(WF_PATH, 'r', encoding='utf-8') as f:
    wf = json.load(f)

for node in wf['nodes']:
    if node['name'] == 'Write Section':
        node['onError'] = 'continueRegularOutput'
        node['retryOnFail'] = True
        node['maxTries'] = 2
        node['waitBetweenTries'] = 10000  # 10 sec
        print(f"✅ Write Section: added onError=continueRegularOutput, retryOnFail=true (2 tries, 10s wait)")
        print(f"   Type: {node['type']}, version: {node.get('typeVersion')}")

with open(WF_PATH, 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)

# Validate
with open(WF_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)
    for node in data['nodes']:
        if node['name'] == 'Write Section':
            assert node['onError'] == 'continueRegularOutput'
            assert node['retryOnFail'] == True
            assert node['maxTries'] == 2
            print("✅ Verified: all error handling fields present")
            break

print("✅ JSON valid, saved.")
