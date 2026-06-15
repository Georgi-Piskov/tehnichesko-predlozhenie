# -*- coding: utf-8 -*-
"""WF00 (00-orchestrator.json) — добавя резервация на кредити преди pipeline разхода.

Issue #135 Фаза 2 (билинг защита, n8n частта).

Поток ПРЕДИ:
    IF Authorized [0] → Init Job → [Status: Init, Send Response] → Split → ... → Extract Requirements (първи LLM разход)

Поток СЛЕД:
    IF Authorized [0] → Init Job → Reserve Credits
        Reserve Credits [0 success] → Restore Init → [Status: Init, Send Response] → (pipeline непроменен)
        Reserve Credits [1 error]   → Status: Insufficient → Respond Insufficient (402)

Резервацията (public.reserve_credits) става на n8n job_id, ПРЕДИ Split/Extract → ако няма
кредити, нито един платен LLM call не се прави. reserve_credits взима auth.uid() от user JWT
(Authorization: Bearer от webhook-а), проверява tier business/admin, дебитира баланса. Idempotent.

Refund при провал НЕ е тук (n8n error flow е ненадежден — урок БЪГ #4) — прави се от
VPS safety-net worker-а през find_stale_tp_reservations.

Идемпотентен: повторно пускане не дублира нодовете.

LIVE patch: ако е зададен N8N_API_KEY (env), прави и PUT към живия workflow.
Иначе само записва JSON → нужен ръчен re-import в n8n.
"""
import json
import os
import sys
import urllib.request

P00 = r"E:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\00-orchestrator.json"
SUPABASE_URL = "https://pxyncifjsyplsotpeopt.supabase.co"
N8N_BASE = "https://n8n.simeontsvetanovn8nworkflows.site"
WF00_ID = "J1xMp1KQF8Oz70WH"

RESERVE = "Reserve Credits"
RESTORE = "Restore Init"
STATUS_INSUF = "Status: Insufficient"
RESPOND_INSUF = "Respond Insufficient"


def load():
    return json.load(open(P00, encoding="utf-8"))


def anon_key(wf):
    """Извлича anon apikey от Check Auth нода (за да не го hardcode-ваме)."""
    for n in wf["nodes"]:
        if n["name"] == "Check Auth":
            for h in n["parameters"]["headerParameters"]["parameters"]:
                if h["name"] == "apikey":
                    return h["value"]
    raise RuntimeError("anon apikey не намерен в Check Auth")


def build_nodes(anon):
    reserve = {
        "id": "n_reserve_credits",
        "name": RESERVE,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [380, 120],
        "onError": "continueErrorOutput",
        "parameters": {
            "method": "POST",
            "url": f"{SUPABASE_URL}/rest/v1/rpc/reserve_credits",
            "sendHeaders": True,
            "headerParameters": {"parameters": [
                {"name": "apikey", "value": anon},
                {"name": "Authorization",
                 "value": "={{ $('Webhook').first().json.headers.authorization || '' }}"},
                {"name": "Content-Type", "value": "application/json"},
            ]},
            "sendBody": True,
            "specifyBody": "json",
            "contentType": "json",
            "jsonBody": "={{ JSON.stringify({ p_job_id: $json.jobId, p_service: 'tp', p_units: $json.targetPages }) }}",
            "options": {"timeout": 15000},
        },
    }
    restore = {
        "id": "n_restore_init",
        "name": RESTORE,
        "type": "n8n-nodes-base.code",
        "typeVersion": 2,
        "position": [520, 200],
        "parameters": {"jsCode":
            "// Връща оригиналния Init Job item (json + binary) — reserve беше прозрачен.\n"
            "var init = $('Init Job').first();\n"
            "return [{ json: init.json, binary: init.binary }];\n"
        },
    }
    status_insuf = {
        "id": "n_status_insufficient",
        "name": STATUS_INSUF,
        "type": "n8n-nodes-base.httpRequest",
        "typeVersion": 4.2,
        "position": [520, 360],
        "parameters": {
            "method": "POST",
            "url": f"{N8N_BASE}/webhook/internal/update-status",
            "sendBody": True,
            "specifyBody": "json",
            "jsonBody": "={{ JSON.stringify({ jobId: $('Init Job').first().json.jobId, userId: $('Init Job').first().json.userId, status: 'error', phase: 'error', progress: 0, message: ($json.message === 'insufficient_credits' ? 'Недостатъчно кредити за тази генерация.' : ($json.message === 'access_denied' ? 'Генерациите изискват Business абонамент.' : 'Грешка при резервиране на кредити.')) }) }}",
            "options": {"timeout": 10000},
        },
    }
    respond_insuf = {
        "id": "n_respond_insufficient",
        "name": RESPOND_INSUF,
        "type": "n8n-nodes-base.respondToWebhook",
        "typeVersion": 1.1,
        "position": [700, 360],
        "parameters": {
            "respondWith": "json",
            "responseBody": "={{ JSON.stringify({ jobId: $('Init Job').first().json.jobId, error: ($json.message || 'insufficient_credits'), message: 'Недостатъчно кредити за тази генерация.' }) }}",
            "options": {
                "responseCode": 402,
                "responseHeaders": {"entries": [
                    {"name": "Access-Control-Allow-Origin", "value": "https://proceno.net"},
                    {"name": "Access-Control-Allow-Headers", "value": "Content-Type, Authorization"},
                ]},
            },
        },
    }
    return [reserve, restore, status_insuf, respond_insuf]


def patch(wf):
    names = {n["name"] for n in wf["nodes"]}
    if RESERVE in names:
        print("  Reserve Credits вече съществува — пропускам (идемпотентно).")
        return False

    anon = anon_key(wf)
    wf["nodes"].extend(build_nodes(anon))

    c = wf["connections"]
    # Запомни какво беше след Init Job (за да го закача след Restore Init).
    init_targets = c.get("Init Job", {}).get("main", [[]])[0]
    # Очаквано: [Status: Init, Send Response]
    c["Init Job"] = {"main": [[{"node": RESERVE, "type": "main", "index": 0}]]}
    c[RESERVE] = {"main": [
        [{"node": RESTORE, "type": "main", "index": 0}],        # output 0 = success
        [{"node": STATUS_INSUF, "type": "main", "index": 0}],   # output 1 = error
    ]}
    c[RESTORE] = {"main": [init_targets]}                       # → [Status: Init, Send Response]
    c[STATUS_INSUF] = {"main": [[{"node": RESPOND_INSUF, "type": "main", "index": 0}]]}
    print(f"  init_targets пренасочени през Restore Init: {[t['node'] for t in init_targets]}")
    return True


def save(wf):
    with open(P00, "w", encoding="utf-8") as f:
        json.dump(wf, f, ensure_ascii=False, indent=2)
    # Валидация
    json.load(open(P00, encoding="utf-8"))
    print("  JSON записан и валидиран.")


def live_put(wf, api_key):
    body = json.dumps({
        "name": wf["name"], "nodes": wf["nodes"],
        "connections": wf["connections"], "settings": wf.get("settings", {}),
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{N8N_BASE}/api/v1/workflows/{WF00_ID}", data=body, method="PUT",
        headers={"X-N8N-API-KEY": api_key, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        print(f"  LIVE PUT status: {r.status}")


def main():
    wf = load()
    changed = patch(wf)
    if changed:
        save(wf)
    key = os.environ.get("N8N_API_KEY")
    if key and ("--live" in sys.argv):
        live_put(load(), key)
        print("  LIVE patch приложен. ВАЖНО: НЕ пускай по време на активна генерация!")
    else:
        print("  (без --live / N8N_API_KEY — само локален JSON; нужен ръчен re-import в n8n)")
    print("DONE")


if __name__ == "__main__":
    main()
