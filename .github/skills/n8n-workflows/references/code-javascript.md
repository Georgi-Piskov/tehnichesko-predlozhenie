# n8n Code Node JavaScript — Detailed Reference

## Mode Selection

### Run Once for All Items (Default, Recommended)

- Code executes **once** regardless of input count
- Data access: `$input.all()` returns array of all items
- Best for: aggregation, filtering, batch processing, transformations
- Performance: faster for multiple items

```javascript
var items = $input.all();
var total = 0;
for (var i = 0; i < items.length; i++) {
  total += items[i].json.amount || 0;
}
return [{ json: { total: total, count: items.length } }];
```

### Run Once for Each Item

- Code executes **separately** for each input item
- Data access: `$input.item` returns current item
- Best for: per-item validation, independent API calls
- Performance: slower for large datasets

```javascript
var item = $input.item;
return [{ json: { ...item.json, processed: true } }];
```

**Decision**: Need multiple items? → All Items. Each item independent? → Each Item. Not sure? → All Items.

---

## Data Access

### $input methods

| Method | Mode | Returns |
|--------|------|---------|
| `$input.all()` | All Items | Array of all items |
| `$input.first()` | All Items | First item only |
| `$input.item` | Each Item | Current item |

### $() — Reference Specific Nodes

```javascript
// Get first output from named node
var data = $('Node Name').first().json;

// Get all outputs
var allItems = $('Node Name').all();

// Access specific field
var email = $('Webhook').first().json.body.email;
```

### $getWorkflowStaticData()

Persists data across loop iterations within a single execution:

```javascript
var sd = $getWorkflowStaticData('global');
sd.counter = (sd.counter || 0) + 1;
sd.results = sd.results || [];
sd.results.push($json.result);
```

---

## Built-in Functions

### $helpers.httpRequest()

```javascript
var response = await $helpers.httpRequest({
  method: 'POST',
  url: 'https://api.example.com/data',
  headers: {
    'Authorization': 'Bearer ' + token,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({ key: 'value' })
});
return [{ json: { data: response } }];
```

### DateTime (Luxon)

```javascript
var now = DateTime.now();
var formatted = now.toFormat('yyyy-MM-dd');
var tomorrow = now.plus({ days: 1 });
var lastWeek = now.minus({ weeks: 1 });
```

### $jmespath()

```javascript
var data = $input.first().json;
var adults = $jmespath(data, 'users[?age >= `18`]');
var names = $jmespath(data, 'users[*].name');
```

---

## Error Patterns & Solutions

### #1: Empty Code or Missing Return

```javascript
// ❌ Missing return
var items = $input.all();
// processing...

// ✅ Always return
var items = $input.all();
return items.map(function(item) { return { json: item.json }; });
```

### #2: Expression Syntax in Code

```javascript
// ❌ Wrong — n8n expression in Code node
var value = "{{ $json.field }}";

// ✅ Correct — direct JS access
var value = $input.first().json.field;
```

### #3: Incorrect Return Wrapper

```javascript
// ❌ Object instead of array
return { json: { result: 'ok' } };

// ✅ Array wrapper
return [{ json: { result: 'ok' } }];
```

### #4: Missing Null Checks

```javascript
// ❌ Crashes if nested field missing
var value = item.json.user.email;

// ✅ Safe access
var user = item.json.user || {};
var value = user.email || '';
```

### #5: Webhook Body Nesting

```javascript
// ❌ Webhook data at root
var email = $json.email;

// ✅ Webhook data under .body
var email = $json.body.email;
```

---

## Production Patterns

### 1. Robust JSON Parse from LLM Output

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

var raw = sanitize(($json.text || '').trim());
var result = tryParse(raw) || tryParse(extractJson(raw));
if (!result) {
  result = { error: true, _raw: raw.substring(0, 5000) };
}
return [{ json: result }];
```

### 2. Data Aggregation Across Items

```javascript
var items = $input.all();
var grouped = {};
for (var i = 0; i < items.length; i++) {
  var key = items[i].json.category || 'other';
  if (!grouped[key]) grouped[key] = [];
  grouped[key].push(items[i].json);
}
return [{ json: { groups: grouped } }];
```

### 3. Flatten Nested Structures

```javascript
function flatten(arr, parentId) {
  var result = [];
  for (var i = 0; i < arr.length; i++) {
    var item = arr[i];
    if (item.children && item.children.length > 0) {
      var nested = flatten(item.children, item.id);
      for (var j = 0; j < nested.length; j++) result.push(nested[j]);
    } else {
      result.push({ id: item.id, parentId: parentId, title: item.title });
    }
  }
  return result;
}
```

### 4. String Truncation with Safety

```javascript
var text = body.fullText || body.specificationText || body.documentationText || '';
if (text.length > 60000) text = text.substring(0, 60000);
```
