"""
Fix the requirements data flow:
1. WF02 - Better JSON parsing (add fixNewlines + truncation repair)
2. WF00 "After Spec Analysis" - Pass documentationText when requirements extraction failed
3. WF04 "Prepare Plan Prompt" - Use raw documentation text as fallback
"""
import json
import sys

# ============================================================
# FIX 1: WF02 - Better Parse Requirements
# ============================================================
print("=== FIX 1: WF02 Parse Requirements ===")

with open('n8n/workflows/02-extract-requirements.json', 'r', encoding='utf-8') as f:
    wf02 = json.load(f)

OLD_PARSE_CODE = r"""// Sanitize Unicode smart quotes that break JSON parsing
function sanitize(s) {
  return s.replace(/[\u201C\u201D\u201E\u201F\u00AB\u00BB\u2018\u2019]/g, "'");
}

function tryParse(s) {
  try { return JSON.parse(s); } catch(e) { return null; }
}

function extractJson(s) {
  var m = s.match(/```(?:json)?\s*([\s\S]*?)```/);
  var c = m ? m[1].trim() : s;
  var start = c.indexOf('{');
  var end = c.lastIndexOf('}');
  if (start === -1 || end === -1) {
    // Try array
    start = c.indexOf('[');
    end = c.lastIndexOf(']');
    if (start === -1 || end === -1) return s;
  }
  return c.substring(start, end + 1);
}

function fixCommon(s) {
  return s.replace(/,\s*([\]\}])/g, '$1');
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

var raw = ($json.text || $json.response || '').trim();
var result = null;

raw = sanitize(raw);

result = tryParse(raw);

if (!result) {
  var extracted = fixCommon(extractJson(raw));
  result = tryParse(extracted);
}

if (!result) {
  var extracted2 = fixCommon(extractJson(raw));
  result = tryParse(fixQuotes(extracted2));
}

if (!result) {
  result = {
    procurement_type: 'unknown',
    requirements: [],
    _raw: raw.substring(0, 5000),
    _parse_error: true
  };
}

return [{ json: result }];"""

NEW_PARSE_CODE = r"""// Sanitize Unicode smart quotes that break JSON parsing
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
  if (start === -1 || end === -1) {
    start = c.indexOf('[');
    end = c.lastIndexOf(']');
    if (start === -1 || end === -1) return s;
  }
  return c.substring(start, end + 1);
}

function fixCommon(s) {
  return s.replace(/,\s*([\]\}])/g, '$1');
}

// Fix unescaped newlines inside JSON string values
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

// Repair truncated JSON by closing open brackets/braces
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
  // If still inside a string, close it
  if (inStr) s += '"';
  // Remove trailing comma before closing
  s = s.replace(/,\s*$/, '');
  // Close all open brackets/braces
  while (stack.length > 0) {
    s += stack.pop();
  }
  return s;
}

var raw = ($json.text || $json.response || '').trim();
var result = null;

raw = sanitize(raw);

// Attempt 1: Direct parse
result = tryParse(raw);

// Attempt 2: Extract JSON block + fix trailing commas
if (!result) {
  var ex = fixCommon(extractJson(raw));
  result = tryParse(ex);
}

// Attempt 3: + fix newlines in strings
if (!result) {
  result = tryParse(fixNewlines(fixCommon(extractJson(raw))));
}

// Attempt 4: + fix unescaped quotes
if (!result) {
  result = tryParse(fixQuotes(fixNewlines(fixCommon(extractJson(raw)))));
}

// Attempt 5: repair truncated JSON (LLM output cut off)
if (!result) {
  var repaired = repairTruncated(fixNewlines(fixCommon(extractJson(raw))));
  result = tryParse(repaired);
  if (!result) {
    result = tryParse(fixQuotes(repaired));
  }
}

if (!result) {
  result = {
    procurement_type: 'unknown',
    requirements: [],
    _raw: raw.substring(0, 8000),
    _parse_error: true
  };
}

return [{ json: result }];"""

for node in wf02['nodes']:
    if node['name'] == 'Parse Requirements':
        old_code = node['parameters']['jsCode']
        old_len = len(old_code)
        node['parameters']['jsCode'] = NEW_PARSE_CODE
        new_len = len(node['parameters']['jsCode'])
        print(f"  Updated Parse Requirements: {old_len} -> {new_len} chars")

# Also increase maxTokens to prevent truncation
for node in wf02['nodes']:
    if node['name'] == 'Claude Sonnet':
        old_tokens = node['parameters']['options']['maxTokens']
        node['parameters']['options']['maxTokens'] = 24000
        print(f"  Updated maxTokens: {old_tokens} -> 24000")

with open('n8n/workflows/02-extract-requirements.json', 'w', encoding='utf-8') as f:
    json.dump(wf02, f, ensure_ascii=False, indent=2)

# Validate
with open('n8n/workflows/02-extract-requirements.json', 'r', encoding='utf-8') as f:
    test = json.load(f)
print(f"  WF02 valid: {len(test['nodes'])} nodes\n")


# ============================================================
# FIX 2: WF00 "After Spec Analysis" - pass documentationText when extraction failed
# ============================================================
print("=== FIX 2: WF00 After Spec Analysis ===")

with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    wf00 = json.load(f)

OLD_AFTER_SPEC = (
    'return [{ json: {\n'
    '  requirements: $(\'Extract Requirements\').first().json.requirements || $(\'Extract Requirements\').first().json,\n'
    '  specData: $json.specData || $json,\n'
    '  contractorInfo: $(\'Init Job\').first().json.contractorInfo\n'
    '} }];'
)

NEW_AFTER_SPEC = (
    'var reqNode = $(\'Extract Requirements\').first().json;\n'
    'var reqs = reqNode.requirements;\n'
    'var extractionOk = reqs && Array.isArray(reqs) && reqs.length > 0 && !reqNode._parse_error;\n'
    'var mt = $(\'Merge Texts\').first().json;\n'
    '\n'
    'return [{ json: {\n'
    '  requirements: extractionOk ? reqs : reqNode,\n'
    '  specData: $json.specData || $json,\n'
    '  contractorInfo: $(\'Init Job\').first().json.contractorInfo,\n'
    '  requirementsExtractionFailed: !extractionOk,\n'
    '  documentationText: !extractionOk ? (mt.documentationText || mt.fullText || \'\').substring(0, 60000) : \'\'\n'
    '} }];'
)

for node in wf00['nodes']:
    if node['name'] == 'After Spec Analysis':
        old_code = node['parameters']['jsCode']
        old_len = len(old_code)
        node['parameters']['jsCode'] = NEW_AFTER_SPEC
        new_len = len(node['parameters']['jsCode'])
        print(f"  Updated After Spec Analysis: {old_len} -> {new_len} chars")

with open('n8n/workflows/00-orchestrator.json', 'w', encoding='utf-8') as f:
    json.dump(wf00, f, ensure_ascii=False, indent=2)

# Validate
with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    test = json.load(f)
print(f"  WF00 valid: {len(test['nodes'])} nodes\n")


# ============================================================
# FIX 3: WF04 "Prepare Plan Prompt" - use raw text as fallback
# ============================================================
print("=== FIX 3: WF04 Prepare Plan Prompt ===")

with open('n8n/workflows/04-plan-document.json', 'r', encoding='utf-8') as f:
    wf04 = json.load(f)

# The current code starts with parsing reqs and building the prompt
# We need to add a fallback: when requirements are empty but documentationText is available
OLD_PROMPT_START = (
    "var body = $json.body || $json;\n"
    "var reqs = body.requirements || {};\n"
    "var reqType = reqs.procurement_type || 'неопределен';\n"
    "var reqStr = JSON.stringify(reqs, null, 2);\n"
    "if (reqStr.length > 40000) reqStr = reqStr.substring(0, 40000);\n"
    "var specStr = JSON.stringify(body.specData || {}, null, 2);\n"
    "if (specStr.length > 40000) specStr = specStr.substring(0, 40000);\n"
    "var ciStr = JSON.stringify(body.contractorInfo || {}, null, 2);\n"
    "\n"
    "var p = '';\n"
    "\n"
    "p += '# ЗАДАЧА\\n';\n"
    "p += 'Създай ДЕТАЙЛЕН ПЛАН за техническо предложение, като РАЗЛОЖИШ изискванията ИЗРЕЧЕНИЕ ПО ИЗРЕЧЕНИЕ.\\n\\n';\n"
    "p += 'ТИП ПОРЪЧКА: ' + reqType + '\\n\\n';\n"
    "\n"
    "p += '## ИЗВЛЕЧЕНИ ИЗИСКВАНИЯ\\n' + reqStr + '\\n\\n';\n"
    "p += '## АНАЛИЗ НА СПЕЦИФИКАЦИЯТА\\n' + specStr + '\\n\\n';\n"
    "p += '## ИНФОРМАЦИЯ ЗА ИЗПЪЛНИТЕЛЯ\\n' + ciStr + '\\n\\n';"
)

NEW_PROMPT_START = (
    "var body = $json.body || $json;\n"
    "var reqs = body.requirements || {};\n"
    "var reqType = reqs.procurement_type || 'неопределен';\n"
    "var extractionFailed = body.requirementsExtractionFailed === true;\n"
    "var hasReqs = reqs.requirements && Array.isArray(reqs.requirements) && reqs.requirements.length > 0;\n"
    "if (!hasReqs && Array.isArray(reqs) && reqs.length > 0) hasReqs = true;\n"
    "var reqStr = JSON.stringify(reqs, null, 2);\n"
    "if (reqStr.length > 40000) reqStr = reqStr.substring(0, 40000);\n"
    "var specStr = JSON.stringify(body.specData || {}, null, 2);\n"
    "if (specStr.length > 40000) specStr = specStr.substring(0, 40000);\n"
    "var ciStr = JSON.stringify(body.contractorInfo || {}, null, 2);\n"
    "var docText = (body.documentationText || '').substring(0, 60000);\n"
    "\n"
    "var p = '';\n"
    "\n"
    "p += '# ЗАДАЧА\\n';\n"
    "p += 'Създай ДЕТАЙЛЕН ПЛАН за техническо предложение, като РАЗЛОЖИШ изискванията ИЗРЕЧЕНИЕ ПО ИЗРЕЧЕНИЕ.\\n\\n';\n"
    "p += 'ТИП ПОРЪЧКА: ' + reqType + '\\n\\n';\n"
    "\n"
    "if (extractionFailed || !hasReqs) {\n"
    "  p += '## ВАЖНО: АВТОМАТИЧНОТО ИЗВЛИЧАНЕ НА ИЗИСКВАНИЯ НЕ УСПЯ\\n';\n"
    "  p += 'Предоставяме ти СУРОВИЯ ТЕКСТ на документацията. ЗАДЪЛЖИТЕЛНО:\\n';\n"
    "  p += '1. ПРОЧЕТИ внимателно целия текст.\\n';\n"
    "  p += '2. НАМЕРИ разделите за техническо предложение/показатели за оценка/методика за оценка.\\n';\n"
    "  p += '3. ИЗВЛЕЧИ всяко номерирано изискване с ДОСЛОВНИЯ му текст.\\n';\n"
    "  p += '4. Използвай ИЗВЛЕЧЕНИТЕ изисквания за основа на плана.\\n\\n';\n"
    "  if (docText.length > 0) {\n"
    "    p += '## СУРОВ ТЕКСТ НА ДОКУМЕНТАЦИЯТА\\n' + docText + '\\n\\n';\n"
    "  }\n"
    "  if (reqStr !== '{}' && reqStr !== '[]') {\n"
    "    p += '## ЧАСТИЧНО ИЗВЛЕЧЕНИ ИЗИСКВАНИЯ (може да са непълни)\\n' + reqStr + '\\n\\n';\n"
    "  }\n"
    "} else {\n"
    "  p += '## ИЗВЛЕЧЕНИ ИЗИСКВАНИЯ\\n' + reqStr + '\\n\\n';\n"
    "}\n"
    "\n"
    "p += '## АНАЛИЗ НА СПЕЦИФИКАЦИЯТА\\n' + specStr + '\\n\\n';\n"
    "p += '## ИНФОРМАЦИЯ ЗА ИЗПЪЛНИТЕЛЯ\\n' + ciStr + '\\n\\n';"
)

for node in wf04['nodes']:
    if node['name'] == 'Prepare Plan Prompt':
        old_code = node['parameters']['jsCode']
        old_len = len(old_code)
        
        # Find and replace the start section
        old_encoded = json.dumps(OLD_PROMPT_START)
        new_encoded = json.dumps(NEW_PROMPT_START)
        
        # Do the replacement on the raw string
        old_code_encoded = json.dumps(old_code)
        if old_encoded[1:-1] in old_code_encoded:
            new_code_encoded = old_code_encoded.replace(old_encoded[1:-1], new_encoded[1:-1], 1)
            node['parameters']['jsCode'] = json.loads(new_code_encoded)
            new_len = len(node['parameters']['jsCode'])
            print(f"  Updated Prepare Plan Prompt: {old_len} -> {new_len} chars")
        else:
            # Try direct string replacement
            if OLD_PROMPT_START in old_code:
                node['parameters']['jsCode'] = old_code.replace(OLD_PROMPT_START, NEW_PROMPT_START, 1)
                new_len = len(node['parameters']['jsCode'])
                print(f"  Updated Prepare Plan Prompt (direct): {old_len} -> {new_len} chars")
            else:
                print("  ERROR: Could not find the target section in Prepare Plan Prompt!")
                print("  Looking for first 100 chars:", repr(OLD_PROMPT_START[:100]))
                print("  Actual first 100 chars:", repr(old_code[:100]))
                sys.exit(1)

with open('n8n/workflows/04-plan-document.json', 'w', encoding='utf-8') as f:
    json.dump(wf04, f, ensure_ascii=False, indent=2)

# Validate
with open('n8n/workflows/04-plan-document.json', 'r', encoding='utf-8') as f:
    test = json.load(f)
print(f"  WF04 valid: {len(test['nodes'])} nodes\n")


# ============================================================
# FINAL VALIDATION
# ============================================================
print("=== FINAL VALIDATION ===")
for fname, expected_nodes in [
    ('02-extract-requirements.json', 6),
    ('00-orchestrator.json', 34),
    ('04-plan-document.json', 6),
]:
    with open(f'n8n/workflows/{fname}', 'r', encoding='utf-8') as f:
        d = json.load(f)
    nodes = len(d['nodes'])
    status = 'OK' if nodes == expected_nodes else f'WARN (expected {expected_nodes})'
    print(f"  {fname}: {len(json.dumps(d)):,} bytes, {nodes} nodes [{status}]")

print("\nAll fixes applied successfully!")
