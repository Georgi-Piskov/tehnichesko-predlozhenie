# -*- coding: utf-8 -*-
"""WF00 cost delivery FIX (issue #135).

Проблем: cost_usd/credits_reserved се пращаха през WF09 (update-status webhook → Store Status
→ Mirror to Supabase upsert на ЦЕЛИЯ ред). При race с финалния document upsert (идват в
~същата секунда) merge-duplicates презаписва cost полетата → губят се.

Фикс: Compute Cost праща И двете (cost_usd + credits_reserved) към НОВ нод
'Write Cost (PATCH)' — директен PostgREST PATCH само на 2-те колони
(?job_id=eq.X, body {cost_usd, credits_reserved}). PATCH на конкретни колони не презаписва
document/status → няма race. Status: Cost (старият WF09 hop) се махва.

Mirror auth модел: директни headers apikey + Authorization: Bearer <service key> (както Mirror).
Идемпотентно. --live за deploy.
"""
import json
import pathlib
import sys
import time
import urllib.request

P00 = r"E:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\00-orchestrator.json"
N8N_BASE = "https://n8n.simeontsvetanovn8nworkflows.site"
WF00_ID = "J1xMp1KQF8Oz70WH"
SUPA = "https://pxyncifjsyplsotpeopt.supabase.co"
WRITE_COST = "Write Cost (PATCH)"
STATUS_COST = "Status: Cost"

ALLOWED_SETTINGS = {
    "saveExecutionProgress", "saveManualExecutions", "saveDataErrorExecution",
    "saveDataSuccessExecution", "executionTimeout", "errorWorkflow",
    "timezone", "executionOrder",
}


def _env():
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


def patch_wf00(wf, srk):
    names = {n["name"] for n in wf["nodes"]}
    if WRITE_COST in names:
        print("  Write Cost (PATCH) вече съществува — пропускам.")
        return False

    # 1. Compute Cost — праща И credits_reserved (взима от Reserve нода), към PATCH формат
    cc = next(n for n in wf["nodes"] if n["name"] == "Compute Cost")
    cc["parameters"]["jsCode"] = (
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
        "var creditsReserved = null;\n"
        "try {\n"
        "  var rc = $('Reserve Credits').first().json;\n"
        "  if (rc && rc.cost != null) creditsReserved = rc.cost;\n"
        "} catch (e) {}\n"
        "if (sd.usage && jobId) delete sd.usage[jobId];\n"
        "// PATCH body — само cost колоните (null се пропуска от PostgREST? не — затова филтрираме)\n"
        "var patch = {};\n"
        "if (costUsd != null) patch.cost_usd = costUsd;\n"
        "if (creditsReserved != null) patch.credits_reserved = creditsReserved;\n"
        "return [{ json: { jobId: jobId, patch: patch, hasData: Object.keys(patch).length > 0 } }];\n"
    )

    # 2. Нов нод Write Cost (PATCH) — директен PostgREST PATCH само на cost колоните
    wf["nodes"].append({
        "id": "n_write_cost", "name": WRITE_COST,
        "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [1040, 1300],
        "onError": "continueRegularOutput",
        "parameters": {
            "method": "PATCH",
            "url": "={{ '" + SUPA + "/rest/v1/tp_jobs?job_id=eq.' + $json.jobId }}",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "apikey", "value": srk},
                {"name": "Authorization", "value": f"Bearer {srk}"},
                {"name": "Content-Type", "value": "application/json"},
                {"name": "Prefer", "value": "return=minimal"},
            ]},
            "sendBody": True, "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify($json.patch) }}",
            "options": {"timeout": 15000, "response": {"response": {"neverError": True}}},
        },
    })

    # 3. Connections: Compute Cost → Write Cost (PATCH); махни Status: Cost
    c = wf["connections"]
    c["Compute Cost"] = {"main": [[{"node": WRITE_COST, "type": "main", "index": 0}]]}
    # Махни стария Status: Cost нод + connection
    wf["nodes"] = [n for n in wf["nodes"] if n["name"] != STATUS_COST]
    c.pop(STATUS_COST, None)
    print("  Compute Cost → Write Cost (PATCH); Status: Cost премахнат.")
    return True


def main():
    env = _env()
    srk = env["SUPABASE_SERVICE_ROLE_KEY"]
    key = env["N8N_API_KEY"]

    if "--live" in sys.argv:
        live = _api("GET", f"workflows/{WF00_ID}", key)
        ts = time.strftime("%Y%m%d_%H%M%S")
        pathlib.Path(rf"E:\VISUAL STUDIO\PUBLIC PROCUREMENT VER.2\_wf00_precostfix_backup_{ts}.json").write_text(
            json.dumps(live, ensure_ascii=False, indent=2), encoding="utf-8")
        if patch_wf00(live, srk):
            clean = {k: v for k, v in live.get("settings", {}).items() if k in ALLOWED_SETTINGS}
            _api("PUT", f"workflows/{WF00_ID}", key, {
                "name": live["name"], "nodes": live["nodes"],
                "connections": live["connections"], "settings": clean})
            print(f"  LIVE PUT OK ({len(live['nodes'])} нода).")
        # СЛЕД live deploy: запиши локалния файл с PLACEHOLDER (git safety — TP repo е публичен)
        local = json.load(open(P00, encoding="utf-8"))
        if patch_wf00(local, "SERVICE_KEY_PLACEHOLDER_SET_IN_N8N"):
            json.dump(local, open(P00, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            json.load(open(P00, encoding="utf-8"))
            print("  Локален JSON записан с PLACEHOLDER (за commit).")
    else:
        # само локален файл (service key се чете от env, не влиза в git — но за локалния
        # файл го МАСКИРАМЕ placeholder, защото TP repo е публичен!)
        wf = json.load(open(P00, encoding="utf-8"))
        if patch_wf00(wf, "SERVICE_KEY_PLACEHOLDER_SET_IN_N8N"):
            json.dump(wf, open(P00, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
            json.load(open(P00, encoding="utf-8"))
            print("  WF00 локален JSON записан (service key = PLACEHOLDER за git safety).")
        print("\n(без --live — локален файл с placeholder; live deploy ползва реалния key от env)")
    print("DONE")


if __name__ == "__main__":
    main()
