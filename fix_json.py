import json
import re

def fix_json_line(line):
    # Remove any control characters except \n
    line = ''.join(char for char in line if ord(char) >= 32 or char == '\n')
    # Ensure proper escaping of quotes and backslashes in HTML
    line = re.sub(r'(?<!\\)"', '\\"', line)
    return line

input_file = 'data/dom_tasks.jsonl'
output_file = 'data/dom_tasks_fixed.jsonl'

with open(input_file, 'r', encoding='utf-8') as f:
    lines = f.readlines()

fixed_lines = []
for i, line in enumerate(lines, 1):
    try:
        # First try to parse the original line
        json.loads(line.strip())
        fixed_lines.append(line.strip())
    except json.JSONDecodeError as e:
        print(f"Error in line {i}: {e}")
        # Try to fix the line
        fixed_line = fix_json_line(line.strip())
        try:
            json.loads(fixed_line)
            fixed_lines.append(fixed_line)
            print(f"Fixed line {i}")
        except json.JSONDecodeError as e:
            print(f"Could not fix line {i}: {e}")
            continue

with open(output_file, 'w', encoding='utf-8') as f:
    for line in fixed_lines:
        f.write(line + '\n')
