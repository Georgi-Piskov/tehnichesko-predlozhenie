# n8n Workflows — Настройка и конфигурация

## 📋 Общ преглед

Системата за генериране на технически предложения се състои от **2 n8n workflow-а**:

| Workflow | Файл | Описание |
|----------|------|----------|
| **Main Orchestrator** | `01-main-orchestrator.json` | Основният pipeline — приема документи, извлича изисквания, анализира спецификации, планира, пише, валидира и финализира |
| **Status & Download API** | `02-status-download-api.json` | API endpoints за проверка на статус, преглед и изтегляне на резултата |

## 🏗️ Архитектура

```
Frontend (GitHub Pages)
    │
    ├── POST /webhook/generate-proposal  ──→  Main Orchestrator
    │       (файлове + данни за фирмата)        │
    │       ←── { jobId }                       ├── Extract PDFs
    │                                           ├── LLM: Extract Requirements (Claude Sonnet 4)
    ├── GET /webhook/job-status?jobId=X  ──→    ├── LLM: Analyze Spec (Claude Sonnet 4)
    │       ←── { status, phase, progress }     ├── LLM: Plan Document (Claude Sonnet 4)
    │                                           ├── LLM: Write Sections (Claude Sonnet 4)
    ├── GET /webhook/preview?jobId=X     ──→    ├── LLM: Completeness Check (Claude Opus 4)
    │       ←── { html, stats }                 ├── LLM: Relevance Check (Gemini 2.5 Pro)
    │                                           ├── [If FAIL → Rewrite with Feedback, max 3x]
    └── GET /webhook/download?jobId=X    ──→    ├── LLM: Final Edit (Claude Opus 4)
            ←── Markdown file                   └── Save Result
```

## 🚀 Стъпки за настройка

### Стъпка 1: Създаване на OpenRouter credentials в n8n

1. Отвори n8n → **Settings** → **Credentials**
2. Натисни **Add Credential**
3. Избери **OpenAI API**
4. Попълни:
   - **Name**: `OpenRouter API`
   - **API Key**: вашият OpenRouter API ключ (от https://openrouter.ai/keys)
   - **Base URL**: `https://openrouter.ai/api/v1`
5. Натисни **Save**

> ⚠️ **ВАЖНО**: OpenRouter е OpenAI-съвместим. Използваме OpenAI credential типа с променен Base URL.

### Стъпка 2: Импортиране на workflow-ите

1. Отвори n8n → **Workflows**
2. Натисни **Add Workflow** → **Import from File**
3. Импортирай `01-main-orchestrator.json`
4. Повтори за `02-status-download-api.json`

### Стъпка 3: Свързване на credentials

След импортиране, всеки LLM node ще показва грешка за липсващи credentials:

1. Отвори **01-main-orchestrator** workflow
2. За ВСЕКИ node с име започващо с "Claude" или "Gemini":
   - Кликни на node-а
   - В полето **Credential** избери `OpenRouter API` (създаденият в Стъпка 1)
   - Потвърди
3. Nodes, които трябва да свържеш:
   - `Claude Sonnet - Requirements`
   - `Claude Sonnet - Spec`
   - `Claude Sonnet - Planner`
   - `Claude Sonnet - Writer`
   - `Claude Opus - Completeness`
   - `Gemini - Relevance`
   - `Claude Sonnet - Rewrite`
   - `Claude Opus - Final Edit`

### Стъпка 4: Активиране на workflow-ите

1. Активирай **02-status-download-api** (бутон Toggle горе вдясно)
2. Активирай **01-main-orchestrator**
3. Запиши Webhook URL-ите:
   - Production URL от Main Orchestrator: `https://YOUR-N8N.com/webhook/generate-proposal`
   - Production URL за Status: `https://YOUR-N8N.com/webhook/job-status`

### Стъпка 5: Конфигурация на Frontend

1. Отвори `js/app.js`
2. Промени `CONFIG.N8N_WEBHOOK_URL`:
   ```javascript
   const CONFIG = {
       N8N_WEBHOOK_URL: 'https://YOUR-N8N-INSTANCE.com'
   };
   ```
3. Замени с реалния URL на вашата n8n инстанция (без `/webhook/...` в края)

## 🔧 AI Модели (чрез OpenRouter)

| Роля | Модел | Защо |
|------|-------|------|
| Извличане на изисквания | `anthropic/claude-sonnet-4-20250514` | Бърз и точен за структурирано извличане |
| Анализ на спецификация | `anthropic/claude-sonnet-4-20250514` | Същият — ефективен за технически анализ |
| Планиране на документ | `anthropic/claude-sonnet-4-20250514` | Добро логично структуриране |
| Писане на секции | `anthropic/claude-sonnet-4-20250514` | Основен writer — бърз, качествен |
| Проверка за пълнота | `anthropic/claude-opus-4-20250514` | Критична валидация — най-мощният модел |
| Проверка за релевантност | `google/gemini-2.5-pro` | Cross-model валидация — различна перспектива |
| Пренаписване | `anthropic/claude-sonnet-4-20250514` | Бързи корекции по обратна връзка |
| Финална редакция | `anthropic/claude-opus-4-20250514` | Критична — финалното качество |

## 📡 API Endpoints

### POST `/webhook/generate-proposal`
**Тяло**: `multipart/form-data`

| Поле | Тип | Описание |
|------|-----|----------|
| `companyName` | string | Име на фирмата |
| `eik` | string | ЕИК номер |
| `address` | string | Адрес |
| `manager` | string | Управител |
| `phone` | string | Телефон |
| `email` | string | Имейл |
| `companyDescription` | string | Описание на фирмата |
| `files` | File[] | PDF/DOCX файлове (документация + спецификация) |

**Отговор**: `{ jobId: "tp-1234567890-abc123", status: "processing", message: "..." }`

### GET `/webhook/job-status?jobId=X`
**Отговор**:
```json
{
  "status": "processing | completed | error",
  "phase": "init | extracting | requirements | spec_analysis | planning | writing | validation | finalizing | completed",
  "progress": 0-100,
  "message": "Текущо описание на етапа"
}
```

### GET `/webhook/preview?jobId=X`
**Отговор**: `{ html: "<div>...</div>", stats: { wordCount, estimatedPages, placeholders, sections } }`

### GET `/webhook/download?jobId=X&format=docx`
**Отговор**: Binary file (Markdown)

## ⚠️ Важни бележки

### Споделяне на състояние между workflow-ите
Двата workflow-а използват `$getWorkflowStaticData('global')` за съхранение на job статус. Това работи само ако и двата workflow-а са в **една и съща n8n инстанция**.

**За production**: Заменете static data със:
- Redis
- PostgreSQL
- Google Sheets
- Или друга споделена база данни

### Лимит на payload (16MB)
n8n webhook-ите приемат до 16MB по подразбиране. За по-големи файлове:
- Увеличете `N8N_PAYLOAD_SIZE_MAX` env variable
- Или качвайте файловете в Google Drive и подавайте линкове

### Retry логика
Ако проверката за пълнота или релевантност върне FAIL:
- Текстът се пренаписва с обратна връзка
- Максимум 3 опита
- След 3-ти опит — продължава с финална редакция (best effort)

### DOCX конвертиране
Текущата имплементация генерира **Markdown** файл. За реално DOCX конвертиране:
1. Добавете `n8n-nodes-base.httpRequest` node, извикващ Markdown-to-DOCX API (напр. Pandoc API)
2. Или добавете Code node с `docx` npm библиотека
3. Или конвертирайте ръчно с Pandoc: `pandoc input.md -o output.docx --reference-doc=template.docx`

## 🔍 Тестване

### Тестване с n8n Test Webhook
1. Отвори Main Orchestrator workflow
2. Натисни **Test Workflow** (или F5)
3. Използвай `curl` или Postman:

```bash
curl -X POST https://YOUR-N8N.com/webhook-test/generate-proposal \
  -F "companyName=Барин АЛП ЕООД" \
  -F "eik=120898837" \
  -F "address=гр. Смолян" \
  -F "manager=Георги Писков" \
  -F "phone=0888123456" \
  -F "email=test@example.com" \
  -F "companyDescription=Строителна фирма" \
  -F "files=@path/to/Dokumentacia.pdf" \
  -F "files=@path/to/Specifikacia.pdf"
```

4. Следи изпълнението в n8n UI

### Тестване на Status endpoint
```bash
curl "https://YOUR-N8N.com/webhook-test/job-status?jobId=tp-1234567890-abc123"
```

## 📁 Структура на файловете

```
n8n/
├── workflows/
│   ├── 01-main-orchestrator.json    # Основен pipeline
│   ├── 02-status-download-api.json  # Status/Preview/Download API
│   └── SETUP.md                     # Тези инструкции
└── prompts/
    ├── requirement-extractor.md     # Prompt за извличане на изисквания
    ├── spec-analyzer.md             # Prompt за анализ на спецификация
    ├── document-planner.md          # Prompt за планиране на документ
    ├── section-writer.md            # Prompt за писане на секции
    ├── completeness-checker.md      # Prompt за проверка за пълнота
    ├── relevance-checker.md         # Prompt за проверка за релевантност
    ├── placeholder-marker.md        # Prompt за маркиране на placeholders
    └── final-editor.md             # Prompt за финална редакция
```

> **Забележка**: Prompt файловете в `/prompts/` са референтни. Реалните промптове са вградени директно в LLM Chain node-ите на workflow-ите за по-лесна работа. Ако желаете да ги промените, редактирайте prompt текста в съответния node в n8n.
