#!/usr/bin/env python3

import os
import json
import logging
import argparse
from pathlib import Path
from typing import Dict, Any, List

from evaluation.auto_eval import run_evaluation

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def load_results(results_file: Path) -> List[Dict[str, Any]]:
    """Load results from a JSON file."""
    if not results_file.exists():
        raise FileNotFoundError(f"Results file not found: {results_file}")
    
    with open(results_file, 'r') as f:
        return json.load(f)

def save_results(results: List[Dict[str, Any]], output_file: Path):
    """Save results to a JSON file."""
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description='Evaluate DOM benchmark results')
    parser.add_argument('--tasks', required=True, help='Path to tasks JSONL file')
    parser.add_argument('--results', required=True, help='Path to results JSON file')
    parser.add_argument('--output', help='Path to output JSON file (default: results_with_eval.json)')
    parser.add_argument('--mode', choices=['serial', 'parallel'], default='serial', help='Evaluation mode')
    parser.add_argument('--max-workers', type=int, default=4, help='Max workers for parallel evaluation')
    args = parser.parse_args()

    # Set up paths
    tasks_file = Path(args.tasks)
    results_file = Path(args.results)
    output_file = Path(args.output) if args.output else results_file.parent / 'results_with_eval.json'

    # Load existing results
    results = load_results(results_file)
    logging.info(f"Loaded {len(results)} results from {results_file}")

    # Get OpenAI API key
    openai_key = os.getenv('OPENAI_API_KEY')
    if not openai_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    try:
        # Run evaluations
        eval_results = run_evaluation(
            tasks_file=tasks_file,
            results_dir=results_file,
            output_file=None,  # Don't save intermediate results
            openai_key=openai_key,
            max_workers=args.max_workers if args.mode == 'parallel' else None
        )

        # Update results with evaluations
        for result in results:
            task_id = result['task_id']
            eval_result = next((e for e in eval_results['evaluations'] if e['task_id'] == task_id), None)
            if eval_result:
                # Get evaluation scores and explanations
                result['visual_score'] = eval_result.get('visual_score', 0.0)
                result['html_score'] = eval_result.get('html_score', 0.0)
                result['visual_explanation'] = eval_result.get('visual_explanation', '')
                result['html_explanation'] = eval_result.get('html_explanation', '')
                result['total_score'] = (result['visual_score'] + result['html_score']) / 2.0

        # Save updated results
        save_results(results, output_file)
        logging.info(f"Saved evaluated results to {output_file}")

        # Print summary
        total_score = sum(r.get('total_score', 0.0) for r in results) / len(results)
        logging.info(f"Average score across {len(results)} tasks: {total_score:.2f}")

    except Exception as e:
        logging.error(f"Evaluation failed: {str(e)}")
        raise

if __name__ == '__main__':
    main()
