import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from openai import OpenAI
import time

from evaluation.image_match import compare_images
from evaluation.fuzzy_match import fuzzy_match_html
from evaluation.parallel_eval import run_parallel_evaluation

def retry_api_call(func, max_retries=3, initial_wait=1):
    """Retry API calls with exponential backoff"""
    def wrapper(*args, **kwargs):
        retries = 0
        while retries < max_retries:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                retries += 1
                if retries == max_retries:
                    raise e
                wait_time = initial_wait * (2 ** (retries - 1))
                logging.warning(f"API call failed, retrying in {wait_time}s. Error: {str(e)}")
                time.sleep(wait_time)
    return wrapper

@retry_api_call
def evaluate_visual(client: OpenAI, prompt: str, ground_truth_path: str, agent_image_path: str) -> Tuple[bool, str]:
    return compare_images(prompt=prompt, 
                        ground_truth_path=ground_truth_path,
                        agent_image_path=agent_image_path,
                        openai_client=client)

@retry_api_call
def evaluate_html(client: OpenAI, task_description: str, actual_html: str, expected_html: str) -> Tuple[bool, str]:
    return fuzzy_match_html(task_description=task_description,
                          actual_html=actual_html,
                          expected_html=expected_html,
                          openai_client=client)

def run_serial_evaluation(
    tasks_file: Path,
    results_dir: Path,
    output_file: Path,
    openai_key: str
) -> Dict[str, Any]:
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
                # Visual evaluation using compare_images with retry
                visual_correctness, visual_reasoning = evaluate_visual(
                    client,
                    prompt=f"Task: {task['task']}\nInteraction: {task['interaction']}\nExpected: {task.get('expected_outcome', 'Complete the task as specified')}",
                    ground_truth_path=task['ground_truth']['screenshot'],
                    agent_image_path=result["after_screenshot"]
                )
                
                # HTML comparison using fuzzy_match with retry
                html_correctness, html_reasoning = evaluate_html(
                    client,
                    task_description=f"{task['task']}\nInteraction: {task['interaction']}\nExpected: {task.get('expected_outcome', 'Complete the task as specified')}",
                    actual_html=result.get("html_element", ""),
                    expected_html=task.get('target_html', '')
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
                    "final_score": (0.8 * visual_score + 0.2 * html_score),
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
    
    evaluation_results = {
        "total_tasks": len(tasks),
        "successful_tasks": sum(1 for e in evaluations if e.get("success", False)),
        "evaluations": evaluations
    }
    
    # Save evaluations if output file is provided
    if output_file:
        with output_file.open('w') as f:
            json.dump(evaluation_results, f, indent=2)
            
    return evaluation_results

def run_evaluation(
    tasks_file: Path,
    results_dir: Path,
    output_file: Path,
    openai_key: str,
    max_workers: int = None
) -> Dict[str, Any]:
    """Run evaluation on task results using either serial or parallel mode"""
    if max_workers:
        return run_parallel_evaluation(tasks_file, results_dir, output_file, openai_key, max_workers)
    else:
        return run_serial_evaluation(tasks_file, results_dir, output_file, openai_key)
