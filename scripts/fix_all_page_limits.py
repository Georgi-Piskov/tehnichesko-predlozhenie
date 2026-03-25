"""
Fix ALL hardcoded page limits across the pipeline.

Problems found:
1. WF04 Prepare Plan Prompt: parseInt(body.targetPages) || 50
2. WF04 system message + Prepare Plan Prompt: "Максимум 5 стр. на подсекция" → adaptive
3. WF00 Flatten Chunks: estimated_pages fallback || 4 / || 5 → adaptive based on targetPages
4. document-planner.md: "20-60 стр." range → remove, use dynamic
5. document-planner.md: "5 страници (~1875 думи)" → adaptive
"""

import json

# ========================================================================
# 1. WF04 — Fix default targetPages and max pages per subsection
# ========================================================================

WF04_PATH = 'n8n/workflows/04-plan-document.json'

with open(WF04_PATH, 'r', encoding='utf-8') as f:
    wf04 = json.load(f)

for node in wf04['nodes']:
    if node['name'] == 'Prepare Plan Prompt':
        code = node['parameters']['jsCode']
        
        # Fix 1: Default targetPages 50 → 250
        code = code.replace(
            "var targetPages = parseInt(body.targetPages) || 50;",
            "var targetPages = parseInt(body.targetPages) || 250;"
        )
        
        # Fix 2: "Максимум 5 стр." → adaptive based on targetPages
        code = code.replace(
            "p += '- Максимум 5 страници на най-долна подсекция\\n';",
            "var maxSubPages = targetPages > 100 ? 10 : (targetPages > 50 ? 8 : 5);\n"
            "p += '- Максимум ' + maxSubPages + ' страници на най-долна подсекция\\n';"
        )
        
        # Fix 3: Also fix in Structural rules section  
        code = code.replace(
            "p += '- Максимум 5 страници на най-долна подсекция\\n';",
            "p += '- Максимум ' + maxSubPages + ' страници на най-долна подсекция\\n';"
        )
        
        # Fix 4: Update the target volume section to be more assertive
        old_volume = (
            "p += '## ЦЕЛЕВИ ОБЕМ: ' + targetPages + ' СТРАНИЦИ\\n';\n"
            "p += 'Целевият обем на документа е ' + targetPages + ' страници.\\n';\n"
            "p += 'Разпредели estimated_pages между подсекциите така че сумата да се доближава до ' + targetPages + '.\\n';\n"
            "p += 'За по-голям обем: повече подсекции + повече страници на подсекция (до 8 стр. макс).\\n';\n"
            "p += 'За по-малък обем: по-малко подсекции + по-кратки (2-3 стр.).\\n\\n';"
        )
        new_volume = (
            "p += '## ⚠️ ЦЕЛЕВИ ОБЕМ: ' + targetPages + ' СТРАНИЦИ (ЗАДЪЛЖИТЕЛНО!)\\n';\n"
            "p += 'Целевият обем на документа е ТОЧНО ' + targetPages + ' страници.\\n';\n"
            "p += 'СУМАТА на estimated_pages на ВСИЧКИ подсекции ТРЯБВА да е = ' + targetPages + ' (±10%).\\n';\n"
            "p += 'Разпредели estimated_pages пропорционално: по-обемни теми → повече стр., по-прости → по-малко.\\n';\n"
            "p += 'Макс ' + maxSubPages + ' стр. на подсекция. Ако тема иска повече → раздели на 2+ подсекции.\\n';\n"
            "p += 'ПРЕДИ ДА ФИНАЛИЗИРАШ: събери estimated_pages на всички подсекции. Ако сумата е < ' + Math.round(targetPages * 0.9) + ' → добави подсекции или увеличи pages.\\n\\n';"
        )
        code = code.replace(old_volume, new_volume)
        
        # Fix 5: Update example estimated_pages from 4 to adaptive
        code = code.replace(
            '"estimated_pages": 4,',
            '"estimated_pages": ' + "' + Math.min(maxSubPages, Math.round(targetPages / 30)) + ',"
        )
        # Actually this is tricky since it's inside a string. Let me use a simpler approach
        # Revert and just fix the string literal
        code = code.replace(
            "' + Math.min(maxSubPages, Math.round(targetPages / 30)) + ',",
            "4,"
        )
        
        node['parameters']['jsCode'] = code
        print(f"✅ WF04 Prepare Plan Prompt: fixed targetPages default + adaptive max pages")

    if node['name'] == 'Plan Document':
        msg = node['parameters'].get('systemMessage', '')
        if not msg:
            # It's in messages.messageValues or systemMessage  
            # For agent nodes it might be in 'text' or 'systemMessage'
            for key in ['systemMessage']:
                if key in node['parameters']:
                    msg = node['parameters'][key]
                    break
        
        if msg and 'Максимум 5 стр.' in msg:
            msg = msg.replace(
                'Максимум 5 стр. на най-долна подсекция',
                'Максимум N стр. на най-долна подсекция (N се определя от целевия обем — виж промпта)'
            )
            node['parameters']['systemMessage'] = msg
            print(f"✅ WF04 Plan Document system message: fixed max pages reference")
        elif msg:
            print(f"   WF04 Plan Document system message: no '5 стр.' found (might be OK)")
        else:
            print(f"   WF04 Plan Document: no systemMessage field found, checking other fields...")
            # Check if it's a different field name for agent
            if 'options' in node['parameters'] and 'systemMessage' in node['parameters']['options']:
                msg = node['parameters']['options']['systemMessage']
                if 'Максимум 5 стр.' in msg:
                    msg = msg.replace(
                        'Максимум 5 стр. на най-долна подсекция',
                        'Максимум N стр. на най-долна подсекция (N зависи от целевия обем)'
                    )
                    node['parameters']['options']['systemMessage'] = msg
                    print(f"✅ WF04 Agent options.systemMessage: fixed max pages")

with open(WF04_PATH, 'w', encoding='utf-8') as f:
    json.dump(wf04, f, ensure_ascii=False, indent=2)

with open(WF04_PATH, 'r', encoding='utf-8') as f:
    json.load(f)
print("   ✅ WF04 JSON valid")

# ========================================================================
# 2. WF00 — Fix Flatten Chunks defaults to be adaptive
# ========================================================================

WF00_PATH = 'n8n/workflows/00-orchestrator.json'

with open(WF00_PATH, 'r', encoding='utf-8') as f:
    wf00 = json.load(f)

for node in wf00['nodes']:
    if node['name'] == 'Flatten Chunks':
        code = node['parameters']['jsCode']
        
        # Add adaptive default based on targetPages
        adaptive_default = (
            "var targetPages = $('Init Job').first().json.targetPages || 250;\n"
            "var defaultSubPages = targetPages > 100 ? 8 : (targetPages > 50 ? 6 : 4);\n"
            "var defaultSecPages = targetPages > 100 ? 10 : (targetPages > 50 ? 8 : 5);\n"
        )
        
        # Insert after the existing targetPages line
        if "var targetPages = $('Init Job').first().json.targetPages || 50;" in code:
            code = code.replace(
                "var targetPages = $('Init Job').first().json.targetPages || 50;",
                "var targetPages = $('Init Job').first().json.targetPages || 250;\n"
                "var defaultSubPages = targetPages > 100 ? 8 : (targetPages > 50 ? 6 : 4);\n"
                "var defaultSecPages = targetPages > 100 ? 10 : (targetPages > 50 ? 8 : 5);"
            )
        else:
            # The targetPages variable might be defined differently
            # Insert before "var sections ="
            code = code.replace(
                "var sections = (plan && plan.sections) || [];",
                adaptive_default + "var sections = (plan && plan.sections) || [];"
            )
        
        # Fix subsection fallback: 4 → defaultSubPages
        code = code.replace(
            "estimated_pages: sub.estimated_pages || 4,",
            "estimated_pages: sub.estimated_pages || defaultSubPages,"
        )
        
        # Fix section fallback: 5 → defaultSecPages
        code = code.replace(
            "estimated_pages: sec.estimated_pages || 5,",
            "estimated_pages: sec.estimated_pages || defaultSecPages,"
        )
        
        node['parameters']['jsCode'] = code
        print(f"✅ WF00 Flatten Chunks: adaptive defaults based on targetPages")

with open(WF00_PATH, 'w', encoding='utf-8') as f:
    json.dump(wf00, f, ensure_ascii=False, indent=2)

with open(WF00_PATH, 'r', encoding='utf-8') as f:
    json.load(f)
print("   ✅ WF00 JSON valid")

# ========================================================================
# 3. document-planner.md — Fix hardcoded limits
# ========================================================================

PLANNER_MD = 'n8n/prompts/document-planner.md'

with open(PLANNER_MD, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix "20-60 стр" range
content = content.replace(
    '- Реалистичен общ обем: 20-60 стр.',
    '- Обемът зависи от targetPages параметъра (задава се от клиента). Планерът ТРЯБВА да разпредели estimated_pages така че сумата ≈ targetPages.'
)

# Fix "5 страници" max
content = content.replace(
    '1. Всяка подсекция МАКСИМУМ **5 страници** (~1875 думи)',
    '1. Всяка подсекция МАКСИМУМ **N страници** (N зависи от targetPages: до 100стр→5стр, до 200стр→8стр, над 200стр→10стр). Ако тема е по-обемна → раздели на 2+ подсекции.'
)

with open(PLANNER_MD, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"✅ document-planner.md: fixed hardcoded page limits")

# ========================================================================
# 4. section-writer.md — Update page guidance
# ========================================================================

WRITER_MD = 'n8n/prompts/section-writer.md'

with open(WRITER_MD, 'r', encoding='utf-8') as f:
    content = f.read()

# This one is OK — it says "спазвай указана обем в страници" which is dynamic
# But let's reinforce it
content = content.replace(
    '5. **Обем** — спазвай указания обем в страници. 1 страница ≈ 350-400 думи.',
    '5. **Обем** — спазвай ТОЧНО указания обем в страници. 1 страница ≈ 375 думи. Ако е указано 8 стр. → пиши ~3000 думи. НЕ съкращавай!'
)

with open(WRITER_MD, 'w', encoding='utf-8') as f:
    f.write(content)
print(f"✅ section-writer.md: reinforced page volume instruction")

# ========================================================================
# Summary  
# ========================================================================

print("\n" + "="*60)
print("ВСИЧКИ ПОПРАВКИ:")
print("="*60)
print("1. WF04 Prepare Plan Prompt: default 50→250, max pages adaptive")
print("2. WF04 Prepare Plan Prompt: target volume section more assertive")
print("3. WF04 System message: '5 стр' → adaptive reference")
print("4. WF00 Flatten Chunks: default 50→250, sub/sec pages adaptive")
print("5. document-planner.md: '20-60 стр' → dynamic targetPages")
print("6. document-planner.md: '5 страници max' → adaptive N")
print("7. section-writer.md: reinforced exact volume instruction")
