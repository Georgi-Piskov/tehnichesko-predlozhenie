"""
Fix targetPages transport:
- Read from ci (contractor JSON) instead of body (FormData field)
- contractor JSON is proven to work (visible in screenshot)
"""
import json

print("=== FIX: targetPages transport via contractor JSON ===\n")

with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    wf00 = json.load(f)

for node in wf00['nodes']:
    if node['name'] == 'Init Job':
        old = node['parameters']['jsCode']
        # Replace body.targetPages with ci.targetPages (contractor JSON has it now)
        new = old.replace(
            'targetPages: parseInt(body.targetPages) || 50,',
            'targetPages: parseInt(ci.targetPages) || 50,'
        )
        if new != old:
            node['parameters']['jsCode'] = new
            print("  Init Job: reads targetPages from ci (contractor JSON)")
        else:
            print("  Init Job: WARNING - pattern not found!")
            print("  Looking for 'body.targetPages'...")
            if 'body.targetPages' in old:
                print("  Found body.targetPages but exact pattern didn't match")
            else:
                print("  body.targetPages not found at all")

with open('n8n/workflows/00-orchestrator.json', 'w', encoding='utf-8') as f:
    json.dump(wf00, f, ensure_ascii=False, indent=2)

# Validate
with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
    # Verify the change
    for node in d['nodes']:
        if node['name'] == 'Init Job':
            code = node['parameters']['jsCode']
            if 'ci.targetPages' in code:
                print("  VERIFIED: ci.targetPages in Init Job code")
            else:
                print("  ERROR: ci.targetPages NOT found!")
    print(f"  00-orchestrator.json: valid, {len(d['nodes'])} nodes")

print("\nDone!")
