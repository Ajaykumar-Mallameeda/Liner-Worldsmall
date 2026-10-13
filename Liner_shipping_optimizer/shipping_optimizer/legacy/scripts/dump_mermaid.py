#!/usr/bin/env python3
"""Dump failing Mermaid diagrams for debugging."""
import re, os, sys

os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

failures = {
    "MASTER_TECHNICAL_DOCUMENTATION_V2.md": [3, 10],
    "ARCHITECTURE_REFERENCE.md": [5, 8, 10, 12, 13],
}

for doc_name, indices in failures.items():
    with open(doc_name, encoding='utf-8') as f:
        content = f.read()

    pattern = r'```mermaid\n([\s\S]*?)```'
    matches = list(re.finditer(pattern, content))

    for idx in indices:
        if idx <= len(matches):
            m = matches[idx - 1]
            inner = m.group(1)
            line_num = content[:m.start()].count('\n') + 1
            print(f"\n{'='*60}")
            print(f"=== {doc_name} -- Diagram #{idx} (line {line_num}) ===")
            print(f"{'='*60}")
            for i, line in enumerate(inner.strip().split('\n'), 1):
                print(f"  {i:3d}| {line}")
            print(f"{'='*60}")
