import json
from pathlib import Path

# Read results file
results_file = Path('results/benchmark_results.json/results.json')
with open(results_file) as f:
    results = json.load(f)

# Calculate succexss percentage
total_tasks = len(results)
successful_tasks = sum(1 for result in results if result.get('success', False))
success_percentage = (successful_tasks / total_tasks) * 100 if total_tasks > 0 else 0

print(f"\nResults Analysis:")
print(f"Total Tasks: {total_tasks}")
print(f"Successful Tasks: {successful_tasks}")
print(f"Success Rate: {success_percentage:.2f}%")
