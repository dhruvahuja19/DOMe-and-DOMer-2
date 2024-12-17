import json
import argparse
from pathlib import Path
from parallel_runner import run_parallel_benchmark
from serial_runner import run_serial_benchmark
from evaluation.auto_eval import run_evaluation
import os

def main():
    parser = argparse.ArgumentParser(description='Run web automation tasks')
    parser.add_argument('--tasks', type=str, required=True, help='Path to tasks JSONL file')
    parser.add_argument('--output', type=str, required=True, help='Output directory for results')
    parser.add_argument('--max-workers', type=int, default=4, help='Number of parallel workers (only for parallel mode)')
    parser.add_argument('--mode', type=str, choices=['serial', 'parallel'], default='parallel',
                       help='Run tasks serially or in parallel')
    parser.add_argument('--save-accessibility-tree', action='store_true', help='Save accessibility trees for each task')
    parser.add_argument('--wait-time', type=float, default=2.0, help='Wait time between actions in seconds')
    parser.add_argument('--evaluate', action='store_true', help='Run evaluation after benchmark')
    parser.add_argument('--evaluate-mode', type=str, choices=['serial', 'parallel'], default='parallel',
                       help='Run evaluations serially or in parallel')
    
    args = parser.parse_args()
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run benchmark based on mode
    if args.mode == 'parallel':
        results = run_parallel_benchmark(
            tasks_file=args.tasks,
            output_dir=args.output,
            max_workers=args.max_workers,
            save_accessibility_tree=args.save_accessibility_tree,
            wait_time=args.wait_time
        )
    else:
        results = run_serial_benchmark(
            tasks_file=args.tasks,
            output_dir=args.output,
            save_accessibility_tree=args.save_accessibility_tree,
            wait_time=args.wait_time
        )
    
    # Save results
    results_file = output_dir / 'results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Run evaluation if requested
    if args.evaluate:
        eval_output = output_dir / "evaluation.json"
        run_evaluation(
            tasks_file=Path(args.tasks),
            results_dir=results_file,
            output_file=eval_output,
            openai_key=os.getenv('OPENAI_API_KEY'),
            max_workers=args.max_workers if args.evaluate_mode == 'parallel' else None
        )

if __name__ == '__main__':
    main()
