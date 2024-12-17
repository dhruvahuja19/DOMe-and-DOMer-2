"""Script to compare different model performances on the DOM benchmark."""

import os
import json
import time
import argparse
from typing import List, Dict
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv

from models import GPT4Model, ClaudeModel
from utils import TaskExecutor

def load_tasks(task_file: str) -> List[Dict]:
    """Load benchmark tasks from a JSON file."""
    with open(task_file, 'r') as f:
        return [json.loads(line) for line in f]

def run_model_on_task(model, task, executor):
    """Run a single task with timing and error handling."""
    start_time = time.time()
    try:
        result = model.run_task(task, executor)
        end_time = time.time()
        return {
            'task': task['task'],
            'success': result.success,
            'error': result.error,
            'time_taken': end_time - start_time
        }
    except Exception as e:
        end_time = time.time()
        return {
            'task': task['task'],
            'success': False,
            'error': str(e),
            'time_taken': end_time - start_time
        }

def evaluate_model(model, tasks: List[Dict], num_workers: int = 4):
    """Evaluate a model on all tasks."""
    results = []
    executor = TaskExecutor()
    
    with ThreadPoolExecutor(max_workers=num_workers) as pool:
        futures = [
            pool.submit(run_model_on_task, model, task, executor)
            for task in tasks
        ]
        results = [f.result() for f in futures]
    
    return results

def calculate_metrics(results: List[Dict]):
    """Calculate performance metrics from results."""
    total_tasks = len(results)
    successful_tasks = sum(1 for r in results if r['success'])
    total_time = sum(r['time_taken'] for r in results)
    error_types = {}
    
    for r in results:
        if r['error']:
            error_type = type(r['error']).__name__
            error_types[error_type] = error_types.get(error_type, 0) + 1
    
    return {
        'total_tasks': total_tasks,
        'successful_tasks': successful_tasks,
        'success_rate': successful_tasks / total_tasks * 100,
        'average_time': total_time / total_tasks,
        'total_time': total_time,
        'error_types': error_types
    }

def main():
    parser = argparse.ArgumentParser(description='Compare model performances on DOM benchmark')
    parser.add_argument('--task-file', default='data/dom_tasks.jsonl', help='Path to task file')
    parser.add_argument('--num-workers', type=int, default=4, help='Number of parallel workers')
    parser.add_argument('--output', default='results/comparison.json', help='Output file for results')
    args = parser.parse_args()
    
    # Load environment variables and tasks
    load_dotenv()
    tasks = load_tasks(args.task_file)
    
    # Initialize models
    models = {
        'gpt4': GPT4Model(api_key=os.getenv("OPENAI_API_KEY")),
        'claude': ClaudeModel(api_key=os.getenv("ANTHROPIC_API_KEY"))
    }
    
    # Run evaluation
    results = {}
    for model_name, model in models.items():
        print(f"\nEvaluating {model_name}...")
        model_results = evaluate_model(model, tasks, args.num_workers)
        metrics = calculate_metrics(model_results)
        results[model_name] = {
            'metrics': metrics,
            'task_results': model_results
        }
        
        print(f"\nResults for {model_name}:")
        print(f"Success rate: {metrics['success_rate']:.2f}%")
        print(f"Average time per task: {metrics['average_time']:.2f}s")
        print("Error types:", metrics['error_types'])
    
    # Save results
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\nResults saved to {args.output}")

if __name__ == "__main__":
    main()
