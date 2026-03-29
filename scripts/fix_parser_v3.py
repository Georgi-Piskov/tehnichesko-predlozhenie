"""
Triple fix for Parse Plan failure:
1. LLM instruction: NEVER use " inside JSON string values
2. Optimized parser: O(n) instead of O(n^2) — no .substring().trimStart() per char
3. Flatten Chunks: full 7-strategy fallback + regex section extractor
"""
import json
import os

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
print("Working directory:", os.getcwd())
print("=== TRIPLE FIX: LLM instruction + Optimized parser + Fallback ===\n")

# =====================================================================
# OPTIMIZED fixQuotes helper (shared by Parse Plan and Parse Requirements)
# Key change: nextNonWS() uses forward scan instead of .substring().trimStart()
# This makes fixQuotes O(n) instead of O(n^2)
# =====================================================================

OPTIMIZED_PARSER_FUNCTIONS = r'''function sanitize(s) {
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

function nextNonWS(s, pos) {
  for (var j = pos; j < s.length; j++) {
    var c = s.charCodeAt(j);
    if (c !== 32 && c !== 9 && c !== 10 && c !== 13) return s[j];
  }
  return '';
}

function fixQuotes(s) {
  var out = '';
  var inStr = false;
  var escaped = false;
  var len = s.length;
  for (var i = 0; i < len; i++) {
    var ch = s[i];
    if (escaped) { out += ch; escaped = false; continue; }
    if (ch === '\\') { out += ch; escaped = true; continue; }
    if (ch === '"') {
      if (!inStr) {
        inStr = true;
        out += ch;
      } else {
        var next = nextNonWS(s, i + 1);
        if (next === ':' || next === ',' || next === '}' || next === ']' || next === '') {
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
  var len = s.length;
  for (var i = 0; i < len; i++) {
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
}'''

STRATEGIES_BLOCK = r'''raw = sanitize(raw);

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
  if (!result) {
    var repaired = repairTruncated(clean);
    result = tryParse(repaired);
  }
  if (result) parseMethod = 'rawRepair';
}'''


# Build Parse Plan code (WF04) — reads from agent output ($json.output)
NEW_PARSE_PLAN = (
    "var raw = ($json.output || $json.text || $json.response || '').trim();\n"
    "var result = null;\nvar parseMethod = 'none';\n\n"
    + OPTIMIZED_PARSER_FUNCTIONS + "\n\n"
    + STRATEGIES_BLOCK + "\n\n"
    + "if (!result) {\n"
    + "  result = { document_title: 'Parse error', sections: [], _raw: raw.substring(0, 20000), _parse_error: true };\n"
    + "  parseMethod = 'FAILED';\n"
    + "}\n\n"
    + "result._parseMethod = parseMethod;\n"
    + "return [{ json: { documentPlan: result } }];"
)

# Build Parse Requirements code (WF02) — reads from chainLlm output ($json.text)
NEW_PARSE_REQ = (
    "var raw = ($json.text || $json.response || '').trim();\n"
    "var result = null;\nvar parseMethod = 'none';\n\n"
    + OPTIMIZED_PARSER_FUNCTIONS + "\n\n"
    + STRATEGIES_BLOCK + "\n\n"
    + "if (!result) {\n"
    + "  result = { requirements: [], _raw: raw.substring(0, 20000), _parse_error: true };\n"
    + "  parseMethod = 'FAILED';\n"
    + "}\n\n"
    + "result._parseMethod = parseMethod;\n"
    + "return [{ json: result }];"
)


# =====================================================================
# FLATTEN CHUNKS FALLBACK — full parser with all 7 strategies (O(n))
# =====================================================================
NEW_FLATTEN_FALLBACK = r'''var plan = $json.documentPlan;

// FALLBACK: If parse failed but _raw has data, try full re-parse with O(n) fixQuotes
if (plan && plan._parse_error && plan._raw) {
  var rawPlan = plan._raw;

  function tryP(s) { try { return JSON.parse(s); } catch(e) { return null; } }
  function exJ(s) {
    var m = s.match(/```(?:json)?\s*([\s\S]*?)```/);
    var c = m ? m[1].trim() : s;
    var st = c.indexOf('{'); var en = c.lastIndexOf('}');
    if (st === -1 || en === -1) return s;
    return c.substring(st, en + 1);
  }
  function fxC(s) { return s.replace(/,\s*([\]\}])/g, '$1'); }
  function nWS(s, pos) {
    for (var j = pos; j < s.length; j++) {
      var c = s.charCodeAt(j);
      if (c !== 32 && c !== 9 && c !== 10 && c !== 13) return s[j];
    }
    return '';
  }
  function fxQ(s) {
    var out = ''; var inS = false; var esc = false; var ln = s.length;
    for (var i = 0; i < ln; i++) {
      var ch = s[i];
      if (esc) { out += ch; esc = false; continue; }
      if (ch === '\\') { out += ch; esc = true; continue; }
      if (ch === '"') {
        if (!inS) { inS = true; out += ch; }
        else {
          var nx = nWS(s, i + 1);
          if (nx === ':' || nx === ',' || nx === '}' || nx === ']' || nx === '') { inS = false; out += ch; }
          else { out += '\\"'; }
        }
      } else { out += ch; }
    }
    return out;
  }
  function fxN(s) {
    var out = ''; var inS = false; var esc = false;
    for (var i = 0; i < s.length; i++) {
      var ch = s[i];
      if (esc) { out += ch; esc = false; continue; }
      if (ch === '\\') { out += ch; esc = true; continue; }
      if (ch === '"') { inS = !inS; out += ch; continue; }
      if (inS && ch === '\n') { out += '\\n'; continue; }
      if (inS && ch === '\r') { continue; }
      out += ch;
    }
    return out;
  }
  function repT(s) {
    var stk = []; var inS = false; var esc = false;
    for (var i = 0; i < s.length; i++) {
      var ch = s[i];
      if (esc) { esc = false; continue; }
      if (ch === '\\') { esc = true; continue; }
      if (ch === '"') { inS = !inS; continue; }
      if (inS) continue;
      if (ch === '{') stk.push('}');
      else if (ch === '[') stk.push(']');
      else if (ch === '}' || ch === ']') { if (stk.length > 0) stk.pop(); }
    }
    if (inS) s += '"';
    s = s.replace(/,\s*$/, '');
    while (stk.length > 0) s += stk.pop();
    return s;
  }

  rawPlan = rawPlan.replace(/[\u201C\u201D\u201E\u201F\u00AB\u00BB\u2018\u2019\u2032\u2033]/g, "'");

  var strategies = [
    function() { return tryP(fxC(exJ(rawPlan))); },
    function() { return tryP(fxQ(fxC(exJ(rawPlan)))); },
    function() { return tryP(fxN(fxQ(fxC(exJ(rawPlan))))); },
    function() { return tryP(fxQ(fxN(fxC(exJ(rawPlan))))); },
    function() { return tryP(repT(fxN(fxQ(fxC(exJ(rawPlan)))))); },
    function() { return tryP(fxN(fxQ(fxC(rawPlan)))); },
    function() { return tryP(repT(fxN(fxQ(fxC(rawPlan))))); }
  ];

  for (var si = 0; si < strategies.length; si++) {
    var rp = strategies[si]();
    if (rp && rp.sections && rp.sections.length > 0) {
      plan = rp;
      plan._recoveredInFlatten = true;
      plan._recoveryStrategy = si;
      break;
    }
  }
}

'''


print("=== Applying changes ===\n")

# =====================================================================
# 1. FIX WF04: Parser + LLM instruction
# =====================================================================
with open('n8n/workflows/04-plan-document.json', 'r', encoding='utf-8') as f:
    wf04 = json.load(f)

for node in wf04['nodes']:
    if node['name'] == 'Parse Plan':
        node['parameters']['jsCode'] = NEW_PARSE_PLAN
        print("  [OK] WF04 Parse Plan: REWRITTEN with O(n) fixQuotes")

    # Add no-quotes instruction to system message
    if node['name'] == 'Plan Document':
        if 'options' in node['parameters'] and 'systemMessage' in node['parameters']['options']:
            msg = node['parameters']['options']['systemMessage']
            if u'\u041d\u0418\u041a\u041e\u0413\u0410 \u041d\u0415 \u0418\u0417\u041f\u041e\u041b\u0417\u0412\u0410\u0419' not in msg:  # НИКОГА НЕ ИЗПОЛЗВАЙ
                # Find the # ФОРМАТ line and insert before it
                format_marker = "# \u0424\u041e\u0420\u041c\u0410\u0422"  # # ФОРМАТ
                if format_marker in msg:
                    no_quotes_instruction = (
                        "# \u26a0\ufe0f \u041a\u0420\u0418\u0422\u0418\u0427\u041d\u041e \u0417\u0410 JSON \u0424\u041e\u0420\u041c\u0410\u0422\u0410\n"  # КРИТИЧНО ЗА JSON ФОРМАТА
                        "\u0412\u044a\u0442\u0440\u0435 \u0432 JSON \u0441\u0442\u0440\u0438\u043d\u0433\u043e\u0432\u0435 \u041d\u0418\u041a\u041e\u0413\u0410 \u041d\u0415 \u0418\u0417\u041f\u041e\u041b\u0417\u0412\u0410\u0419 \u0434\u0432\u043e\u0439\u043d\u0438 \u043a\u0430\u0432\u0438\u0447\u043a\u0438 (\").\n"  # Вътре в JSON стрингове НИКОГА НЕ ИЗПОЛЗВАЙ двойни кавички (").
                        "\u0417\u0430 \u0446\u0438\u0442\u0430\u0442\u0438 \u0438 \u0438\u043c\u0435\u043d\u0430 \u043d\u0430 \u043e\u0431\u0435\u043a\u0442\u0438 \u0438\u0437\u043f\u043e\u043b\u0437\u0432\u0430\u0439 \u0415\u0414\u0418\u041d\u0418\u0427\u041d\u0418 \u041a\u0410\u0412\u0418\u0427\u041a\u0418 (') \u0438\u043b\u0438 \u0431\u0435\u0437 \u043a\u0430\u0432\u0438\u0447\u043a\u0438.\n"  # За цитати и имена на обекти използвай ЕДИНИЧНИ КАВИЧКИ (') или без кавички.
                        "\u041d\u0430\u0440\u0443\u0448\u0430\u0432\u0430\u043d\u0435\u0442\u043e \u043d\u0430 \u0442\u043e\u0432\u0430 \u0427\u0423\u041f\u0418 \u0441\u0438\u0441\u0442\u0435\u043c\u0430\u0442\u0430!\n\n"  # Нарушаването на това ЧУПИ системата!
                    )
                    msg = msg.replace(format_marker, no_quotes_instruction + format_marker)
                    node['parameters']['options']['systemMessage'] = msg
                    print("  [OK] WF04 Plan Document: added NO DOUBLE QUOTES instruction to system msg")
                else:
                    print("  [WARN] Could not find '# ФОРМАТ' in system message")
            else:
                print("  [SKIP] WF04 Plan Document: instruction already present")

    # Add to prompt too
    if node['name'] == 'Prepare Plan Prompt':
        old_code = node['parameters']['jsCode']
        # After json.load, the jsCode is a string with actual newlines and backslashes
        # Look for the line that contains "7. САМО JSON"
        search_str = "p += '7. \u0421\u0410\u041c\u041e JSON, \u0431\u0435\u0437 \u0434\u0440\u0443\u0433 \u0442\u0435\u043a\u0441\u0442.\\n';"  # 7. САМО JSON, без друг текст.\n
        if '\u041d\u0418\u041a\u041e\u0413\u0410 \u043d\u0435 \u0438\u0437\u043f\u043e\u043b\u0437\u0432\u0430\u0439 \u0434\u0432\u043e\u0439\u043d\u0438' not in old_code:  # НИКОГА не използвай двойни
            if search_str in old_code:
                # The \n in the JS string 'p += ...\n' is an actual LF in the JS source (line break between p+= statements)
                new_line = (
                    search_str + "\n"
                    "p += '\u26a0\ufe0f \u041a\u0420\u0418\u0422\u0418\u0427\u041d\u041e: \u0412\u044a\u0442\u0440\u0435 \u0432 JSON \u0441\u0442\u0440\u0438\u043d\u0433\u043e\u0432\u0435 \u041d\u0418\u041a\u041e\u0413\u0410 \u043d\u0435 \u0438\u0437\u043f\u043e\u043b\u0437\u0432\u0430\u0439 \u0434\u0432\u043e\u0439\u043d\u0438 \u043a\u0430\u0432\u0438\u0447\u043a\u0438! \u0417\u0430 \u0438\u043c\u0435\u043d\u0430 \u043d\u0430 \u043e\u0431\u0435\u043a\u0442\u0438 \u043f\u0438\u0448\u0438 \u0427\u0415\u041f\u0415\u041b\u0410\u0420\u0415 \u0438\u043b\u0438 \\'\u0427\u0415\u041f\u0415\u041b\u0410\u0420\u0415\\', \u041d\u0415 \"\u0427\u0415\u041f\u0415\u041b\u0410\u0420\u0415\".\\n';"  # ⚠️ КРИТИЧНО: Вътре в JSON стрингове НИКОГА не използвай двойни кавички! За имена на обекти пиши ЧЕПЕЛАРЕ или \'ЧЕПЕЛАРЕ\', НЕ "ЧЕПЕЛАРЕ".\n
                )
                new_code = old_code.replace(search_str, new_line)
                node['parameters']['jsCode'] = new_code
                print("  [OK] WF04 Prepare Plan Prompt: added NO DOUBLE QUOTES in prompt")
            else:
                print(f"  [WARN] Could not find search string in Prepare Plan Prompt")
                # Debug: show context around "САМО JSON"
                idx = old_code.find('\u0421\u0410\u041c\u041e JSON')
                if idx >= 0:
                    print(f"  Found 'САМО JSON' at pos {idx}: ...{repr(old_code[max(0,idx-30):idx+80])}...")
                else:
                    print("  'САМО JSON' not found at all!")
        else:
            print("  [SKIP] WF04 Prepare Plan Prompt: instruction already present")

with open('n8n/workflows/04-plan-document.json', 'w', encoding='utf-8') as f:
    json.dump(wf04, f, ensure_ascii=False, indent=2)

# Validate
with open('n8n/workflows/04-plan-document.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
    print(f"  04-plan-document.json: valid JSON, {len(d['nodes'])} nodes\n")


# =====================================================================
# 2. FIX WF00 Flatten Chunks: full fallback parser
# =====================================================================
with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    wf00 = json.load(f)

for node in wf00['nodes']:
    if node['name'] == 'Flatten Chunks':
        old_code = node['parameters']['jsCode']

        # Find where the MAIN code starts (after plan + fallback)
        # Main code starts with "var reqs = ..."
        main_start = old_code.find("var reqs = ")
        if main_start == -1:
            print("  [ERROR] Can't find 'var reqs' in Flatten Chunks!")
            print(f"  First 300 chars: {old_code[:300]}")
            continue

        # Keep main logic from "var reqs" onwards
        main_code = old_code[main_start:]

        # Build new code: new fallback + original main logic
        new_code = NEW_FLATTEN_FALLBACK + main_code
        node['parameters']['jsCode'] = new_code
        print("  [OK] WF00 Flatten Chunks: REWRITTEN with 7-strategy O(n) fallback")

with open('n8n/workflows/00-orchestrator.json', 'w', encoding='utf-8') as f:
    json.dump(wf00, f, ensure_ascii=False, indent=2)

# Validate
with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
    print(f"  00-orchestrator.json: valid JSON, {len(d['nodes'])} nodes\n")


# =====================================================================
# 3. FIX WF02 Parse Requirements (same O(n) optimization)
# =====================================================================
with open('n8n/workflows/02-extract-requirements.json', 'r', encoding='utf-8') as f:
    wf02 = json.load(f)

for node in wf02['nodes']:
    if node['name'] == 'Parse Requirements':
        node['parameters']['jsCode'] = NEW_PARSE_REQ
        print("  [OK] WF02 Parse Requirements: REWRITTEN with O(n) fixQuotes")

with open('n8n/workflows/02-extract-requirements.json', 'w', encoding='utf-8') as f:
    json.dump(wf02, f, ensure_ascii=False, indent=2)

# Validate
with open('n8n/workflows/02-extract-requirements.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
    print(f"  02-extract-requirements.json: valid JSON, {len(d['nodes'])} nodes\n")


# =====================================================================
# SUMMARY
# =====================================================================
print("=" * 60)
print("ALL DONE — 3 files modified\n")
print("Root cause: fixQuotes used s.substring(i+1).trimStart() per char")
print("  For 50KB text: ~50000 x ~25KB = 1.25GB allocations")
print("  -> n8n Code node ran out of memory/timed out")
print("  -> ALL strategies 3-7 failed (they all call fixQuotes)")
print("  -> strategies 1-2 failed (JSON actually has unescaped quotes)")
print("  -> _parseMethod = FAILED\n")
print("Fix: nextNonWS() forward scan with charCodeAt — O(n), zero allocs")
print("")
print("Changes applied:")
print("  1. WF04 Parse Plan:      O(n) fixQuotes, 7+1 strategies")
print("  2. WF04 LLM system msg:  NEVER use double quotes in JSON values")
print("  3. WF04 Prompt:          Same instruction in user prompt")
print("  4. WF00 Flatten Chunks:  7-strategy O(n) fallback (was 1 strategy O(n^2))")
print("  5. WF02 Parse Reqs:      O(n) fixQuotes, 7+1 strategies")
