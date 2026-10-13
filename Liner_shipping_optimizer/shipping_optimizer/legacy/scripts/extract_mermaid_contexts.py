#!/usr/bin/env python3
"""Extract Mermaid diagram contexts for caption mapping."""
import re, sys, json

def extract_mermaid_contexts(filepath):
    content = open(filepath, encoding='utf-8').read()
    pattern = r'```mermaid\n([\s\S]*?)```'
    contexts = []

    for match in re.finditer(pattern, content):
        start = match.start()
        text_before = content[max(0, start-200):start].strip()

        lines_before = text_before.split('\n')
        context_line = ''
        for line in reversed(lines_before):
            clean = line.strip()
            if clean and not clean.startswith('```') and not clean.startswith('|') and not clean.startswith('#'):
                context_line = clean[:100]
                break

        section = content[:start].split('\n')
        heading = ''
        for line in reversed(section):
            if line.startswith('## '):
                heading = line.strip().lstrip('#').strip()
                break
        subheading = ''
        for line in reversed(section):
            if line.startswith('### '):
                subheading = line.strip().lstrip('#').strip()
                break

        inner = match.group(1)
        first_line = inner.strip().split('\n')[0].strip() if inner.strip() else 'unknown'

        contexts.append({
            'position': start,
            'type': first_line.split()[0] if first_line.split() else 'unknown',
            'first_line': first_line[:80],
            'heading': heading,
            'subheading': subheading,
            'context': context_line[:100],
        })

    return contexts

for doc, path in [
    ('MASTER', 'MASTER_TECHNICAL_DOCUMENTATION_V2.md'),
    ('ARCH', 'ARCHITECTURE_REFERENCE.md'),
    ('CODE', 'CODE_REFERENCE.md'),
]:
    ctxs = extract_mermaid_contexts(path)
    print(f'\n=== {doc} ({len(ctxs)} diagrams) ===')
    for i, c in enumerate(ctxs, 1):
        print(f'\n  #{i}: Type={c["type"]}, First={c["first_line"][:50]}')
        print(f'       Section: {c["heading"]}')
        if c['subheading']:
            print(f'       Sub-section: {c["subheading"]}')
        print(f'       Context: {c["context"][:80]}')
