"""
THOROUGH audit of ALL workflow JSONs + all prompts for anything that could
limit page output.  Checks:

1. jsCode in every node of every workflow JSON  — || <number>, hardcoded page nums, 
   "стр", "pages", maxTokens, maxPages, etc.
2. System messages (options.systemMessage) in agent/chainLlm nodes
3. Markdown prompt files
4. n8n expression strings (={{ ... }}) that reference page counts
5. maxTokens settings that could truncate output
"""
import json, re, glob, os

RED   = lambda s: f'  ❌ {s}'
WARN  = lambda s: f'  ⚠️  {s}'
OK    = lambda s: f'  ✅ {s}'

problems = []

# ─────────────── 1. All workflow JSON files ───────────────
wf_files = sorted(glob.glob('n8n/workflows/*.json'))
print(f'Scanning {len(wf_files)} workflow JSON files...\n')

for wf_file in wf_files:
    with open(wf_file, 'r', encoding='utf-8') as f:
        wf = json.load(f)
    
    basename = os.path.basename(wf_file)
    header_printed = [False]
    
    def pheader():
        if not header_printed[0]:
            print(f'=== {basename} ===')
            header_printed[0] = True
    
    for node in wf['nodes']:
        name = node['name']
        params = node.get('parameters', {})
        
        # ── Check jsCode ──
        code = params.get('jsCode', '')
        if code:
            # a) || <small number> defaults that look like page counts
            for m in re.finditer(r'(\w+)\s*\|\|\s*(\d+)', code):
                varname = m.group(1)
                val = int(m.group(2))
                ctx = code[max(0,m.start()-20):m.end()+20].replace('\n',' ')
                # Flag if variable name suggests pages AND value is suspicious
                page_vars = ['pages', 'targetpages', 'maxpages', 'subpages', 
                             'secpages', 'estimated', 'defaultsub', 'defaultsec']
                is_page_var = any(pv in varname.lower() for pv in page_vars)
                if is_page_var and val < 200:
                    pheader()
                    msg = f'{name}: {varname} || {val}  ...{ctx}...'
                    print(RED(msg))
                    problems.append(msg)
            
            # b) Hardcoded "50 стр" / "50 pages" / "50 страници" patterns in strings
            for m in re.finditer(r'[\'\"].*?(\d{2,3})\s*(стр|page|страниц).*?[\'\"]', code, re.I):
                val = int(m.group(1))
                if val < 200 and val not in (375,):  # 375 = words per page constant
                    pheader()
                    ctx = m.group(0)[:80]
                    msg = f'{name}: hardcoded "{val} {m.group(2)}" in string: {ctx}'
                    print(WARN(msg))
            
            # c) "20-60" or similar page ranges
            for m in re.finditer(r'(\d{1,3})\s*[-–—]\s*(\d{1,3})\s*(стр|page|страниц)', code, re.I):
                pheader()
                msg = f'{name}: range "{m.group(0)}" found'
                print(RED(msg))
                problems.append(msg)
        
        # ── Check system messages (Agent / chainLlm) ──
        sm = params.get('options', {}).get('systemMessage', '')
        if not sm:
            # Also check text field and prompt field
            sm = params.get('text', '') or params.get('prompt', '')
        if sm:
            # Same checks as above
            for m in re.finditer(r'(\d{1,3})\s*(стр|page|страниц)', sm, re.I):
                val = int(m.group(1))
                if val < 200 and val > 1 and val not in (375,):
                    ctx = sm[max(0,m.start()-30):m.end()+30].replace('\n',' ')
                    pheader()
                    msg = f'{name} [sysMsg]: "{val} {m.group(2)}" → ...{ctx}...'
                    print(WARN(msg))
            
            for m in re.finditer(r'(\d{1,3})\s*[-–—]\s*(\d{1,3})\s*(стр|page)', sm, re.I):
                pheader()
                msg = f'{name} [sysMsg]: range "{m.group(0)}"'
                print(RED(msg))
                problems.append(msg)
        
        # ── Check maxTokens ──
        max_tokens = None
        # In chainLlm nodes
        if 'maxTokensToSample' in str(params):
            mt_match = re.search(r'"maxTokensToSample":\s*(\d+)', json.dumps(params))
            if mt_match:
                max_tokens = int(mt_match.group(1))
        # In agent model options
        model_params = params.get('options', {})
        if isinstance(model_params, dict) and 'maxTokens' in model_params:
            max_tokens = model_params['maxTokens']
        
        if max_tokens and max_tokens < 4000:
            pheader()
            msg = f'{name}: maxTokens = {max_tokens} (may truncate long sections)'
            print(WARN(msg))
        
        # ── Check n8n expressions in all string params ──
        param_str = json.dumps(params)
        for m in re.finditer(r'\{\{.*?(\d{2,3})\s*(стр|page).*?\}\}', param_str, re.I):
            val = int(m.group(1))
            if val < 200:
                pheader()
                msg = f'{name} [expression]: {m.group(0)[:80]}'
                print(WARN(msg))
    
    if not header_printed[0]:
        pass  # clean file, skip

# ─────────────── 2. Markdown prompt files ───────────────
print(f'\n=== Markdown prompts ===')
md_files = sorted(glob.glob('n8n/prompts/*.md'))
for md_file in md_files:
    with open(md_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    basename = os.path.basename(md_file)
    
    # Check for hardcoded page numbers
    for m in re.finditer(r'(\d{1,3})\s*(стр|page|страниц)', content, re.I):
        val = int(m.group(1))
        if val < 200 and val > 1 and val not in (375,):
            line_num = content[:m.start()].count('\n') + 1
            ctx = content[max(0,m.start()-30):m.end()+30].replace('\n',' ')
            msg = f'{basename}:{line_num}: "{val} {m.group(2)}" → ...{ctx}...'
            print(WARN(msg))
    
    # Check for page ranges
    for m in re.finditer(r'(\d{1,3})\s*[-–—]\s*(\d{1,3})\s*(стр|page)', content, re.I):
        line_num = content[:m.start()].count('\n') + 1
        msg = f'{basename}:{line_num}: range "{m.group(0)}"'
        print(RED(msg))
        problems.append(msg)
    
    # Check for "максимум N" patterns
    for m in re.finditer(r'(максимум|макс\.?|max)\s+(\d{1,3})\b', content, re.I):
        val = int(m.group(2))
        if val < 200 and val > 1:
            line_num = content[:m.start()].count('\n') + 1
            ctx = content[max(0,m.start()-20):m.end()+40].replace('\n',' ')
            msg = f'{basename}:{line_num}: "{m.group(0)}" → ...{ctx}...'
            print(WARN(msg))

# ─────────────── 3. JS files ───────────────
print(f'\n=== JS files ===')
js_files = sorted(glob.glob('js/*.js'))
for js_file in js_files:
    with open(js_file, 'r', encoding='utf-8') as f:
        content = f.read()
    basename = os.path.basename(js_file)
    for m in re.finditer(r'targetPages[^\n]{0,60}', content, re.I):
        print(f'  {basename}: {m.group(0).strip()}')

# ─────────────── Summary ───────────────
print(f'\n{"="*50}')
if problems:
    print(f'⚠️  Found {len(problems)} CRITICAL issues:')
    for p in problems:
        print(f'  • {p}')
else:
    print('✅ No critical hardcoded page limits found!')
print(f'{"="*50}')
