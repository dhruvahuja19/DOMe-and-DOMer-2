import json
from pathlib import Path
from collections import defaultdict

# Load results
with open('results/results.json') as f:
    results = json.load(f)

# Overall metrics
total_tasks = len(results)
successes = [r for r in results if r.get('final_score', 0) == 1]
failures = [r for r in results if r.get('final_score', 0) != 1]
success_rate = (len(successes) / total_tasks) * 100 if total_tasks > 0 else 0

print("\nOverall Metrics:")
print("-" * 80)
print(f"Total Tasks: {total_tasks}")
print(f"Successful Tasks: {len(successes)}")
print(f"Failed Tasks: {len(failures)}")
print(f"Success Rate: {success_rate:.2f}%")

print("\nSuccessful Tasks:")
print("-" * 80)
for task in successes:
    print(f"ID: {task['task_id']}")
    print(f"Task: {task.get('task', '')}")
    print(f"Website: {task.get('web', '')}")
    if task.get('input_text'):
        print(f"Input: {task.get('input_text', '')}")
    if task.get('target_element'):
        print(f"Target: {task['target_element'].get('type', '')}={task['target_element'].get('value', '')}")
    print()

# Analyze element overlaps
success_elements = defaultdict(list)
failure_elements = defaultdict(list)

for task in successes:
    if 'target_element' in task:
        element_key = (
            task['target_element'].get('type', ''),
            task['target_element'].get('value', '')
        )
        success_elements[element_key].append(task['task_id'])

for task in failures:
    if 'target_element' in task:
        element_key = (
            task['target_element'].get('type', ''),
            task['target_element'].get('value', '')
        )
        failure_elements[element_key].append(task['task_id'])

# Find overlapping elements
overlapping_elements = set(success_elements.keys()) & set(failure_elements.keys())

if overlapping_elements:
    print("\nElements that appear in both successes and failures:")
    print("-" * 80)
    for element in sorted(overlapping_elements):
        element_type, element_value = element
        print(f"\nElement: {element_type}={element_value}")
        print("\nSuccessful tasks:")
        for task_id in success_elements[element]:
            task = next(t for t in successes if t['task_id'] == task_id)
            print(f"- {task_id}: {task.get('task', '')}")
        print("\nFailed tasks:")
        for task_id in failure_elements[element]:
            task = next(t for t in failures if t['task_id'] == task_id)
            print(f"- {task_id}: {task.get('task', '')}")
        print("-" * 40)
else:
    print("\nNo elements appear in both successes and failures.")

# Group tasks by website
website_tasks = defaultdict(lambda: {'success': [], 'fail': []})

for task in results:
    website = task.get('web', '')
    if not website:
        continue
    
    if task.get('final_score', 0) == 1:
        website_tasks[website]['success'].append(task)
    else:
        website_tasks[website]['fail'].append(task)

# Find websites with both successes and failures
mixed_websites = {
    website: data 
    for website, data in website_tasks.items() 
    if data['success'] and data['fail']
}

if mixed_websites:
    print("\nWebsites with both successful and failed tasks:")
    print("-" * 80)
    
    for website, data in sorted(mixed_websites.items()):
        success_count = len(data['success'])
        fail_count = len(data['fail'])
        total = success_count + fail_count
        success_rate = (success_count / total) * 100
        
        print(f"\nWebsite: {website}")
        print(f"Success Rate: {success_rate:.2f}% ({success_count}/{total} tasks)")
        
        print("\nSuccessful Tasks:")
        for task in sorted(data['success'], key=lambda x: x.get('task', '')):
            task_desc = task.get('task', '').strip()
            if task_desc:
                print(f"✓ {task_desc}")
        
        print("\nFailed Tasks:")
        for task in sorted(data['fail'], key=lambda x: x.get('task', '')):
            task_desc = task.get('task', '').strip()
            if task_desc:
                print(f"✗ {task_desc}")
        
        print("-" * 80)
else:
    print("\nNo websites have both successes and failures - each website either consistently succeeds or fails.")
