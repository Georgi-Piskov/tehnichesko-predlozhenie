# n8n Workflows — Настройка и конфигурация

## 📋 Общ преглед

Системата за генериране на технически предложения се състои от **9 отделни n8n workflow-а**, свързани чрез **Webhook + HTTP Request** Pattern. Всеки под-workflow е самостоятелен webhook endpoint. Оркестраторът вика всеки от тях последователно чрез HTTP Request POST:
- Лесно дебъгване — виждате точно къде се получава грешка
- Независимо тестване — всеки workflow може да се тества отделно чрез POST към неговия webhook
- По-малко timeout-и — всяка операция е по-кратка
- Лесно мащабиране — промяна на един workflow не засяга останалите
- Без остарели executeWorkflowTrigger nodes — всичко е Webhook + Respond to Webhook

## 🏗️ Архитектура

```
Frontend (GitHub Pages)
    │
    ├── POST /webhook/tp-generate ──→ 00 Orchestrator
    │     ←── { jobId }                   │
    │                                     ├── (inline) Split PDF → Extract Text
    │                                     ├── HTTP POST /webhook/tp-step-02-requirements → 02
    │                                     ├── HTTP POST /webhook/tp-step-03-analyze → 03
    │                                     ├── HTTP POST /webhook/tp-step-04-plan → 04
    │                                     ├── HTTP POST /webhook/tp-step-05-write → 05
    │                                     ├── HTTP POST /webhook/tp-step-06-validate → 06
    │                                     └── HTTP POST /webhook/tp-step-07-finalize → 07
    │
    │   (между всяка стъпка → status update)
    │           ↓
    ├── ← GET /webhook/job-status?jobId=X ──→ 09 Status API
    ├── ← GET /webhook/preview?jobId=X    ──→ 09 Status API
    └── ← GET /webhook/download?jobId=X   ──→ 09 Status API
```

> 📌 **Забележка**: Текстовото извличане (01) се изпълнява inline в оркестратора (Split Binary → Extract PDF → Merge). Workflow 01 съществува като самостоятелен webhook за директно тестване.

## 📦 Workflow-и

| # | Файл | Описание | AI модел |
|---|------|----------|----------|
| 00 | `00-orchestrator.json` | Главен координатор — приема файлове, извлича текст inline, вика 02-07 чрез HTTP Request | — |
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

### Стъпка 2: Импортиране на workflow-ите

Импортирайте всички workflow-и в n8n (редът не е от значение — няма workflow ID зависимости):

1. `09-status-api.json` — REST API за статус
2. `01-extract-text.json` — Самостоятелен webhook за извличане на текст
3. `02-extract-requirements.json` — Webhook за извличане на изисквания
4. `03-analyze-spec.json` — Webhook за анализ на спецификация
5. `04-plan-document.json` — Webhook за планиране
6. `05-write-document.json` — Webhook за писане
7. `06-validate-document.json` — Webhook за валидация
8. `07-finalize-document.json` — Webhook за финализиране
9. `00-orchestrator.json` — Главен координатор

> 💡 Не е нужно да свързвате Workflow ID-та! Оркестраторът вика под-workflow-ите чрез HTTP Request POST към техните webhook endpoints.

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

**ВСИЧКИ workflow-и трябва да бъдат активирани**, за да са достъпни техните webhook endpoints!

1. Активирайте **09-status-api** — ПЪРВО
2. Активирайте **02 до 07** — под-workflow-ите (те имат webhook endpoints, които оркестраторът вика)
3. Активирайте **00-orchestrator** — ПОСЛЕДНО
4. Workflow **01** е опционален — активирайте го само ако искате да тествате извличане на текст директно

> ⚠️ Ако под-workflow (02-07) НЕ е активиран, оркестраторът ще получи грешка при HTTP Request!

**Webhook endpoints след активиране:**

| Workflow | Webhook path |
|----------|--------------|
| 00 | `/webhook/tp-generate` |
| 01 | `/webhook/tp-step-01-extract` |
| 02 | `/webhook/tp-step-02-requirements` |
| 03 | `/webhook/tp-step-03-analyze` |
| 04 | `/webhook/tp-step-04-plan` |
| 05 | `/webhook/tp-step-05-write` |
| 06 | `/webhook/tp-step-06-validate` |
| 07 | `/webhook/tp-step-07-finalize` |

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
  ├─→ (inline) Split Binary → Extract PDF → Merge Texts
  │     Output: { fullText, documentCount, totalCharacters }
  │
  ├─→ HTTP POST → 02 Extract Requirements
  │     Input:  { fullText }
  │     Output: { requirements: { ... } }
  │
  ├─→ HTTP POST → 03 Analyze Spec
  │     Input:  { fullText }
  │     Output: { specData: { ... } }
  │
  ├─→ HTTP POST → 04 Plan Document
  │     Input:  { requirements, specData, contractorInfo }
  │     Output: { documentPlan: { ... } }
  │
  ├─→ HTTP POST → 05 Write Document
  │     Input:  { requirements, specData, contractorInfo, documentPlan }
  │     Output: { draftText, stats }
  │
  ├─→ HTTP POST → 06 Validate Document
  │     Input:  { draftText, requirements, specData }
  │     Output: { validationPassed, completenessResult, relevanceResult, rewriteInstructions }
  │
  └─→ HTTP POST → 07 Finalize Document
        Input:  { draftText, validationFeedback }
        Output: { finalText, stats }
```

## 📡 API Endpoints

### POST `/webhook/tp-generate`
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

Всеки workflow може да се тества чрез POST към неговия webhook:

**Примерен тест за 02-extract-requirements:**
```bash
curl -X POST https://n8n.simeontsvetanovn8nworkflows.site/webhook/tp-step-02-requirements \
  -H 'Content-Type: application/json' \
  -d '{"fullText": "1. Изпълнителят трябва да представи работна програма..."}'
```

> ⚠️ За тестване: при неактивиран workflow, ползвайте `/webhook-test/` вместо `/webhook/`

### Тестване на целия pipeline
```bash
curl -X POST https://n8n.simeontsvetanovn8nworkflows.site/webhook/tp-generate \
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
- Оркестраторът извършва PDF извличане inline (Split Binary → Extract from PDF → Merge)
- Workflow 01 е самостоятелен webhook за директно тестване на PDF извличане
- Code nodes преименуват бинарните полета на `data` за `Extract from File` node

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
│   ├── 00-orchestrator.json          # Координатор — inline PDF + HTTP Request към 02-07
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
