"""Audit ALL workflow JSONs for hardcoded page limits."""
import json, re

WF_FILES = [
    'n8n/workflows/00-orchestrator.json',
    'n8n/workflows/04-plan-document.json',
    'n8n/workflows/05-write-section.json',
]

for wf_file in WF_FILES:
    with open(wf_file, 'r', encoding='utf-8') as f:
        wf = json.load(f)
    print(f'=== {wf_file} ===')
    found = False
    for node in wf['nodes']:
        code = node.get('parameters', {}).get('jsCode', '')
        if not code:
            continue
        name = node['name']
        # Check for || <number> defaults
        for m in re.finditer(r'\|\|\s*(\d+)', code):
            val = int(m.group(1))
            context = code[max(0, m.start()-30):m.end()+10]
            context = context.replace('\n', ' ').strip()
            if val in (40, 50, 60):
                print(f'  BAD  {name}: || {val}  -->  ...{context}...')
                found = True
            elif val == 250:
                print(f'  OK   {name}: || {val}')
        # Check targetPages references
        for m in re.finditer(r'targetPages[^\n]{0,60}', code):
            snippet = m.group(0).replace('\n', ' ').strip()
            if '50' in snippet or '40' in snippet or '60' in snippet:
                print(f'  BAD  {name}: {snippet}')
                found = True

    # Also check system messages in Agent nodes
    for node in wf['nodes']:
        sm = node.get('parameters', {}).get('options', {}).get('systemMessage', '')
        if sm:
            for m in re.finditer(r'(\d+)\s*(стр|pages|страниц)', sm):
                val = int(m.group(1))
                if val <= 60:
                    ctx = sm[max(0, m.start()-20):m.end()+20].replace('\n', ' ')
                    print(f'  CHECK {node["name"]}: {ctx}')

    if not found:
        print('  All clean!')
    print()
