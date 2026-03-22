"""
Fix 3 problems in the requirements data flow:
1. WF00 "After Spec Analysis" - use fullText instead of documentationText (which is empty)
2. WF02 "Prepare Data" - try specificationText when documentationText is empty
3. WF04 "Parse Plan" - add fixNewlines + repairTruncated (same as WF02 fix)
"""
import json
import sys

ROBUST_PARSE_CODE = r"""var raw = ($json.text || $json.response || '').trim();
var result = null;

function sanitize(s) {
  return s.replace(/[\u201C\u201D\u201E\u201F\u00AB\u00BB\u2018\u2019\u2032\u2033]/g, "'");
}

function tryParse(s) {
  try { return JSON.parse(s); } catch(e) { return null; }
}

function extractJson(s) {
  var m = s.match(/```(?:json)?\s*([\s\S]*?)```/);
  var c = m ? m[1].trim() : s;
  var start = c.indexOf('{');
  var end = c.lastIndexOf('}');
  if (start === -1 || end === -1) return s;
  return c.substring(start, end + 1);
}

function fixCommon(s) {
  return s.replace(/,\s*([\]\}])/g, '$1');
}

function fixNewlines(s) {
  var out = '';
  var inStr = false;
  var escaped = false;
  for (var i = 0; i < s.length; i++) {
    var ch = s[i];
    if (escaped) { out += ch; escaped = false; continue; }
    if (ch === '\\') { out += ch; escaped = true; continue; }
    if (ch === '"') { inStr = !inStr; out += ch; continue; }
    if (inStr && ch === '\n') { out += '\\n'; continue; }
    if (inStr && ch === '\r') { continue; }
    if (inStr && ch === '\t') { out += '\\t'; continue; }
    out += ch;
  }
  return out;
}

function fixQuotes(s) {
  var out = '';
  var inStr = false;
  var escaped = false;
  for (var i = 0; i < s.length; i++) {
    var ch = s[i];
    if (escaped) { out += ch; escaped = false; continue; }
    if (ch === '\\') { out += ch; escaped = true; continue; }
    if (ch === '"') {
      if (!inStr) {
        inStr = true;
        out += ch;
      } else {
        var rest = s.substring(i + 1).trimStart();
        var next = rest.length > 0 ? rest[0] : '';
        if (next === ':' || next === ',' || next === '}' || next === ']' || rest.length === 0) {
          inStr = false;
          out += ch;
        } else {
          out += '\\"';
        }
      }
    } else {
      out += ch;
    }
  }
  return out;
}

function repairTruncated(s) {
  var stack = [];
  var inStr = false;
  var escaped = false;
  for (var i = 0; i < s.length; i++) {
    var ch = s[i];
    if (escaped) { escaped = false; continue; }
    if (ch === '\\') { escaped = true; continue; }
    if (ch === '"') { inStr = !inStr; continue; }
    if (inStr) continue;
    if (ch === '{') stack.push('}');
    else if (ch === '[') stack.push(']');
    else if (ch === '}' || ch === ']') { if (stack.length > 0) stack.pop(); }
  }
  if (inStr) s += '"';
  s = s.replace(/,\s*$/, '');
  while (stack.length > 0) s += stack.pop();
  return s;
}

raw = sanitize(raw);

result = tryParse(raw);

if (!result) {
  result = tryParse(fixCommon(extractJson(raw)));
}

if (!result) {
  result = tryParse(fixNewlines(fixCommon(extractJson(raw))));
}

if (!result) {
  result = tryParse(fixQuotes(fixNewlines(fixCommon(extractJson(raw)))));
}

if (!result) {
  var repaired = repairTruncated(fixNewlines(fixCommon(extractJson(raw))));
  result = tryParse(repaired);
  if (!result) result = tryParse(fixQuotes(repaired));
}"""


# ============================================================
# FIX 1: WF00 "After Spec Analysis" - use fullText instead of documentationText
# ============================================================
print("=== FIX 1: WF00 After Spec Analysis ===")

with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    wf00 = json.load(f)

NEW_AFTER_SPEC = (
    "var reqNode = $('Extract Requirements').first().json;\n"
    "var reqs = reqNode.requirements;\n"
    "var extractionOk = reqs && Array.isArray(reqs) && reqs.length > 0 && !reqNode._parse_error;\n"
    "var mt = $('Merge Texts').first().json;\n"
    "var rawText = mt.fullText || mt.specificationText || mt.documentationText || '';\n"
    "\n"
    "return [{ json: {\n"
    "  requirements: extractionOk ? reqs : reqNode,\n"
    "  specData: $json.specData || $json,\n"
    "  contractorInfo: $('Init Job').first().json.contractorInfo,\n"
    "  requirementsExtractionFailed: !extractionOk,\n"
    "  documentationText: !extractionOk ? rawText.substring(0, 60000) : ''\n"
    "} }];"
)

for node in wf00['nodes']:
    if node['name'] == 'After Spec Analysis':
        old_len = len(node['parameters']['jsCode'])
        node['parameters']['jsCode'] = NEW_AFTER_SPEC
        new_len = len(node['parameters']['jsCode'])
        print(f"  Updated: {old_len} -> {new_len} chars")

with open('n8n/workflows/00-orchestrator.json', 'w', encoding='utf-8') as f:
    json.dump(wf00, f, ensure_ascii=False, indent=2)

with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    test = json.load(f)
print(f"  WF00 valid: {len(test['nodes'])} nodes\n")


# ============================================================
# FIX 2: WF02 "Prepare Data" - try specificationText when documentationText is empty
# ============================================================
print("=== FIX 2: WF02 Prepare Data ===")

with open('n8n/workflows/02-extract-requirements.json', 'r', encoding='utf-8') as f:
    wf02 = json.load(f)

NEW_PREPARE_DATA = (
    "var body = $json.body || $json;\n"
    "var docText = body.documentationText || body.fullText || body.specificationText || '';\n"
    "if (!docText && body.text) docText = body.text;\n"
    "if (docText.length > 80000) docText = docText.substring(0, 80000);\n"
    "return [{ json: { documentText: docText } }];"
)

for node in wf02['nodes']:
    if node['name'] == 'Prepare Data':
        old_len = len(node['parameters']['jsCode'])
        node['parameters']['jsCode'] = NEW_PREPARE_DATA
        new_len = len(node['parameters']['jsCode'])
        print(f"  Updated: {old_len} -> {new_len} chars")

with open('n8n/workflows/02-extract-requirements.json', 'w', encoding='utf-8') as f:
    json.dump(wf02, f, ensure_ascii=False, indent=2)

with open('n8n/workflows/02-extract-requirements.json', 'r', encoding='utf-8') as f:
    test = json.load(f)
print(f"  WF02 valid: {len(test['nodes'])} nodes\n")


# ============================================================
# FIX 3: WF04 "Parse Plan" - add fixNewlines + repairTruncated
# ============================================================
print("=== FIX 3: WF04 Parse Plan ===")

with open('n8n/workflows/04-plan-document.json', 'r', encoding='utf-8') as f:
    wf04 = json.load(f)

WF04_PARSE_CODE = ROBUST_PARSE_CODE + """

if (!result) {
  result = { document_title: 'Parse error', sections: [], _raw: raw.substring(0, 8000), _parse_error: true };
}

return [{ json: { documentPlan: result } }];"""

for node in wf04['nodes']:
    if node['name'] == 'Parse Plan':
        old_len = len(node['parameters']['jsCode'])
        node['parameters']['jsCode'] = WF04_PARSE_CODE
        new_len = len(node['parameters']['jsCode'])
        print(f"  Updated: {old_len} -> {new_len} chars")

with open('n8n/workflows/04-plan-document.json', 'w', encoding='utf-8') as f:
    json.dump(wf04, f, ensure_ascii=False, indent=2)

with open('n8n/workflows/04-plan-document.json', 'r', encoding='utf-8') as f:
    test = json.load(f)
print(f"  WF04 valid: {len(test['nodes'])} nodes\n")


# ============================================================
# FINAL VALIDATION
# ============================================================
print("=== FINAL VALIDATION ===")
for fname, expected in [
    ('00-orchestrator.json', 34),
    ('02-extract-requirements.json', 6),
    ('04-plan-document.json', 6),
]:
    with open(f'n8n/workflows/{fname}', 'r', encoding='utf-8') as f:
        d = json.load(f)
    n = len(d['nodes'])
    ok = 'OK' if n == expected else f'WARN ({n} != {expected})'
    print(f"  {fname}: {len(json.dumps(d)):,} bytes, {n} nodes [{ok}]")

# Specific checks
with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
for node in d['nodes']:
    if node['name'] == 'After Spec Analysis':
        code = node['parameters']['jsCode']
        assert 'fullText' in code, 'WF00: fullText NOT in After Spec Analysis'
        assert 'specificationText' in code, 'WF00: specificationText NOT in After Spec Analysis'
        print("  WF00 After Spec: fullText + specificationText fallback OK")

with open('n8n/workflows/02-extract-requirements.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
for node in d['nodes']:
    if node['name'] == 'Prepare Data':
        code = node['parameters']['jsCode']
        assert 'specificationText' in code, 'WF02: specificationText NOT in Prepare Data'
        print("  WF02 Prepare Data: specificationText fallback OK")

with open('n8n/workflows/04-plan-document.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
for node in d['nodes']:
    if node['name'] == 'Parse Plan':
        code = node['parameters']['jsCode']
        assert 'fixNewlines' in code, 'WF04: fixNewlines NOT in Parse Plan'
        assert 'repairTruncated' in code, 'WF04: repairTruncated NOT in Parse Plan'
        print("  WF04 Parse Plan: fixNewlines + repairTruncated OK")

print("\nAll fixes applied successfully!")
