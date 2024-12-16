import argparse
import os
import json
import time
import base64
from pathlib import Path
from typing import List, Dict, Any

from openai import OpenAI
from dotenv import load_dotenv

SYSTEM_PROMPT = """As an evaluator for DOM and DOMer-2 benchmark, you will assess web element interactions based on visual comparison:

1. Task Description: A specific web interaction task (e.g., "Click the search button", "Type text in input field")

2. Visual Validation:
   - Before: Initial webpage state
   - After: Actual result after interaction
   - Ground Truth: Expected result for successful interaction
   - Expected Visual Changes: List of specific visual changes to verify

Your evaluation should:
1. Compare the after screenshot with the ground truth screenshot
2. Verify all listed visual changes occurred
3. Pay special attention to the relevant regions where changes should occur

Provide your evaluation as:
1. A score from 0-100 based on visual similarity and completion of expected changes
2. 'SUCCESS' if score ≥ 90, otherwise 'NOT SUCCESS'
3. Brief explanation of:
   - Visual changes observed/missing
   - Why the interaction succeeded or failed"""

def encode_image(image_path: str) -> str:
    """Encode image as base64 string"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def evaluate_task(
    task: Dict[str, Any],
    result: Dict[str, Any],
    ground_truth: Dict[str, Any],
    openai_client: OpenAI
) -> Dict[str, Any]:
    """Evaluate a single task using GPT-4V based on visual comparison"""
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": f"""
Task: {task['task']}

Please compare:
1. Before screenshot (initial state)
2. After screenshot (actual result)
3. Ground truth screenshot (expected result)

Expected visual changes:
{json.dumps(ground_truth['visual_changes'], indent=2)}

Provide:
1. Similarity score (0-100)
2. Success status
3. Brief explanation"""},
        {"role": "assistant", "content": "I'll examine the screenshots and evaluate based on visual similarity and expected changes."},
        {"role": "user", "content": [
            {"type": "text", "text": "Before interaction:"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_image(result['before_screenshot'])}"}},
            {"type": "text", "text": "After interaction:"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_image(result['after_screenshot'])}"}},
            {"type": "text", "text": "Ground Truth:"},
            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_image(ground_truth['screenshot'])}"}},
        ]}
    ]

    try:
        response = openai_client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=messages,
            max_tokens=1000,
            temperature=0
        )
        
        evaluation = response.choices[0].message.content
        
        # Extract score and success status
        import re
        score_match = re.search(r'(\d+)(?=/100|%)', evaluation)
        score = int(score_match.group(1)) if score_match else 0
        
        return {
            "task_id": task["id"],
            "score": score,
            "success": score >= 90,
            "evaluation": evaluation,
            "timestamp": int(time.time())
        }
        
    except Exception as e:
        return {
            "task_id": task["id"],
            "score": 0,
            "success": False,
            "evaluation": f"Evaluation failed: {str(e)}",
            "timestamp": int(time.time())
        }

def run_evaluation(
    tasks_file: Path,
    results_dir: Path,
    ground_truth_dir: Path,
    output_file: Path,
    openai_key: str
):
    """Run evaluation on benchmark results"""
    # Load environment variables
    load_dotenv()
    
    # Initialize OpenAI client
    openai_client = OpenAI(api_key=openai_key)
    
    # Load tasks and results
    with open(tasks_file) as f:
        tasks = [json.loads(line) for line in f]
    
    with open(results_dir / "results.json") as f:
        results = json.load(f)
    
    # Evaluate each task
    evaluations = []
    for task in tasks:
        task_result = next((r for r in results if r["task_id"] == task["id"]), None)
        if task_result:
            evaluation = evaluate_task(
                task,
                task_result,
                ground_truth_dir,
                openai_client
            )
            evaluations.append(evaluation)
    
    # Save evaluations
    output = {
        "total_tasks": len(tasks),
        "successful_tasks": sum(1 for e in evaluations if e["success"]),
        "evaluations": evaluations
    }
    
    with open(output_file, "w") as f:
        json.dump(output, f, indent=2)

def main():
    parser = argparse.ArgumentParser(description="Evaluate DOM benchmark results")
    parser.add_argument("--tasks", type=Path, required=True, help="Path to tasks JSONL file")
    parser.add_argument("--results", type=Path, required=True, help="Path to results directory")
    parser.add_argument("--ground-truth", type=Path, required=True, help="Path to ground truth directory")
    parser.add_argument("--output", type=Path, required=True, help="Path to output evaluation file")
    parser.add_argument("--openai-key", type=str, required=True, help="OpenAI API key")
    
    args = parser.parse_args()
    run_evaluation(args.tasks, args.results, args.ground_truth, args.output, args.openai_key)

if __name__ == "__main__":
    main()
