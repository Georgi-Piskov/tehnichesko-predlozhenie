# n8n Workflows — Настройка и конфигурация

## 📋 Общ преглед

Системата за генериране на технически предложения се състои от **9 отделни n8n workflow-а**, свързани чрез **Execute Sub-workflow** Pattern. Всеки workflow изпълнява една конкретна операция, което позволява:
- Лесно дебъгване — виждате точно къде се получава грешка
- Независимо тестване — всеки workflow може да се тества отделно
- По-малко timeout-и — всяка операция е по-кратка
- Лесно мащабиране — промяна на един workflow не засяга останалите

## 🏗️ Архитектура

```
Frontend (GitHub Pages)
    │
    ├── POST /webhook/generate-proposal ──→ 00 Orchestrator
    │     ←── { jobId }                        │
    │                                          ├── Execute Sub-WF → 01 Extract Text
    │                                          ├── Execute Sub-WF → 02 Extract Requirements
    │                                          ├── Execute Sub-WF → 03 Analyze Spec
    │                                          ├── Execute Sub-WF → 04 Plan Document
    │                                          ├── Execute Sub-WF → 05 Write Document
    │                                          ├── Execute Sub-WF → 06 Validate Document
    │                                          └── Execute Sub-WF → 07 Finalize Document
    │
    │   (между всяка стъпка → HTTP POST)
    │           ↓
    ├── ← GET /webhook/job-status?jobId=X ──→ 09 Status API
    ├── ← GET /webhook/preview?jobId=X    ──→ 09 Status API
    └── ← GET /webhook/download?jobId=X   ──→ 09 Status API
```

## 📦 Workflow-и

| # | Файл | Описание | AI модел |
|---|------|----------|----------|
| 00 | `00-orchestrator.json` | Главен координатор — приема файлове, вика под-workflow-и последователно, обновява статус | — |
| 01 | `01-extract-text.json` | Извлича текст от PDF/DOCX файлове | — |
| 02 | `02-extract-requirements.json` | Извлича всички изисквания от документацията | Claude Sonnet 4 |
| 03 | `03-analyze-spec.json` | Анализира техническата спецификация | Claude Sonnet 4 |
| 04 | `04-plan-document.json` | Създава план на документа | Claude Sonnet 4 |
| 05 | `05-write-document.json` | Пише целия документ (до 64K tokens) | Claude Sonnet 4 |
| 06 | `06-validate-document.json` | Двойна проверка: пълнота + релевантност | Claude Opus 4 + Gemini 2.5 Pro |
| 07 | `07-finalize-document.json` | Финална редакция и форматиране | Claude Opus 4 |
| 09 | `09-status-api.json` | Storage + REST endpoints за статус, преглед, изтегляне | — |

## 🚀 Стъпки за настройка

### Стъпка 1: Създаване на OpenRouter credentials

1. Отворете n8n → **Settings** → **Credentials**
2. Натиснете **Add Credential** → **OpenAI API**
3. Попълнете:
   - **Name**: `OpenRouter API`
   - **API Key**: вашият OpenRouter API ключ (от https://openrouter.ai/keys)
   - **Base URL**: `https://openrouter.ai/api/v1`
4. Натиснете **Save**

> ⚠️ OpenRouter е OpenAI-съвместим. Използваме OpenAI credential с променен Base URL.

### Стъпка 2: Импортиране на workflow-ите (редът е ВАЖЕН!)

Импортирайте в този ред, за да може по-лесно да свържете ID-тата:

1. **Първо** — импортирайте **под-workflow-ите** (01–07 и 09):
   - `09-status-api.json`
   - `01-extract-text.json`
   - `02-extract-requirements.json`
   - `03-analyze-spec.json`
   - `04-plan-document.json`
   - `05-write-document.json`
   - `06-validate-document.json`
   - `07-finalize-document.json`

2. **Последно** — импортирайте **00-orchestrator.json**

### Стъпка 3: Свържете Workflow ID-та в Orchestrator-а

След импортиране, всеки workflow получава уникално ID. Трябва да ги въведете в Orchestrator-а:

1. Отворете всеки импортиран workflow и запишете ID-то му (от URL-а: `/workflow/XXXX`)
2. Отворете **00 Orchestrator**
3. Намерете всеки **Execute Sub-workflow** node и попълнете правилното ID:

| Node в Orchestrator-а | Workflow ID за |
|----------------------|----------------|
| `Extract Text` | ID на `TP - Step 1: Extract Text` |
| `Extract Requirements` | ID на `TP - Step 2: Extract Requirements` |
| `Analyze Spec` | ID на `TP - Step 3: Analyze Spec` |
| `Plan Document` | ID на `TP - Step 4: Plan Document` |
| `Write Document` | ID на `TP - Step 5: Write Document` |
| `Validate Document` | ID на `TP - Step 6: Validate Document` |
| `Finalize Document` | ID на `TP - Step 7: Finalize Document` |

> 💡 **Съвет**: В n8n, може да изберете workflow-а от падащ списък вместо да поставяте ID ръчно. Кликнете на Execute Sub-workflow node → Source: Database → From list → изберете правилния workflow.

### Стъпка 4: Свържете credentials за LLM nodes

За ВСЕКИ workflow с LLM (02, 03, 04, 05, 06, 07):

1. Отворете workflow-а
2. Намерете node-а с модел (Claude Sonnet, Claude Opus, Gemini Pro)
3. В полето **Credential** изберете `OpenRouter API`

**Списък на модел nodes по workflow:**

| Workflow | Node | Модел |
|----------|------|-------|
| 02 | Claude Sonnet | `anthropic/claude-sonnet-4-20250514` |
| 03 | Claude Sonnet | `anthropic/claude-sonnet-4-20250514` |
| 04 | Claude Sonnet | `anthropic/claude-sonnet-4-20250514` |
| 05 | Claude Sonnet | `anthropic/claude-sonnet-4-20250514` |
| 06 | Claude Opus (Completeness) | `anthropic/claude-opus-4-20250514` |
| 06 | Gemini Pro (Relevance) | `google/gemini-2.5-pro` |
| 07 | Claude Opus | `anthropic/claude-opus-4-20250514` |

### Стъпка 5: Активиране

1. Активирайте **09-status-api** — ПЪРВО (Orchestrator-ът праща status updates към него)
2. Активирайте **00-orchestrator** — ВТОРО
3. Под-workflow-ите (01–07) НЕ е нужно да се активират — те се викат директно от Orchestrator-а

### Стъпка 6: Конфигурация на Frontend

`js/app.js` вече е конфигуриран с:
```javascript
const CONFIG = {
    N8N_WEBHOOK_URL: 'https://n8n.simeontsvetanovn8nworkflows.site'
};
```

## 📊 Поток на данните

```
Webhook (FormData: contractor JSON + PDF бинарни файлове)
  │
  ├─→ 01 Extract Text
  │     Input:  binary { documentation, specification }
  │     Output: { fullText, documentCount, totalCharacters }
  │
  ├─→ 02 Extract Requirements
  │     Input:  { fullText }
  │     Output: { requirements: { ... } }
  │
  ├─→ 03 Analyze Spec
  │     Input:  { fullText }
  │     Output: { specData: { ... } }
  │
  ├─→ 04 Plan Document
  │     Input:  { requirements, specData, contractorInfo }
  │     Output: { documentPlan: { ... } }
  │
  ├─→ 05 Write Document
  │     Input:  { requirements, specData, contractorInfo, documentPlan }
  │     Output: { draftText, stats }
  │
  ├─→ 06 Validate Document
  │     Input:  { draftText, requirements, specData }
  │     Output: { validationPassed, completenessResult, relevanceResult, rewriteInstructions }
  │
  └─→ 07 Finalize Document
        Input:  { draftText, validationFeedback }
        Output: { finalText, stats }
```

## 📡 API Endpoints

### POST `/webhook/generate-proposal`
**Тяло**: `multipart/form-data`

| Поле | Тип | Описание |
|------|-----|----------|
| `contractor` | JSON string | `{"name":"...", "city":"...", "manager":"...", ...}` |
| `documentation` | File | PDF/DOCX — документация за обществената поръчка |
| `specification` | File | PDF/DOCX — техническа спецификация |
| `additionalNotes` | string | Допълнителни бележки (опционално) |

**Отговор**: `{ success: true, jobId: "tp_1234567890_abc123" }`

### GET `/webhook/job-status?jobId=X`
```json
{
  "status": "processing | completed | error | not_found",
  "phase": "extracting_requirements | analyzing_spec | planning | writing | validating | finalizing | exporting",
  "progress": 0-100,
  "message": "Текущо описание"
}
```

### GET `/webhook/preview?jobId=X`
```json
{ "html": "<div>...</div>", "stats": { "wordCount": 28000, "pages": 75, "placeholders": 25 } }
```

### GET `/webhook/download?jobId=X`
Binary Markdown файл

## 🔧 Обновяване на статуса

Orchestrator-ът обновява статуса чрез `fetch()` в Code nodes:
```javascript
await fetch('https://n8n.simeontsvetanovn8nworkflows.site/webhook/internal/update-status', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ jobId, status, phase, progress, message })
});
```

> ⚠️ Ако `fetch()` не работи във вашата n8n sandbox, заменете всеки Code node в orchestrator-а с два отделни node-а: HTTP Request (за status update) + Code (за data prep). Обработката на данни ще продължи нормално — status updates са обвити в try-catch.

## 🔍 Тестване

### Тестване на отделен под-workflow

Всеки workflow може да се тества независимо:

1. Отворете желания workflow в n8n
2. Натиснете **Test Workflow**
3. Задайте тестови входни данни чрез Manual Trigger или директно в Execute Workflow Trigger

**Примерен тест за 02-extract-requirements:**
```json
{
  "fullText": "1. Изпълнителят трябва да представи работна програма... 2. Организация на строителната площадка..."
}
```

### Тестване на целия pipeline
```bash
curl -X POST https://n8n.simeontsvetanovn8nworkflows.site/webhook/generate-proposal \
  -F 'contractor={"name":"Барин АЛП ЕООД","city":"Смолян","manager":"Георги Писков"}' \
  -F "documentation=@path/to/Dokumentacia.pdf" \
  -F "specification=@path/to/Specifikacia.pdf"
```

### Тестване на Status API
```bash
curl "https://n8n.simeontsvetanovn8nworkflows.site/webhook/job-status?jobId=tp_1234567890_abc123"
```

## ⚠️ Важни бележки

### Binary данни
- `01-extract-text` очаква binary файлове в полета `documentation` и/или `specification`
- Code node в workflow 01 преименува бинарните полета на `data` за `Extract from File` node

### Лимити
- n8n webhook: 16MB по подразбиране (`N8N_PAYLOAD_SIZE_MAX`)
- LLM контекст: текстът се отрязва на 80,000 символа за prompt-ите
- Write Document: maxTokens = 64,000

### Static Data (Status API)
`09-status-api` използва `$getWorkflowStaticData('global')` за съхранение на job статуси. Данните се пазят в паметта на n8n и могат да се загубят при рестарт.

**За production**: заменете с Redis, PostgreSQL или Google Sheets.

### DOCX конвертиране
Системата генерира **Markdown** файл. За DOCX:
- Pandoc: `pandoc input.md -o output.docx --reference-doc=template.docx`
- Или добавете HTTP Request node за online Markdown-to-DOCX API

## 📁 Структура на файловете

```
n8n/
├── workflows/
│   ├── 00-orchestrator.json          # Координатор — вика под-workflow-и
│   ├── 01-extract-text.json          # PDF → текст
│   ├── 02-extract-requirements.json  # Текст → изисквания (Claude Sonnet)
│   ├── 03-analyze-spec.json          # Текст → тех. параметри (Claude Sonnet)
│   ├── 04-plan-document.json         # Изисквания → план (Claude Sonnet)
│   ├── 05-write-document.json        # Всички данни → документ (Claude Sonnet 64K)
│   ├── 06-validate-document.json     # Двойна проверка (Opus + Gemini)
│   ├── 07-finalize-document.json     # Финална редакция (Claude Opus)
│   ├── 09-status-api.json            # REST API за статус/преглед/изтегляне
│   └── SETUP.md                      # Тези инструкции
└── prompts/                          # Референтни prompt файлове
    ├── requirement-extractor.md
    ├── spec-analyzer.md
    ├── document-planner.md
    ├── section-writer.md
    ├── completeness-checker.md
    ├── relevance-checker.md
    ├── placeholder-marker.md
    └── final-editor.md
```

> Prompt файловете в `/prompts/` са референтни. Промптовете са вградени директно в LLM Chain nodes.
