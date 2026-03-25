"""
Convert WF04 (Plan Document) from chainLlm to Agent + Code Tool.

Changes:
1. Prepare Plan Prompt: stores specData in workflow static data, builds summary for prompt
2. Plan Document: chainLlm → Agent node (typeVersion 1.6)
3. NEW: Analyze Spec Tool (toolCode) — allows Agent to query spec data programmatically
4. Parse Plan: updated to read from $json.output (Agent output format)
5. Connections: updated for Agent + Tool wiring
"""

import json

WF_PATH = 'n8n/workflows/04-plan-document.json'

with open(WF_PATH, 'r', encoding='utf-8') as f:
    wf = json.load(f)

# =============================================================================
# 1. PREPARE PLAN PROMPT — store specData in static data, build summary
# =============================================================================
PREP_CODE = r"""var body = $json.body || $json;
var reqs = body.requirements || {};
var reqType = reqs.procurement_type || 'неопределен';
var extractionFailed = body.requirementsExtractionFailed === true;
var hasReqs = reqs.requirements && Array.isArray(reqs.requirements) && reqs.requirements.length > 0;
if (!hasReqs && Array.isArray(reqs) && reqs.length > 0) hasReqs = true;
var reqStr = JSON.stringify(reqs, null, 2);
if (reqStr.length > 40000) reqStr = reqStr.substring(0, 40000);
var specData = body.specData || {};
var ciStr = JSON.stringify(body.contractorInfo || {}, null, 2);
var docText = (body.documentationText || '').substring(0, 40000);
var targetPages = parseInt(body.targetPages) || 50;

// Store FULL spec data in workflow static data for the Code Tool
var sd = $getWorkflowStaticData('global');
sd._specData = specData;
sd._requirements = reqs;

// Build spec SUMMARY for the prompt (instead of full dump)
var specSummary = '';
var specKeys = Object.keys(specData);
if (specKeys.length > 0) {
  specSummary += 'Спецификацията съдържа ' + specKeys.length + ' основни раздела:\n';
  for (var k = 0; k < specKeys.length; k++) {
    var key = specKeys[k];
    var val = specData[key];
    if (Array.isArray(val)) {
      specSummary += '- ' + key + ': масив с ' + val.length + ' елемента';
      if (val.length > 0 && typeof val[0] === 'object') {
        specSummary += ' (полета: ' + Object.keys(val[0]).slice(0, 8).join(', ') + ')';
      }
      specSummary += '\n';
    } else if (typeof val === 'object' && val !== null) {
      specSummary += '- ' + key + ': обект с полета: ' + Object.keys(val).slice(0, 10).join(', ') + '\n';
    } else {
      specSummary += '- ' + key + ': ' + String(val).substring(0, 200) + '\n';
    }
  }
  // Add first 3 items as examples for the most populated array
  var biggestArr = '';
  var biggestLen = 0;
  for (var k = 0; k < specKeys.length; k++) {
    if (Array.isArray(specData[specKeys[k]]) && specData[specKeys[k]].length > biggestLen) {
      biggestLen = specData[specKeys[k]].length;
      biggestArr = specKeys[k];
    }
  }
  if (biggestArr && biggestLen > 0) {
    specSummary += '\nПримерни елементи от "' + biggestArr + '":\n';
    var examples = specData[biggestArr].slice(0, 3);
    for (var e = 0; e < examples.length; e++) {
      specSummary += JSON.stringify(examples[e]).substring(0, 400) + '\n';
    }
    if (biggestLen > 3) specSummary += '... и още ' + (biggestLen - 3) + ' елемента\n';
  }
} else {
  specSummary = 'Спецификацията е празна или не е предоставена.';
}

var p = '';

p += '# ЗАДАЧА\n';
p += 'Създай ДЕТАЙЛЕН ПЛАН за техническо предложение, като РАЗЛОЖИШ изискванията ИЗРЕЧЕНИЕ ПО ИЗРЕЧЕНИЕ.\n\n';
p += 'ТИП ПОРЪЧКА: ' + reqType + '\n\n';

if (extractionFailed || !hasReqs) {
  p += '## ВАЖНО: АВТОМАТИЧНОТО ИЗВЛИЧАНЕ НА ИЗИСКВАНИЯ НЕ УСПЯ\n';
  p += 'Предоставяме ти СУРОВИЯ ТЕКСТ на документацията. ЗАДЪЛЖИТЕЛНО:\n';
  p += '1. ПРОЧЕТИ внимателно целия текст.\n';
  p += '2. НАМЕРИ разделите за техническо предложение/показатели за оценка/методика за оценка.\n';
  p += '3. ИЗВЛЕЧИ всяко номерирано изискване с ДОСЛОВНИЯ му текст.\n';
  p += '4. Използвай ИЗВЛЕЧЕНИТЕ изисквания за основа на плана.\n\n';
  if (docText.length > 0) {
    p += '## СУРОВ ТЕКСТ НА ДОКУМЕНТАЦИЯТА\n' + docText + '\n\n';
  }
  if (reqStr !== '{}' && reqStr !== '[]') {
    p += '## ЧАСТИЧНО ИЗВЛЕЧЕНИ ИЗИСКВАНИЯ (може да са непълни)\n' + reqStr + '\n\n';
  }
} else {
  p += '## ИЗВЛЕЧЕНИ ИЗИСКВАНИЯ\n' + reqStr + '\n\n';
}

p += '## ОБЗОР НА СПЕЦИФИКАЦИЯТА\n' + specSummary + '\n\n';
p += '⚠️ ИЗПОЛЗВАЙ ИНСТРУМЕНТА analyze_spec за да проучиш спецификацията в детайли!\n';
p += 'Задължително извикай analyze_spec ПРЕДИ да създадеш плана.\n\n';

p += '## ИНФОРМАЦИЯ ЗА ИЗПЪЛНИТЕЛЯ\n' + ciStr + '\n\n';

p += '## МЕТОД НА РАБОТА\n\n';

p += '### СТЪПКА 0: ПРОУЧИ СПЕЦИФИКАЦИЯТА (задължителна)\n';
p += 'Използвай инструмента analyze_spec за да:\n';
p += '1. Извикай {"action": "structure"} — виж структурата на спецификацията\n';
p += '2. Извикай {"action": "get", "param": "field_name"} за всяко релевантно поле\n';
p += '3. Извикай {"action": "search", "param": "ключова дума"} за конкретни данни\n';
p += 'Целта е да разбереш ПЪЛНАТА спецификация преди да правиш план.\n\n';

p += '### СТЪПКА 1: РАЗЛАГАНЕ НА ИЗИСКВАНИЯ (задължителна)\n';
p += 'Преди да правиш план, РАЗЛОЖИ всяко изискване ИЗРЕЧЕНИЕ ПО ИЗРЕЧЕНИЕ:\n';
p += '1. Прочети full_text на ВСЯКО изискване.\n';
p += '2. Всяко отделно изречение/фраза описва ОТДЕЛЕН структурен елемент — идентифицирай го.\n';
p += '3. Пример: "Предложение за изпълнение на отделните етапи. Следва да бъдат обхванати всички работни и технологични процеси" → ТРИ елемента:\n';
p += '   а) "етапи на изпълнение" → секция с подсекция за ВСЕКИ отделен етап от спецификацията\n';
p += '   б) "работни процеси" → секция с подсекция за ВСЕКИ работен процес\n';
p += '   в) "технологични процеси" → секция с подсекция за ВСЕКИ технологичен процес\n';
p += '4. Когато изискване казва "минимум N мерки/елемента" → създай ТОЧНО N (или повече) подсекции.\n';
p += '5. sub_requirements ЗАДЪЛЖИТЕЛНО стават подсекции.\n';
p += '6. Фрази като "включително", "в това число", "като обхваща" → ВСЯКО изброено нещо = отделен елемент.\n\n';

p += '### СТЪПКА 2: ИЗВЛИЧАНЕ НА ПРАВИЛА ЗА ПИСАНЕ\n';
p += 'Изискванията съдържат ДВА типа информация:\n';
p += 'А) СЪДЪРЖАТЕЛНИ — какво трябва да присъства → стават секции и подсекции на плана\n';
p += 'Б) КАЧЕСТВЕНИ — как трябва да е написано → стават writing_rules\n';
p += 'Примери за качествени:\n';
p += '- "изложението да не е формално" → writing_rule\n';
p += '- "да отчита спецификата на конкретния предмет" → writing_rule\n';
p += '- "по своята същност да може да се съотнесе към съответния елемент" → writing_rule\n';
p += '- Ако дефинират какво е "формално" → включи дефиницията ДОСЛОВНО в source_text на writing_rule\n\n';

p += '### СТЪПКА 3: СЪЗДАВАНЕ НА ПЛАН\n\n';

p += '#### Структурни правила\n';
p += '- Секции = requirement IDs (1.1, 1.2, ...) с ТОЧНИТЕ заглавия от изискванията\n';
p += '- НЕ добавяй секции непоискани от възложителя\n';
p += '- НЕ преименувай секциите\n';
p += '- Всяка ГЛАВНА секция → МИНИМУМ 3 подсекции\n';
p += '- Всяка подсекция → МИНИМУМ 3 конкретни указания в content_guidance\n';
p += '- Подсекция може да има свои подсекции (до 4 нива дълбочина)\n';
p += '- Максимум 5 страници на най-долна подсекция\n';
p += '- Изисквания от общ характер (срок, гаранции) НЕ стават отделни секции — интегрират се в съответните\n';
p += '- Линеен график ЗАДЪЛЖИТЕЛНО е ОТДЕЛНА подсекция с таблична форма\n\n';

p += '#### Правила за мерки\n';
p += 'Когато изискване изисква МЯРКА:\n';
p += '- Всяка мярка = ОТДЕЛНА подсекция\n';
p += '- content_guidance за мярка ЗАДЪЛЖИТЕЛНО съдържа инструкция за 7 елемента:\n';
p += '  1. Наименование на мярката\n';
p += '  2. Същност — какво постига\n';
p += '  3. Конкретни дейности за изпълнение\n';
p += '  4. Времеви план за прилагане\n';
p += '  5. Конкретен експерт + задължения\n';
p += '  6. Контрол и мониторинг (честота, действия при отклонения, отговорни лица)\n';
p += '  7. Очакван ефект от мярката\n';
p += '- ЗАБРАНЕНО е обединяване на елементи от различни мерки!\n\n';

p += '#### Правила за content_guidance\n';
p += 'content_guidance НЕ ТРЯБВА да е абстрактно! За всяка подсекция:\n';
p += '- Включи КОНКРЕТНИ данни от спецификацията (количества, артикули, параметри, локации)\n';
p += '- Дай КОНКРЕТНА инструкция: "Опиши етапа на демонтаж на 350 м2 стари подови настилки в сграда A, бл. 3"\n';
p += '- НЕ пиши: "Опиши етапа на демонтаж" без конкретика\n';
p += '- Посочи кои таблици да се включат с КОНКРЕТНИ колони и данни\n';
p += '- Всяка подсекция ще бъде писана от ОТДЕЛЕН AI агент — указанията ТРЯБВА да са САМОДОСТАТЪЧНИ\n';
p += '- Ако в спецификацията има конкретни стойности — ЦИТИРАЙ ги в content_guidance\n\n';

p += '## ФОРМАТ\n';
p += 'Върни САМО валиден JSON (БЕЗ markdown блокове):\n';
p += '{\n';
p += '  "document_title": "ПРЕДЛОЖЕНИЕ ЗА ИЗПЪЛНЕНИЕ на [точно наименование на поръчката]",\n';
p += '  "procurement_type": "' + reqType + '",\n';
p += '  "total_estimated_pages": ' + targetPages + ',\n';
p += '  "writing_rules": [\n';
p += '    {\n';
p += '      "rule_id": "WR1",\n';
p += '      "rule": "Кратко описание на правилото",\n';
p += '      "source_text": "ДОСЛОВЕН цитат от документацията на възложителя",\n';
p += '      "instruction_for_writer": "Конкретна инструкция какво да прави writer-ът",\n';
p += '      "instruction_for_validator": "Как validator-ът да проверява спазването",\n';
p += '      "violation_consequence": "отстраняване | намалени точки | забележка"\n';
p += '    }\n';
p += '  ],\n';
p += '  "sections": [\n';
p += '    {\n';
p += '      "id": "1.1",\n';
p += '      "title": "ТОЧНО заглавието от изискването",\n';
p += '      "requirement_id": "1.1",\n';
p += '      "source_decomposition": [\n';
p += '        {"source_phrase": "изречението от което произлиза", "structural_type": "etap|process|measure|table|timeline"}\n';
p += '      ],\n';
p += '      "subsections": [\n';
p += '        {\n';
p += '          "id": "1.1.1",\n';
p += '          "title": "Подзаглавие",\n';
p += '          "estimated_pages": 4,\n';
p += '          "content_guidance": [\n';
p += '            "КОНКРЕТНА инструкция 1 с данни от спецификацията",\n';
p += '            "КОНКРЕТНА инструкция 2...",\n';
p += '            "КОНКРЕТНА инструкция 3..."\n';
p += '          ],\n';
p += '          "spec_data_to_use": ["key_quantities", "technical_parameters"],\n';
p += '          "tables_needed": [{"title": "Заглавие", "columns": ["Кол1", "Кол2"]}],\n';
p += '          "subsections": []\n';
p += '        }\n';
p += '      ]\n';
p += '    }\n';
p += '  ],\n';
p += '  "appendices": []\n';
p += '}\n\n';

p += '## ЦЕЛЕВИ ОБЕМ: ' + targetPages + ' СТРАНИЦИ\n';
p += 'Целевият обем на документа е ' + targetPages + ' страници.\n';
p += 'Разпредели estimated_pages между подсекциите така че сумата да се доближава до ' + targetPages + '.\n';
p += 'За по-голям обем: повече подсекции + повече страници на подсекция (до 8 стр. макс).\n';
p += 'За по-малък обем: по-малко подсекции + по-кратки (2-3 стр.).\n\n';

p += '## КРИТИЧНИ ПРАВИЛА\n';
p += '1. Секциите = requirement IDs. НЕ измисляй собствена структура!\n';
p += '2. МИНИМУМ 3 подсекции на секция, МИНИМУМ 3 content_guidance на подсекция.\n';
p += '3. Всяка мярка = ОТДЕЛНА подсекция с инструкция за 7 елемента.\n';
p += '4. content_guidance включва КОНКРЕТНИ ДАННИ от спецификацията!\n';
p += '5. Разложи изискванията ИЗРЕЧЕНИЕ ПО ИЗРЕЧЕНИЕ — всяко изречение = структурен елемент.\n';
p += '6. writing_rules = качествените изисквания от документацията.\n';
p += '7. САМО JSON, без друг текст.\n';
p += '8. В content_guidance: ЗАБРАНЕНО е да се задават конкретни имена на хора. Вместо това пишете: [⚠️ ПОПЪЛНЕТЕ: име на ръководител обект], [⚠️ ПОПЪЛНЕТЕ: име на експерт по качество] и т.н.';

return [{ json: { prompt: p } }];"""

# =============================================================================
# 2. SYSTEM MESSAGE for the Agent
# =============================================================================
SYSTEM_MSG = """# РОЛЯ И ЦЕЛ
Ти си експерт по структуриране на технически предложения за обществени поръчки в Република България. Създаваш ДЕТАЙЛНИ планове, разлагайки изискванията на възложителя ИЗРЕЧЕНИЕ ПО ИЗРЕЧЕНИЕ.

# ИНСТРУМЕНТИ
Имаш достъп до инструмент analyze_spec за проучване на спецификацията. ЗАДЪЛЖИТЕЛНО го използвай ПРЕДИ да създадеш плана:
1. Първо извикай {"action": "structure"} — виж какви данни има в спецификацията
2. После извикай {"action": "get", "param": "име_на_поле"} за всяко важно поле
3. Извикай {"action": "search", "param": "ключова дума"} за конкретни данни (напр. количества, материали, сгради)
Целта: СЪБЕРИ МАКСИМАЛНО КОНКРЕТНИ ДАННИ от спецификацията за content_guidance на всяка подсекция.

# МЕТОД НА РАБОТА — РАЗЛАГАНЕ НА ИЗИСКВАНИЯ
Преди да създадеш план, ЗАДЪЛЖИТЕЛНО разложи ВСЯКО изискване:
1. Прочети full_text на изискването ИЗРЕЧЕНИЕ ПО ИЗРЕЧЕНИЕ
2. Всяко изречение/фраза описва ОТДЕЛЕН структурен елемент → става подсекция
3. "минимум N мерки" → ТОЧНО N подсекции за мерки
4. "включително A, B, C" → ТРИ отделни подсекции
5. Sub-requirements → ЗАДЪЛЖИТЕЛНИ подсекции
6. Кръстосани препратки ("съгласно ТС") → запиши ги за writer-а

# СТРУКТУРНИ ИЗИСКВАНИЯ
- Секции = requirement IDs с ТОЧНИТЕ заглавия от документацията
- МИНИМУМ 3 подсекции на главна секция
- МИНИМУМ 3 елемента content_guidance на подсекция
- Подсекции могат да имат свои подсекции (до 4 нива дълбочина)
- Максимум 5 стр. на най-долна подсекция
- Линеен график = ОТДЕЛНА подсекция с таблична форма

# КАЧЕСТВЕНИ ПРАВИЛА (writing_rules)
Изискванията съдържат ДВА типа информация:
- СЪДЪРЖАТЕЛНИ (какво трябва да присъства) → стават секции/подсекции
- КАЧЕСТВЕНИ (как трябва да е написано) → стават writing_rules
Извлечи ВСИЧКИ качествени изисквания в writing_rules. Включи:
- Дословен цитат от документацията
- Конкретна инструкция за writer-а
- Конкретна инструкция за validator-а
- Последица при нарушение

# ФОРМАТ НА МЕРКИ
Всяка мярка = ОТДЕЛНА подсекция с 7 елемента в content_guidance:
наименование, същност, дейности, времеви план, експерт+задължения, контрол+мониторинг, очакван ефект.
ЗАБРАНЕНО: обединяване на елементи от различни мерки.

# content_guidance — НЕ АБСТРАКТНО!
Всяко указание ТРЯБВА да е КОНКРЕТНО с данни от спецификацията:
ДОБРО: "Опиши доставката на 15 бр. климатици за сграда X — модели, монтаж, изпитвания"
ЛОШО: "Опиши процеса на доставка"
Всяка подсекция ще се пише от ОТДЕЛЕН AI агент → указанията ТРЯБВА да са САМОДОСТАТЪЧНИ.

# СТЪПКИ
1. Използвай analyze_spec за да проучиш ЦЯЛАТА спецификация — види структура, категории, количества
2. За всяко изискване: разложи full_text изречение по изречение → идентифицирай структурните елементи
3. Раздели на съдържателни (→ секции) и качествени (→ writing_rules)
4. За всеки структурен елемент → определи подсекции (мин. 3 на секция)
5. За всяка подсекция → напиши КОНКРЕТНИ content_guidance с данни от спецификацията (мин. 3)
6. Мерки → отделни подсекции с пълен 7-елементен формат
7. Провери: покрити ли са ВСИЧКИ изречения от ВСЯКО изискване?
8. Провери: има ли поне 3 подсекции на секция? Поне 3 content_guidance на подсекция?

# ФОРМАТ
Изход: САМО валиден JSON. Без markdown блокове, без обяснения. Език: български."""

# =============================================================================
# 3. CODE TOOL — analyze_spec
# =============================================================================
TOOL_NAME = "analyze_spec"
TOOL_DESC = """Анализирай спецификацията на обществената поръчка. Изпращай JSON команди:

- {"action": "structure"} — покажи структурата (полета, масиви, размери)
- {"action": "summary"} — кратко обобщение с примерни данни
- {"action": "get", "param": "field_name"} — вземи съдържанието на конкретно поле (използвай точните имена от structure)
- {"action": "search", "param": "ключова дума"} — търси навсякъде в спецификацията (напр. "подова настилка", "климатик", "сграда А")
- {"action": "group", "param": "field_name"} — групирай елементи по поле (напр. "category", "section", "building")
- {"action": "count"} — общ брой елементи и имена на полета

Можеш да изпратиш и просто текст — ще се търси като ключова дума.
ВАЖНО: Извикай structure/summary ПЪРВО, после get/search за конкретни данни."""

TOOL_CODE = r"""// Tool input from agent is in 'query' variable
var sd = $getWorkflowStaticData('global');
var specData = sd._specData || {};

// Parse command
var action, param;
try {
  var cmd = JSON.parse(query);
  action = cmd.action || 'search';
  param = cmd.param || cmd.keyword || cmd.category || cmd.field || '';
} catch(e) {
  action = 'search';
  param = query;
}

// Generic item extraction from nested structures
function extractItems(data) {
  var items = [];
  if (!data || typeof data !== 'object') return items;
  if (Array.isArray(data)) {
    for (var i = 0; i < data.length; i++) {
      if (typeof data[i] === 'object' && data[i] !== null) items.push(data[i]);
    }
    return items;
  }
  for (var key in data) {
    if (Array.isArray(data[key])) {
      for (var j = 0; j < data[key].length; j++) {
        if (typeof data[key][j] === 'object' && data[key][j] !== null) {
          data[key][j]._source_field = key;
          items.push(data[key][j]);
        }
      }
    }
  }
  return items;
}

var allItems = extractItems(specData);

if (action === 'structure') {
  var result = {};
  for (var key in specData) {
    var val = specData[key];
    if (Array.isArray(val)) {
      result[key] = 'Масив с ' + val.length + ' елемента';
      if (val.length > 0 && typeof val[0] === 'object') {
        result[key] += ' (полета: ' + Object.keys(val[0]).slice(0, 12).join(', ') + ')';
      }
    } else if (typeof val === 'object' && val !== null) {
      result[key] = 'Обект с ' + Object.keys(val).length + ' полета: ' + Object.keys(val).slice(0, 12).join(', ');
    } else {
      result[key] = typeof val + ': ' + String(val).substring(0, 300);
    }
  }
  return JSON.stringify(result, null, 2);

} else if (action === 'summary') {
  var summary = 'Обща структура: ' + Object.keys(specData).length + ' полета\n';
  summary += 'Общо елементи: ' + allItems.length + '\n\n';
  for (var key in specData) {
    var val = specData[key];
    if (Array.isArray(val)) {
      summary += '## ' + key + ' (' + val.length + ' елемента)\n';
      if (val.length > 0 && typeof val[0] === 'object') {
        summary += 'Полета: ' + Object.keys(val[0]).join(', ') + '\n';
        for (var i = 0; i < Math.min(3, val.length); i++) {
          summary += 'Пример ' + (i+1) + ': ' + JSON.stringify(val[i]).substring(0, 500) + '\n';
        }
        if (val.length > 3) summary += '... и още ' + (val.length - 3) + ' елемента\n';
      }
      summary += '\n';
    } else if (typeof val === 'object' && val !== null) {
      var s = JSON.stringify(val, null, 2);
      summary += '## ' + key + ' (обект)\n' + s.substring(0, 1000) + '\n\n';
    } else {
      summary += '## ' + key + ': ' + String(val).substring(0, 500) + '\n\n';
    }
  }
  if (summary.length > 15000) summary = summary.substring(0, 15000) + '\n...[използвай get/search за повече детайли]';
  return summary;

} else if (action === 'get') {
  // Get a specific field (supports dot notation: "field.subfield")
  var parts = param.split('.');
  var current = specData;
  for (var i = 0; i < parts.length; i++) {
    if (current === null || current === undefined) break;
    // Support array index access: "items.0" or "items[0]"
    var part = parts[i].replace(/\[(\d+)\]/, '.$1');
    var subParts = part.split('.');
    for (var j = 0; j < subParts.length; j++) {
      if (current === null || current === undefined) break;
      var idx = parseInt(subParts[j]);
      if (!isNaN(idx) && Array.isArray(current)) {
        current = current[idx];
      } else {
        current = current[subParts[j]];
      }
    }
  }
  if (current === undefined || current === null) return 'Полето "' + param + '" не е намерено. Налични полета: ' + Object.keys(specData).join(', ');
  var r = JSON.stringify(current, null, 2);
  if (r.length > 15000) r = r.substring(0, 15000) + '\n...[резултатът е съкратен, използвай search за филтриране]';
  return r;

} else if (action === 'search') {
  var q = param.toLowerCase();
  if (!q) return 'Моля, задай ключова дума за търсене.';
  var found = [];

  // Search in all extracted items
  for (var i = 0; i < allItems.length; i++) {
    var itemStr = JSON.stringify(allItems[i]).toLowerCase();
    if (itemStr.indexOf(q) !== -1) {
      found.push(allItems[i]);
    }
  }

  // If no items found, search in top-level values
  if (found.length === 0) {
    for (var key in specData) {
      var valStr = JSON.stringify(specData[key]).toLowerCase();
      if (valStr.indexOf(q) !== -1) {
        var snippet = JSON.stringify(specData[key], null, 2);
        if (snippet.length > 5000) snippet = snippet.substring(0, 5000) + '...[съкратено]';
        return 'Намерено в поле "' + key + '":\n' + snippet;
      }
    }
    return 'Няма резултати за: "' + param + '". Пробвай с различна ключова дума.';
  }

  var resultStr = 'Намерени ' + found.length + ' елемента за "' + param + '":\n';
  resultStr += JSON.stringify(found.slice(0, 40), null, 2);
  if (found.length > 40) resultStr += '\n... и още ' + (found.length - 40) + ' елемента';
  if (resultStr.length > 15000) resultStr = resultStr.substring(0, 15000) + '\n...[съкратено]';
  return resultStr;

} else if (action === 'group') {
  var field = param || 'category';
  var groups = {};
  for (var i = 0; i < allItems.length; i++) {
    var val = allItems[i][field] || 'неопределено';
    if (!groups[val]) groups[val] = { count: 0, examples: [] };
    groups[val].count++;
    if (groups[val].examples.length < 2) {
      groups[val].examples.push(allItems[i]);
    }
  }
  var r = JSON.stringify(groups, null, 2);
  if (r.length > 15000) {
    // Return just counts
    var summary = {};
    for (var g in groups) summary[g] = groups[g].count + ' елемента';
    return JSON.stringify(summary, null, 2);
  }
  return r;

} else if (action === 'count') {
  var fieldCounts = {};
  for (var key in specData) {
    var val = specData[key];
    if (Array.isArray(val)) fieldCounts[key] = val.length + ' елемента';
    else if (typeof val === 'object' && val !== null) fieldCounts[key] = Object.keys(val).length + ' полета';
    else fieldCounts[key] = '1 стойност';
  }
  return 'Общо елементи в масиви: ' + allItems.length + '\n' + JSON.stringify(fieldCounts, null, 2);

} else {
  return 'Непозната команда: "' + action + '". Налични: structure, summary, get, search, group, count.\nФормат: {"action": "search", "param": "ключова дума"} или просто текст.';
}"""

# =============================================================================
# APPLY CHANGES TO WORKFLOW
# =============================================================================

# Find and update nodes
for node in wf['nodes']:
    if node['name'] == 'Prepare Plan Prompt':
        node['parameters']['jsCode'] = PREP_CODE
        print(f"✅ Updated: {node['name']}")

    elif node['name'] == 'Plan Document':
        # Convert from chainLlm to Agent
        node['type'] = '@n8n/n8n-nodes-langchain.agent'
        node['typeVersion'] = 1.6
        node['parameters'] = {
            'text': '={{ $json.prompt }}',
            'promptType': 'define',
            'options': {
                'systemMessage': SYSTEM_MSG,
                'maxIterations': 15
            }
        }
        print(f"✅ Converted to Agent: {node['name']}")

    elif node['name'] == 'Parse Plan':
        # Update to also read from $json.output (Agent output format)
        old_first_line = "var raw = ($json.text || $json.response || '').trim();"
        new_first_line = "var raw = ($json.output || $json.text || $json.response || '').trim();"
        node['parameters']['jsCode'] = node['parameters']['jsCode'].replace(
            old_first_line, new_first_line, 1
        )
        print(f"✅ Updated Parse Plan to read $json.output")

# Add the Code Tool node
tool_node = {
    'id': 'tool_spec',
    'name': 'Analyze Spec Tool',
    'type': '@n8n/n8n-nodes-langchain.toolCode',
    'position': [600, 520],
    'parameters': {
        'name': TOOL_NAME,
        'description': TOOL_DESC,
        'language': 'javaScript',
        'jsCode': TOOL_CODE
    },
    'typeVersion': 2
}
wf['nodes'].append(tool_node)
print("✅ Added: Analyze Spec Tool (toolCode)")

# Update connections
wf['connections'] = {
    'Webhook': {
        'main': [[{
            'node': 'Prepare Plan Prompt',
            'type': 'main',
            'index': 0
        }]]
    },
    'Prepare Plan Prompt': {
        'main': [[{
            'node': 'Plan Document',
            'type': 'main',
            'index': 0
        }]]
    },
    'Claude Sonnet': {
        'ai_languageModel': [[{
            'node': 'Plan Document',
            'type': 'ai_languageModel',
            'index': 0
        }]]
    },
    'Analyze Spec Tool': {
        'ai_tool': [[{
            'node': 'Plan Document',
            'type': 'ai_tool',
            'index': 0
        }]]
    },
    'Plan Document': {
        'main': [[{
            'node': 'Parse Plan',
            'type': 'main',
            'index': 0
        }]]
    },
    'Parse Plan': {
        'main': [[{
            'node': 'Respond',
            'type': 'main',
            'index': 0
        }]]
    }
}
print("✅ Updated connections: Agent + tool wiring")

# Save
with open(WF_PATH, 'w', encoding='utf-8') as f:
    json.dump(wf, f, ensure_ascii=False, indent=2)
print(f"\n✅ Saved: {WF_PATH}")

# Validate
with open(WF_PATH, 'r', encoding='utf-8') as f:
    validated = json.load(f)

# Quick node summary
print(f"\nNodes ({len(validated['nodes'])}):")
for n in validated['nodes']:
    print(f"  - {n['name']} ({n['type']}) v{n.get('typeVersion', '?')}")

print(f"\nConnections ({len(validated['connections'])}):")
for src, conns in validated['connections'].items():
    for conn_type, targets in conns.items():
        for target_list in targets:
            for t in target_list:
                print(f"  {src} --[{conn_type}]--> {t['node']}")

print("\n✅ JSON validation passed!")
