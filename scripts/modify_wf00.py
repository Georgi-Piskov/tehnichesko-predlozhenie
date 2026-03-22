"""
Modify WF00 Orchestrator — pass writingRules through the pipeline.

Changes:
1. Flatten Chunks — extract writing_rules from plan, include in each chunk
2. Prep Write — pass writingRules to WF05
3. Prep Validate — pass writingRules to WF06
4. Prep Rewrite — pass writingRules to retry WF05
"""
import json

FILE = r"e:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\00-orchestrator.json"

# ─── NEW Flatten Chunks jsCode ───
NEW_FLATTEN = r"""var plan = $json.documentPlan;
var reqs = $('Extract Requirements').first().json.requirements || $('Extract Requirements').first().json;
var spec = $('Analyze Spec').first().json.specData || $('Analyze Spec').first().json;
var ci = $('Init Job').first().json.contractorInfo || {};
var pt = (reqs && reqs.procurement_type) || 'unknown';
var sections = (plan && plan.sections) || [];
var writingRules = (plan && plan.writing_rules) || [];
if (sections.length === 0) throw new Error('Plan has no sections');

var sd = $getWorkflowStaticData('global');
sd.fullDoc = '# ' + (plan.document_title || 'ТЕХНИЧЕСКО ПРЕДЛОЖЕНИЕ') + '\n\n';
sd.lastParent = '';
sd.results = [];

function flattenSubs(subs, parentId, parentTitle, reqId) {
  var result = [];
  for (var j = 0; j < subs.length; j++) {
    var sub = subs[j];
    var chunk = {
      id: sub.id, title: sub.title,
      parentId: parentId, parentTitle: parentTitle,
      estimated_pages: sub.estimated_pages || 4,
      content_guidance: sub.content_guidance || [],
      spec_data_to_use: sub.spec_data_to_use || [],
      tables_needed: sub.tables_needed || [],
      requirement_id: sub.requirement_id || reqId
    };
    if (sub.subsections && sub.subsections.length > 0) {
      var nested = flattenSubs(sub.subsections, sub.id, sub.title, sub.requirement_id || reqId);
      for (var n = 0; n < nested.length; n++) result.push(nested[n]);
    } else {
      result.push(chunk);
    }
  }
  return result;
}

var chunks = [];
for (var s = 0; s < sections.length; s++) {
  var sec = sections[s];
  var subs = sec.subsections || [];
  if (subs.length === 0) {
    chunks.push({
      id: sec.id, title: sec.title, parentId: null, parentTitle: null,
      estimated_pages: sec.estimated_pages || 5,
      content_guidance: sec.content_guidance || [],
      spec_data_to_use: sec.spec_data_to_use || [],
      tables_needed: sec.tables_needed || [],
      requirement_id: sec.requirement_id
    });
  } else {
    var flat = flattenSubs(subs, sec.id, sec.title, sec.requirement_id);
    for (var f = 0; f < flat.length; f++) chunks.push(flat[f]);
  }
}

var items = [];
for (var i = 0; i < chunks.length; i++) {
  items.push({
    json: {
      chunk: chunks[i],
      chunkIndex: i,
      totalChunks: chunks.length,
      requirements: reqs,
      specData: spec,
      contractorInfo: ci,
      procurementType: pt,
      writingRules: writingRules
    }
  });
}
return items;"""

# ─── NEW Prep Write jsCode ───
NEW_PREP_WRITE = r"""var sd = $getWorkflowStaticData('global');
var prevCtx = sd.fullDoc || '';
if (prevCtx.length > 2000) prevCtx = prevCtx.substring(prevCtx.length - 2000);

return [{ json: {
  section: $json.chunk,
  requirements: $json.requirements,
  specData: $json.specData,
  contractorInfo: $json.contractorInfo,
  previousContext: prevCtx,
  feedback: '',
  procurementType: $json.procurementType,
  sectionIndex: $json.chunkIndex,
  totalSections: $json.totalChunks,
  writingRules: $json.writingRules || []
} }];"""

# ─── NEW Prep Validate jsCode ───
NEW_PREP_VALIDATE = r"""var pw = $('Prep Write').first().json;
return [{ json: {
  sectionText: $json.sectionText || $json.text || '',
  section: pw.section,
  requirements: pw.requirements,
  procurementType: pw.procurementType,
  writingRules: pw.writingRules || []
} }];"""

# ─── NEW Prep Rewrite jsCode ───
NEW_PREP_REWRITE = r"""var sd = $getWorkflowStaticData('global');
var pw = $('Prep Write').first().json;
var valResult = $json;
var prevCtx = sd.fullDoc || '';
if (prevCtx.length > 2000) prevCtx = prevCtx.substring(prevCtx.length - 2000);

var fb = valResult.feedback || '';
if (valResult.issues && Array.isArray(valResult.issues)) {
  fb += '\n\nКонкретни проблеми:\n';
  for (var i = 0; i < valResult.issues.length; i++) {
    fb += '- ' + valResult.issues[i] + '\n';
  }
}

return [{ json: {
  section: pw.section,
  requirements: pw.requirements,
  specData: pw.specData,
  contractorInfo: pw.contractorInfo,
  previousContext: prevCtx,
  feedback: fb,
  procurementType: pw.procurementType,
  sectionIndex: pw.sectionIndex,
  totalSections: pw.totalSections,
  writingRules: pw.writingRules || []
} }];"""

# ─── Apply changes ───
with open(FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

updates = {
    'Flatten Chunks': NEW_FLATTEN,
    'Prep Write': NEW_PREP_WRITE,
    'Prep Validate': NEW_PREP_VALIDATE,
    'Prep Rewrite': NEW_PREP_REWRITE,
}

for node in data['nodes']:
    name = node.get('name', '')
    if name in updates and node.get('type') == 'n8n-nodes-base.code':
        old = node['parameters']['jsCode']
        node['parameters']['jsCode'] = updates[name]
        print(f"  Updated '{name}': {len(old)} -> {len(updates[name])} chars")

with open(FILE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

with open(FILE, 'r', encoding='utf-8') as f:
    json.load(f)
print("JSON valid. WF00 orchestrator updated.")
