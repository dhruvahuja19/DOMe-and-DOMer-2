import json

def add_target_html_field():
    tasks = []
    
    # Read existing tasks
    with open('../data/dom_tasks.jsonl', 'r') as f:
        for line in f:
            task = json.loads(line)
            # Add target_html field if not present
            if 'target_html' not in task:
                task['target_html'] = ""
            tasks.append(task)
    
    # Write back tasks with new field
    with open('../data/dom_tasks.jsonl', 'w') as f:
        for task in tasks:
            f.write(json.dumps(task) + '\n')

if __name__ == "__main__":
    add_target_html_field()
