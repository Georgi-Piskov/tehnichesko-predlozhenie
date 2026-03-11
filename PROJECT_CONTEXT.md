# PROJECT CONTEXT — Технически Предложения Generator

> **ПРОЧЕТИ ТОЗИ ФАЙЛ ПЪРВО при нова сесия, за да хванеш пълния контекст на проекта.**
> Последна актуализация: 17.02.2026

---

## 1. КАКВО Е ПРОЕКТЪТ

Система за автоматично генериране на **технически предложения за обществени поръчки** (България) + **оценка на технически предложения** от гледна точка на възложител.

### Pipeline 1 — Генератор
- **Потребителят** качва PDF документация + техническа спецификация
- **AI pipeline** извлича изисквания, анализира, планира, пише секция по секция, валидира
- **Изход**: готов документ (~30-50 страници) — запазва се като Google Doc в Google Drive + .md download

### Pipeline 2 — Оценка (НОВА)
- **Потребителят** качва документация на възложителя + техническо предложение на кандидата
- **AI pipeline** извлича изисквания, анализира предложението, кръстосано сравнява, правна валидация
- **Изход**: протокол от оценка с основания за отстраняване/допускане — запазва се като Google Doc + .md download
- **Правна обосновка**: чл. 107 ЗОП (отстраняване), чл. 104 ал. 5 (разяснения), чл. 104 ал. 7 (нередовности)

**Основно изискване от потребителя:**
> "Работата изискява много точност и никаква възможност за грешки."

**Бюджет:** ~$20 на документ (без Finalize стъпката — ~$15)

---

## 2. АРХИТЕКТУРА

```
Frontend (GitHub Pages)          n8n Instance (v2.0.2)              OpenRouter API
  app.html + JS files     →    Orchestrator (WF00)           →    Claude Sonnet 4
  eval.html + JS files    →    Eval Orchestrator (WF20)      →    Claude Opus 4 (legal)
                           →    Sub-workflows (WF02-06)       →    (Generation pipeline)
                           →    Eval Sub-workflows (WF21-25)  →    (Evaluation pipeline)
                           →    Status API (WF09)             →    (shared)
                           →    Google Drive (save output)
```

### Компоненти:

| Компонент | Описание |
|-----------|----------|
| **Frontend — Генератор** | GitHub Pages: `app.html`, `js/api.js`, `js/app.js`, `js/fileUpload.js`, `css/styles.css` |
| **Frontend — Оценка** | GitHub Pages: `eval.html`, `js/eval-app.js`, `css/styles.css` (reused) |
| **n8n** | v2.0.2 на `https://n8n.simeontsvetanovn8nworkflows.site` |
| **AI Models** | OpenRouter: Claude Sonnet 4 (писане/анализ), Claude Opus 4 (валидация/правна) |
| **Google Drive** | Запазва генерирания документ/протокол като нативен Google Doc |
| **GitHub Repo** | `Georgi-Piskov/tehnichesko-predlozhenie` (public) |

---

## 3. n8n WORKFLOWS — ПЪЛЕН СПИСЪК

### WF00 — Orchestrator (`00-orchestrator.json`)
**Главният pipeline.** Приема файлове от frontend, координира всички под-workflows.

**АКТУАЛЕН Pipeline flow (commit 818e350):**
```
Webhook POST /tp-generate
  → Init Job (parse FormData, generate jobId)
  → [Send Response (jobId + CORS) | Status: Init (5%)]    ← ПАРАЛЕЛНО
  → Split Binary Files → Extract from PDF → Merge Texts
  → [Extract Requirements (HTTP → WF02) | Status: Requirements (20%)]
  → After Requirements
  → [Analyze Spec (HTTP → WF03) | Status: Analyzing (35%)]
  → After Spec Analysis
  → [Plan Document (HTTP → WF04) | Status: Planning (50%)]
  → Flatten Chunks (sections→subsections flat array)
  → Loop Over Items (SplitInBatches, batchSize=1)
    ↓ per chunk:
    → [Prep Write | Status: Writing (50-88%, per-section)]
    → Write Section (HTTP → WF05)
    → Prep Validate → Validate Section (HTTP → WF06)
    → Check Validation (IF passed=true)
      TRUE  → Accumulate Section → back to Loop
      FALSE → Prep Rewrite (with feedback) → Rewrite Section (HTTP → WF05) → Accumulate Retry → back to Loop
  → [Assemble Document | Status: Finalizing (88%)]
  → Pipeline Complete
  → [Status: Complete (100%) | Save to Google Drive]    ← ПАРАЛЕЛНО
```

**ВАЖНО — Finalize Document е BYPASSED:**
- Node-овете `Prep Finalize` и `Finalize Document` (WF07) СЪЩЕСТВУВАТ в JSON-а, но НЕ СА СВЪРЗАНИ
- `Assemble Document` → `Pipeline Complete` директно (без финализация)
- Причина: WF07 изпраща целия 20K+ думи документ до Claude Opus с maxTokens=64000, отнема 10-20 мин, причинява "connection was aborted" грешка и се повтаря 3 пъти = $9-15 загуба
- Документът е достатъчно добър без финализация

**Ключови детайли:**
- `$getWorkflowStaticData('global')` — съхранява `sd.fullDoc`, `sd.lastParent`, `sd.results` между SplitInBatches итерации
- Всички 7 pipeline HTTP ноди имат `retryOnFail: true`, `maxTries: 3`, `waitBetweenTries: 15000`
- 7 Status HTTP ноди (dead-end forks): Init, Requirements, Analyzing, Planning, Writing (per-section), Finalizing, Complete
- Status: Init се пуска от Init Job (паралелно с Send Response) — НЕ от Send Response, за да е записан статус преди frontend да почне да poll-ва
- Send Response има CORS headers (`Access-Control-Allow-Origin: *`, `Access-Control-Allow-Headers: Content-Type`)
- Init Job парсва `body.contractor` като JSON string от FormData
- **Save to Google Drive** — `onError: continueRegularOutput`, Google Drive v3, `createFromText` с `convertToGoogleDocument: true`
  - Credential трябва да се конфигурира ръчно в n8n (id/name: "CONFIGURE_IN_N8N")
  - Файл: `ТП_yyyy-MM-dd_HHmm`

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
- **ВАЖНО**: chainLlm НЕ е с `onError: continueRegularOutput` — гърми при грешка, за да може orchestrator да retry-не с `retryOnFail`

### WF06 — Validate Section (`06-validate-section.json`)
- Webhook: `/tp-validate-section`
- Pattern: Webhook → Code (Prepare Validation Prompt) → chainLlm (Claude Opus, maxTokens=4000, temp=0.1) → Parse Result → Respond
- `onError: "continueRegularOutput"` на chainLlm — ако гърмне, auto-pass (score 75)
- Returns `{passed, score, issues, feedback}` — score >= 80 = PASS
- Parse Result има defensive error handling

### WF07 — Finalize Document (`07-finalize-document.json`) — ⚠️ BYPASSED
- Webhook: `/tp-step-07-finalize`
- Pattern: Webhook → Code → chainLlm (Claude Opus, maxTokens=64000, temp=0.15) → Process Result → Respond
- **НЕ СЕ ИЗПОЛЗВА** в текущия orchestrator — node-ът е disconnected
- Причина: connection timeout + висока цена ($3-5 на опит, x3 retry = $9-15)

### WF10 — Format Document (`10-format-document.json`) — НОВА
**Отделен workflow за форматиране на генериран документ.** Не е част от pipeline-а.

**Flow:**
```
Manual Trigger → Config (Set: fileId, outputName, folderId)
→ Google Drive: Download (export as text/plain)
→ Code: Extract Text (binary → text)
→ Code: Split into Sections (по ## headers, fallback по ### или ~3000 думи)
→ SplitInBatches (batchSize: 1)
  → Code: Prep Format Prompt
  → chainLlm (Claude Sonnet, temp 0.15): Markdown → HTML
  → Code: Accumulate HTML (staticData)
→ Code: Assemble HTML Document (CSS wrapper + binary output)
→ Google Drive: Upload (HTML → Google Doc, convertToGoogleDocument: true)
→ Done (link to formatted doc)
```

**Какво прави AI-ът:**
- Конвертира Markdown таблици → HTML `<table>` с borders, thead, tbody
- `##` → `<h2>`, `###` → `<h3>`, `**bold**` → `<strong>`
- Подчертава (`<u>`) нормативни документи, стандарти, ключови изисквания
- Маркира `[⚠️ ПОПЪЛНЕТЕ:]` placeholders с жълт фон
- НЕ променя съдържанието — само форматирането

**Как се ползва:**
1. Импортирай в n8n
2. Конфигурирай Google Drive credential
3. Отвори "Config" node → попълни `sourceFileId` (от URL на Google Doc)
4. Click "Test Workflow"
5. Изчакай — резултатът се запазва като нов Google Doc

**Credential:** Същият Google Drive OAuth2 (`CONFIGURE_IN_N8N`)
**Модел:** Claude Sonnet 4 (temp: 0.15, maxTokens: 16000)
**Error handling:** `onError: continueRegularOutput` на chainLlm + `retryOnFail: true` (2 опита)

### WF09 — Status API (`09-status-api.json`)
- 4 webhook endpoints:
  - `POST /webhook/internal/update-status` → Store Status (uses `$getWorkflowStaticData('global').jobs[jobId]`)
  - `GET /webhook/job-status?jobId=X` → Read Status → Respond (с CORS)
  - `GET /webhook/preview?jobId=X` → Build Preview (Markdown→HTML) → Respond
  - `GET /webhook/download?jobId=X` → Build Download (returns .md file as binary)
- Store Status merge-ва нови данни с existing job data
- Read Status: ако `status === 'completed' && job.result`, връща `result.stats` + `hasDocument: true`
- Build Preview: basic Markdown→HTML (headers, bold, lists), с placeholder highlighting
- Build Download: текстът → Buffer → base64 binary, mime: `text/markdown`, Content-Disposition header

---

### 🔍 EVALUATION PIPELINE (WF20-25) — НОВА

### WF20 — Eval Orchestrator (`20-eval-orchestrator.json`)
**Главен pipeline за оценка.** Приема файлове от eval frontend, координира всички eval под-workflows.

**Pipeline flow:**
```
Webhook POST /eval-generate
  → Init Job (parse FormData, generate eval_jobId)
  → [Send Response (jobId + CORS) | Status: Init]    ← ПАРАЛЕЛНО
  → Split Binary Files → Extract from PDF → Merge Texts (req vs proposal)
  → [Extract Requirements (HTTP → WF21) | Status: Extracting Requirements]
  → After Requirements
  → [Analyze Proposal (HTTP → WF22) | Status: Analyzing Proposal]
  → After Proposal Analysis
  → Flatten Requirements (sections→individual requirements)
  → Loop Over Items (SplitInBatches, batchSize=1)
    ↓ per requirement:
    → [Prep Cross-Ref | Status: Cross-Referencing (per-requirement progress)]
    → Cross-Reference (HTTP → WF23)
    → Accumulate Finding (staticData)
  → Assemble Findings
  → [Legal Validation (HTTP → WF24, Claude Opus) | Status: Legal Validation]
  → After Legal
  → [Generate Report (HTTP → WF25) | Status: Generating Report]
  → Pipeline Complete
  → [Status: Complete | Save to Google Drive]    ← ПАРАЛЕЛНО
```

**Ключови детайли:**
- Webhook path: `/webhook/eval-generate`
- JobId prefix: `eval_` (различен от генератора)
- Merge Texts разделя файловете по sourceField (`requirements` vs `proposal`)
- WF24 (Legal Validation) получава САМО non-compliant findings (оптимизация на цена)
- COMPLIANT findings се пропускат за правната валидация
- `$getWorkflowStaticData('global')` за натрупване на findings между итерации
- Parse fallback при WF23 грешка: defaults to COMPLIANT (избягва false positives)
- Реизползва WF09 Status API (същите endpoints)
- **Приблизителна цена**: ~$8-15 на оценка (15-25 Sonnet calls + 1 Opus call)

### WF21 — Extract Eval Requirements (`21-extract-eval-requirements.json`)
- Webhook: `/eval-extract-requirements`
- Pattern: Webhook → Code (Prepare Data) → chainLlm (Claude Sonnet, temp 0.1) → Parse → Respond
- Извлича ВСИЧКИ изисквания от документацията на възложителя
- Категоризира: MANDATORY (отстранително по чл. 107 ЗОП), EVALUATIVE (за оценяване), UNCLEAR
- Извлича: подизисквания, критерии за оценка, необходими доказателства, източник в документацията
- Truncate: 120K chars
- maxTokens: 16000

### WF22 — Analyze Proposal (`22-analyze-proposal.json`)
- Webhook: `/eval-analyze-proposal`
- Pattern: Webhook → Code (Prepare Data) → chainLlm (Claude Sonnet, temp 0.15) → Parse → Respond
- Анализира техническото предложение на кандидата
- Извлича: секции, методология, екип, оборудване, график, таблици
- Флагове за червени знамена: vague, copy_paste, contradiction, unrealistic, missing_info, generic
- Truncate: 120K chars
- maxTokens: 16000

### WF23 — Cross-Reference (`23-cross-reference.json`)
- Webhook: `/eval-cross-reference`
- Pattern: Webhook → Code (Prepare Prompt) → chainLlm (Claude Sonnet, temp 0.1) → Parse → Respond
- Кръстосано сравнява ЕДНО изискване с предложението
- Input: `{ requirement, proposalAnalysis, proposalText }` — proposalText truncate до 50K chars
- Output: `{ finding: { requirement_id, status, analysis, proposal_citations, requirement_citations, deficiencies, score } }`
- Status стойности: COMPLIANT, PARTIALLY_COMPLIANT, NON_COMPLIANT, MISSING
- Parse fallback: defaults to COMPLIANT при грешка (избягва false positives)
- maxTokens: 8000

### WF24 — Legal Validation (`24-legal-validation.json`)
- Webhook: `/eval-legal-validation`
- Pattern: Webhook → Code (Prepare & Filter) → chainLlm (**Claude Opus**, temp 0.1) → Parse → Respond
- **КРИТИЧЕН СТЪП** — използва Claude Opus за максимална точност
- Получава САМО non-compliant findings (COMPLIANT се пропускат)
- За всяка констатация определя:
  - Основание за отстраняване (да/не)
  - Правна основа (конкретни членове от ЗОП/ППЗОП)
  - Тип нарушение (MANDATORY_REQUIREMENT / EVALUATION_CRITERIA / FORMAL_DEFECT)
  - Увереност (HIGH/MEDIUM/LOW)
  - Риск от обжалване пред КЗК (LOW/MEDIUM/HIGH)
  - Препоръка (DISQUALIFY/REQUEST_CLARIFICATION/REDUCE_POINTS/NO_VIOLATION)
- **Консервативен подход**: препоръчва отстраняване САМО при ясно и безспорно нарушение
- При AI грешка: returns ACCEPT_WITH_REMARKS default + бележка за ръчен преглед
- maxTokens: 16000

### WF25 — Generate Eval Report (`25-generate-eval-report.json`)
- Webhook: `/eval-generate-report`
- Pattern: Webhook → Code (Prepare Report Prompt) → chainLlm (Claude Sonnet, temp 0.2) → Parse → Respond
- Генерира ПРОТОКОЛ ОТ ОЦЕНКА в Markdown
- Секции: I. Обща информация, II. Обхват, III. Обобщена таблица, IV. Подробен анализ, V. Правна обосновка, VI. Заключение, VII. Рискове при обжалване
- Включва disclaimer: "подготвен с помощта на AI анализ и подлежи на потвърждение от оценителната комисия"
- maxTokens: 16000

---

## 4. FRONTEND АРХИТЕКТУРА

### `app.html`
- 4-стъпков wizard: Изпълнител → Документи → Генериране (прогрес) → Резултат
- Phase items: upload, extract, analyze, plan, write, validate, finalize, export
- Download бутон: "Изтегли документа" (не "DOCX")

### `js/api.js`
- `API.submitJob(formData)` → POST `/webhook/tp-generate`
- `API.getJobStatus(jobId)` → GET `/webhook/job-status?jobId=X`
- `API.getPreview(jobId)` → GET `/webhook/preview?jobId=X`
- `API.downloadDocx(jobId)` → GET `/webhook/download?jobId=X&format=docx`

### `js/app.js` — ТЕКУЩО СЪСТОЯНИЕ (commit 818e350)
- `CONFIG.N8N_WEBHOOK_URL = 'https://n8n.simeontsvetanovn8nworkflows.site'`
- `POLL_INTERVAL = 4000` (4 сек)
- `MAX_POLL_TIME = 90 * 60 * 1000` (90 мин)
- **8-секундно начално закъснение** преди първия poll (дава време на Status: Init)
- **not_found handling**: Не показва "Заявка не е намерена" на потребителя
  - 0-60 сек: "Инициализация на заявката..."
  - 60-120 сек: "Очакване на статус... Моля, изчакайте."
  - 120+ сек: "⚠️ Няма статус. Проверете дали TP-Status API е активиран в n8n."
- `handleStatusUpdate()` — phaseMap:
  - `uploading` → `upload`, `extracting_requirements` → `extract`, `analyzing_spec` → `analyze`
  - `planning` → `plan`, `writing_sections` / `writing` → `write`
  - `validating` → `validate`, `finalizing` → `finalize`, `exporting` → `export`
- **Writing phase**: Dynamic text от `status.message` (напр. "Писане на секция 5 от 23...")
- **Manual refresh**: `showManualRefresh()` бутон "🔄 Провери статус" при timeout
- `onGenerationComplete()` — чете `status.result.stats.estimatedPages / sections / placeholderCount`
- Download: файл с разширение `.md`
- Saves contractor info to localStorage

### `js/fileUpload.js`
- Drag & drop + file selection
- Accepts PDF, DOC, DOCX (max 50MB)
- `buildFormData()` — appends files + `JSON.stringify(contractorInfo)` as 'contractor'

### `eval.html` — НОВА (Оценка на предложения)
- 3-стъпков wizard: Документи → Анализ (прогрес) → Резултат
- Стъпка 1: Две зони за качване — документация на възложителя + предложение на кандидата + бележки
- Стъпка 2: Прогрес с 7 фази (upload, extract, analyze, crossref, legal, report, export)
- Стъпка 3: Резултати с recommendation badge (ОТСТРАНЯВАНЕ/ДОПУСКАНЕ С БЕЛЕЖКИ/ДОПУСКАНЕ)
  - Stats cards: общо, съответстващи, частично, несъответстващи, основания за отстраняване
  - Download/preview бутони
- Reuses `css/styles.css` + inline eval-specific стилове
- Nav link: ← Генератор на технически предложения (app.html)

### `js/eval-app.js` — НОВА (Combined API + file upload + app logic)
- **EvalAPI**: `submitJob` (POST /webhook/eval-generate), `getJobStatus`, `getPreview`, `downloadReport`
  - Реизползва WF09 endpoints за status/preview/download
- **EvalFileUpload**: Две зони (reqFile, propFile), `buildFormData` appends като `requirements` и `proposal`
- **Phase mapping**: `extracting_requirements→extract`, `analyzing_proposal→analyze`, `cross_referencing→crossref`, `legal_validation→legal`, `generating_report→report`
- Същият 8-секунден initial poll delay, 90-мин timeout, not_found handling
- Download filename: `Оценка_ТП_YYYY-MM-DD.md`

---

## 5. CREDENTIALS & CONFIGURATION

```
OpenRouter Credential:
  - id: "UjrrZkDAIpdRXbb8"
  - name: "GP-Open_Router_Test"
  - type: "openRouterApi"

Google Drive Credential:
  - ТРЯБВА ДА СЕ КОНФИГУРИРА РЪЧНО в n8n
  - Тип: googleDriveOAuth2Api
  - В orchestrator.json и 10-format-document.json: id/name е "CONFIGURE_IN_N8N" (placeholder)

Native LLM Node:
  - type: "@n8n/n8n-nodes-langchain.lmChatOpenRouter"
  - typeVersion: 1

Models:
  - Writing/Extraction: "anthropic/claude-sonnet-4" (maxTokens: 16000, temp: 0.2-0.3)
  - Validation: "anthropic/claude-opus-4" (maxTokens: 4000, temp: 0.1)
  - Finalization (BYPASSED): "anthropic/claude-opus-4" (maxTokens: 64000, temp: 0.15)
  - Formatting (WF10): "anthropic/claude-sonnet-4" (maxTokens: 16000, temp: 0.15)

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
| 2 | `JSON.stringify()` в n8n Expression | В `responseBody` ТРЯБВА `={{ JSON.stringify($json) }}`. За сложни обекти подготви в Code node |
| 3 | Webhook typeVersion 2 → POST body е под `$json.body.*` | НЕ `$json.*` — трябва `$json.body.contractor`, `$json.body.additionalNotes` и т.н. |
| 4 | `responseBody: "={{ $json }}"` → `[object Object]` | ВИНАГИ `={{ JSON.stringify($json) }}` или explicit field selection |
| 5 | `$getWorkflowStaticData('global')` за натрупване | Единственият начин да натрупваш данни между SplitInBatches итерации. Изтрий след Assemble! |
| 6 | Status updates = native HTTP nodes (dead-end fork) | Не fetch() в Code node. Паралелен fork от main pipeline |
| 7 | FormData `contractor` поле → JSON string | Frontend праща `JSON.stringify(contractorInfo)`, backend трябва `JSON.parse()` |
| 8 | CORS headers на всеки Respond node | `Access-Control-Allow-Origin: *` за GitHub Pages → n8n комуникация |
| 9 | Всички workflows **ТРЯБВА да са ACTIVATED** | Production: `/webhook/`, test: `/webhook-test/` — различни URL-и! |
| 10 | `retryOnFail` на HTTP nodes | За transient OpenRouter грешки ("Unexpected end of JSON input"). 3 опита, 15 сек пауза |
| 11 | `onError: "continueRegularOutput"` | На chainLlm nodes които не са критични (WF06 validator) — auto-pass при грешка |
| 12 | Finalize Document timeout | 20K+ думи → Claude Opus maxTokens=64000 → 10-20 мин → connection abort. BYPASS-ни го |
| 13 | Status: Init трябва от Init Job, не от Send Response | Ако е от Send Response, frontend може да poll-не преди статус да е записан → "not_found" |
| 14 | Frontend initial poll delay | 8 сек закъснение преди първия poll — дава време на Status: Init |
| 15 | Google Drive node с `onError: continueRegularOutput` | Drive failure не трябва да убива pipeline-а |

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
08f47e5  docs: add PROJECT_CONTEXT.md
5d1b47b  fix: skip Finalize Document step - saves ~/run + prevents timeout
2e52e40  fix: align frontend stats with backend data + fix download format (.md)
d9cba6c  fix: frontend stuck on planning - add writing status + increase poll timeout
689b110  fix: handle 'not_found' status gracefully + fix Status:Init timing
818e350  feat: save generated document to Google Drive as Google Doc
815bf75  docs: update PROJECT_CONTEXT.md with full project state (Feb 16)
9aed98b  feat: add WF10 - Format Document workflow (standalone Markdown→HTML→Google Doc)
85ee7c5  fix: use n8n getBinaryDataBuffer helper for binary read in WF10
```

---

## 8. ТЕКУЩ СТАТУС НА ПРОЕКТА (18.02.2026)

### ✅ Готово:
- Пълен pipeline: Extract → Requirements → Analyze → Plan → Write (per-section) → Validate → Assemble
- Retry на transient AI грешки (retryOnFail x3, 15s wait)
- Validation + rewrite loop (при score < 80)
- 7 Status HTTP ноди в orchestrator (включително per-section writing прогрес)
- Frontend: 90 мин timeout, 8-сек initial delay, manual refresh бутон
- Frontend: graceful not_found handling (не показва грешка)
- Frontend: динамичен текст при writing фаза ("Писане на секция X от Y...")
- Frontend: stats mapping (estimatedPages, sections, placeholderCount)
- Frontend: download като .md файл
- CORS headers навсякъде
- FormData parsing
- Save to Google Drive като нативен Google Doc
- WF06 auto-pass при crash (onError: continueRegularOutput)
- Finalize Document bypassed (спестява $5+/run и 10-20 мин)
- WF10 Format Document: създаден (Manual Trigger → Download → Split → AI Format → Upload)

### ⚠️ НЕ Е ТЕСТВАНО / НЕИЗВЕСТНО:
- **Пълен end-to-end тест НЕ Е ЗАВЪРШЕН УСПЕШНО**
- Google Drive credential НЕ Е конфигуриран — трябва ръчно в n8n

### 🐛 WF10 Format Document — BUG (18.02.2026):
- **Симптом**: Всички 26 секции показват "⚠️ Грешка при форматиране на секция X" (червен текст)
- **Означава**: chainLlm "Format Section" node гърми за ВСЯКА секция
- **`onError: continueRegularOutput`** хваща грешката → Accumulate записва error HTML fallback
- **Вероятни причини (за дебъг следващата сесия)**:
  1. **chainLlm получава празен prompt** — провери output на "Prep Format Prompt" node
  2. **SplitInBatches connections** — output 0 (item) трябва да отива към Prep Format, output 1 (done) към Assemble
  3. **Model connection** — провери дали Claude Sonnet е свързан с ai_languageModel port на Format Section
  4. **OpenRouter credential** — може credential да не работи (rate limit, expired)
  5. **Prompt е твърде дълъг** — секциите може да надвишават context window
- **Как да дебъгнеш**: В n8n отвори execution → кликни на "Format Section" node → виж Error details в output
- **Binary read е ПОПРАВЕН** (commit 85ee7c5) — вече използва `this.helpers.getBinaryDataBuffer()`

### 🔲 TODO за следващата сесия:
1. **Дебъгни WF10**: Отвори failed execution → виж error на "Format Section" node
2. **Провери connections**: SplitInBatches output 0 → Prep Format → Format Section → Accumulate → back to Loop; output 1 → Assemble
3. **Провери model link**: Claude Sonnet → ai_languageModel → Format Section
4. **Тествай с 1 секция**: Промени Split into Sections да върне само 1 секция за бърз тест
5. **Ако WF10 работи** → тествай с пълен документ
6. **Основен pipeline** (WF00): Все още не е тестван end-to-end

---

## 9. ИЗВЕСТНИ ПРОБЛЕМИ

| # | Проблем | Статус | Бележки |
|---|---------|--------|---------|
| 1 | Download е .md, не .docx | Known | WF09 Build Download генерира Markdown. За DOCX нужен pandoc или JS lib |
| 2 | Preview endpoint — basic HTML | Known | Само headers, bold, lists. Таблици НЕ се конвертират |
| 3 | Max retry = 1 за validation | Known | При fail → 1 rewrite → accumulate. Няма 3-ти опит |
| 4 | Няма pipeline resume | Known | Ако crash на секция 15/23, целият pipeline трябва пак |
| 5 | CORS preflight (OPTIONS) | Unknown | n8n може да не хендълва OPTIONS. Ако frontend не достига n8n, може да е това |
| 6 | Prompt files не са синхронизирани | Known | `n8n/prompts/*.md` са от по-ранна итерация, не отразяват текущите inline prompts |
| 7 | placeholderCount не се агрегира | Known | Pipeline Complete не брои `[⚠️ ПОПЪЛНЕТЕ:]` patterns |
| 8 | WF10: chainLlm гърми за всички секции | **Active BUG** | Всички 26 секции → error fallback HTML. Виж секция 8 за дебъг стъпки |

---

## 10. ФАЙЛОВА СТРУКТУРА

```
e:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\
├── .github/                  # GitHub Actions (Pages deployment)
├── app.html                  # Main frontend UI (4-step wizard)
├── index.html                # Redirect to app.html
├── css/
│   └── styles.css            # Frontend styles
├── js/
│   ├── api.js                # API module (fetch calls to n8n)
│   ├── app.js                # Main app logic, polling, phases (425 lines)
│   └── fileUpload.js         # Drag & drop file handling (127 lines)
├── n8n/
│   ├── prompts/              # AI prompt files (.md) — ⚠️ NOT synced with workflow code
│   │   ├── completeness-checker.md
│   │   ├── document-planner.md
│   │   ├── final-editor.md
│   │   ├── placeholder-marker.md
│   │   ├── relevance-checker.md
│   │   ├── requirement-extractor.md
│   │   ├── section-writer.md
│   │   └── spec-analyzer.md
│   └── workflows/
│       ├── 00-orchestrator.json    # Main pipeline (~550 lines) — HAS Save to Google Drive
│       ├── 01-extract-text.json    # PDF text extraction
│       ├── 02-extract-requirements.json  # AI: extract requirements
│       ├── 03-analyze-spec.json    # AI: analyze specification
│       ├── 04-plan-document.json   # AI: create document plan
│       ├── 05-write-section.json   # AI: write one section
│       ├── 06-validate-section.json # AI: validate section quality
│       ├── 07-finalize-document.json # AI: final editing (⚠️ BYPASSED)
│       ├── 09-status-api.json      # Status/preview/download API
│       ├── 10-format-document.json # Document formatter (standalone)
│       └── SETUP.md                # Setup instructions
├── general_instructions.txt  # Global AI assistant instructions
├── github_mcp_README.md      # n8n-specific instructions
├── read_pdf.py               # Python PDF reader (utility)
├── README.md                 # Project README
└── PROJECT_CONTEXT.md        # THIS FILE
```

---

## 11. WORKFLOW WEBHOOK PATHS

| Workflow | Webhook Path | Method | Mode |
|----------|-------------|--------|------|
| WF00 Orchestrator | `/webhook/tp-generate` | POST | responseNode |
| WF02 Extract Requirements | `/webhook/tp-step-02-requirements` | POST | responseNode |
| WF03 Analyze Spec | `/webhook/tp-step-03-analyze` | POST | responseNode |
| WF04 Plan Document | `/webhook/tp-step-04-plan` | POST | responseNode |
| WF05 Write Section | `/webhook/tp-write-section` | POST | responseNode |
| WF06 Validate Section | `/webhook/tp-validate-section` | POST | responseNode |
| WF07 Finalize Document | `/webhook/tp-step-07-finalize` | POST | responseNode (⚠️ BYPASSED) |
| WF09 Update Status | `/webhook/internal/update-status` | POST | onReceived |
| WF09 Job Status | `/webhook/job-status` | GET | responseNode |
| WF09 Preview | `/webhook/preview` | GET | responseNode |
| WF09 Download | `/webhook/download` | GET | responseNode |

---

## 12. ORCHESTRATOR NODE MAP (за бърз reference)

```
Nodes:
  n01  Webhook                    n02  Init Job
  n03  Send Response              n04  Split Binary Files
  n05  Extract from PDF           n06  Merge Texts
  n07  Extract Requirements       n08  After Requirements
  n09  Analyze Spec               n10  After Spec Analysis
  n11  Plan Document              n12  Flatten Chunks
  n13  Loop Over Items            n14  Assemble Document
  n15  Prep Finalize (DISCONNECTED)  n16  Finalize Document (DISCONNECTED)
  n17  Pipeline Complete          n18  Prep Write
  n19  Write Section              n20  Prep Validate
  n21  Validate Section           n22  Check Validation (IF)
  n23  Accumulate Section         n24  Prep Rewrite
  n25  Rewrite Section            n26  Accumulate Retry
  gdrive1  Save to Google Drive

Status nodes (dead-end forks):
  s01  Status: Init (5%)          s02  Status: Requirements (20%)
  s03  Status: Analyzing (35%)    s04  Status: Planning (50%)
  s05  Status: Finalizing (88%)   s06  Status: Complete (100%)
  s07  Status: Writing (50-88%, dynamic per section)
```

---

## 13. ИНСТРУКЦИИ ЗА ПРОДЪЛЖАВАНЕ

### При започване на нова сесия:
1. **Прочети този файл** (PROJECT_CONTEXT.md) — пълен контекст
2. **Прочети `general_instructions.txt`** — глобални правила за стила
3. **Прочети `github_mcp_README.md`** — n8n специфични инструкции
4. **Питай потребителя**: "Какъв е резултатът от последния тест?" — за да знаеш какво трябва да се поправи
5. **Преди промени** — прочети конкретния JSON файл, не разчитай само на този контекст (може да е outdated)

### При дебъгване:
- Винаги питай за screenshot или error message от n8n Executions
- Проверявай кой node гърми и input/output данните
- Помни: n8n sandbox е ограничен (без fetch, ограничен в expressions)
- Проверявай дали ВСИЧКИ workflows са ACTIVATED

### При добавяне на нови features:
- Следвай pattern: Webhook → Code (prepare) → chainLlm → Code (parse) → Respond
- Добавяй `retryOnFail: true, maxTries: 3, waitBetweenTries: 15000` на HTTP ноди в orchestrator
- Добавяй CORS headers на Respond ноди
- Тествай с Production webhook URLs (`/webhook/`), не test (`/webhook-test/`)
- Добавяй `onError: "continueRegularOutput"` на некритични chainLlm nodes

### Чеклист преди тест:
- [ ] Всички workflows IMPORTED в n8n
- [ ] Всички workflows ACTIVATED (зелен toggle)
- [ ] Google Drive credential конфигуриран в "Save to Google Drive" node
- [ ] Frontend deployed (GitHub Pages) или локално
- [ ] DevTools: "Any XHR or fetch" breakpoint е ИЗКЛЮЧЕН
- [ ] Hard refresh (Ctrl+Shift+R) за нов JS код
