import logging
import json
from pathlib import Path
from typing import Dict, Any, List
from openai import OpenAI

from evaluation.image_match import compare_images
from evaluation.fuzzy_match import fuzzy_match_html
from evaluation.parallel_eval import run_parallel_evaluation

def run_serial_evaluation(
    tasks_file: Path,
    results_dir: Path,
    output_file: Path,
    openai_key: str
) -> None:
    """Run evaluation on task results serially"""
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
    for task in tasks:
        task_id = task['id']
        result = next((r for r in results if r.get('task_id') == task_id), None)
        if result:
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

                # Combine scores and create evaluation
                evaluation = {
                    "task_id": task_id,
                    "success": result["success"],
                    "visual_score": visual_score,
                    "html_score": html_score,
                    "final_score": (visual_score + html_score) / 2,
                    "visual_reasoning": visual_reasoning,
                    "html_reasoning": html_reasoning
                }
                evaluations.append(evaluation)
                logging.info(f"Evaluated task {task_id}: score={evaluation.get('final_score', 0.0):.2f}")
            except Exception as e:
                logging.error(f"Error evaluating task {task_id}: {str(e)}")
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

def run_evaluation(
    tasks_file: Path,
    results_dir: Path,
    output_file: Path,
    openai_key: str,
    max_workers: int = None
) -> None:
    """Run evaluation on task results using either serial or parallel mode"""
    if max_workers:
        run_parallel_evaluation(tasks_file, results_dir, output_file, openai_key, max_workers)
    else:
        run_serial_evaluation(tasks_file, results_dir, output_file, openai_key)
