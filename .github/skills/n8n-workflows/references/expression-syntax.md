# n8n Expression Syntax — Quick Reference

## Format

All expressions: `{{ expression }}`

## Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `$json` | Current node output | `{{ $json.email }}` |
| `$json.body` | Webhook request body | `{{ $json.body.name }}` |
| `$node["Name"].json` | Specific node output | `{{ $node["HTTP Request"].json.data }}` |
| `$now` | Current timestamp (Luxon) | `{{ $now.toFormat('yyyy-MM-dd') }}` |
| `$env.KEY` | Environment variable | `{{ $env.API_KEY }}` |

## Webhook Data Structure

```
$json = {
  headers: {...},
  params: {...},
  query: {...},
  body: {          ← USER DATA IS HERE
    name: "...",
    email: "..."
  }
}
```

Access: `{{ $json.body.name }}` (NOT `{{ $json.name }}`)

## Common Patterns

```javascript
// Nested fields
{{ $json.user.email }}
{{ $json.items[0].name }}

// Bracket notation (spaces)
{{ $json['field name'] }}
{{ $node["HTTP Request"].json.data }}

// Ternary
{{ $json.status === 'active' ? 'Yes' : 'No' }}

// Default value
{{ $json.email || 'none' }}

// String body (for httpRequest)
={{ JSON.stringify($json) }}
={{ JSON.stringify($('Node Name').first().json) }}
```

## Rules

1. Always `{{ }}` in node fields
2. NEVER `{{ }}` in Code nodes
3. Webhook data under `.body`
4. Quote node names: `$node["Name"]`
5. Case-sensitive node names

## In JSON Body Fields (httpRequest)

```
={{ JSON.stringify($json) }}
={{ JSON.stringify({ key: $json.value }) }}
```

## DateTime

```javascript
{{ $now.toFormat('yyyy-MM-dd') }}
{{ $now.plus({days: 7}).toISO() }}
{{ $now.minus({hours: 24}).toFormat('HH:mm') }}
```
