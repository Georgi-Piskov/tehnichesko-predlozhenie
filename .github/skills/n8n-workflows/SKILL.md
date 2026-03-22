---
name: n8n-workflows
description: 'Expert guidance for building and editing n8n workflows — Code node JavaScript, expression syntax, node configuration, JSON workflow file editing, and validation error fixing. Use when: writing n8n Code node JavaScript; editing workflow JSON files; fixing n8n expression syntax; configuring n8n nodes; troubleshooting n8n validation errors; working with chainLlm or AI nodes; modifying jsCode embedded in JSON.'
---

# n8n Workflow Development

Expert skill for building production-ready n8n workflows. Covers Code node JavaScript, expression syntax, node configuration, workflow JSON editing, and validation.

---

## CRITICAL: Editing jsCode in Workflow JSON Files

**jsCode is stored as a JSON string value** inside workflow JSON → 2 levels of escaping.

### NEVER Edit jsCode Manually via Text Replace

The `jsCode` field in workflow JSON is a single-line JSON string with all newlines as `\n`, all quotes escaped as `\"`, etc. Manual text replacement WILL break the JSON.

### ALWAYS Use a Python Script

```python
import json

with open('n8n/workflows/XX-workflow.json', 'r', encoding='utf-8') as f:
    wf = json.load(f)

# Define JS code as a normal Python string (no JSON escaping needed)
NEW_CODE = """var items = $input.all();
var result = [];
for (var i = 0; i < items.length; i++) {
  result.push({ json: { processed: true } });
}
return result;"""

for node in wf['nodes']:
    if node['name'] == 'Target Node Name':
        node['parameters']['jsCode'] = NEW_CODE

with open('n8n/workflows/XX-workflow.json', 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)

# Validate
with open('n8n/workflows/XX-workflow.json', 'r', encoding='utf-8') as f:
    json.load(f)  # Will throw if invalid
```

### System Messages in chainLlm Nodes

System messages use `messages.messageValues` (NOT `messages.values`):

```python
for node in wf['nodes']:
    if node['name'] == 'LLM Node Name':
        # Access system message
        msg = node['parameters']['messages']['messageValues'][0]['message']
        # Update it
        node['parameters']['messages']['messageValues'][0]['message'] = NEW_MSG
```

### Unicode in Bulgarian Text

Bulgarian smart quotes `„"` (U+201C/U+201D/U+201E) cause LLMs to produce broken JSON. Always sanitize at input AND output boundaries.

---

## Code Node JavaScript

### Essential Rules

1. **Use `var`** instead of `const`/`let` (safer in n8n runtime)
2. **Return format**: Must return `[{json: {...}}]`
3. **Webhook data**: Under `$json.body` (not `$json` directly)
4. **Mode**: "Run Once for All Items" is default and recommended

### Data Access Patterns

```javascript
// All items from previous node
var items = $input.all();

// First item only
var first = $input.first();

// Current item (Each Item mode only)
var item = $input.item;

// Reference specific node by name
var data = $('Node Name').first().json;
var allFromNode = $('Node Name').all();

// Workflow static data (persists across loop iterations)
var sd = $getWorkflowStaticData('global');
```

### Correct Return Formats

```javascript
// ✅ Single result
return [{ json: { field: value } }];

// ✅ Multiple results (creates multiple items for next node)
return items.map(function(item) {
  return { json: { id: item.json.id, processed: true } };
});

// ✅ Empty (skip)
return [];

// ❌ WRONG: Object without array
return { json: { field: value } };

// ❌ WRONG: Missing json wrapper
return [{ field: value }];
```

### Common Patterns

```javascript
// Filter + transform
var items = $input.all();
var result = [];
for (var i = 0; i < items.length; i++) {
  if (items[i].json.status === 'active') {
    result.push({ json: { id: items[i].json.id } });
  }
}
return result;

// Aggregate
var items = $input.all();
var total = 0;
for (var i = 0; i < items.length; i++) {
  total += items[i].json.amount || 0;
}
return [{ json: { total: total, count: items.length } }];

// HTTP request inside Code node
var response = await $helpers.httpRequest({
  method: 'GET',
  url: 'https://api.example.com/data',
  headers: { 'Authorization': 'Bearer ' + token }
});
return [{ json: { data: response } }];
```

### Error Prevention

| Mistake | Fix |
|---------|-----|
| No return statement | Always end with `return [...]` |
| Expression syntax in code | Use `$json.field` not `{{ $json.field }}` |
| Object instead of array | Wrap in `[...]` |
| Missing null check | Use `item.json.field \|\| ''` or check before access |
| Webhook data at root | Access via `$json.body.field` |

---

## Expression Syntax (Outside Code Nodes)

### Format

All dynamic content uses double curly braces: `{{ expression }}`

```javascript
// ✅ Correct
{{ $json.email }}
{{ $json.body.name }}         // Webhook data
{{ $node["HTTP Request"].json.data }}

// ❌ Wrong
$json.email                   // Missing braces
{$json.email}                 // Single braces
{{ $json.name }}              // Wrong for webhook (need .body)
```

### Core Variables

| Variable | Use |
|----------|-----|
| `$json` | Current node data |
| `$json.body` | Webhook request body |
| `$node["Name"].json` | Data from named node |
| `$now` | Current timestamp (Luxon) |
| `$env.VAR` | Environment variable |

### Key Rules

1. **Always use `{{ }}`** for expressions in node fields
2. **NEVER use `{{ }}`** in Code nodes — use direct JS access
3. **Webhook data** is under `.body`
4. **Quote node names** with spaces: `$node["HTTP Request"]`
5. **Case-sensitive** node names

---

## Node Configuration

### Operation-Aware Configuration

Different operations require different fields:

```javascript
// HTTP Request: GET needs no body
{ "method": "GET", "url": "...", "authentication": "none" }

// HTTP Request: POST needs sendBody + body
{
  "method": "POST",
  "url": "...",
  "sendBody": true,
  "body": { "contentType": "json", "content": {...} }
}
```

### Property Dependencies (displayOptions)

Fields appear/disappear based on other values:
- `sendBody` → controls `body` visibility
- `method` → controls which fields show
- `resource` + `operation` → determine required fields

### Common Node Patterns

**HTTP Request**: method, url, authentication, sendBody, body
**Webhook**: httpMethod, path, responseMode
**Code**: jsCode, mode (runOnceForAllItems/runOnceForEachItem)
**chainLlm**: text (prompt), messages.messageValues (system), promptType
**IF**: conditions with type, operation, value1, value2
**Set**: assignments (replace mode)

### AI Workflow Nodes

**chainLlm** (LLM Chain):
- `text`: The user prompt (supports expressions with `={{ }}`)
- `messages.messageValues[0]`: System message (`{type: "system", message: "..."}`)
- `promptType`: Usually `"define"`
- Connected to an LLM model node via `ai_languageModel` connection type

**LLM Model** (e.g., lmChatOpenRouter):
- `model`: Model identifier (e.g., `"anthropic/claude-sonnet-4"`)
- `options.maxTokens`: Output token limit
- `options.temperature`: Randomness (0.0-1.0)
- Connected to chainLlm via `ai_languageModel` connection

---

## JSON Parsing Robustness

When parsing LLM JSON output, use multiple fallback strategies:

```javascript
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
  if (start === -1 || end === -1) return s;
  return c.substring(start, end + 1);
}

function fixCommon(s) {
  return s.replace(/,\s*([\]\}])/g, '$1');
}

function fixNewlines(s) {
  // Fix unescaped newlines inside JSON string values
  var out = '', inStr = false, escaped = false;
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

function repairTruncated(s) {
  // Close open brackets/braces when LLM output was cut off
  var stack = [], inStr = false, escaped = false;
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
```

### Parse Strategy (5 attempts)

1. Direct `JSON.parse` after sanitizing smart quotes
2. Extract JSON block (strip markdown fences), fix trailing commas
3. + Fix unescaped newlines in strings
4. + Fix unescaped quotes (heuristic)
5. + Repair truncated JSON (close open brackets)

---

## Workflow Connection Types

```json
{
  "connections": {
    "Source Node": {
      "main": [[{"node": "Target Node", "type": "main", "index": 0}]]
    },
    "LLM Model": {
      "ai_languageModel": [[{"node": "chainLlm Node", "type": "ai_languageModel", "index": 0}]]
    }
  }
}
```

### Connection Types

| Type | Use |
|------|-----|
| `main` | Standard data flow between nodes |
| `ai_languageModel` | LLM model → AI chain node |
| `ai_tool` | Tool → AI Agent node |
| `ai_memory` | Memory → AI Agent node |
| `ai_outputParser` | Output parser → AI chain |

---

## Workflow JSON Structure

```json
{
  "name": "Workflow Name",
  "nodes": [
    {
      "id": "unique-id",
      "name": "Display Name",
      "type": "n8n-nodes-base.code",
      "position": [x, y],
      "parameters": { "jsCode": "..." },
      "typeVersion": 2
    }
  ],
  "connections": { ... },
  "settings": { "executionOrder": "v1" }
}
```

### Webhook-Based Sub-Workflows

Pattern used in this project: Main orchestrator calls sub-workflows via HTTP:

```json
{
  "type": "n8n-nodes-base.httpRequest",
  "parameters": {
    "method": "POST",
    "url": "https://n8n-host/webhook/step-name",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "={{ JSON.stringify($json) }}",
    "options": { "timeout": 180000 }
  }
}
```

Sub-workflow receives via Webhook node, processes, returns via Respond to Webhook.

---

## Quick Reference Checklist

Before deploying workflow changes:

- [ ] **jsCode edited via Python script** (never manual text replace)
- [ ] **JSON validated** after editing (`json.load()`)
- [ ] **Return format correct** in all Code nodes (`[{json: {...}}]`)
- [ ] **Webhook data** accessed via `.body`
- [ ] **Node names** match exactly (case-sensitive)
- [ ] **System messages** use `messages.messageValues` (not `values`)
- [ ] **Using `var`** instead of `const`/`let` in Code nodes
- [ ] **Expressions** use `{{ }}` in node fields, NOT in Code nodes
- [ ] **Parse nodes** have multiple fallback strategies
