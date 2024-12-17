import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed

from evaluation.image_match import compare_images
from evaluation.fuzzy_match import fuzzy_match_html

def evaluate_task(task: Dict[str, Any], result: Dict[str, Any], client: OpenAI) -> Dict[str, Any]:
    """Evaluate a single task in parallel"""
    task_id = task['id']
    try:
        # Visual evaluation using compare_images
        visual_correctness, visual_reasoning = compare_images(
            prompt=f"Task: {task['task']}\nInteraction: {task['interaction']}\nExpected: {task.get('expected_outcome', 'Complete the task as specified')}",
            ground_truth_path=task['ground_truth']['screenshot'],
            agent_image_path=result["after_screenshot"],
            openai_client=client
        )
        
        # HTML comparison using fuzzy_match
        html_correctness, html_reasoning = fuzzy_match_html(
            task_description=f"{task['task']}\nInteraction: {task['interaction']}\nExpected: {task.get('expected_outcome', 'Complete the task as specified')}",
            actual_html=result.get("html_element", ""),
            expected_html=task.get('target_html', ''),
            openai_client=client
        )

        # Convert bool to float for scoring
        visual_score = 1.0 if visual_correctness else 0.0
        html_score = 1.0 if html_correctness else 0.0

        evaluation = {
            "task_id": task_id,
            "success": result["success"],
            "visual_score": visual_score,
            "html_score": html_score,
            "final_score": (visual_score + html_score) / 2,
            "visual_reasoning": visual_reasoning,
            "html_reasoning": html_reasoning
        }
        logging.info(f"Evaluated task {task_id}: score={evaluation.get('final_score', 0.0):.2f}")
        return evaluation
    except Exception as e:
        logging.error(f"Error evaluating task {task_id}: {str(e)}")
        return {
            "task_id": task_id,
            "success": False,
            "visual_score": 0.0,
            "html_score": 0.0,
            "final_score": 0.0,
            "error": str(e)
        }

def run_parallel_evaluation(
    tasks_file: Path,
    results_dir: Path,
    output_file: Path,
    openai_key: str,
    max_workers: int = 4
) -> None:
    """Run evaluation on task results in parallel"""
    # Initialize OpenAI client
    client = OpenAI(api_key=openai_key)
    
    # Load tasks and results
    with tasks_file.open() as f:
        tasks = [json.loads(line) for line in f if line.strip()]
    
    with results_dir.open() as f:
        results = json.load(f)
        if not isinstance(results, list):
            results = [results]
    
    evaluations = []
    task_pairs = []
    
    # Create task-result pairs
    for task in tasks:
        task_id = task['id']
        result = next((r for r in results if r.get('task_id') == task_id), None)
        if result:
            task_pairs.append((task, result))
    
    # Run evaluations in parallel
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_task = {
            executor.submit(evaluate_task, task, result, client): task_id
            for task, result in task_pairs
        }
        
        for future in as_completed(future_to_task):
            try:
                evaluation = future.result()
                evaluations.append(evaluation)
            except Exception as e:
                task_id = future_to_task[future]
                logging.error(f"Error in evaluation future for task {task_id}: {str(e)}")
                evaluations.append({
                    "task_id": task_id,
                    "success": False,
                    "visual_score": 0.0,
                    "html_score": 0.0,
                    "final_score": 0.0,
                    "error": str(e)
                })
    
    # Save evaluations to output file
    with output_file.open('w') as f:
        json.dump({
            "total_tasks": len(tasks),
            "successful_tasks": sum(1 for e in evaluations if e.get("success", False)),
            "evaluations": evaluations
        }, f, indent=2)
