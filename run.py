import json
import argparse
from pathlib import Path
from parallel_runner import run_parallel_benchmark
from serial_runner import run_serial_benchmark
from evaluation.auto_eval import run_evaluation
from models import GPT4Model, ClaudeModel, GeminiModel
import os
from dotenv import load_dotenv

def get_model(model_name):
    """Get the appropriate model based on command line argument."""
    load_dotenv()
    
    models = {
        'gpt4': lambda: GPT4Model(api_key=os.getenv("OPENAI_API_KEY")),
        'claude': lambda: ClaudeModel(api_key=os.getenv("ANTHROPIC_API_KEY"), model_config={}),
        'gemini': lambda: GeminiModel(api_key=os.getenv("GOOGLE_API_KEY"), model_config={})
    }
    
    if model_name not in models:
        raise ValueError(f"Model {model_name} not supported. Choose from: {', '.join(models.keys())}")
    
    return models[model_name]()

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
    parser.add_argument('--model', choices=['gpt4', 'claude', 'gemini'], default='gpt4', help='Model to use for the benchmark')
    
    args = parser.parse_args()
    
    # Initialize the selected model
    model = get_model(args.model)
    
    # Create output directory
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Run benchmark based on mode
    if args.mode == 'parallel':
        results = run_parallel_benchmark(
            tasks_file=args.tasks,
            output_dir=str(output_dir),
            max_workers=args.max_workers,
            save_accessibility_tree=args.save_accessibility_tree,
            wait_time=args.wait_time,
            model=model
        )
    else:
        results = run_serial_benchmark(
            tasks_file=args.tasks,
            output_dir=str(output_dir),
            save_accessibility_tree=args.save_accessibility_tree,
            wait_time=args.wait_time,
            model=model
        )
    
    # Save results
    results_file = output_dir / 'results.json'
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    # Run evaluation if requested
    if args.evaluate:
        # Run evaluations
        eval_results = run_evaluation(
            tasks_file=Path(args.tasks),
            results_dir=results_file,
            output_file=None,  # Don't save to separate file
            openai_key=os.getenv('OPENAI_API_KEY'),
            max_workers=args.max_workers if args.evaluate_mode == 'parallel' else None
        )
        
        # Update results with evaluations
        for result in results:
            task_id = result['task_id']
            eval_result = next((e for e in eval_results['evaluations'] if e['task_id'] == task_id), None)
            if eval_result:
                # Get evaluation scores and explanations, with defaults if missing
                visual_score = eval_result.get('visual_score', 0.0)
                html_score = eval_result.get('html_score', 0.0)
                final_score = eval_result.get('final_score', 0.0)  # Get final score from evaluation
                visual_reasoning = eval_result.get('visual_reasoning', 'No visual evaluation available')
                html_reasoning = eval_result.get('html_reasoning', 'No HTML evaluation available')
                
                # Add evaluation scores to result
                result['final_score'] = final_score  # Add final score at top level
                result['llm_evaluations'] = {
                    'image_similarity': {
                        'score': visual_score,
                        'explanation': visual_reasoning
                    },
                    'html_fuzzy_match': {
                        'score': html_score,
                        'explanation': html_reasoning
                    }
                }
                # Update success based on evaluation scores
                # Only mark as success if both image and HTML evaluations pass
                result['success'] = (visual_score > 0.5 and html_score > 0.5)
                if not result['success'] and not result['error']:
                    result['error'] = "Failed evaluation checks"
        
        # Save updated results
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

if __name__ == '__main__':
    main()
