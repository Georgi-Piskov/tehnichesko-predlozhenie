"""
Two fixes:
1. NO FAKE NAMES — strengthen instructions in WF05, WF06, WF04
2. DYNAMIC PAGE COUNT — pass targetPages through WF00 → WF04
"""
import json

print("=== FIX: No Fake Names + Dynamic Page Count ===\n")

# =====================================================================
# WF00: Init Job reads targetPages; pass it through the pipeline
# =====================================================================
with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    wf00 = json.load(f)

for node in wf00['nodes']:
    if node['name'] == 'Init Job':
        old = node['parameters']['jsCode']
        # Add targetPages extraction
        new = old.replace(
            "additionalNotes: body.additionalNotes || '',",
            "additionalNotes: body.additionalNotes || '',\n    targetPages: parseInt(body.targetPages) || 50,"
        )
        node['parameters']['jsCode'] = new
        print("  WF00 Init Job: added targetPages extraction")

    # Flatten Chunks needs to pass targetPages to each chunk
    if node['name'] == 'Flatten Chunks':
        old = node['parameters']['jsCode']
        # Add targetPages to the context, read from Init Job
        new = old.replace(
            "var ci = $('Init Job').first().json.contractorInfo || {};",
            "var ci = $('Init Job').first().json.contractorInfo || {};\nvar targetPages = $('Init Job').first().json.targetPages || 50;"
        )
        # Pass targetPages in each chunk item
        new = new.replace(
            "writingRules: writingRules",
            "writingRules: writingRules,\n      targetPages: targetPages"
        )
        node['parameters']['jsCode'] = new
        print("  WF00 Flatten Chunks: passes targetPages to chunks")

    # After Spec Analysis: pass targetPages
    if node['name'] == 'After Spec Analysis':
        old = node['parameters']['jsCode']
        # Add targetPages to the output
        new = old.replace(
            "specData: specData",
            "specData: specData,\n    targetPages: $('Init Job').first().json.targetPages || 50"
        )
        node['parameters']['jsCode'] = new
        print("  WF00 After Spec Analysis: passes targetPages")

with open('n8n/workflows/00-orchestrator.json', 'w', encoding='utf-8') as f:
    json.dump(wf00, f, ensure_ascii=False, indent=2)

with open('n8n/workflows/00-orchestrator.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
    print(f"  00-orchestrator.json: valid, {len(d['nodes'])} nodes\n")


# =====================================================================
# WF04: Prepare Plan Prompt uses targetPages instead of hardcoded 40
# =====================================================================
with open('n8n/workflows/04-plan-document.json', 'r', encoding='utf-8') as f:
    wf04 = json.load(f)

for node in wf04['nodes']:
    if node['name'] == 'Prepare Plan Prompt':
        old = node['parameters']['jsCode']
        # Add targetPages reading
        new = old.replace(
            "var docText = (body.documentationText || '').substring(0, 40000);",
            "var docText = (body.documentationText || '').substring(0, 40000);\nvar targetPages = parseInt(body.targetPages) || 50;"
        )
        # Replace hardcoded total_estimated_pages: 40
        new = new.replace(
            """'  "total_estimated_pages": 40,\\n'""",
            """'  "total_estimated_pages": ' + targetPages + ',\\n'"""
        )
        # Add instruction about page distribution
        new = new.replace(
            "p += '## КРИТИЧНИ ПРАВИЛА\\n';",
            "p += '## ЦЕЛЕВИ ОБЕМ: ' + targetPages + ' СТРАНИЦИ\\n';\n"
            "p += 'Целевият обем на документа е ' + targetPages + ' страници.\\n';\n"
            "p += 'Разпредели estimated_pages между подсекциите така че сумата да се доближава до ' + targetPages + '.\\n';\n"
            "p += 'За по-голям обем: повече подсекции + повече страници на подсекция (до 8 стр. макс).\\n';\n"
            "p += 'За по-малък обем: по-малко подсекции + по-кратки (2-3 стр.).\\n\\n';\n\n"
            "p += '## КРИТИЧНИ ПРАВИЛА\\n';"
        )
        # Add NO FAKE NAMES rule
        new = new.replace(
            "p += '7. САМО JSON, без друг текст.';",
            "p += '7. САМО JSON, без друг текст.\\n';\n"
            "p += '8. В content_guidance: ЗАБРАНЕНО е да се задават конкретни имена на хора. Вместо това пишете: [⚠️ ПОПЪЛНЕТЕ: име на ръководител обект], [⚠️ ПОПЪЛНЕТЕ: име на експерт по качество] и т.н.';"
        )
        node['parameters']['jsCode'] = new
        print("  WF04 Prepare Plan Prompt: uses targetPages, no-fake-names rule")

with open('n8n/workflows/04-plan-document.json', 'w', encoding='utf-8') as f:
    json.dump(wf04, f, ensure_ascii=False, indent=2)

with open('n8n/workflows/04-plan-document.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
    print(f"  04-plan-document.json: valid, {len(d['nodes'])} nodes\n")


# =====================================================================
# WF05: Strengthen NO FAKE NAMES in system message + prompt
# =====================================================================
with open('n8n/workflows/05-write-section.json', 'r', encoding='utf-8') as f:
    wf05 = json.load(f)

for node in wf05['nodes']:
    if node['name'] == 'Write Section':
        msg = node['parameters']['messages']['messageValues'][0]['message']
        # Add a very prominent section about no fake names right after the role
        msg = msg.replace(
            "# ИНСТРУКЦИИ И ОГРАНИЧЕНИЯ\n\n## Задължителни правила",
            "# ⛔ АБСОЛЮТНА ЗАБРАНА: ИЗМИСЛЕНИ ИМЕНА\n"
            "НИКОГА НЕ ИЗМИСЛЯЙ ИМЕНА НА ХОРА. Това включва:\n"
            "- Имена на експерти, инженери, ръководители, работници\n"
            "- Имена на членове на екипа, отговорни лица, контролни органи\n"
            "- Имена на подизпълнители или партньори\n"
            "Вместо конкретно име ВИНАГИ използвай placeholder:\n"
            "- [⚠️ ПОПЪЛНЕТЕ: име на ръководител обект]\n"
            "- [⚠️ ПОПЪЛНЕТЕ: име на експерт по контрол на качеството]\n"
            "- [⚠️ ПОПЪЛНЕТЕ: име на координатор по безопасност]\n"
            "НЕ измисляй имена като \"Мария Петрова\", \"Георги Иванов\" и т.н. — ВИНАГИ placeholder.\n"
            "Нарушаването на тази забрана е КРИТИЧНА грешка.\n\n"
            "# ИНСТРУКЦИИ И ОГРАНИЧЕНИЯ\n\n## Задължителни правила"
        )
        node['parameters']['messages']['messageValues'][0]['message'] = msg
        print("  WF05 Write Section: added prominent NO FAKE NAMES section")

    if node['name'] == 'Prepare Section Prompt':
        old = node['parameters']['jsCode']
        # Add no-fake-names reminder in the rules section
        new = old.replace(
            "prompt += '6. НЕ измисляй факти, НЕ пиши generic текст приложим за всяка поръчка\\n';",
            "prompt += '6. НЕ измисляй факти, НЕ пиши generic текст приложим за всяка поръчка\\n';\n"
            "prompt += '   ⛔ АБСОЛЮТНА ЗАБРАНА: НЕ ИЗМИСЛЯЙ ИМЕНА НА ХОРА! За всеки експерт/лице → [⚠️ ПОПЪЛНЕТЕ: роля]\\n';"
        )
        node['parameters']['jsCode'] = new
        print("  WF05 Prepare Section Prompt: added no-fake-names reminder")

with open('n8n/workflows/05-write-section.json', 'w', encoding='utf-8') as f:
    json.dump(wf05, f, ensure_ascii=False, indent=2)

with open('n8n/workflows/05-write-section.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
    print(f"  05-write-section.json: valid, {len(d['nodes'])} nodes\n")


# =====================================================================
# WF06: Add fake name detection in validator
# =====================================================================
with open('n8n/workflows/06-validate-section.json', 'r', encoding='utf-8') as f:
    wf06 = json.load(f)

for node in wf06['nodes']:
    if node['name'] == 'Validate Section':
        msg = node['parameters']['messages']['messageValues'][0]['message']
        msg = msg.replace(
            "# СТЪПКИ ЗА ОЦЕНКА",
            "# СПЕЦИАЛНА ПРОВЕРКА: ИЗМИСЛЕНИ ИМЕНА\n"
            "Проверете дали текстът съдържа конкретни имена на хора (напр. \"Мария Петрова\", \"Петър Стоянов\").\n"
            "Имената на хора (освен управителя от contractorInfo) са ИЗМИСЛЕНИ от AI и са ЗАБРАНЕНИ.\n"
            "Правилно: [⚠️ ПОПЪЛНЕТЕ: име на ръководител обект] — placeholder вместо име.\n"
            "Наличието на измислени имена = автоматичен FAIL с feedback за замяна с placeholders.\n\n"
            "# СТЪПКИ ЗА ОЦЕНКА"
        )
        node['parameters']['messages']['messageValues'][0]['message'] = msg
        print("  WF06 Validate Section: added fake name detection")

    if node['name'] == 'Prepare Validation Prompt':
        old = node['parameters']['jsCode']
        new = old.replace(
            "p += '3. ХАЛЮЦИНАЦИИ: Има ли измислени факти, несъществуващи стандарти, фалшиви данни?\\n';",
            "p += '3. ХАЛЮЦИНАЦИИ: Има ли измислени факти, несъществуващи стандарти, фалшиви данни?\\n';\n"
            "p += '   ⛔ ИЗМИСЛЕНИ ИМЕНА: Има ли конкретни имена на хора (Мария Петрова, Георги Иванов и т.н.)? Ако да → FAIL. Трябва да са placeholders [⚠️ ПОПЪЛНЕТЕ: роля].\\n';"
        )
        node['parameters']['jsCode'] = new
        print("  WF06 Prepare Validation Prompt: added fake name check")

with open('n8n/workflows/06-validate-section.json', 'w', encoding='utf-8') as f:
    json.dump(wf06, f, ensure_ascii=False, indent=2)

with open('n8n/workflows/06-validate-section.json', 'r', encoding='utf-8') as f:
    d = json.load(f)
    print(f"  06-validate-section.json: valid, {len(d['nodes'])} nodes\n")


print("=== ALL DONE ===")
print("\nChanges summary:")
print("  NO FAKE NAMES:")
print("    - WF04: content_guidance instruction to use placeholders")
print("    - WF05: prominent ⛔ section in system msg + reminder in prompt")
print("    - WF06: fake name detection → auto-FAIL + specific check in prompt")
print("  DYNAMIC PAGE COUNT:")
print("    - Frontend: targetPages input (20-500, default 50)")
print("    - WF00 Init Job: reads targetPages from form data")
print("    - WF00 After Spec Analysis: passes targetPages")
print("    - WF00 Flatten Chunks: passes targetPages to each chunk")
print("    - WF04 Prepare Plan Prompt: uses targetPages, distribution instructions")
