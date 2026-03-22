"""
Fix WF04 timeout:
1. WF00 "Plan Document" HTTP node - increase timeout 180s -> 600s
2. WF00 "After Spec Analysis" - reduce documentationText from 60K to 40K
3. Also increase timeout for Analyze Spec node if it exists
"""
import json

print("=== FIX: WF00 Timeouts + Text Size ===")

with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    wf00 = json.load(f)

for node in wf00['nodes']:
    # Fix 1: Plan Document timeout
    if node['name'] == 'Plan Document':
        old_timeout = node['parameters'].get('options', {}).get('timeout', 'not set')
        node['parameters']['options'] = node['parameters'].get('options', {})
        node['parameters']['options']['timeout'] = 600000  # 10 minutes
        print(f"  Plan Document timeout: {old_timeout} -> 600000")

    # Fix 2: Analyze Spec timeout (same issue could happen)
    if node['name'] == 'Analyze Spec':
        old_timeout = node['parameters'].get('options', {}).get('timeout', 'not set')
        node['parameters']['options'] = node['parameters'].get('options', {})
        node['parameters']['options']['timeout'] = 600000
        print(f"  Analyze Spec timeout: {old_timeout} -> 600000")

    # Fix 3: Extract Requirements timeout
    if node['name'] == 'Extract Requirements':
        old_timeout = node['parameters'].get('options', {}).get('timeout', 'not set')
        node['parameters']['options'] = node['parameters'].get('options', {})
        node['parameters']['options']['timeout'] = 600000
        print(f"  Extract Requirements timeout: {old_timeout} -> 600000")

    # Fix 4: Write Section timeout
    if node['name'] == 'Write Section':
        old_timeout = node['parameters'].get('options', {}).get('timeout', 'not set')
        node['parameters']['options'] = node['parameters'].get('options', {})
        node['parameters']['options']['timeout'] = 600000
        print(f"  Write Section timeout: {old_timeout} -> 600000")

    # Fix 5: Validate Section timeout
    if node['name'] == 'Validate Section':
        old_timeout = node['parameters'].get('options', {}).get('timeout', 'not set')
        node['parameters']['options'] = node['parameters'].get('options', {})
        node['parameters']['options']['timeout'] = 600000
        print(f"  Validate Section timeout: {old_timeout} -> 600000")

    # Fix 6: Reduce documentationText from 60K to 40K
    if node['name'] == 'After Spec Analysis':
        old_code = node['parameters']['jsCode']
        new_code = old_code.replace('.substring(0, 60000)', '.substring(0, 40000)')
        if new_code != old_code:
            node['parameters']['jsCode'] = new_code
            print(f"  After Spec Analysis: documentationText 60K -> 40K")
        else:
            print(f"  After Spec Analysis: no 60000 found, checking...")
            print(f"  Code: {old_code[:200]}")

with open('n8n/workflows/00-orchestrator.json', 'w', encoding='utf-8') as f:
    json.dump(wf00, f, ensure_ascii=False, indent=2)

# Also reduce in WF04 Prepare Plan Prompt
with open('n8n/workflows/04-plan-document.json', 'r', encoding='utf-8') as f:
    wf04 = json.load(f)

for node in wf04['nodes']:
    if node['name'] == 'Prepare Plan Prompt':
        old_code = node['parameters']['jsCode']
        new_code = old_code.replace('.substring(0, 60000)', '.substring(0, 40000)')
        if new_code != old_code:
            node['parameters']['jsCode'] = new_code
            print(f"  WF04 Prepare Plan Prompt: documentationText 60K -> 40K")

with open('n8n/workflows/04-plan-document.json', 'w', encoding='utf-8') as f:
    json.dump(wf04, f, ensure_ascii=False, indent=2)

# Validate
for fname in ['00-orchestrator.json', '04-plan-document.json']:
    with open(f'n8n/workflows/{fname}', 'r', encoding='utf-8') as f:
        d = json.load(f)
    print(f"  {fname}: valid, {len(d['nodes'])} nodes")

print("\nDone!")
