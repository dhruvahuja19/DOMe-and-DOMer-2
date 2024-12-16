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
from .image_match import compare_images
from .fuzzy_match import fuzzy_match_html

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
    """Compare two HTML elements for structural similarity"""
    from bs4 import BeautifulSoup
    import difflib
    
    if not html1 or not html2:
        return {
            "total_score": 0.0,
            "structure_score": 0.0,
            "attributes_score": 0.0,
            "content_score": 0.0
        }
    
    # Parse HTML
    soup1 = BeautifulSoup(html1, 'html.parser')
    soup2 = BeautifulSoup(html2, 'html.parser')
    
    # Compare structure (tag names and hierarchy)
    def get_structure(soup):
        return [tag.name for tag in soup.find_all()]
    structure1 = get_structure(soup1)
    structure2 = get_structure(soup2)
    structure_score = difflib.SequenceMatcher(None, structure1, structure2).ratio()
    
    # Compare attributes
    def get_attributes(soup):
        attrs = []
        for tag in soup.find_all():
            attrs.extend(sorted(tag.attrs.items()))
        return attrs
    attrs1 = get_attributes(soup1)
    attrs2 = get_attributes(soup2)
    attributes_score = difflib.SequenceMatcher(None, attrs1, attrs2).ratio()
    
    # Compare content
    def get_content(soup):
        return [text.strip() for text in soup.stripped_strings]
    content1 = get_content(soup1)
    content2 = get_content(soup2)
    content_score = difflib.SequenceMatcher(None, content1, content2).ratio()
    
    # Calculate total score (weighted average)
    total_score = (
        0.4 * structure_score +    # Structure is most important
        0.3 * attributes_score +   # Attributes are second
        0.3 * content_score        # Content is third
    )
    
    return {
        "total_score": total_score,
        "structure_score": structure_score,
        "attributes_score": attributes_score,
        "content_score": content_score
    }

def evaluate_task(
    task: Dict[str, Any],
    result: Dict[str, Any],
    ground_truth: Dict[str, Any],
    openai_client: OpenAI
) -> Dict[str, Any]:
    """Evaluate a task using GPT-4V for visual comparison and GPT-4 for HTML comparison"""
    try:
        # 1. Visual Evaluation using GPT-4V (50% of total score)
        visual_correct, visual_reason = compare_images(
            prompt=task['task'],
            ground_truth_path=ground_truth['screenshot'],
            agent_image_path=result['after_screenshot'],
            note=ground_truth.get('description', '')
        )
        visual_score = 1.0 if visual_correct else 0.0
        
        # 2. HTML Evaluation using GPT-4 (50% of total score)
        html_correct, html_reason = fuzzy_match_html(
            task_description=task['task'],
            actual_html=result.get('html_element', ''),
            expected_html=ground_truth.get('target_html', ''),
            note=ground_truth.get('description', '')
        )
        html_score = 1.0 if html_correct else 0.0
        
        # Calculate final score (50-50 split between visual and HTML)
        final_score = (
            0.5 * visual_score +    # Visual evaluation (50%)
            0.5 * html_score        # HTML evaluation (50%)
        )
        
        success = final_score >= 0.9  # Success threshold
        
        return {
            "task_id": task["id"],
            "success": success,
            "visual_evaluation": {
                "score": visual_score,
                "details": visual_reason
            },
            "html_evaluation": {
                "score": html_score,
                "details": html_reason
            },
            "final_score": final_score,
            "timestamp": time.time()
        }
        
    except Exception as e:
        logging.error(f"Error evaluating task {task['id']}: {str(e)}")
        return {
            "task_id": task["id"],
            "success": False,
            "error": str(e),
            "timestamp": time.time()
        }

def run_evaluation(
    tasks_file: Path,
    results_dir: Path,
    ground_truth_dir: Path,
    output_file: Path,
    openai_key: str
):
    """Run evaluation on benchmark results"""
    # Load tasks
    with open(tasks_file) as f:
        tasks = [json.loads(line) for line in f if line.strip()]
    
    # Load results
    with open(results_dir / "results.json") as f:
        results = json.load(f)
    
    # Initialize OpenAI client
    client = OpenAI(api_key=openai_key)
    
    # Run evaluation for each task
    evaluations = []
    for task in tasks:
        # Get result for this task
        task_result = next(
            (r for r in results if r["task_id"] == task["id"]),
            None
        )
        if not task_result:
            logging.warning(f"No result found for task {task['id']}")
            continue
        
        # Get ground truth
        ground_truth = {
            "screenshot": str(ground_truth_dir / task["ground_truth"]["screenshot"]),
            "description": task["ground_truth"].get("description", ""),
            "target_html": task.get("target_html", "")
        }
        
        # Evaluate task
        evaluation = evaluate_task(task, task_result, ground_truth, client)
        evaluations.append(evaluation)
    
    # Save evaluations
    with open(output_file, 'w') as f:
        json.dump({
            "total_tasks": len(tasks),
            "successful_tasks": sum(1 for e in evaluations if e.get("success", False)),
            "evaluations": evaluations
        }, f, indent=2)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--openai-key", type=str, required=True)
    args = parser.parse_args()
    
    run_evaluation(
        args.tasks,
        args.results,
        args.ground_truth,
        args.output,
        args.openai_key
    )

if __name__ == "__main__":
    main()
