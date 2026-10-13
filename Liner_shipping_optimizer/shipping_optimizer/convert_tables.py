#!/usr/bin/env python3
"""Convert ASCII box-drawing tables to Markdown pipe tables."""
import re

def convert_ascii_table(table_str):
    """Parse an ASCII box-drawing table and return a Markdown pipe table string."""
    lines = table_str.split('\n')

    # Filter to only │ content lines (skip ┌┐└┘├─┤ separator lines)
    body_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('┌') or stripped.startswith('└'):
            continue
        if '│' in stripped:
            body_lines.append(stripped)

    if not body_lines:
        return table_str

    # Group: every other line is data, the ones between are continuations
    # Actually: lines with │ that have content are data rows;
    # lines that are just continuations of the previous row (no │ at start, or │ with just spaces)
    rows_raw = []
    i = 0
    while i < len(body_lines):
        line = body_lines[i]
        # Check if this is a real data row (has │ with actual content between them)
        if line.startswith('│'):
            # Check for continuation rows (lines between data rows that don't start with │)
            parts = [p.strip() for p in line.split('│')]
            cells = [p for p in parts if p]
            conts = []
            i += 1
            # Collect continuation lines (lines without │ prefix that belong to this row)
            while i < len(body_lines):
                next_line = body_lines[i]
                # Continuation lines have │ but with leading spaces, OR are plain text lines
                if next_line.startswith('│') and next_line.strip().startswith('│'):
                    # This might be a continuation or a new row
                    inner = next_line[1:].strip()
                    if inner == '' or all(c in ' -═' for c in inner):
                        # It's a continuation - merge with previous cell content
                        parts = [p.strip() for p in next_line.split('│')]
                        cont_cells = [p for p in parts if p]
                        if cont_cells:
                            # Merge first cell with continuation
                            if cells:
                                cells[0] += ' ' + cont_cells[0]
                            else:
                                cells = cont_cells
                        i += 1
                    else:
                        break
                else:
                    # Plain continuation line
                    conts.append(next_line.rstrip())
                    i += 1
            rows_raw.append((cells, conts))
        else:
            i += 1

    if not rows_raw:
        return table_str

    num_cols = len(rows_raw[0][0])
    result_lines = []

    for idx, (cells, conts) in enumerate(rows_raw):
        if idx == 0:
            # Header row
            result_lines.append('| ' + ' | '.join(cells) + ' |')
            # Separator
            result_lines.append('|' + '|'.join(['---'] * num_cols) + '|')
        else:
            result_lines.append('| ' + ' | '.join(cells) + ' |')
            for cont in conts:
                result_lines.append(cont.rstrip())

    return '\n'.join(result_lines)


def main():
    with open('verfication/01_GOLDEN_SPECIFICATION.md', 'r', encoding='utf-8') as f:
        content = f.read()

    # Match complete ASCII table blocks from ┌ to └
    table_pattern = re.compile(r'(┌[─┬┐].*?└[─┴┘])', re.DOTALL)

    matches = list(table_pattern.finditer(content))
    print(f"Found {len(matches)} ASCII tables to convert")

    # Process in reverse order to preserve positions
    new_content = content
    for match in reversed(matches):
        table_str = match.group(0)
        converted = convert_ascii_table(table_str)
        new_content = new_content[:match.start()] + converted + new_content[match.end():]

    # Write back
    with open('verfication/01_GOLDEN_SPECIFICATION.md', 'w', encoding='utf-8') as f:
        f.write(new_content)

    # Verify
    remaining = re.findall(r'[┌┬┐├─┤└┴┘]', new_content)
    print(f"Remaining box-drawing chars: {len(remaining)}")

if __name__ == '__main__':
    main()
