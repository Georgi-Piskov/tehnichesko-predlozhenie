# -*- coding: utf-8 -*-
"""Фаза 2: JWT auth + CORS заключване на WF00 orchestrator.

Промени:
1. Webhook: options.allowedOrigins = https://proceno.net (n8n хендълва OPTIONS preflight)
2. Нови ноди след Webhook: Check Auth (HTTP → Supabase rpc/get_my_profile с JWT
   от Authorization header) → Verify Access (Code: role check + възстановяване на
   оригиналния webhook item с binary) → IF Authorized → Init Job / Respond 403
3. Send Response: CORS * → https://proceno.net + Authorization в Allow-Headers
"""
import json

WF_PATH = r"E:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\00-orchestrator.json"
ORIGIN = "https://proceno.net"
SUPABASE_URL = "https://pxyncifjsyplsotpeopt.supabase.co"
ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InB4eW5jaWZqc3lwbHNvdHBlb3B0Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzMzNDIwODEsImV4cCI6MjA4ODkxODA4MX0.Gq28u9cusCOPyBg7NrQKW09ve96d6qlc0M8nEXl-z5I"

wf = json.load(open(WF_PATH, encoding="utf-8"))
nodes = {n["name"]: n for n in wf["nodes"]}

# --- 1. Webhook: allowedOrigins (preflight за Authorization header) ---
nodes["Webhook"]["parameters"].setdefault("options", {})["allowedOrigins"] = ORIGIN

# --- 2. Нови ноди ---
verify_js = """var resp = $json;
var p = resp;
if (Array.isArray(p)) p = p[0] || {};
// get_my_profile връща профила; при 401/грешка няма role
var role = (p && p.role) ? String(p.role) : '';
var authorized = role === 'admin' || role === 'business';
// Възстановяваме оригиналния webhook item (body + binary), HTTP нодът го замени
var wh = $('Webhook').first();
var out = Object.assign({}, wh.json, { _authRole: role, _authorized: authorized });
return [{ json: out, binary: wh.binary }];"""

check_auth = {
    "id": "auth1",
    "name": "Check Auth",
    "type": "n8n-nodes-base.httpRequest",
    "position": [150, 40],
    "parameters": {
        "method": "POST",
        "url": SUPABASE_URL + "/rest/v1/rpc/get_my_profile",
        "sendHeaders": True,
        "headerParameters": {
            "parameters": [
                {"name": "apikey", "value": ANON_KEY},
                {"name": "Authorization", "value": "={{ $json.headers.authorization || '' }}"},
                {"name": "Content-Type", "value": "application/json"},
            ]
        },
        "sendBody": True,
        "specifyBody": "json",
        "contentType": "json",
        "jsonBody": "{}",
        "options": {
            "timeout": 10000,
            "response": {"response": {"neverError": True}},
        },
    },
    "typeVersion": 4.2,
}

verify_access = {
    "id": "auth2",
    "name": "Verify Access",
    "type": "n8n-nodes-base.code",
    "position": [300, 40],
    "parameters": {"jsCode": verify_js},
    "typeVersion": 2,
}

if_authorized = {
    "id": "auth3",
    "name": "IF Authorized",
    "type": "n8n-nodes-base.if",
    "position": [450, 40],
    "parameters": {
        "conditions": {
            "options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
            "conditions": [
                {
                    "id": "authcond1",
                    "leftValue": "={{ $json._authorized }}",
                    "rightValue": True,
                    "operator": {"type": "boolean", "operation": "equals"},
                }
            ],
            "combinator": "and",
        }
    },
    "typeVersion": 2.2,
}

respond_403 = {
    "id": "auth4",
    "name": "Respond 403",
    "type": "n8n-nodes-base.respondToWebhook",
    "position": [600, 40],
    "parameters": {
        "respondWith": "json",
        "responseBody": "={{ JSON.stringify({ error: 'forbidden', message: 'Достъпът изисква Business акаунт в Proceno.' }) }}",
        "options": {
            "responseCode": 403,
            "responseHeaders": {
                "entries": [
                    {"name": "Access-Control-Allow-Origin", "value": ORIGIN},
                    {"name": "Access-Control-Allow-Headers", "value": "Content-Type, Authorization"},
                ]
            },
        },
    },
    "typeVersion": 1.1,
}

existing_ids = {n["id"] for n in wf["nodes"]}
for node in (check_auth, verify_access, if_authorized, respond_403):
    assert node["id"] not in existing_ids, f"duplicate id {node['id']}"
    wf["nodes"].append(node)

# --- 3. Пренасочване на connections: Webhook → Check Auth → Verify → IF → Init Job / 403 ---
conns = wf["connections"]
assert conns["Webhook"]["main"][0][0]["node"] == "Init Job"
conns["Webhook"]["main"][0] = [{"node": "Check Auth", "type": "main", "index": 0}]
conns["Check Auth"] = {"main": [[{"node": "Verify Access", "type": "main", "index": 0}]]}
conns["Verify Access"] = {"main": [[{"node": "IF Authorized", "type": "main", "index": 0}]]}
conns["IF Authorized"] = {
    "main": [
        [{"node": "Init Job", "type": "main", "index": 0}],   # TRUE
        [{"node": "Respond 403", "type": "main", "index": 0}],  # FALSE
    ]
}

# --- 4. Send Response: CORS заключване ---
entries = nodes["Send Response"]["parameters"]["options"]["responseHeaders"]["entries"]
for e in entries:
    if e["name"] == "Access-Control-Allow-Origin":
        e["value"] = ORIGIN
    if e["name"] == "Access-Control-Allow-Headers":
        e["value"] = "Content-Type, Authorization"

with open(WF_PATH, "w", encoding="utf-8") as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)

# Валидация
re_wf = json.load(open(WF_PATH, encoding="utf-8"))
names = [n["name"] for n in re_wf["nodes"]]
assert "Check Auth" in names and "IF Authorized" in names
print("OK:", len(re_wf["nodes"]), "nodes")
print("Webhook ->", re_wf["connections"]["Webhook"]["main"][0][0]["node"])
print("IF TRUE ->", re_wf["connections"]["IF Authorized"]["main"][0][0]["node"])
print("IF FALSE ->", re_wf["connections"]["IF Authorized"]["main"][1][0]["node"])
