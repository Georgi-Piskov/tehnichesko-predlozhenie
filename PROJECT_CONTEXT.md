# PROJECT CONTEXT — Технически Предложения Generator

> **ПРОЧЕТИ ТОЗИ ФАЙЛ ПЪРВО при нова сесия, за да хванеш пълния контекст на проекта.**
> Последна актуализация: 12.02.2026, commit `b8a575d`

---

## 1. КАКВО Е ПРОЕКТЪТ

Система за автоматично генериране на **технически предложения за обществени поръчки** (България).

- **Потребителят** качва PDF документация + техническа спецификация
- **AI pipeline** извлича изисквания, анализира, планира, пише секция по секция, валидира, финализира
- **Изход**: готов документ (~30-50 страници) в Markdown (планирано: DOCX)

**Основно изискване от потребителя:**
> "Работата изискява много точност и никаква възможност за грешки."

**Бюджет:** ~$20 на документ

---

## 2. АРХИТЕКТУРА

```
Frontend (GitHub Pages)          n8n Instance (v2.0.2)              OpenRouter API
  app.html + JS files     →    Orchestrator (WF00)           →    Claude Sonnet 4
                           →    Sub-workflows (WF01-07)       →    Claude Opus 4
                           →    Status API (WF09)
```

### Компоненти:

| Компонент | Описание |
|-----------|----------|
| **Frontend** | GitHub Pages: `app.html`, `js/api.js`, `js/app.js`, `js/fileUpload.js`, `css/styles.css` |
| **n8n** | v2.0.2 на `https://n8n.simeontsvetanovn8nworkflows.site` |
| **AI Models** | OpenRouter: Claude Sonnet 4 (писане), Claude Opus 4 (валидация/финализация) |
| **GitHub Repo** | `Georgi-Piskov/tehnichesko-predlozhenie` (public) |

---

## 3. n8n WORKFLOWS — ПЪЛЕН СПИСЪК

### WF00 — Orchestrator (`00-orchestrator.json`)
**Главният pipeline.** Приема файлове от frontend, координира всички подWorkflow-та.

**Pipeline flow:**
```
Webhook POST /tp-generate
  → Init Job (parse FormData, generate jobId)
  → Send Response (jobId + CORS headers) + Status: Init (5%)
  → Split Binary Files → Extract from PDF → Merge Texts
  → Extract Requirements (HTTP → WF02) + Status: Requirements (20%)
  → After Requirements
  → Analyze Spec (HTTP → WF03) + Status: Analyzing (35%)
  → After Spec Analysis
  → Plan Document (HTTP → WF04) + Status: Planning (50%)
  → Flatten Chunks (sections→subsections flat array)
  → Loop Over Items (SplitInBatches, batchSize=1)
    ↓ per chunk:
    → Prep Write → Write Section (HTTP → WF05)
    → Prep Validate → Validate Section (HTTP → WF06)
    → Check Validation (IF passed=true)
      TRUE  → Accumulate Section → back to Loop
      FALSE → Prep Rewrite (with feedback) → Rewrite Section (HTTP → WF05) → Accumulate Retry → back to Loop
  → Assemble Document + Status: Finalizing (88%)
  → Prep Finalize → Finalize Document (HTTP → WF07)
  → Pipeline Complete → Status: Complete (100%)
```

**Ключови детайли:**
- `$getWorkflowStaticData('global')` — съхранява `sd.fullDoc`, `sd.lastParent`, `sd.results`
- Всички 7 pipeline HTTP ноди имат `retryOnFail: true`, `maxTries: 3`, `waitBetweenTries: 15000`
- 6 Status HTTP ноди (fire-and-forget forks) пращат до `/webhook/internal/update-status`
- Send Response има CORS headers (`Access-Control-Allow-Origin: *`)
- Init Job парсва `body.contractor` като JSON string от FormData

### WF01 — Extract Text (`01-extract-text.json`)
- Webhook: `/tp-step-01-extract`
- Извлича текст от PDF файлове

### WF02 — Extract Requirements (`02-extract-requirements.json`)
- Webhook: `/tp-step-02-requirements`
- Pattern: Webhook → Code (Prepare Data) → chainLlm (Claude Sonnet) → Parse → Respond
- Извлича изисквания от документацията

### WF03 — Analyze Spec (`03-analyze-spec.json`)
- Webhook: `/tp-step-03-analyze`
- Pattern: Webhook → Code (Prepare Data) → chainLlm (Claude Sonnet) → Parse → Respond
- Анализира техническата спецификация

### WF04 — Plan Document (`04-plan-document.json`)
- Webhook: `/tp-step-04-plan`
- Pattern: Webhook → Code (Prepare Plan Prompt) → chainLlm (Claude Sonnet) → Parse Plan → Respond
- Prompt enforces: max 5 pages per subsection, self-sufficient guidance
- System message: "Each subsection will be written by a SEPARATE AI in a SEPARATE API call"

### WF05 — Write Section (`05-write-section.json`)
- Webhook: `/tp-write-section`
- Pattern: Webhook → Code (Prepare Section Prompt) → chainLlm (Claude Sonnet, maxTokens=16000, temp=0.3) → Format Output → Respond
- Accepts `feedback` field for retry writes
- Format Output has error handling (detects error items and returns safe JSON fallback)
- **ВАЖНО**: chainLlm НЕ е с `onError: continueRegularOutput` — гърми при грешка, за да може orchestrator да retry-не

### WF06 — Validate Section (`06-validate-section.json`)
- Webhook: `/tp-validate-section`
- Pattern: Webhook → Code (Prepare Validation Prompt) → chainLlm (Claude Opus, maxTokens=4000, temp=0.1) → Parse Result → Respond
- `onError: "continueRegularOutput"` на chainLlm — ако гърмне, auto-pass (score 75)
- Returns `{passed, score, issues, feedback}` — score >= 80 = PASS
- Parse Result има defensive error handling

### WF07 — Finalize Document (`07-finalize-document.json`)
- Webhook: `/tp-step-07-finalize`
- Pattern: Webhook → Code (Prepare Data) → chainLlm (Claude Opus, maxTokens=64000, temp=0.15) → Process Result → Respond
- responseBody: `JSON.stringify({ finalText: $json.finalText || '', stats: $json.stats || {} })`

### WF09 — Status API (`09-status-api.json`)
- 4 webhook endpoints:
  - `POST /webhook/internal/update-status` → Store Status (uses `$getWorkflowStaticData('global').jobs[jobId]`)
  - `GET /webhook/job-status?jobId=X` → Read Status → Respond (с CORS)
  - `GET /webhook/preview?jobId=X` → Build Preview (Markdown→HTML) → Respond
  - `GET /webhook/download?jobId=X` → Build Download (returns .md file as binary)

---

## 4. FRONTEND АРХИТЕКТУРА

### `app.html`
- 4-стъпков wizard: Изпълнител → Документи → Прогрес → Резултат
- Phase items: upload, extract, analyze, plan, write, validate, finalize, export

### `js/api.js`
- `API.submitJob(formData)` → POST `/webhook/tp-generate`
- `API.getJobStatus(jobId)` → GET `/webhook/job-status?jobId=X`
- `API.getPreview(jobId)` → GET `/webhook/preview?jobId=X`
- `API.downloadDocx(jobId)` → GET `/webhook/download?jobId=X&format=docx`

### `js/app.js`
- `CONFIG.N8N_WEBHOOK_URL = 'https://n8n.simeontsvetanovn8nworkflows.site'`
- `POLL_INTERVAL = 4000` (4 сек)
- `MAX_POLL_TIME = 30 * 60 * 1000` (30 мин)
- `handleStatusUpdate()` — phaseMap maps backend phases to frontend phases
- Saves contractor info to localStorage

### `js/fileUpload.js`
- Drag & drop + file selection
- `buildFormData()` — appends files + `JSON.stringify(contractorInfo)` as 'contractor'

---

## 5. CREDENTIALS & CONFIGURATION

```
OpenRouter Credential:
  - id: "UjrrZkDAIpdRXbb8"
  - name: "GP-Open_Router_Test"
  - type: "openRouterApi"

Native LLM Node:
  - type: "@n8n/n8n-nodes-langchain.lmChatOpenRouter"
  - typeVersion: 1

Models:
  - Writing/Extraction: "anthropic/claude-sonnet-4" (maxTokens: 16000, temp: 0.2-0.3)
  - Validation/Finalization: "anthropic/claude-opus-4" (maxTokens: 4000-64000, temp: 0.1-0.15)

n8n Instance:
  - URL: https://n8n.simeontsvetanovn8nworkflows.site
  - Version: 2.0.2
```

---

## 6. КРИТИЧНИ n8n УРОЦИ (научени по трудния начин)

Тези грешки бяха намерени и поправени с часове дебъгване. **НЕ ГИ ПОВТАРЯЙ:**

| # | Урок | Детайл |
|---|------|--------|
| 1 | `fetch()` НЕ РАБОТИ в n8n Code node sandbox | Използвай native HTTP Request nodes |
| 2 | `JSON.stringify()` НЕ РАБОТИ в n8n Expression `{{ }}` | В `responseBody` ТРЯБВА `={{ JSON.stringify($json) }}`, но JSON.stringify вътре в `{{ }}` за сложни обекти може да изведе `[object Object]`. Използвай Code node за подготовка |
| 3 | Webhook typeVersion 2 → POST body е под `$json.body.*` | НЕ `$json.*` — трябва `$json.body.contractor`, `$json.body.additionalNotes` и т.н. |
| 4 | `responseBody: "={{ $json }}"` → `[object Object]` | ВИНАГИ `={{ JSON.stringify($json) }}` или explicit field selection |
| 5 | `$getWorkflowStaticData('global')` за натрупване | Единственият начин да натрупваш данни между SplitInBatches итерации |
| 6 | Status updates трябва да са native HTTP nodes | Не fetch() в Code node. Dead-end fork от main pipeline |
| 7 | FormData `contractor` поле → JSON string | Frontend праща `JSON.stringify(contractorInfo)`, backend трябва да парсне |
| 8 | CORS headers трябва на всеки Respond node | `Access-Control-Allow-Origin: *` за GitHub Pages → n8n комуникация |
| 9 | Всички workflows **ТРЯБВА да са ACTIVATED** | Production mode използва `/webhook/`, test mode използва `/webhook-test/` |
| 10 | `retryOnFail` на HTTP nodes | За transient OpenRouter грешки (напр. "Unexpected end of JSON input") |
| 11 | `onError: "continueRegularOutput"` | На chainLlm nodes които не са критични (WF06 validator) — auto-pass при грешка |

---

## 7. GIT ИСТОРИЯ (хронологична)

```
d6d482d  Initial commit: project setup with GitHub Pages structure
cec6f4e  Add GitHub Actions workflow for Pages deployment
bae46d3  Add README with project description
d6e260f  feat: Add complete technical proposal generator system
06761be  config: Set real n8n webhook URL
f7ab095  Refactor: split monolithic into 9 separate sub-workflows
683dd38  fix: update executeWorkflowTrigger to typeVersion 1.1
1e9c9c5  refactor: replace executeWorkflowTrigger with Webhook+Respond pattern
ecdeeea  fix: anti-hallucination overhaul for all LLM prompts
057d5fb  refactor: section-by-section writing pipeline with validation loop
4021cff  fix: use .body.* for webhook typeVersion 2 data access
8be85ee  fix: add Code nodes to pre-process webhook body data before chainLlm
577ad57  fix: flatten Section Loop to subsections + improve planner prompt
90a7e3d  fix: replace fetch() with native n8n HTTP Request nodes in Section Loop
a80fa98  fix: add retry on validation fail + fix JSON response in all workflows
2ca8482  fix: add status updates + CORS + FormData parsing in orchestrator
b8a575d  fix: add retryOnFail + error resilience for transient API errors
```

---

## 8. ИЗВЕСТНИ ПРОБЛЕМИ / TODO

### Нерешени:
1. **Download връща .md, не .docx** — WF09 Build Download генерира Markdown файл. Frontend очаква .docx. Нужен е DOCX conversion (евентуално с pandoc или JS библиотека в Code node).
2. **Per-chunk progress updates** — Фазите "writing" и "validating" не показват прогрес по чънкове (напр. 5/23). Трябва Status HTTP ноди вътре в Loop Over Items.
3. **CORS preflight (OPTIONS)** — Браузърът може да прати OPTIONS request преди POST. n8n може да не го хендълва. Ако frontend не може да достигне n8n, това може да е причината.
4. **Preview endpoint** — Build Preview прави basic Markdown→HTML conversion (само headers, bold, lists). Таблиците НЕ се конвертират правилно.
5. **Max retry = 1** — При validation fail, секцията се презаписва само веднъж (Accumulate Retry). Няма трети опит.
6. **Error recovery** — Ако pipeline гърмне по средата (напр. на секция 15 от 23), няма механизъм да продължи от място. Целият pipeline трябва да се пусне отново.
7. **Prompt files** — В `n8n/prompts/` има 8 .md файла с AI промпти (от по-ранна итерация). Не са синхронизирани с текущия inline prompt code в workflow JSON файловете.

### Тествано:
- ✅ Full pipeline run ~35 мин (23 секции + валидация)
- ✅ Retry на transient AI грешки при `Write Section`
- ✅ Status updates от orchestrator до Status API
- ✅ CORS headers на frontend→n8n комуникация
- ✅ FormData parsing (contractor info)
- ✅ Validation + rewrite loop

### Последен тест (12.02.2026):
- Pipeline стигна до 35 мин, ~20 секции написани успешно
- Гръмна на `Write Section` с "Unexpected end of JSON input" (Claude Sonnet OpenRouter transient error)
- **FIX**: Добавен `retryOnFail: true` (3 опита, 15 сек пауза) на всички pipeline HTTP ноди

---

## 9. ФАЙЛОВА СТРУКТУРА

```
e:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\
├── .github/                  # GitHub Actions (Pages deployment)
├── app.html                  # Main frontend UI (4-step wizard)
├── index.html                # Redirect to app.html
├── css/
│   └── styles.css            # Frontend styles
├── js/
│   ├── api.js                # API module (fetch calls to n8n)
│   ├── app.js                # Main app logic, polling, phases
│   └── fileUpload.js         # Drag & drop file handling
├── n8n/
│   ├── prompts/              # AI prompt files (.md) — NOT synced with workflow code
│   │   ├── completeness-checker.md
│   │   ├── document-planner.md
│   │   ├── final-editor.md
│   │   ├── placeholder-marker.md
│   │   ├── relevance-checker.md
│   │   ├── requirement-extractor.md
│   │   ├── section-writer.md
│   │   └── spec-analyzer.md
│   └── workflows/
│       ├── 00-orchestrator.json    # Main pipeline coordinator
│       ├── 01-extract-text.json    # PDF text extraction
│       ├── 02-extract-requirements.json  # AI: extract requirements
│       ├── 03-analyze-spec.json    # AI: analyze specification
│       ├── 04-plan-document.json   # AI: create document plan
│       ├── 05-write-section.json   # AI: write one section
│       ├── 06-validate-section.json # AI: validate section quality
│       ├── 07-finalize-document.json # AI: final editing pass
│       ├── 09-status-api.json      # Status/preview/download API
│       └── SETUP.md                # Setup instructions
├── general_instructions.txt  # Global AI assistant instructions
├── github_mcp_README.md      # n8n-specific instructions
├── read_pdf.py               # Python PDF reader (utility)
├── README.md                 # Project README
└── PROJECT_CONTEXT.md        # THIS FILE
```

---

## 10. WORKFLOW WEBHOOK PATHS (за reference)

| Workflow | Webhook Path | Method | Mode |
|----------|-------------|--------|------|
| WF00 Orchestrator | `/webhook/tp-generate` | POST | responseNode |
| WF01 Extract Text | `/webhook/tp-step-01-extract` | POST | responseNode |
| WF02 Extract Requirements | `/webhook/tp-step-02-requirements` | POST | responseNode |
| WF03 Analyze Spec | `/webhook/tp-step-03-analyze` | POST | responseNode |
| WF04 Plan Document | `/webhook/tp-step-04-plan` | POST | responseNode |
| WF05 Write Section | `/webhook/tp-write-section` | POST | responseNode |
| WF06 Validate Section | `/webhook/tp-validate-section` | POST | responseNode |
| WF07 Finalize Document | `/webhook/tp-step-07-finalize` | POST | responseNode |
| WF09 Update Status | `/webhook/internal/update-status` | POST | onReceived |
| WF09 Job Status | `/webhook/job-status` | GET | responseNode |
| WF09 Preview | `/webhook/preview` | GET | responseNode |
| WF09 Download | `/webhook/download` | GET | responseNode |

---

## 11. ИНСТРУКЦИИ ЗА ПРОДЪЛЖАВАНЕ

1. **Прочети `general_instructions.txt`** — глобални правила за стила
2. **Прочети `github_mcp_README.md`** — n8n специфични инструкции
3. **Прочети този файл** — пълен контекст
4. **Питай потребителя**: "Какъв е резултатът от последния тест?" — за да знаеш какво трябва да се поправи
5. **Преди промени** — прочети конкретния JSON файл, не разчитай само на този контекст (може да е outdated)

### При дебъгване:
- Винаги питай за screenshot или error message от n8n Executions
- Проверявай кой node гърмя и input/output данните
- Помни: n8n sandbox е ограничен (без fetch, ограничен JSON.stringify в expressions)

### При добавяне на нови features:
- Следвай същия pattern: Webhook → Code (prepare) → chainLlm → Code (parse) → Respond
- Винаги добавяй `retryOnFail` на HTTP ноди в orchestrator
- Винаги добавяй CORS headers на Respond ноди
- Тествай с Production webhook URLs (`/webhook/`), не test (`/webhook-test/`)
