import logging
import json
from pathlib import Path
from typing import Dict, Any, List, Tuple
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

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

        # Calculate final score: 80% visual, 20% HTML
        final_score = (0.8 * visual_score) + (0.2 * html_score)

        evaluation = {
            "task_id": task_id,
            "success": result["success"],
            "visual_score": visual_score,
            "html_score": html_score,
            "final_score": final_score,
            "visual_reasoning": visual_reasoning,
            "html_reasoning": html_reasoning
        }
        logging.info(f"Evaluated task {task_id}: score={final_score:.2f}")
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
) -> Dict[str, Any]:
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
    
    # Process tasks in smaller batches to avoid rate limits
    batch_size = min(max_workers, 3)  # Process at most 3 tasks at a time
    for i in range(0, len(task_pairs), batch_size):
        batch = task_pairs[i:i + batch_size]
        logging.info(f"Processing evaluation batch {i//batch_size + 1}/{(len(task_pairs) + batch_size - 1)//batch_size}")
        
        # Run evaluations in parallel for this batch
        with ThreadPoolExecutor(max_workers=batch_size) as executor:
            future_to_task = {
                executor.submit(evaluate_task, task, result, client): task['id']
                for task, result in batch
            }
            
            for future in as_completed(future_to_task):
                try:
                    evaluation = future.result(timeout=60)  # 60 second timeout per evaluation
                    evaluations.append(evaluation)
                    logging.info(f"Completed evaluation for task {future_to_task[future]}")
                except Exception as e:
                    task_id = future_to_task[future]
                    error_msg = f"Error in evaluation future for task {task_id}: {str(e)}"
                    logging.error(error_msg)
                    evaluations.append({
                        "task_id": task_id,
                        "success": False,
                        "visual_score": 0.0,
                        "html_score": 0.0,
                        "final_score": 0.0,
                        "error": error_msg
                    })
        
        # Add a small delay between batches to avoid rate limits
        if i + batch_size < len(task_pairs):
            time.sleep(1)
    
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
