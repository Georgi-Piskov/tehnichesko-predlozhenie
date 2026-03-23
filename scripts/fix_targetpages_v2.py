"""
Fix the ACTUAL broken link: After Spec Analysis doesn't pass targetPages.
This is the node whose output gets sent to WF04 via HTTP.
"""
import json

print("=== FIX: After Spec Analysis must pass targetPages ===\n")

with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    wf00 = json.load(f)

for node in wf00['nodes']:
    if node['name'] == 'After Spec Analysis':
        old_code = node['parameters']['jsCode']
        print("BEFORE:")
        print(old_code)
        print()
        
        # The return object ends with:
        #   documentationText: !extractionOk ? rawText.substring(0, 40000) : ''
        # We need to add targetPages AFTER that line
        
        old_line = "documentationText: !extractionOk ? rawText.substring(0, 40000) : ''"
        new_line = "documentationText: !extractionOk ? rawText.substring(0, 40000) : '',\n  targetPages: $('Init Job').first().json.targetPages || 50"
        
        new_code = old_code.replace(old_line, new_line)
        
        if new_code == old_code:
            print("ERROR: replacement pattern not found!")
            # Try to find what's actually there
            if 'documentationText' in old_code:
                idx = old_code.index('documentationText')
                print(f"Found documentationText at position {idx}")
                print(f"Context: ...{old_code[idx:idx+100]}...")
        else:
            node['parameters']['jsCode'] = new_code
            print("AFTER:")
            print(new_code)
            print("\nSUCCESS: targetPages added to After Spec Analysis output")

with open('n8n/workflows/00-orchestrator.json', 'w', encoding='utf-8') as f:
    json.dump(wf00, f, ensure_ascii=False, indent=2)

# VERIFY the entire chain
print("\n=== VERIFICATION ===")
with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    d = json.load(f)

checks = {
    'Init Job': False,
    'After Spec Analysis': False,
    'Flatten Chunks': False,
}

for node in d['nodes']:
    code = node['parameters'].get('jsCode', '')
    
    if node['name'] == 'Init Job':
        if 'ci.targetPages' in code:
            checks['Init Job'] = True
            print("  ✓ Init Job: reads ci.targetPages from contractor JSON")
        else:
            print("  ✗ Init Job: MISSING ci.targetPages!")
    
    if node['name'] == 'After Spec Analysis':
        if "targetPages" in code and "Init Job" in code:
            checks['After Spec Analysis'] = True
            print("  ✓ After Spec Analysis: passes targetPages from Init Job")
        else:
            print("  ✗ After Spec Analysis: MISSING targetPages!")
    
    if node['name'] == 'Flatten Chunks':
        if "targetPages" in code:
            checks['Flatten Chunks'] = True
            print("  ✓ Flatten Chunks: passes targetPages to chunks")
        else:
            print("  ✗ Flatten Chunks: MISSING targetPages!")
    
    if node['name'] == 'Plan Document' and node['type'] == 'n8n-nodes-base.httpRequest':
        body = node['parameters'].get('jsonBody', '')
        if 'After Spec Analysis' in body:
            print("  ✓ Plan Document HTTP: sends After Spec Analysis output (which now has targetPages)")
        else:
            print(f"  ? Plan Document HTTP body: {body[:100]}")

# Check WF04
with open('n8n/workflows/04-plan-document.json', 'r', encoding='utf-8') as f:
    wf04 = json.load(f)

for node in wf04['nodes']:
    if node['name'] == 'Prepare Plan Prompt':
        code = node['parameters']['jsCode']
        if 'body.targetPages' in code:
            print("  ✓ WF04 Prepare Plan Prompt: reads body.targetPages")
        else:
            print("  ✗ WF04 Prepare Plan Prompt: MISSING body.targetPages!")
        if 'total_estimated_pages' in code and 'targetPages' in code:
            # Check it's not hardcoded 40
            if "'  \"total_estimated_pages\": 40" not in code:
                print("  ✓ WF04: total_estimated_pages uses targetPages (not hardcoded)")
            else:
                print("  ✗ WF04: total_estimated_pages is STILL hardcoded to 40!")

all_ok = all(checks.values())
print(f"\n{'ALL CHECKS PASSED ✓' if all_ok else 'SOME CHECKS FAILED ✗'}")
print(f"  00-orchestrator.json: valid, {len(d['nodes'])} nodes")
