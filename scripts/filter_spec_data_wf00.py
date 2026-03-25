"""
Priority 3: Filter specData in WF00 Prep Write node by spec_data_to_use from the plan.

Instead of sending the FULL specData to WF05 for every section,
filter it to only include fields listed in chunk.spec_data_to_use.

This reduces token usage and focuses the writer on relevant data.
"""

import json

WF_PATH = 'n8n/workflows/00-orchestrator.json'

# --- New Prep Write code with specData filtering ---
NEW_PREP_WRITE = r"""var sd = $getWorkflowStaticData('global');
var prevCtx = sd.fullDoc || '';
if (prevCtx.length > 2000) prevCtx = prevCtx.substring(prevCtx.length - 2000);

// === Filter specData by spec_data_to_use from the plan ===
var fullSpec = $json.specData || {};
var fields = ($json.chunk && $json.chunk.spec_data_to_use) || [];
var filteredSpec = fullSpec;

if (fields.length > 0) {
  filteredSpec = {};
  for (var i = 0; i < fields.length; i++) {
    var key = fields[i].split('.')[0];
    if (fullSpec[key] !== undefined) {
      filteredSpec[key] = fullSpec[key];
    }
  }
  if (Object.keys(filteredSpec).length === 0) {
    filteredSpec = fullSpec;
  }
}

return [{ json: {
  section: $json.chunk,
  requirements: $json.requirements,
  specData: filteredSpec,
  contractorInfo: $json.contractorInfo,
  previousContext: prevCtx,
  feedback: '',
  procurementType: $json.procurementType,
  sectionIndex: $json.chunkIndex,
  totalSections: $json.totalChunks,
  writingRules: $json.writingRules || []
} }];"""

# --- Load, update, save ---
with open(WF_PATH, 'r', encoding='utf-8') as f:
    wf = json.load(f)

updated = False
for node in wf['nodes']:
    if node['name'] == 'Prep Write':
        old_code = node['parameters']['jsCode']
        node['parameters']['jsCode'] = NEW_PREP_WRITE
        updated = True
        print(f"✅ Updated 'Prep Write' node (n{node['id'][-2:] if isinstance(node['id'], str) else node['id']})")
        print(f"   Old code: {len(old_code)} chars")
        print(f"   New code: {len(NEW_PREP_WRITE)} chars")
        print(f"   Added: specData filtering by spec_data_to_use")
        break

if not updated:
    print("❌ 'Prep Write' node not found!")
    exit(1)

with open(WF_PATH, 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)

# Validate
with open(WF_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)
    # Verify the code is there
    for node in data['nodes']:
        if node['name'] == 'Prep Write':
            code = node['parameters']['jsCode']
            assert 'spec_data_to_use' in code, "spec_data_to_use not found in updated code!"
            assert 'filteredSpec' in code, "filteredSpec not found in updated code!"
            assert 'specData: filteredSpec' in code, "specData: filteredSpec not found!"
            print("✅ JSON valid, all assertions passed.")
            break
