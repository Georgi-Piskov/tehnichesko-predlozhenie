# -*- coding: utf-8 -*-
"""Фаза 3: n8n промени.

WF09 (09-status-api.json):
  Store Status → връща и реда за Supabase → нов HTTP нод "Mirror to Supabase"
  (upsert в tp_jobs през service_role Header Auth credential — конфигурира се
  ръчно в n8n, НЕ е в repo-то).

WF00 (00-orchestrator.json):
  - Verify Access: добавя _authUserId от профила
  - Init Job: включва userId в output-а
  - Status: Init: праща и userId (останалите status ъпдейти не го пращат —
    PostgREST merge-duplicates не пипа липсващи колони)
  - Pipeline Complete: statusPayload.result.text → пълният документ отива
    в колоната document (отделно поле в payload)
  - Премахва Save to Google Drive node + connection
"""
import json

P00 = r"E:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\00-orchestrator.json"
P09 = r"E:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\09-status-api.json"
SUPABASE_URL = "https://pxyncifjsyplsotpeopt.supabase.co"

# ============================================================
# WF09
# ============================================================
wf9 = json.load(open(P09, encoding="utf-8"))
n9 = {n["name"]: n for n in wf9["nodes"]}

store_js = """const body = $json.body || $json;
const jobId = body.jobId;
if (!jobId) return [];

const sd = $getWorkflowStaticData('global');
if (!sd.jobs) sd.jobs = {};

// If result is included, store it
if (body.result) {
  sd.jobs[jobId] = {
    ...sd.jobs[jobId],
    ...body,
    completedAt: new Date().toISOString()
  };
} else {
  sd.jobs[jobId] = {
    ...(sd.jobs[jobId] || {}),
    status: body.status || 'processing',
    phase: body.phase || 'init',
    progress: body.progress || 0,
    message: body.message || '',
    updatedAt: new Date().toISOString()
  };
}

// === Proceno Phase 3: подготвя ред за tp_jobs upsert (Supabase) ===
var row = {
  job_id: jobId,
  status: body.status || 'processing',
  phase: body.phase || 'init',
  progress: body.progress || 0,
  message: body.message || '',
  updated_at: new Date().toISOString()
};
if (body.userId) row.user_id = body.userId;
if (body.result) {
  var r = Object.assign({}, body.result);
  if (r.text) { row.document = r.text; delete r.text; }
  row.result = r;
}
return [{ json: { ok: true, supabaseRow: row } }];"""

n9["Store Status"]["parameters"]["jsCode"] = store_js

mirror = {
    "id": "sb-mirror",
    "name": "Mirror to Supabase",
    "type": "n8n-nodes-base.httpRequest",
    "position": [600, 0],
    "parameters": {
        "method": "POST",
        "url": SUPABASE_URL + "/rest/v1/tp_jobs?on_conflict=job_id",
        "authentication": "genericCredentialType",
        "genericAuthType": "httpHeaderAuth",
        "sendHeaders": True,
        "headerParameters": {
            "parameters": [
                {"name": "Prefer", "value": "resolution=merge-duplicates"},
                {"name": "Content-Type", "value": "application/json"},
            ]
        },
        "sendBody": True,
        "specifyBody": "json",
        "contentType": "json",
        "jsonBody": "={{ JSON.stringify($json.supabaseRow) }}",
        "options": {
            "timeout": 15000,
            "response": {"response": {"neverError": True}},
        },
    },
    "credentials": {
        "httpHeaderAuth": {"id": "CONFIGURE_IN_N8N", "name": "Supabase TP service_role (apikey header)"}
    },
    "typeVersion": 4.2,
    "onError": "continueRegularOutput",
}
assert "Mirror to Supabase" not in n9
wf9["nodes"].append(mirror)
wf9["connections"]["Store Status"] = {"main": [[{"node": "Mirror to Supabase", "type": "main", "index": 0}]]}

json.dump(wf9, open(P09, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
json.load(open(P09, encoding="utf-8"))
print("WF09 OK:", len(wf9["nodes"]), "nodes")

# ============================================================
# WF00
# ============================================================
wf0 = json.load(open(P00, encoding="utf-8"))
n0 = {n["name"]: n for n in wf0["nodes"]}

# 1. Verify Access — добавя _authUserId
va = n0["Verify Access"]["parameters"]["jsCode"]
old = "var out = Object.assign({}, wh.json, { _authRole: role, _authorized: authorized });"
new = ("var userId = (p && p.id) ? String(p.id) : '';\n"
       "var out = Object.assign({}, wh.json, { _authRole: role, _authUserId: userId, _authorized: authorized });")
assert old in va
n0["Verify Access"]["parameters"]["jsCode"] = va.replace(old, new)

# 2. Init Job — userId в output
ij = n0["Init Job"]["parameters"]["jsCode"]
old = "return [{\n  json: {\n    jobId: jobId,"
new = "return [{\n  json: {\n    jobId: jobId,\n    userId: $json._authUserId || '',"
assert old in ij
n0["Init Job"]["parameters"]["jsCode"] = ij.replace(old, new)

# 3. Status: Init — праща userId
si = n0["Status: Init"]["parameters"]
old = "JSON.stringify({ jobId: $json.jobId, status: 'processing'"
new = "JSON.stringify({ jobId: $json.jobId, userId: $json.userId, status: 'processing'"
assert old in si["jsonBody"]
si["jsonBody"] = si["jsonBody"].replace(old, new)

# 4. Премахва Save to Google Drive
wf0["nodes"] = [n for n in wf0["nodes"] if n["name"] != "Save to Google Drive"]
pc = wf0["connections"]["Pipeline Complete"]["main"][0]
wf0["connections"]["Pipeline Complete"]["main"][0] = [
    t for t in pc if t["node"] != "Save to Google Drive"
]

json.dump(wf0, open(P00, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
re0 = json.load(open(P00, encoding="utf-8"))
names = [n["name"] for n in re0["nodes"]]
assert "Save to Google Drive" not in names
print("WF00 OK:", len(re0["nodes"]), "nodes; Pipeline Complete ->",
      [t["node"] for t in re0["connections"]["Pipeline Complete"]["main"][0]])
