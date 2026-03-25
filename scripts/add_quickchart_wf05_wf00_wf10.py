"""
Priority 4: QuickChart.io visual improvements.

Three changes:
1. WF05 system message — add chart marker instruction (ПОДОБРЕНИЕ 8)
2. WF00 Assemble Document (n14) — process chart markers → QuickChart URLs
3. WF10 Format Section system message — handle <img> tags
"""

import json

# ========================================================================
# 1. WF05 — Add ПОДОБРЕНИЕ 8 to system message
# ========================================================================

WF05_PATH = 'n8n/workflows/05-write-section.json'

CHART_INSTRUCTION = """

# ПОДОБРЕНИЕ 8: ВИЗУАЛИЗАЦИЯ — ЛИНЕЙНИ ГРАФИЦИ

Когато секцията съдържа ЛИНЕЕН ГРАФИК или ВРЕМЕВИ ПЛАН:
1. ПЪРВО напиши Markdown ТАБЛИЦАТА (задължителна за текстовата версия)
2. СЛЕД таблицата, добави блок с данни за автоматична диаграма:

```chart:gantt
{"title":"Заглавие на графика","unit":"Седмици","tasks":[
  {"name":"Мобилизация","start":1,"duration":2},
  {"name":"Доставка на материали","start":2,"duration":3},
  {"name":"Монтаж","start":4,"duration":5}
]}
```

Правила за chart блока:
- start = начална единица (1-базирано число)
- duration = продължителност (число)
- unit = "Седмици" или "Дни" или "Месеци"
- name = КРАТКО име на дейността (до 40 символа)
- МАКСИМУМ 15 задачи в една диаграма (разбий на подграфици ако повече)
- САМО за линейни графици и времеви планове (НЕ за произволни таблици)
- Таблицата е ОСНОВНА, диаграмата е ДОПЪЛНИТЕЛНА визуализация
- Данните в chart блока ТРЯБВА да съвпадат с таблицата"""

with open(WF05_PATH, 'r', encoding='utf-8') as f:
    wf05 = json.load(f)

for node in wf05['nodes']:
    if node['name'] == 'Write Section':
        msg = node['parameters']['messages']['messageValues'][0]['message']
        # Insert before "# СТЪПКИ НА РАЗСЪЖДЕНИЕ"
        insert_point = msg.find('# СТЪПКИ НА РАЗСЪЖДЕНИЕ')
        if insert_point == -1:
            # Fallback: insert before final instructions
            insert_point = msg.find('# ФИНАЛНИ ИНСТРУКЦИИ')
        if insert_point == -1:
            msg += CHART_INSTRUCTION
        else:
            msg = msg[:insert_point] + CHART_INSTRUCTION + '\n\n' + msg[insert_point:]
        
        node['parameters']['messages']['messageValues'][0]['message'] = msg
        print(f"✅ WF05: Added chart instruction to system message ({len(msg)} chars)")
        break

with open(WF05_PATH, 'w', encoding='utf-8') as f:
    json.dump(wf05, f, ensure_ascii=False, indent=2)

# Validate
with open(WF05_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)
    for node in data['nodes']:
        if node['name'] == 'Write Section':
            assert 'chart:gantt' in node['parameters']['messages']['messageValues'][0]['message']
            print("   ✅ Verified: chart:gantt in system message")
            break

# ========================================================================
# 2. WF00 — Update Assemble Document (n14) to process chart markers
# ========================================================================

WF00_PATH = 'n8n/workflows/00-orchestrator.json'

NEW_ASSEMBLE = r"""var sd = $getWorkflowStaticData('global');
var fullDoc = sd.fullDoc || '';
var results = sd.results || [];

// === Process chart:gantt markers → QuickChart.io URLs ===
var chartRegex = /```chart:gantt\s*\n([\s\S]*?)\n```/g;
var match;
var processedDoc = fullDoc;
var chartCount = 0;

while ((match = chartRegex.exec(fullDoc)) !== null) {
  try {
    var chartJson = JSON.parse(match[1].trim());
    var tasks = chartJson.tasks || [];
    var title = chartJson.title || 'Линеен график';
    var unit = chartJson.unit || 'Седмици';
    
    if (tasks.length === 0) continue;
    
    // Build horizontal bar chart config for Gantt
    var labels = [];
    var startData = [];
    var durationData = [];
    
    for (var i = 0; i < tasks.length; i++) {
      labels.push(tasks[i].name || ('Задача ' + (i+1)));
      startData.push((tasks[i].start || 1) - 1); // 0-based offset
      durationData.push(tasks[i].duration || 1);
    }
    
    // Reverse for top-to-bottom display
    labels.reverse();
    startData.reverse();
    durationData.reverse();
    
    var chartConfig = {
      type: 'horizontalBar',
      data: {
        labels: labels,
        datasets: [
          {
            label: 'Начало',
            data: startData,
            backgroundColor: 'rgba(0,0,0,0)',
            borderWidth: 0
          },
          {
            label: unit,
            data: durationData,
            backgroundColor: 'rgba(54,162,235,0.7)',
            borderColor: 'rgba(54,162,235,1)',
            borderWidth: 1
          }
        ]
      },
      options: {
        indexAxis: 'y',
        scales: {
          xAxes: [{
            stacked: true,
            ticks: { beginAtZero: true },
            scaleLabel: { display: true, labelString: unit }
          }],
          yAxes: [{
            stacked: true,
            ticks: { fontSize: 11 }
          }]
        },
        title: { display: true, text: title, fontSize: 14 },
        legend: { display: false },
        plugins: {
          datalabels: {
            display: function(ctx) { return ctx.datasetIndex === 1; },
            color: '#fff',
            font: { weight: 'bold', size: 10 }
          }
        }
      }
    };
    
    var configStr = JSON.stringify(chartConfig);
    var encoded = encodeURIComponent(configStr);
    var chartUrl = 'https://quickchart.io/chart?w=800&h=' + Math.max(300, tasks.length * 35 + 80) + '&bkg=white&c=' + encoded;
    
    // Replace chart marker with image
    var imgMarkdown = '\n\n![' + title + '](' + chartUrl + ')\n\n';
    processedDoc = processedDoc.replace(match[0], imgMarkdown);
    chartCount++;
  } catch(e) {
    // If JSON parse fails, leave original marker
  }
}

var totalWC = processedDoc.trim().split(/\s+/).length;

// Clean static data
sd.fullDoc = '';
sd.lastParent = '';
sd.results = [];

return [{ json: {
  fullDocument: processedDoc,
  sectionResults: results,
  totalWordCount: totalWC,
  estimatedPages: Math.round(totalWC / 375),
  chartsGenerated: chartCount
} }];"""

with open(WF00_PATH, 'r', encoding='utf-8') as f:
    wf00 = json.load(f)

for node in wf00['nodes']:
    if node['name'] == 'Assemble Document':
        old_code = node['parameters']['jsCode']
        node['parameters']['jsCode'] = NEW_ASSEMBLE
        print(f"✅ WF00: Updated 'Assemble Document' ({len(old_code)} → {len(NEW_ASSEMBLE)} chars)")
        break

with open(WF00_PATH, 'w', encoding='utf-8') as f:
    json.dump(wf00, f, ensure_ascii=False, indent=2)

# Validate
with open(WF00_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)
    for node in data['nodes']:
        if node['name'] == 'Assemble Document':
            code = node['parameters']['jsCode']
            assert 'quickchart.io' in code, "quickchart.io not found!"
            assert 'chartsGenerated' in code, "chartsGenerated not found!"
            print("   ✅ Verified: QuickChart processing in Assemble Document")
            break

# ========================================================================
# 3. WF10 — Update Format Section system message to handle images
# ========================================================================

WF10_PATH = 'n8n/workflows/10-format-document.json'

with open(WF10_PATH, 'r', encoding='utf-8') as f:
    wf10 = json.load(f)

for node in wf10['nodes']:
    if node['name'] == 'Format Section':
        msg = node['parameters']['messages']['messageValues'][0]['message']
        # Add image handling rule before the last rule
        img_rule = '\n15. Images: ![alt](url) → <img src="url" alt="alt" style="max-width:100%; height:auto; margin:16px 0; display:block">'
        img_rule += '\n16. Do NOT modify image URLs — pass them through EXACTLY as-is'
        
        # Insert after rule 14 (Preserve the original language)
        insert_after = 'Preserve the original language (Bulgarian)'
        if insert_after in msg:
            msg = msg.replace(insert_after, insert_after + img_rule)
            node['parameters']['messages']['messageValues'][0]['message'] = msg
            print(f"✅ WF10: Added image handling rules to system message ({len(msg)} chars)")
        else:
            print("⚠️ WF10: Could not find insertion point, appending")
            msg += img_rule
            node['parameters']['messages']['messageValues'][0]['message'] = msg
            print(f"   Added at end ({len(msg)} chars)")
        break

with open(WF10_PATH, 'w', encoding='utf-8') as f:
    json.dump(wf10, f, ensure_ascii=False, indent=2)

# Validate  
with open(WF10_PATH, 'r', encoding='utf-8') as f:
    data = json.load(f)
    for node in data['nodes']:
        if node['name'] == 'Format Section':
            assert '<img src=' in node['parameters']['messages']['messageValues'][0]['message']
            print("   ✅ Verified: img rule in WF10 system message")
            break

print("\n✅ All 3 workflows updated successfully!")
print("   WF05: Chart marker instruction in system message")
print("   WF00: QuickChart.io URL generation in Assemble Document")
print("   WF10: Image handling in Format Section")
