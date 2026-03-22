# Editing n8n Workflow JSON Files — Safe Patterns

## The Problem

n8n workflow JSON files contain JavaScript code (`jsCode`) as JSON string values. This means:
- Newlines become `\n`
- Quotes become `\"`
- Backslashes become `\\`
- Any manual text replacement risks breaking the JSON

## The Solution: Python Scripts

Always use Python scripts to modify jsCode or system messages in workflow JSON files.

### Template: Modify jsCode

```python
import json

WORKFLOW_FILE = 'n8n/workflows/XX-workflow.json'
TARGET_NODE = 'Node Name'

with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
    wf = json.load(f)

# Define new code as a normal Python string
NEW_CODE = """var body = $json.body || $json;
var result = processData(body);
return [{ json: result }];"""

for node in wf['nodes']:
    if node['name'] == TARGET_NODE:
        old_len = len(node['parameters']['jsCode'])
        node['parameters']['jsCode'] = NEW_CODE
        new_len = len(node['parameters']['jsCode'])
        print(f"Updated {TARGET_NODE}: {old_len} -> {new_len} chars")

with open(WORKFLOW_FILE, 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)

# Validate
with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
    test = json.load(f)
print(f"Valid JSON: {len(test['nodes'])} nodes")
```

### Template: Modify System Message in chainLlm

```python
import json

WORKFLOW_FILE = 'n8n/workflows/XX-workflow.json'
TARGET_NODE = 'LLM Chain Node'

with open(WORKFLOW_FILE, 'r', encoding='utf-8') as f:
    wf = json.load(f)

NEW_SYSTEM_MSG = """# ROLE
You are an expert in...

# INSTRUCTIONS
1. Do this
2. Do that

# FORMAT
Return JSON only."""

for node in wf['nodes']:
    if node['name'] == TARGET_NODE:
        # CRITICAL: use messageValues, not values
        mv = node['parameters']['messages']['messageValues']
        old_msg = mv[0]['message']
        mv[0]['message'] = NEW_SYSTEM_MSG
        print(f"Updated system message: {len(old_msg)} -> {len(NEW_SYSTEM_MSG)} chars")

with open(WORKFLOW_FILE, 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)
```

### Template: Modify maxTokens

```python
for node in wf['nodes']:
    if node['name'] == 'Claude Sonnet':
        node['parameters']['options']['maxTokens'] = 24000
```

### Template: Find and Inspect Nodes

```python
import json

with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    wf = json.load(f)

for node in wf['nodes']:
    if 'jsCode' in node.get('parameters', {}):
        code = node['parameters']['jsCode']
        print(f"=== {node['name']} ({len(code)} chars) ===")
        print(code[:200])
        print()
```

## Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Using `replace_string_in_file` on jsCode | Use Python script instead |
| Triple-quoted strings in `python -c` | Write separate .py files |
| System message field name | `messages.messageValues`, NOT `messages.values` |
| Unicode smart quotes in Bulgarian | `json.dumps()` handles encoding automatically |
| File encoding | Always use `encoding='utf-8'` |

## Validation Checklist

After every modification:
1. `json.load()` the file — confirms valid JSON
2. Count nodes — confirms no data loss
3. Check the specific node's jsCode/message length — confirms the edit applied
4. Run assertions on key strings in the modified content
