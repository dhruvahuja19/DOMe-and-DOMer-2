import argparse
import os
import json
import time
import base64
from pathlib import Path
from typing import List, Dict, Any
import logging
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from openai import OpenAI
from dotenv import load_dotenv

SYSTEM_PROMPT = """You are an expert web automation evaluator. Your task is to:
1. Analyze the provided HTML source and accessibility tree
2. Identify and extract the complete HTML element that matches the target description
3. Score the visual interaction based on the provided before/after screenshots

For HTML element selection:
- Return the complete HTML element including its attributes and inner content
- Consider the element's context and relationship with surrounding elements
- Ensure the selected element uniquely matches the target description

For visual evaluation:
- Score how well the interaction matches the expected outcome
- Consider element visibility, positioning, and state changes
- Account for any dynamic content or loading states

Provide your response in the following JSON format:
{
    "selected_html": "<complete html element>",
    "visual_score": float,  # 0.0 to 1.0
    "confidence": float,    # 0.0 to 1.0
    "reasoning": "string"   # Brief explanation of your evaluation
}"""

def encode_image(image_path: str) -> str:
    """Encode image as base64 string"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode('utf-8')

def get_element_html_context(driver: webdriver.Chrome, element) -> str:
    """Get HTML context of an element"""
    return driver.execute_script("return arguments[0].outerHTML;", element)

def get_accessibility_tree(driver: webdriver.Chrome) -> Dict[str, Any]:
    """Get accessibility tree of the current page"""
    return driver.execute_script("return window.axe.getEntireContext();")

def compare_html_elements(html1: str, html2: str) -> Dict[str, Any]:
    """Compare two HTML elements"""
    # Implement HTML comparison logic here
    # For demonstration purposes, return a dummy score
    return {"total_score": 0.8, "attribute_score": 0.9, "content_score": 0.7, "structure_score": 0.8}

def get_llm_evaluation(context: Dict[str, Any]) -> Dict[str, Any]:
    """Get LLM evaluation"""
    # Implement LLM evaluation logic here
    # For demonstration purposes, return a dummy response
    return {
        "selected_html": "<div>Selected HTML element</div>",
        "visual_score": 0.9,
        "confidence": 0.8,
        "reasoning": "Brief explanation of the evaluation"
    }

def evaluate_task(
    task: Dict[str, Any],
    result: Dict[str, Any],
    ground_truth: Dict[str, Any],
    openai_client: OpenAI
) -> Dict[str, Any]:
    """Evaluate a task using both visual comparison and HTML matching"""
    try:
        # 1. Visual Evaluation (existing)
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": [
                {"type": "text", "text": "Compare these screenshots:"},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_image(result['before_screenshot'])}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_image(result['after_screenshot'])}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{encode_image(ground_truth['screenshot'])}"}},
            ]}
        ]
        
        visual_response = openai_client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=messages,
            max_tokens=1000,
            temperature=0
        )
        
        # 2. HTML Element Matching (new)
        html_score = compare_html_elements(
            result.get('html_element', ''),  # From model's response
            ground_truth.get('target_html', ''),  # From ground truth
        )
        
        # 3. Combine Scores
        visual_score = extract_score(visual_response.choices[0].message.content)
        
        final_score = (
            visual_score * 0.6 +  # Weight visual score more
            html_score['total_score'] * 0.4  # HTML matching score
        )
        
        return {
            "task_id": task["id"],
            "visual_evaluation": {
                "score": visual_score,
                "details": visual_response.choices[0].message.content
            },
            "html_evaluation": {
                "score": html_score['total_score'],
                "structure_score": html_score['structure_score'],
                "attributes_score": html_score['attributes_score'],
                "content_score": html_score['content_score']
            },
            "final_score": final_score,
            "success": final_score >= 0.9,
            "timestamp": int(time.time())
        }
        
    except Exception as e:
        logging.error(f"Error evaluating task: {str(e)}")
        return {
            "task_id": task["id"],
            "error": str(e),
            "final_score": 0.0,
            "success": False,
            "timestamp": int(time.time())
        }

def extract_score(evaluation_text: str) -> float:
    """Extract numerical score from evaluation text"""
    import re
    score_match = re.search(r'(\d+)(?=/100|%)', evaluation_text)
    return float(score_match.group(1)) / 100 if score_match else 0.0

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
            ground_truth = next((gt for gt in ground_truth_dir.iterdir() if gt.name == f"{task['id']}.json"), None)
            if ground_truth:
                with open(ground_truth) as f:
                    ground_truth_data = json.load(f)
                evaluation = evaluate_task(
                    task,
                    task_result,
                    ground_truth_data,
                    openai_client
                )
                evaluations.append(evaluation)
    
    # Save evaluations
    output = {
        "total_tasks": len(tasks),
        "successful_tasks": sum(1 for e in evaluations if e["final_score"] > 0.5),
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
