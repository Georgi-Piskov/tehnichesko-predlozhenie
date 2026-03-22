"""
Modify WF06 (Validate Section) — add writingRules to validation criteria.

Changes:
1. Prepare Validation Prompt jsCode — include writingRules in validation checks
2. System message — add section about checking procurement-specific writing rules
"""
import json

FILE = r"e:\VISUAL STUDIO\TEHNICHESKO PREDLOJENIE\n8n\workflows\06-validate-section.json"

# ─── NEW Prepare Validation Prompt jsCode ───
NEW_PREPARE_JS = r"""var body = $json.body || $json;
var pt = body.procurementType || 'неопределен';
var secText = (body.sectionText || '').substring(0, 30000);
var secStr = JSON.stringify(body.section || {}, null, 2).substring(0, 5000);
var reqStr = JSON.stringify(body.requirements || {}, null, 2).substring(0, 15000);
var writingRules = body.writingRules || [];

var p = 'Ти си строг одитор на технически предложения за обществени поръчки.\n';
p += 'Проверяваш ЕДНА секция от документа.\n\n';
p += 'ТИП ПОРЪЧКА: ' + pt + '\n\n';
p += 'СЕКЦИЯ ЗА ПРОВЕРКА:\n' + secText + '\n\n';
p += 'ИЗИСКВАНЕ КОЕТО ТРЯБВА ДА ПОКРИЕ:\n' + secStr + '\n\n';
p += 'ОРИГИНАЛНИ ИЗИСКВАНИЯ ОТ ДОКУМЕНТАЦИЯТА:\n' + reqStr + '\n\n';

if (writingRules.length > 0) {
  p += '⚠️ ПРАВИЛА ЗА ПИСАНЕ ОТ ДОКУМЕНТАЦИЯТА НА ВЪЗЛОЖИТЕЛЯ:\n';
  for (var wr = 0; wr < writingRules.length; wr++) {
    var rule = writingRules[wr];
    p += (wr+1) + '. ' + (rule.rule || '') + '\n';
    if (rule.instruction_for_validator) p += '   → Проверка: ' + rule.instruction_for_validator + '\n';
    if (rule.violation_consequence) p += '   ⚠️ При нарушение: ' + rule.violation_consequence + '\n';
  }
  p += '\n';
}

p += 'ПРОВЕРКИ:\n';
p += '1. ПОКРИТИЕ: Покрива ли ВСИЧКИ подточки на изискването? Пропуснати ли са аспекти?\n';
p += '2. КОНКРЕТНОСТ: Конкретна ли е за тази поръчка или е generic/шаблонен текст?\n';
p += '3. ХАЛЮЦИНАЦИИ: Има ли измислени факти, несъществуващи стандарти, фалшиви данни?\n';
p += '4. РЕЛЕВАНТНОСТ: Съответства ли на типа поръчка? (не строителство за IT и обратно)\n';
p += '5. ТАБЛИЦИ: Има ли подходящи таблици? Добре форматирани ли са?\n';
p += '6. ОБЕМ: Адекватен ли е? (не прекалено кратък, не раздут с повторения)\n';
p += '7. ПРАВИЛА НА ВЪЗЛОЖИТЕЛЯ: Спазени ли са ВСИЧКИ writing_rules по-горе?\n';
p += '8. ФОРМАЛНОСТ: Текстът отчита ли спецификата на КОНКРЕТНАТА поръчка, или е формално разработен (generic)?\n\n';
p += 'ОЦЕНКА:\n';
p += '- 80+ точки = PASS (секцията е достатъчно добра)\n';
p += '- Под 80 = FAIL (нужна е корекция)\n';
p += '- FAIL САМО при: пропуснати изисквания, халюцинации, изцяло generic текст, нарушени writing_rules\n';
p += '- При FAIL: дай КОНКРЕТНИ инструкции какво точно да се поправи\n\n';
p += 'Върни САМО валиден JSON (без markdown блокове):\n';
p += '{\n  "passed": true,\n  "score": 85,\n  "issues": ["кратко описание на проблем"],\n';
p += '  "feedback": "конкретни инструкции за поправка (само ако passed=false)"\n}';

return [{ json: { prompt: p } }];"""

# ─── NEW system message ───
NEW_SYSTEM_MSG = (
    "# РОЛЯ И ЦЕЛ\n"
    "Ти си строг, но справедлив одитор по качеството на технически предложения за обществени поръчки.\n\n"

    "# ИНСТРУКЦИИ\n"
    "1. Оценяваш ЕДНА секция наведнъж.\n"
    "2. PASS (score >= 80): секцията е адекватна и покрива изискванията.\n"
    "3. FAIL (score < 80): САМО при сериозни проблеми — липсващи реквизити, измислени данни, изцяло generic текст, "
    "нарушени writing_rules от възложителя.\n\n"

    "# СТЪПКИ ЗА ОЦЕНКА\n"
    "1. Секцията покрива ли ВСИЧКИ реквизити от изискването на възложителя?\n"
    "2. Текстът конкретен ли е за ТАЗИ поръчка или е generic/формален?\n"
    "3. Има ли измислени данни (имена, числа, сертификати без placeholder)?\n"
    "4. Мерките (ако има) имат ли ВСИЧКИ 7 елемента (наименование, същност, дейности, план, експерт, контрол, ефект)?\n"
    "5. Има ли вътрешни противоречия?\n"
    "6. Спазен ли е обемът?\n"
    "7. Спазени ли са ВСИЧКИ writing_rules от документацията на възложителя?\n"
    "8. Текстът формален ли е? (generic текст, приложим за всяка поръчка = формален)\n\n"

    "# ПРАВИЛА ОТ ВЪЗЛОЖИТЕЛЯ\n"
    "Ако в промпта има секция ПРАВИЛА ЗА ПИСАНЕ ОТ ДОКУМЕНТАЦИЯТА НА ВЪЗЛОЖИТЕЛЯ — "
    "проверете ВСЯКО правило поотделно. Нарушение на writing_rule с последица \"отстраняване\" = автоматичен FAIL.\n\n"

    "# СПЕЦИАЛЕН ФОКУС: ФОРМАЛНОСТ\n"
    "Текст е \"формално разработен\" когато:\n"
    "- По външни признаци присъства минимално изискуемият елемент\n"
    "- Но при анализ на съдържанието НЕ отчита спецификата на конкретната поръчка\n"
    "- Или по своята същност НЕ може да се съотнесе към елемента за който е разработен\n"
    "- Или поради начин на изписване НЕ може да се установи съответствие\n"
    "Формален текст = FAIL.\n\n"

    "# ФОРМАТ\n"
    "Изход: САМО валиден JSON с полета: passed (boolean), score (0-100), issues (array), feedback (string).\n"
    "При FAIL — feedback ТРЯБВА да е КОНКРЕТЕН и actionable. "
    "Не просто \"подобрете секцията\", а \"липсва времеви план в мярката за взаимозаменяемост\".\n"
    "Език: български."
)


# ─── Apply changes ───
with open(FILE, 'r', encoding='utf-8') as f:
    data = json.load(f)

for node in data['nodes']:
    name = node.get('name', '')
    ntype = node.get('type', '')
    
    # 1. Update Prepare Validation Prompt jsCode
    if 'Prepare' in name and 'Valid' in name:
        if ntype == 'n8n-nodes-base.code':
            old_js = node['parameters']['jsCode']
            node['parameters']['jsCode'] = NEW_PREPARE_JS
            print(f"  Updated jsCode for '{name}': {len(old_js)} -> {len(NEW_PREPARE_JS)} chars")
    
    # 2. Update chainLlm system message
    if 'Validate' in name and 'chainLlm' in ntype:
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
print("JSON valid. WF06 updated.")
