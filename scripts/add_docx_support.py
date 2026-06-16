# -*- coding: utf-8 -*-
"""WF00 — DOCX support (issue: DOCX spec чупеше pipeline).

ПРОБЛЕМ: Extract from PDF (extractFromFile operation:pdf) пада на DOCX → целият pipeline error.
РЕШЕНИЕ (n8n-native, нула външни зависимости): route по разширение.

ПРЕДИ:  Split Binary Files → Extract from PDF → Merge Texts
СЛЕД:   Split Binary Files → Is DOCX (IF)
          [false=PDF]  → Extract from PDF ──────────────────────┐
          [true=DOCX]  → Rename to Zip → Decompress →           │
                         Extract DOCX Text ──────────────────────┤
                                                    Join Branches (Merge append) → Merge Texts

DOCX екстракция: DOCX е ZIP → Compression нод (след rename на .zip) разархивира →
word/document.xml (n8n маха префикса → 'document.xml') → Code чете през
this.helpers.getBinaryDataBuffer (filesystem binary mode) → <w:t> текст.

Валидирано с $0 тестове: DOCX→3874 симв. чист текст; Merge итемКаунт=2 (PDF+DOCX и PDF+PDF).
fullText (downstream използва него) получава целия текст → НЯМА регресия.

Идемпотентен. --live за deploy.
"""
import json
import sys
import time
import urllib.request

P00 = r"E:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\00-orchestrator.json"
N8N_BASE = "https://n8n.simeontsvetanovn8nworkflows.site"
WF00_ID = "J1xMp1KQF8Oz70WH"

IS_DOCX = "Is DOCX"
RENAME_ZIP = "Rename to Zip"
DECOMPRESS = "Decompress DOCX"
EXTRACT_DOCX = "Extract DOCX Text"
JOIN = "Join Files"

ALLOWED_SETTINGS = {
    "saveExecutionProgress", "saveManualExecutions", "saveDataErrorExecution",
    "saveDataSuccessExecution", "executionTimeout", "errorWorkflow",
    "timezone", "executionOrder",
}

RENAME_JS = (
    "// DOCX е ZIP, но Compression разпознава по разширение → преименувай на .zip\n"
    "var items = $input.all();\n"
    "return items.map(function(item){\n"
    "  var bin = item.binary || {};\n"
    "  if (bin.data) {\n"
    "    bin.data.fileName = 'doc.zip';\n"
    "    bin.data.fileExtension = 'zip';\n"
    "    bin.data.mimeType = 'application/zip';\n"
    "  }\n"
    "  return { json: item.json, binary: bin };\n"
    "});\n"
)

EXTRACT_DOCX_JS = (
    "// Извлича текст от word/document.xml на разархивиран DOCX.\n"
    "// n8n binary е filesystem mode → ВИНАГИ getBinaryDataBuffer (не .data).\n"
    "var items = $input.all();\n"
    "var results = [];\n"
    "for (var idx = 0; idx < items.length; idx++) {\n"
    "  var item = items[idx];\n"
    "  var bin = item.binary || {};\n"
    "  var keys = Object.keys(bin);\n"
    "  var docKey = null;\n"
    "  for (var i = 0; i < keys.length; i++) {\n"
    "    var fn = (bin[keys[i]].fileName || '').toLowerCase();\n"
    "    if (fn === 'document.xml' || fn.endsWith('/document.xml')) { docKey = keys[i]; break; }\n"
    "  }\n"
    "  var text = '';\n"
    "  if (docKey) {\n"
    "    var buf = await this.helpers.getBinaryDataBuffer(idx, docKey);\n"
    "    var xml = buf.toString('utf-8');\n"
    "    var paras = xml.split(/<\\/w:p>/);\n"
    "    var out = [];\n"
    "    for (var p = 0; p < paras.length; p++) {\n"
    "      var m = paras[p].match(/<w:t[^>]*>([\\s\\S]*?)<\\/w:t>/g) || [];\n"
    "      var line = m.map(function(t){ return t.replace(/<[^>]+>/g, ''); }).join('');\n"
    "      if (line.trim()) out.push(line);\n"
    "    }\n"
    "    text = out.join('\\n')\n"
    "      .replace(/&amp;/g,'&').replace(/&lt;/g,'<').replace(/&gt;/g,'>')\n"
    "      .replace(/&quot;/g,'\"').replace(/&apos;/g,\"'\");\n"
    "  }\n"
    "  results.push({ json: { text: text, sourceField: item.json.sourceField || '', fileName: item.json.fileName || '' } });\n"
    "}\n"
    "return results;\n"
)


def patch_wf00(wf):
    names = {n["name"] for n in wf["nodes"]}
    if IS_DOCX in names:
        print("  WF00: DOCX support вече съществува — пропускам.")
        return False

    # Намери позиции на референтните нодове
    pos = {n["name"]: n.get("position", [0, 0]) for n in wf["nodes"]}
    base = pos.get("Extract from PDF", [1200, 200])
    bx, by = base[0], base[1]

    # Премести Extract from PDF малко надолу (PDF branch)
    for n in wf["nodes"]:
        if n["name"] == "Extract from PDF":
            n["position"] = [bx + 200, by + 160]

    # Нови ноди
    wf["nodes"].append({
        "id": "n_is_docx", "name": IS_DOCX, "type": "n8n-nodes-base.if", "typeVersion": 2,
        "position": [bx, by],
        "parameters": {"conditions": {"options": {"caseSensitive": False, "version": 2},
            "combinator": "and", "conditions": [{"id": "c_docx",
                "operator": {"type": "string", "operation": "endsWith"},
                "leftValue": "={{ $json.fileName }}", "rightValue": ".docx"}]}},
    })
    wf["nodes"].append({
        "id": "n_rename_zip", "name": RENAME_ZIP, "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": [bx + 200, by - 160], "parameters": {"jsCode": RENAME_JS},
    })
    wf["nodes"].append({
        "id": "n_decompress", "name": DECOMPRESS, "type": "n8n-nodes-base.compression", "typeVersion": 1.1,
        "position": [bx + 400, by - 160],
        "parameters": {"operation": "decompress", "binaryPropertyName": "data", "outputPrefix": "file_"},
    })
    wf["nodes"].append({
        "id": "n_extract_docx", "name": EXTRACT_DOCX, "type": "n8n-nodes-base.code", "typeVersion": 2,
        "position": [bx + 600, by - 160], "parameters": {"jsCode": EXTRACT_DOCX_JS},
    })
    wf["nodes"].append({
        "id": "n_join_files", "name": JOIN, "type": "n8n-nodes-base.merge", "typeVersion": 3,
        "position": [bx + 800, by], "parameters": {"mode": "append", "numberInputs": 2},
    })

    # Connections
    c = wf["connections"]
    # Split Binary Files → Is DOCX (вместо → Extract from PDF)
    c["Split Binary Files"] = {"main": [[{"node": IS_DOCX, "type": "main", "index": 0}]]}
    # Is DOCX: [0]=true=DOCX, [1]=false=PDF
    c[IS_DOCX] = {"main": [
        [{"node": RENAME_ZIP, "type": "main", "index": 0}],
        [{"node": "Extract from PDF", "type": "main", "index": 0}],
    ]}
    c[RENAME_ZIP] = {"main": [[{"node": DECOMPRESS, "type": "main", "index": 0}]]}
    c[DECOMPRESS] = {"main": [[{"node": EXTRACT_DOCX, "type": "main", "index": 0}]]}
    c[EXTRACT_DOCX] = {"main": [[{"node": JOIN, "type": "main", "index": 0}]]}      # Join input 0 = DOCX
    c["Extract from PDF"] = {"main": [[{"node": JOIN, "type": "main", "index": 1}]]}  # Join input 1 = PDF
    c[JOIN] = {"main": [[{"node": "Merge Texts", "type": "main", "index": 0}]]}
    print("  WF00: добавени Is DOCX + Rename to Zip + Decompress DOCX + Extract DOCX Text + Join Files.")
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


def main():
    wf = json.load(open(P00, encoding="utf-8"))
    if patch_wf00(wf):
        json.dump(wf, open(P00, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        json.load(open(P00, encoding="utf-8"))
        print("  WF00 локален JSON записан.")

    if "--live" in sys.argv:
        key = _env()["N8N_API_KEY"]
        live = _api("GET", f"workflows/{WF00_ID}", key)
        import pathlib
        ts = time.strftime("%Y%m%d_%H%M%S")
        pathlib.Path(rf"E:\VISUAL STUDIO\PUBLIC PROCUREMENT VER.2\_wf00_predocx_backup_{ts}.json").write_text(
            json.dumps(live, ensure_ascii=False, indent=2), encoding="utf-8")
        if patch_wf00(live):
            clean = {k: v for k, v in live.get("settings", {}).items() if k in ALLOWED_SETTINGS}
            _api("PUT", f"workflows/{WF00_ID}", key, {
                "name": live["name"], "nodes": live["nodes"],
                "connections": live["connections"], "settings": clean})
            print(f"  LIVE PUT OK ({len(live['nodes'])} нода).")
    else:
        print("\n(без --live — само локален файл)")
    print("DONE")


if __name__ == "__main__":
    main()
