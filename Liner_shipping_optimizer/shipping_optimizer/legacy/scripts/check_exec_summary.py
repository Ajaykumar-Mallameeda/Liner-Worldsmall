import json, re
with open('pipeline_output.json') as f:
    d = json.load(f)

es = d.get('executive_summary', '')
print('=== EXECUTIVE SUMMARY ===')
print(es)

print()
print('=== CHECKS ===')
print(f'Length > 100: {len(es) > 100} ({len(es)} chars)')
print(f'Has verdict: {any(v in es for v in ("Good", "Moderate", "Poor"))}')
print(f'Has Strength: {"Strength" in es}')
print(f'Has Weakness: {"Weakness" in es}')
print(f'Has Priority/Action: {"Priority" in es or "Action" in es}')
print(f'Has dollar figure: {bool(re.search(r"\\$[\\d,]+", es))}')
print(f'Has percentage: {bool(re.search(r"\\d+\\.?\\d*%", es))}')
vague = ['consider', 'explore', 'may ', 'could potentially', 'perhaps', 'renegotiating contracts', 'more efficient technologies']
print(f'Has vague language: {any(v in es.lower() for v in vague)}')
