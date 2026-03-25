"""Fix remaining page limit issues found by full audit:
1. WF05 Prepare Section Prompt: estimated_pages || 5  →  || 8 (better fallback for large docs)
2. app.js: targetPages default 50 → 250
"""
import json

# ── Fix 1: WF05 ──
WF05 = 'n8n/workflows/05-write-section.json'
with open(WF05, 'r', encoding='utf-8') as f:
    wf = json.load(f)

for node in wf['nodes']:
    if node['name'] == 'Prepare Section Prompt':
        old = node['parameters']['jsCode']
        new = old.replace('estimated_pages || 5', 'estimated_pages || 8')
        if new != old:
            node['parameters']['jsCode'] = new
            print('✅ WF05 Prepare Section Prompt: estimated_pages || 5 → || 8')
        else:
            print('⚠️  WF05: pattern not found')

with open(WF05, 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)
with open(WF05, 'r', encoding='utf-8') as f:
    json.load(f)
print('   JSON valid ✓')

# ── Fix 2: app.js ──
APP_JS = 'js/app.js'
with open(APP_JS, 'r', encoding='utf-8') as f:
    content = f.read()

old_line = "targetPages: (tp >= 20 && tp <= 500) ? tp : 50"
new_line = "targetPages: (tp >= 20 && tp <= 500) ? tp : 250"

if old_line in content:
    content = content.replace(old_line, new_line)
    with open(APP_JS, 'w', encoding='utf-8') as f:
        f.write(content)
    print('✅ app.js: targetPages default 50 → 250')
else:
    print('⚠️  app.js: pattern not found')

print('\n✅ All fixes applied!')
