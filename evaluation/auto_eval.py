import argparse
import os
import json
import time
import base64
from pathlib import Path
from typing import List, Dict, Any

from openai import OpenAI
from dotenv import load_dotenv

SYSTEM_PROMPT = """As an evaluator for DOM and DOMer-2 benchmark, you will assess web element interactions based on:

1. Task Description: A specific web interaction task (e.g., "Click the search button", "Type text in input field")

2. Visual Validation:
   - Before: Initial webpage state
   - After: Actual result after interaction
   - Ground Truth: Expected result for successful interaction
   - Expected Visual Changes: List of specific visual changes to verify
   
3. Accessibility Validation:
   - Accessibility Tree: JSON representation of webpage's accessibility state
   - Expected Accessibility Changes: List of specific accessibility changes to verify

4. Success Criteria:
   - Specific conditions that must be met for success
   - Visual state matches ground truth
   - Accessibility state reflects expected changes

Your evaluation should:
1. Compare before/after/ground-truth screenshots
2. Verify all listed visual changes occurred
3. Validate accessibility tree changes
4. Check all success criteria are met

Provide your evaluation as:
1. 'SUCCESS' or 'NOT SUCCESS'
2. Detailed explanation of:
   - Visual changes observed/missing
   - Accessibility changes verified/missing
   - Success criteria met/failed"""

def encode_image(image_path: str) -> str:
    """Encode image as base64 string"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def evaluate_task(
    task: Dict[str, Any],
    result: Dict[str, Any],
    output_dir: Path,
    ground_truth_dir: Path,
    openai_client: OpenAI
) -> Dict[str, Any]:
    """Evaluate a single task using GPT-4V"""
    
    # Get screenshots
    before_img = encode_image(str(output_dir / f"before_{task['id']}.png"))
    after_img = encode_image(str(output_dir / f"after_{task['id']}.png"))
    ground_truth_img = encode_image(str(ground_truth_dir / task['ground_truth']['screenshot']))
    
    # Get accessibility tree if available
    tree_path = output_dir / f"accessibility_tree_{task['id']}.json"
    accessibility_tree = None
    if tree_path.exists():
        with open(tree_path) as f:
            accessibility_tree = json.load(f)
    
    # Format prompt with enhanced ground truth information
    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": f"""Task: {task['task']}
Website: {task['web_name']}
Interaction: {task['interaction']}
Element Type: {task['element_type']}

Ground Truth Information:
1. Description: {task['ground_truth']['description']}
2. Expected Visual Changes:
{chr(10).join(f'   - {change}' for change in task['ground_truth'].get('visual_changes', []))}
3. Expected Accessibility Changes:
{chr(10).join(f'   - {change}' for change in task['ground_truth'].get('accessibility_changes', []))}
4. Success Criteria:
{chr(10).join(f'   - {criterion}' for criterion in task['ground_truth'].get('success_criteria', []))}

Accessibility Tree:
{json.dumps(accessibility_tree, indent=2) if accessibility_tree else 'Not available'}

Please evaluate the interaction by comparing:
1. Before screenshot (initial state)
2. After screenshot (actual result)
3. Ground Truth screenshot (expected result)"""
                },
                {
                    "type": "text",
                    "text": "Before interaction:"
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{before_img}"}
                },
                {
                    "type": "text",
                    "text": "After interaction:"
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{after_img}"}
                },
                {
                    "type": "text",
                    "text": "Ground Truth:"
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{ground_truth_img}"}
                }
            ]
        }
    ]
    
    # Get GPT-4V evaluation
    response = openai_client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=messages,
        max_tokens=1000
    )
    
    evaluation = response.choices[0].message.content
    success = "SUCCESS" in evaluation.upper()
    
    return {
        "task_id": task["id"],
        "success": success,
        "evaluation": evaluation,
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
                results_dir,
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
