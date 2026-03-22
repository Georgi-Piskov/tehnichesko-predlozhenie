"""
Modify WF05 (Write Section) — add writingRules to prompt + filter specData per section.

Changes:
1. Prepare Section Prompt jsCode — include writingRules, filter specData by spec_data_to_use
2. System message — add section about procurement-specific writing rules
"""
import json

FILE = r"e:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\05-write-section.json"

# ─── NEW Prepare Section Prompt jsCode ───
NEW_PREPARE_JS = r"""var b = $json.body || $json;
var s = b.section;
var reqs = b.requirements;
var spec = b.specData;
var ci = b.contractorInfo;
var prev = b.previousContext || '';
var fb = b.feedback || '';
var pt = b.procurementType || 'неопределен';
var idx = b.sectionIndex;
var total = b.totalSections;
var pages = s.estimated_pages || 5;
var writingRules = b.writingRules || [];
var headingLevel = (s.parentId || s.parentTitle) ? '###' : '##';

var guide = '';
if (s.content_guidance && s.content_guidance.length > 0) {
  guide = '\nУказания от плана:\n';
  for (var g = 0; g < s.content_guidance.length; g++) {
    guide += '- ' + s.content_guidance[g] + '\n';
  }
}
if (s.tables_needed && s.tables_needed.length > 0) {
  guide += '\nТаблици за включване:\n';
  for (var t = 0; t < s.tables_needed.length; t++) {
    var tbl = s.tables_needed[t];
    if (tbl.title) guide += '- ' + tbl.title + (tbl.columns ? ' (' + tbl.columns.join(', ') + ')' : '') + '\n';
  }
}
if (s.spec_data_to_use && s.spec_data_to_use.length > 0) {
  guide += '\nДанни от спецификацията за ползване: ' + s.spec_data_to_use.join(', ') + '\n';
}

var prompt = 'Напиши САМО секция "' + s.id + '. ' + s.title + '" от техническото предложение.\n';
prompt += 'Секция ' + (idx + 1) + ' от ' + total + '. Обем: ~' + pages + ' стр. (~' + (pages * 375) + ' думи).\n\n';
prompt += 'ТИП ПОРЪЧКА: ' + pt + '\n\n';

if (s.requirement_id) {
  var reqArr = reqs.requirements || reqs;
  if (Array.isArray(reqArr)) {
    for (var r = 0; r < reqArr.length; r++) {
      if (reqArr[r].id === s.requirement_id || reqArr[r].id === s.parentId) {
        prompt += 'ИЗИСКВАНЕ НА ВЪЗЛОЖИТЕЛЯ (ДОСЛОВНО):\n' + (reqArr[r].full_text || reqArr[r].title || '') + '\n\n';
        if (reqArr[r].sub_requirements && reqArr[r].sub_requirements.length > 0) {
          prompt += 'ПОД-ИЗИСКВАНИЯ:\n';
          for (var sr = 0; sr < reqArr[r].sub_requirements.length; sr++) {
            prompt += '- ' + reqArr[r].sub_requirements[sr].id + ': ' + reqArr[r].sub_requirements[sr].text + '\n';
          }
          prompt += '\n';
        }
        break;
      }
    }
  }
}

prompt += 'УКАЗАНИЯ ОТ ПЛАНА:\n' + (guide || s.title) + '\n\n';

var filteredSpec = {};
var specKeys = s.spec_data_to_use || [];
if (specKeys.length > 0 && spec) {
  for (var k = 0; k < specKeys.length; k++) {
    var key = specKeys[k];
    if (spec[key] !== undefined) filteredSpec[key] = spec[key];
  }
  if (Object.keys(filteredSpec).length === 0) filteredSpec = spec;
} else {
  filteredSpec = spec;
}
var specJson = JSON.stringify(filteredSpec, null, 2);
if (specJson.length > 15000) specJson = specJson.substring(0, 15000);
prompt += 'ТЕХНИЧЕСКИ ДАННИ ОТ СПЕЦИФИКАЦИЯТА:\n' + specJson + '\n\n';

prompt += 'ИНФОРМАЦИЯ ЗА ИЗПЪЛНИТЕЛЯ:\n' + JSON.stringify(ci, null, 2) + '\n\n';

if (prev) {
  prompt += 'ПРЕДИШЕН КОНТЕКСТ (НЕ повтаряй, осигури кохерентност):\n...' + prev.substring(prev.length > 2000 ? prev.length - 2000 : 0) + '\n\n';
}
if (fb) {
  prompt += '⚠️ ОБРАТНА ВРЪЗКА ОТ ВАЛИДАЦИЯ — ЗАДЪЛЖИТЕЛНО ПОПРАВИ:\n' + fb + '\n\n';
}

if (writingRules.length > 0) {
  prompt += '⚠️ ПРАВИЛА ЗА ПИСАНЕ ОТ ДОКУМЕНТАЦИЯТА НА ВЪЗЛОЖИТЕЛЯ:\n';
  for (var wr = 0; wr < writingRules.length; wr++) {
    var rule = writingRules[wr];
    prompt += (wr+1) + '. ' + (rule.rule || '') + '\n';
    if (rule.instruction_for_writer) prompt += '   → ' + rule.instruction_for_writer + '\n';
    if (rule.violation_consequence) prompt += '   ⚠️ При нарушение: ' + rule.violation_consequence + '\n';
  }
  prompt += '\n';
}

prompt += 'ПРАВИЛА ЗА ПИСАНЕ:\n';
prompt += '1. САМО тази секция — започни с ' + headingLevel + ' ' + s.id + '. ' + s.title + '\n';
prompt += '2. За всяка дейност: КАКВО → КАК → С КАКВО → КОЙ → КОНТРОЛ\n';
prompt += '3. Markdown таблици за: оборудване, персонал, графици, контролни планове\n';
prompt += '4. Графици: таблици (Дейност | Срок/Период | Ресурси | Отговорник)\n';
prompt += '5. Placeholders [⚠️ ПОПЪЛНЕТЕ: ...] за неизвестна информация\n';
prompt += '6. НЕ измисляй факти, НЕ пиши generic текст приложим за всяка поръчка\n';
prompt += '7. Текстът ТРЯБВА да отчита спецификата на КОНКРЕТНАТА поръчка — конкретни обекти, артикули, местоположения, количества от спецификацията\n';
prompt += '8. НЕ повтаряй текст от предишните секции — препращай: "Както е описано в т. X.X..."\n';
prompt += '9. НЕ пиши въведение/заключение на ЦЕЛИЯ документ\n';
prompt += '10. ФОРМАТ НА МЕРКИ: Ако секцията изисква мярка, всяка мярка е САМОСТОЯТЕЛНА и включва:\n';
prompt += '   а) Наименование и същност на мярката\n';
prompt += '   б) Конкретни дейности за изпълнение\n';
prompt += '   в) Времеви план за прилагане\n';
prompt += '   г) Конкретен експерт + конкретни задължения\n';
prompt += '   д) Контролни дейности и мониторинг (честота, действия при отклонения, лица за контрол)\n';
prompt += '   е) Очакван и целен ефект от мярката\n';
prompt += '   НЕ обединявай елементи от различни мерки!\n';
prompt += '11. Текстът НЕ ТРЯБВА да е формален — трябва да показва реално разбиране на конкретната поръчка\n';

return [{ json: { prompt: prompt } }];"""

# ─── NEW system message ───
NEW_SYSTEM_MSG = (
    "# РОЛЯ И ЦЕЛ\n"
    "Ти си експерт по изготвяне на технически предложения за обществени поръчки в Република България. "
    "Пишеш ЕДНА секция наведнъж — професионално, конкретно и технически издържано. "
    "Адаптираш стила и нормативните препратки спрямо типа на поръчката (строителство, доставки, услуги).\n\n"

    "# ИНСТРУКЦИИ И ОГРАНИЧЕНИЯ\n\n"

    "## Задължителни правила\n"
    "1. Пиши САМО поисканата секция — не целия документ.\n"
    "2. Всяко твърдение ТРЯБВА да е обвързано с КОНКРЕТНАТА поръчка — обекти, артикули, количества, местоположения от спецификацията.\n"
    "3. НИКОГА не измисляй имена, дати, числа, сертификати. Ако данни липсват → placeholder [⚠️ ПОПЪЛНЕТЕ: ...].\n"
    "4. Нормативни препратки: цитирай САМО реални и релевантни за типа поръчка нормативни актове. "
    "За доставки: ЗЗП, ЗТИП, БДС EN стандарти, CE маркировка. За строителство: ЗУТ, Наредба №3/2003, БДС EN. За всички: ЗОП, ППЗОП.\n"
    "5. НЕ повтаряй текст от предишни секции — препращай: \"Както е описано в т. X.X...\"\n"
    "6. Пиши на български език.\n\n"

    "## Структура на дейности: КАКВО → КАК → С КАКВО → КОЙ → КОНТРОЛ\n"
    "При описание на ВСЯКА дейност задължително покрий:\n"
    "- КАКВО се прави (конкретната дейност)\n"
    "- КАК се изпълнява (технология, метод, последователност)\n"
    "- С КАКВО (материали, оборудване, инструменти)\n"
    "- КОЙ го прави (експерт/длъжност + квалификация)\n"
    "- КАКЪВ КОНТРОЛ се осъществява (проверки, документиране)\n\n"

    "## Формат на МЕРКИ\n"
    "Когато секцията изисква мярка/мерки, ВСЯКА мярка е САМОСТОЯТЕЛНА и задължително включва:\n"
    "а) Наименование на мярката\n"
    "б) Същност — какво постига мярката\n"
    "в) Конкретни дейности за изпълнение\n"
    "г) Времеви план за прилагане на дейностите\n"
    "д) Конкретен експерт + конкретни задължения (ако повече от 1 — кой коя дейност)\n"
    "е) Контрол и мониторинг: честота на прегледи, действия при отклонения, отговорни лица\n"
    "ж) Очакван ефект от мярката\n"
    "ЗАБРАНЕНО: обединяване на елементи от различни мерки!\n\n"

    "## Правила от възложителя\n"
    "Ако в промпта има секция ПРАВИЛА ЗА ПИСАНЕ ОТ ДОКУМЕНТАЦИЯТА НА ВЪЗЛОЖИТЕЛЯ — тези правила са "
    "извлечени от КОНКРЕТНАТА документация на ТОЗИ възложител и са ЗАДЪЛЖИТЕЛНИ. Нарушаването им "
    "води до последицата посочена в правилото (отстраняване/намалени точки).\n\n"

    "## Забрани\n"
    "- Generic текст, приложим за всяка поръчка\n"
    "- \"Ще осигурим високо качество\" без конкретен механизъм\n"
    "- Измислени данни (имена, марки, номера на сертификати)\n"
    "- Въведение/заключение на целия документ\n"
    "- Отменени нормативни актове\n\n"

    "# СТЪПКИ НА РАЗСЪЖДЕНИЕ (ПРЕДИ ДА ПИШЕШ)\n"
    "Преди да генерираш текст, следвай тези стъпки мислено:\n"
    "1. Прочети изискването на възложителя — идентифицирай ВСЕКИ реквизит, който трябва да присъства.\n"
    "2. За всеки реквизит провери: има ли конкретни данни в спецификацията? Ако да — ЦИТИРАЙ ги с точни стойности.\n"
    "3. Ако данни липсват — постави placeholder, не измисляй.\n"
    "4. Провери: текстът ти отчита ли спецификата на ТАЗИ поръчка (конкретни обекти, локации, артикули) или е generic?\n"
    "5. Ако секцията изисква МЯРКА — структурирай я с 7-те елемента (а-ж).\n"
    "6. Провери спрямо writing_rules от възложителя — спазено ли е всяко правило?\n"
    "7. Провери за вътрешна непротиворечивост с предишните секции.\n"
    "8. Провери: спазен ли е указаният обем?\n\n"

    "# ФОРМАТ НА ИЗХОДА\n"
    "- Markdown с правилно ниво на заглавие (## или ### според инструкцията)\n"
    "- Таблици за: списъци на оборудване, персонал, графици, контролни планове, спецификации\n"
    "- Графици: таблица (Дейност | Срок/Период | Ресурси | Отговорник)\n"
    "- Placeholders: [⚠️ ПОПЪЛНЕТЕ: Точно описание какво да се попълни]\n\n"

    "# ПРИМЕРИ\n\n"

    "## ЛОШО (generic, формално):\n"
    "\"Фирмата ни разполага с квалифициран персонал и модерно оборудване. Ще осигурим навременна доставка. "
    "Качеството ще бъде на най-високо ниво. Нашият екип има богат опит.\"\n\n"

    "## ДОБРО (конкретно, обвързано с поръчката):\n"
    "\"За доставка на корпусни мебели за ДГ Чепеларе — База Здравец (5 занимални + 3 спални) и База Елхица "
    "(4 занимални + 2 спални), ще приложим следния подход:\n"
    "**Етап 1: Производство (Седмица 1-3)** — ПДЧ 18 мм, клас Е1 съгласно БДС EN 14322, ABS кантиране 2 мм\n"
    "Контрол: 100% проверка на размерите с калибрирани инструменти.\"\n\n"

    "# ФИНАЛНИ ИНСТРУКЦИИ\n"
    "- Текстът НЕ ТРЯБВА да е формален — трябва да показва реално разбиране на конкретната поръчка.\n"
    "- Спази ВСИЧКИ writing_rules от документацията на възложителя.\n"
    "- Всяка мярка е НАПЪЛНО самостоятелна с всички 7 елемента.\n"
    "- Ако нещо не знаеш — placeholder, НИКОГА не измисляй.\n"
    "- Пиши САМО поисканата секция."
)


# ─── Apply changes ───
with open(FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

nodes = data.get('nodes', [])

for node in nodes:
    name = node.get('name', '')
    ntype = node.get('type', '')
    
    # 1. Update Prepare Section Prompt jsCode
    if 'Prepare' in name and 'Section' in name and 'Prompt' in name:
        if ntype == 'n8n-nodes-base.code':
            old_js = node['parameters']['jsCode']
            node['parameters']['jsCode'] = NEW_PREPARE_JS
            print(f"  Updated jsCode for '{name}': {len(old_js)} -> {len(NEW_PREPARE_JS)} chars")
    
    # 2. Update chainLlm system message
    if 'Write' in name and 'Section' in name and 'chainLlm' in ntype:
        msgs = node.get('parameters', {}).get('messages', {})
        mv = msgs.get('messageValues', [])
        for v in mv:
            if v.get('type') == 'system':
                old_msg = v['message']
                v['message'] = NEW_SYSTEM_MSG
                print(f"  Updated system message for '{name}': {len(old_msg)} -> {len(NEW_SYSTEM_MSG)} chars")

with open(FILE, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

with open(FILE, 'r', encoding='utf-8') as f:
    json.load(f)
print("JSON valid. WF05 updated.")
