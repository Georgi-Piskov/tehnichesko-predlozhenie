"""Fix hardcoded || 50 in Init Job and After Spec Analysis nodes."""
import json

FILEPATH = 'n8n/workflows/00-orchestrator.json'

with open(FILEPATH, 'r', encoding='utf-8') as f:
    wf = json.load(f)

fixes = 0
for node in wf['nodes']:
    if node['name'] == 'Init Job':
        old = node['parameters']['jsCode']
        # Fix: parseInt(ci.targetPages) || 50 → || 250
        new = old.replace('parseInt(ci.targetPages) || 50', 'parseInt(ci.targetPages) || 250')
        if new != old:
            node['parameters']['jsCode'] = new
            fixes += 1
            print('✅ Init Job: || 50 → || 250')
        else:
            print('⚠️ Init Job: pattern not found (already fixed?)')

    elif node['name'] == 'After Spec Analysis':
        old = node['parameters']['jsCode']
        # Fix: .json.targetPages || 50 → || 250
        new = old.replace('.json.targetPages || 50', '.json.targetPages || 250')
        if new != old:
            node['parameters']['jsCode'] = new
            fixes += 1
            print('✅ After Spec Analysis: || 50 → || 250')
        else:
            print('⚠️ After Spec Analysis: pattern not found (already fixed?)')

with open(FILEPATH, 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)

# Validate
with open(FILEPATH, 'r', encoding='utf-8') as f:
    json.load(f)
print(f'\n✅ {fixes} fixes applied, JSON valid')
