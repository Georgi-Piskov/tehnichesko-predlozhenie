"""
Fix Parse Plan parser in WF04 AND WF02:
- ROOT CAUSE: fixNewlines runs BEFORE fixQuotes, but fixNewlines gets confused
  by unescaped double quotes inside string values (e.g. "ЧЕПЕЛАРЕ", "ЗДРАВЕЦ").
  Once fixNewlines misidentifies string boundaries, everything fails.
- FIX: Run fixQuotes BEFORE fixNewlines in all strategies.
- Also fix in WF00 Flatten Chunks: add fallback re-parsing from _raw.
"""
import json

# ========== NEW PARSE PLAN CODE ==========
NEW_PARSE_PLAN = r'''var raw = ($json.text || $json.response || '').trim();
var result = null;
var parseMethod = 'none';

function sanitize(s) {
  return s.replace(/[\u201C\u201D\u201E\u201F\u00AB\u00BB\u2018\u2019\u2032\u2033]/g, "'")
          .replace(/^\uFEFF/, '');
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
        if (next === ':' || next === ',' || next === '}' || next === ']' || next === '\n' || rest.length === 0) {
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

// Strategy 1: direct parse
result = tryParse(raw);
if (result) parseMethod = 'direct';

// Strategy 2: extract JSON block + fix trailing commas
if (!result) {
  var clean = fixCommon(extractJson(raw));
  result = tryParse(clean);
  if (result) parseMethod = 'extractJson';
}

// Strategy 3: fix quotes FIRST (handles unescaped " inside strings)
if (!result) {
  var clean = fixQuotes(fixCommon(extractJson(raw)));
  result = tryParse(clean);
  if (result) parseMethod = 'fixQuotes';
}

// Strategy 4: fix quotes FIRST, THEN fix newlines (KEY strategy for Bulgarian text)
if (!result) {
  var clean = fixNewlines(fixQuotes(fixCommon(extractJson(raw))));
  result = tryParse(clean);
  if (result) parseMethod = 'fixQuotes+fixNewlines';
}

// Strategy 5: fix newlines first, then quotes (original order, fallback)
if (!result) {
  var clean = fixQuotes(fixNewlines(fixCommon(extractJson(raw))));
  result = tryParse(clean);
  if (result) parseMethod = 'fixNewlines+fixQuotes';
}

// Strategy 6: repair truncated output (LLM hit max_tokens)
if (!result) {
  var clean = fixNewlines(fixQuotes(fixCommon(extractJson(raw))));
  var repaired = repairTruncated(clean);
  result = tryParse(repaired);
  if (result) parseMethod = 'repairTruncated';
}

// Strategy 7: aggressive - just fixQuotes on the raw text (no extractJson)
if (!result) {
  var clean = fixNewlines(fixQuotes(fixCommon(raw)));
  result = tryParse(clean);
  if (result) parseMethod = 'rawFixQuotes';
}

// Fallback: return error with raw for debugging
if (!result) {
  result = { document_title: 'Parse error', sections: [], _raw: raw.substring(0, 15000), _parse_error: true };
  parseMethod = 'FAILED';
}

result._parseMethod = parseMethod;
return [{ json: { documentPlan: result } }];'''


# ========== NEW PARSE REQUIREMENTS CODE (WF02) ==========
NEW_PARSE_REQ = r'''var raw = ($json.text || $json.response || '').trim();
var result = null;
var parseMethod = 'none';

function sanitize(s) {
  return s.replace(/[\u201C\u201D\u201E\u201F\u00AB\u00BB\u2018\u2019\u2032\u2033]/g, "'")
          .replace(/^\uFEFF/, '');
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
        if (next === ':' || next === ',' || next === '}' || next === ']' || next === '\n' || rest.length === 0) {
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
if (result) parseMethod = 'direct';

if (!result) {
  var clean = fixCommon(extractJson(raw));
  result = tryParse(clean);
  if (result) parseMethod = 'extractJson';
}

if (!result) {
  var clean = fixQuotes(fixCommon(extractJson(raw)));
  result = tryParse(clean);
  if (result) parseMethod = 'fixQuotes';
}

if (!result) {
  var clean = fixNewlines(fixQuotes(fixCommon(extractJson(raw))));
  result = tryParse(clean);
  if (result) parseMethod = 'fixQuotes+fixNewlines';
}

if (!result) {
  var clean = fixQuotes(fixNewlines(fixCommon(extractJson(raw))));
  result = tryParse(clean);
  if (result) parseMethod = 'fixNewlines+fixQuotes';
}

if (!result) {
  var clean = fixNewlines(fixQuotes(fixCommon(extractJson(raw))));
  var repaired = repairTruncated(clean);
  result = tryParse(repaired);
  if (result) parseMethod = 'repairTruncated';
}

if (!result) {
  var clean = fixNewlines(fixQuotes(fixCommon(raw)));
  result = tryParse(clean);
  if (result) parseMethod = 'rawFixQuotes';
}

if (!result) {
  result = { requirements: [], _raw: raw.substring(0, 15000), _parse_error: true };
  parseMethod = 'FAILED';
}

result._parseMethod = parseMethod;
return [{ json: result }];'''


# ========== FLATTEN CHUNKS FALLBACK ==========
# Read the current Flatten Chunks code and add _raw re-parsing at the beginning
NEW_FLATTEN_PREFIX = r'''var plan = $json.documentPlan;

// FALLBACK: If parse failed but _raw has data, try to re-parse
if (plan && plan._parse_error && plan._raw) {
  var rawPlan = plan._raw;
  function tryParse2(s) { try { return JSON.parse(s); } catch(e) { return null; } }
  function extractJson2(s) {
    var m = s.match(/```(?:json)?\s*([\s\S]*?)```/);
    var c = m ? m[1].trim() : s;
    var start = c.indexOf('{'); var end = c.lastIndexOf('}');
    if (start === -1 || end === -1) return s;
    return c.substring(start, end + 1);
  }
  function fixQuotes2(s) {
    var out = ''; var inStr = false; var escaped = false;
    for (var i = 0; i < s.length; i++) {
      var ch = s[i];
      if (escaped) { out += ch; escaped = false; continue; }
      if (ch === '\\') { out += ch; escaped = true; continue; }
      if (ch === '"') {
        if (!inStr) { inStr = true; out += ch; }
        else {
          var rest = s.substring(i + 1).trimStart();
          var next = rest.length > 0 ? rest[0] : '';
          if (next === ':' || next === ',' || next === '}' || next === ']' || next === '\n' || rest.length === 0) { inStr = false; out += ch; }
          else { out += '\\"'; }
        }
      } else { out += ch; }
    }
    return out;
  }
  function fixNewlines2(s) {
    var out = ''; var inStr = false; var escaped = false;
    for (var i = 0; i < s.length; i++) {
      var ch = s[i];
      if (escaped) { out += ch; escaped = false; continue; }
      if (ch === '\\') { out += ch; escaped = true; continue; }
      if (ch === '"') { inStr = !inStr; out += ch; continue; }
      if (inStr && ch === '\n') { out += '\\n'; continue; }
      if (inStr && ch === '\r') { continue; }
      out += ch;
    }
    return out;
  }
  var rp = tryParse2(fixNewlines2(fixQuotes2(extractJson2(rawPlan).replace(/,\s*([\]\}])/g, '$1'))));
  if (rp && rp.sections && rp.sections.length > 0) {
    plan = rp;
    plan._recoveredInFlatten = true;
  }
}

'''


print("=== FIX: Parse Plan + Parse Requirements + Flatten Chunks ===")

# ========== Fix WF04 Parse Plan ==========
with open('n8n/workflows/04-plan-document.json', 'r', encoding='utf-8') as f:
    wf04 = json.load(f)

for node in wf04['nodes']:
    if node['name'] == 'Parse Plan':
        node['parameters']['jsCode'] = NEW_PARSE_PLAN
        print("  WF04 Parse Plan: REWRITTEN with fixQuotes-first strategies")

with open('n8n/workflows/04-plan-document.json', 'w', encoding='utf-8') as f:
    json.dump(wf04, f, ensure_ascii=False, indent=2)

# Validate
with open('n8n/workflows/04-plan-document.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
    print(f"  04-plan-document.json: valid, {len(d['nodes'])} nodes")


# ========== Fix WF02 Parse Requirements ==========
with open('n8n/workflows/02-extract-requirements.json', 'r', encoding='utf-8') as f:
    wf02 = json.load(f)

for node in wf02['nodes']:
    if node['name'] == 'Parse Requirements':
        node['parameters']['jsCode'] = NEW_PARSE_REQ
        print("  WF02 Parse Requirements: REWRITTEN with fixQuotes-first strategies")

with open('n8n/workflows/02-extract-requirements.json', 'w', encoding='utf-8') as f:
    json.dump(wf02, f, ensure_ascii=False, indent=2)

with open('n8n/workflows/02-extract-requirements.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
    print(f"  02-extract-requirements.json: valid, {len(d['nodes'])} nodes")


# ========== Fix WF00 Flatten Chunks ==========
with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    wf00 = json.load(f)

for node in wf00['nodes']:
    if node['name'] == 'Flatten Chunks':
        old_code = node['parameters']['jsCode']
        # The old code starts with "var plan = $json.documentPlan;"
        # Replace that line with the new prefix + the rest
        if old_code.startswith('var plan = $json.documentPlan;'):
            new_code = NEW_FLATTEN_PREFIX + old_code[len('var plan = $json.documentPlan;\n'):]
            node['parameters']['jsCode'] = new_code
            print("  WF00 Flatten Chunks: Added _raw re-parsing fallback")
        else:
            print(f"  WF00 Flatten Chunks: unexpected start: {old_code[:50]}")

with open('n8n/workflows/00-orchestrator.json', 'w', encoding='utf-8') as f:
    json.dump(wf00, f, ensure_ascii=False, indent=2)

with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
    print(f"  00-orchestrator.json: valid, {len(d['nodes'])} nodes")


print("\n=== ALL DONE ===")
print("Changes:")
print("  1. WF04 Parse Plan: fixQuotes runs BEFORE fixNewlines (7 strategies)")
print("  2. WF02 Parse Requirements: same fix (7 strategies)")
print("  3. WF00 Flatten Chunks: fallback re-parses _raw if sections is empty")
print("  4. fixQuotes now also treats \\n after closing quote as valid delimiter")
print("  5. _raw increased from 8K to 15K chars for debugging")
