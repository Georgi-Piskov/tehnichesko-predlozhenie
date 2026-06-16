# -*- coding: utf-8 -*-
"""WF00 + WF09 — cost tracking (issue #135). БЕЗОПАСЕН дизайн.

КРИТИЧНО: пътят за запазване на документа (Pipeline Complete → Status: Complete)
остава НЕПРОМЕНЕН. Cost tracking е изцяло ПАРАЛЕЛЕН страничен клон — ако се счупи,
документът вече е запазен и единствено cost_usd остава null.

WF00:
  Restore Init → [..., Usage Start]               (нов dead-end: GET /credits → staticData baseline)
  Usage Start → Store Usage Start
  Pipeline Complete → [Status: Complete, Usage End]  (Usage End = НОВ паралелен клон)
  Usage End → Compute Cost → Status: Cost          (GET /credits в края → cost_usd → отделен update)
  Pipeline Complete: + credits_reserved в statusPayload (синхронно от Reserve нода — безопасно)

WF09 Store Status: ако body.cost_usd/credits_reserved → пише ги в supabaseRow (→ tp_jobs).
  Cost update праща status:'completed' → merge-duplicates upsert, БЕЗ да сваля статуса.

Mgmt key = n8n credential (НЕ в JSON). GET /credits е БЕЗПЛАТНО (метадата).
Всички cost HTTP ноди: neverError + onError continueRegularOutput. Идемпотентно.
"""
import json
import sys
import time
import urllib.request

P00 = r"E:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\00-orchestrator.json"
P09 = r"E:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\09-status-api.json"
N8N_BASE = "https://n8n.simeontsvetanovn8nworkflows.site"
WF00_ID = "J1xMp1KQF8Oz70WH"
WF09_ID = "5OrUJW2C87lA5nEF"
CRED_ID = "m178K0X375Ulvip9"
CRED_NAME = "OpenRouter Mgmt (cost tracking)"
CREDITS_URL = "https://openrouter.ai/api/v1/credits"

USAGE_START = "Usage Start"
STORE_START = "Store Usage Start"
USAGE_END = "Usage End"
COMPUTE_COST = "Compute Cost"
STATUS_COST = "Status: Cost"
UPDATE_STATUS_URL = f"{N8N_BASE}/webhook/internal/update-status"

ALLOWED_SETTINGS = {
    "saveExecutionProgress", "saveManualExecutions", "saveDataErrorExecution",
    "saveDataSuccessExecution", "executionTimeout", "errorWorkflow",
    "timezone", "executionOrder",
}


def credits_node(name, node_id, pos):
    return {
        "id": node_id, "name": name, "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2, "position": pos, "onError": "continueRegularOutput",
        "parameters": {
            "method": "GET", "url": CREDITS_URL,
            "authentication": "genericCredentialType", "genericAuthType": "httpHeaderAuth",
            "options": {"timeout": 10000, "response": {"response": {"neverError": True}}},
        },
        "credentials": {"httpHeaderAuth": {"id": CRED_ID, "name": CRED_NAME}},
    }


def patch_wf00(wf):
    names = {n["name"] for n in wf["nodes"]}
    if USAGE_START in names:
        print("  WF00: cost nodes вече съществуват — пропускам.")
        return False

    # 1. Baseline клон
    wf["nodes"].append(credits_node(USAGE_START, "n_usage_start", [720, 360]))
    wf["nodes"].append({
        "id": "n_store_usage_start", "name": STORE_START,
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [900, 360],
        "parameters": {"jsCode":
            "var sd = $getWorkflowStaticData('global');\n"
            "sd.usage = sd.usage || {};\n"
            "var jobId = $('Init Job').first().json.jobId;\n"
            "var u = ($json && $json.data && $json.data.total_usage != null) ? parseFloat($json.data.total_usage) : null;\n"
            "if (jobId && u != null && !isNaN(u)) sd.usage[jobId] = u;\n"
            "return [{ json: { ok: true } }];\n"
        },
    })

    # 2. Краен клон (паралелно с Status: Complete)
    wf["nodes"].append(credits_node(USAGE_END, "n_usage_end", [500, 1300]))
    wf["nodes"].append({
        "id": "n_compute_cost", "name": COMPUTE_COST,
        "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [680, 1300],
        "parameters": {"jsCode":
            "var sd = $getWorkflowStaticData('global');\n"
            "var jobId = $('Init Job').first().json.jobId;\n"
            "var startUsage = (sd.usage && sd.usage[jobId] != null) ? sd.usage[jobId] : null;\n"
            "var endUsage = null;\n"
            "try {\n"
            "  var ue = $('Usage End').first().json;\n"
            "  if (ue && ue.data && ue.data.total_usage != null) endUsage = parseFloat(ue.data.total_usage);\n"
            "} catch (e) {}\n"
            "var costUsd = null;\n"
            "if (startUsage != null && endUsage != null && endUsage >= startUsage) {\n"
            "  costUsd = Math.round((endUsage - startUsage) * 10000) / 10000;\n"
            "}\n"
            "if (sd.usage && jobId) delete sd.usage[jobId];\n"
            "return [{ json: { statusPayload: {\n"
            "  jobId: jobId, status: 'completed', phase: 'completed', progress: 100,\n"
            "  message: 'Готово!', cost_usd: costUsd\n"
            "} } }];\n"
        },
    })
    wf["nodes"].append({
        "id": "n_status_cost", "name": STATUS_COST,
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [860, 1300],
        "onError": "continueRegularOutput",
        "parameters": {
            "method": "POST", "url": UPDATE_STATUS_URL,
            "sendBody": True, "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify($json.statusPayload) }}",
            "options": {"timeout": 10000, "response": {"response": {"neverError": True}}},
        },
    })

    # 3. Pipeline Complete: добави credits_reserved (синхронно от Reserve нода)
    pc = next(n for n in wf["nodes"] if n["name"] == "Pipeline Complete")
    js = pc["parameters"]["jsCode"]
    marker = "    result: {"
    inject = (
        "    credits_reserved: (function(){ try { var rc = $('Reserve Credits').first().json; "
        "return (rc && rc.cost != null) ? rc.cost : null; } catch(e){ return null; } })(),\n"
        + marker
    )
    pc["parameters"]["jsCode"] = js.replace(marker, inject, 1)

    # 4. Connections
    c = wf["connections"]
    c["Restore Init"]["main"][0].append({"node": USAGE_START, "type": "main", "index": 0})
    c[USAGE_START] = {"main": [[{"node": STORE_START, "type": "main", "index": 0}]]}
    c["Pipeline Complete"]["main"][0].append({"node": USAGE_END, "type": "main", "index": 0})
    c[USAGE_END] = {"main": [[{"node": COMPUTE_COST, "type": "main", "index": 0}]]}
    c[COMPUTE_COST] = {"main": [[{"node": STATUS_COST, "type": "main", "index": 0}]]}
    print("  WF00: baseline + краен cost клон (паралелен); save-път НЕПРОМЕНЕН.")
    return True


def patch_wf09(wf):
    store = next(n for n in wf["nodes"] if n["name"] == "Store Status")
    js = store["parameters"]["jsCode"]
    if "cost_usd" in js:
        print("  WF09: вече патчнат — пропускам.")
        return False
    anchor = "return [{ json: { ok: true, supabaseRow: row } }];"
    inject = (
        "if (body.cost_usd != null) row.cost_usd = body.cost_usd;\n"
        "if (body.credits_reserved != null) row.credits_reserved = body.credits_reserved;\n"
        + anchor
    )
    store["parameters"]["jsCode"] = js.replace(anchor, inject)
    print("  WF09: Store Status пише cost_usd + credits_reserved.")
    return True


def _env():
    import pathlib
    env = {}
    for line in pathlib.Path(r"E:\VISUAL STUDIO\PUBLIC PROCUREMENT VER.2\.env").read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            env[k.strip()] = v.strip()
    return env


def _api(method, path, key, body=None):
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(f"{N8N_BASE}/api/v1/{path}", data=data, method=method,
                                 headers={"X-N8N-API-KEY": key, "Accept": "application/json",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:400]}")
        raise


def deploy_live(wf_id, patch_fn):
    import pathlib
    key = _env()["N8N_API_KEY"]
    live = _api("GET", f"workflows/{wf_id}", key)
    ts = time.strftime("%Y%m%d_%H%M%S")
    bdir = pathlib.Path(r"E:\VISUAL STUDIO\PUBLIC PROCUREMENT VER.2")
    (bdir / f"_wf_{wf_id}_backup_{ts}.json").write_text(
        json.dumps(live, ensure_ascii=False, indent=2), encoding="utf-8")
    if not patch_fn(live):
        print(f"  {wf_id}: без промяна.")
        return
    clean = {k: v for k, v in live.get("settings", {}).items() if k in ALLOWED_SETTINGS}
    _api("PUT", f"workflows/{wf_id}", key, {
        "name": live["name"], "nodes": live["nodes"],
        "connections": live["connections"], "settings": clean})
    print(f"  {wf_id}: PUT OK ({len(live['nodes'])} нода).")


def main():
    wf00 = json.load(open(P00, encoding="utf-8"))
    if patch_wf00(wf00):
        json.dump(wf00, open(P00, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        json.load(open(P00, encoding="utf-8"))
        print("  WF00 локален JSON записан.")
    wf09 = json.load(open(P09, encoding="utf-8"))
    if patch_wf09(wf09):
        json.dump(wf09, open(P09, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        json.load(open(P09, encoding="utf-8"))
        print("  WF09 локален JSON записан.")

    if "--live" in sys.argv:
        print("\n--- LIVE DEPLOY ---")
        deploy_live(WF00_ID, patch_wf00)
        deploy_live(WF09_ID, patch_wf09)
    else:
        print("\n(без --live — само локални файлове)")
    print("DONE")


if __name__ == "__main__":
    main()
