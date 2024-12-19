import json
from pathlib import Path

# Read results file
results_file = Path('results/results.json')
with open(results_file) as f:
    results = json.load(f)

# Calculate success percentage
total_tasks = len(results)
successful_tasks = [result for result in results if result.get('final_score', 0) == 1]
success_percentage = (len(successful_tasks) / total_tasks) * 100 if total_tasks > 0 else 0

print(f"\nResults Analysis:")
print(f"Total Tasks: {total_tasks}")
print(f"Successful Tasks: {len(successful_tasks)}")
print(f"Success Rate: {success_percentage:.2f}%")

print("\nPassed Tests:")
print("-" * 80)
for task in successful_tasks:
    print(f"Task ID: {task['task_id']}")
    print(f"Website: {task.get('web_name', 'N/A')}")
    print(f"Task: {task.get('task_description', 'N/A')}")
    print(f"Score: {task.get('final_score', 0)}")
    print("-" * 80)
