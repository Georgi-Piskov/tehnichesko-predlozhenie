import PyPDF2
import sys

filepath = sys.argv[1]
max_pages = int(sys.argv[2]) if len(sys.argv) > 2 else 5

with open(filepath, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    print(f'Total pages: {len(reader.pages)}')
    for i, page in enumerate(reader.pages[:max_pages]):
        text = page.extract_text()
        if text:
            print(f'\n--- Page {i+1} ---')
            print(text[:3000])
