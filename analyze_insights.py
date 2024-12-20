import json
from collections import defaultdict
from typing import Dict, List, Any

def load_results() -> List[Dict[str, Any]]:
    with open('results/results.json') as f:
        return json.load(f)

def analyze_results(results: List[Dict[str, Any]]) -> None:
    total_tasks = len(results)
    successes = [r for r in results if r.get('success', False)]
    failures = [r for r in results if not r.get('success', False)]
    
    print("\n=== Overall Statistics ===")
    print(f"Total Tasks: {total_tasks}")
    print(f"Success Rate: {len(successes)/total_tasks*100:.2f}% ({len(successes)} successes, {len(failures)} failures)")

    # Error Analysis
    error_types = defaultdict(int)
    for task in failures:
        error = task.get('error', 'Unknown error')
        if isinstance(error, str):
            # Simplify error messages to group similar errors
            if 'has no attribute' in error:
                error = "Missing attribute error"
            elif 'timeout' in error.lower():
                error = "Timeout error"
            elif 'not found' in error.lower():
                error = "Element not found"
            elif 'failed evaluation' in error.lower():
                error = "Failed evaluation checks"
        error_types[error] += 1

    print("\n=== Error Analysis ===")
    print("Common failure reasons:")
    for error, count in sorted(error_types.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(failures)) * 100
        print(f"{error}: {percentage:.1f}% ({count} tasks)")

    # Task Type Analysis
    def categorize_task(task_desc: str) -> str:
        desc = task_desc.lower()
        if 'click' in desc:
            return 'Click'
        elif 'type' in desc or 'enter' in desc:
            return 'Type/Input'
        elif 'search' in desc:
            return 'Search'
        elif 'hover' in desc:
            return 'Hover'
        return 'Other'

    task_types = defaultdict(lambda: {'success': 0, 'fail': 0})
    for task in results:
        task_type = categorize_task(task.get('task_description', ''))
        if task.get('success', False):
            task_types[task_type]['success'] += 1
        else:
            task_types[task_type]['fail'] += 1

    print("\n=== Task Type Analysis ===")
    for task_type, stats in task_types.items():
        total = stats['success'] + stats['fail']
        success_rate = (stats['success']/total*100) if total > 0 else 0
        print(f"{task_type}: {success_rate:.1f}% success rate ({stats['success']}/{total} tasks)")

    # Website Analysis
    def extract_website(task_id: str) -> str:
        return task_id.split('_')[0] if '_' in task_id else 'unknown'

    website_stats = defaultdict(lambda: {'success': 0, 'fail': 0})
    for task in results:
        website = extract_website(task.get('task_id', 'unknown'))
        if task.get('success', False):
            website_stats[website]['success'] += 1
        else:
            website_stats[website]['fail'] += 1

    print("\n=== Website Performance ===")
    for website, stats in sorted(website_stats.items(), 
                               key=lambda x: (x[1]['success'] + x[1]['fail']), 
                               reverse=True):
        total = stats['success'] + stats['fail']
        if total < 2:  # Skip websites with very few tasks
            continue
        success_rate = (stats['success']/total*100)
        print(f"{website}: {success_rate:.1f}% success rate ({stats['success']}/{total} tasks)")

    # Example Analysis
    print("\n=== Example Cases ===")
    print("\nSuccessful Tasks:")
    for task in successes[:3]:
        print(f"✓ {task.get('task_description', '')}")
        print(f"  ID: {task.get('task_id', '')}")
        if task.get('error'):
            print(f"  Note: {task['error']}")
        print()

    print("\nFailed Tasks:")
    for task in failures[:3]:
        print(f"✗ {task.get('task_description', '')}")
        print(f"  ID: {task.get('task_id', '')}")
        if task.get('error'):
            print(f"  Error: {task['error']}")
        print()

if __name__ == "__main__":
    results = load_results()
    analyze_results(results)
