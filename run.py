import argparse
import json
import os
import time
import logging
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from utils import execute_interaction, save_screenshot, get_accessibility_tree, save_accessibility_tree, load_tasks_with_ground_truth, save_results
from evaluation.auto_eval import run_evaluation
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables at the start
load_dotenv()

def setup_logging(output_dir: Path) -> None:
    """Setup logging configuration"""
    log_file = output_dir / "benchmark.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def construct_interaction(task):
    """Construct interaction dict from task"""
    return {
        "action": task.get("interaction", "click"),  # Default to click
        "selector": f"{task['target_element']['type']}={task['target_element']['value']}" if task.get('target_element') else "",
        "value": task.get("input_text", "")  # For type actions
    }

def main():
    parser = argparse.ArgumentParser(description='Run web automation tasks')
    parser.add_argument('--tasks', required=True, help='Path to tasks JSONL file')
    parser.add_argument('--output', required=True, help='Output directory for results')
    parser.add_argument('--save-accessibility-tree', action='store_true', help='Save accessibility tree')
    parser.add_argument('--evaluate', action='store_true', help='Run evaluation after benchmark')
    parser.add_argument('--wait-time', type=float, default=2.0, help='Wait time in seconds after page load and interactions')
    args = parser.parse_args()

    # Create output directory and setup logging
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(output_dir)
    
    # Setup Chrome
    chrome_options = Options()
    # chrome_options.add_argument('--headless')  # Comment out headless for debugging
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--force-device-scale-factor=1')
    chrome_options.add_argument('--window-size=1920,1080')  # Add window size
    chrome_options.add_argument(
        'user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
    )
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    try:
        # Load tasks
        tasks = load_tasks_with_ground_truth(args.tasks)
        logging.info(f"Loaded {len(tasks)} tasks")
        results = []
        
        for i, task in enumerate(tasks, 1):
            task_id = task.get('id', 'unknown')
            logging.info(f"\nProcessing task {i}/{len(tasks)}: {task_id}")
            logging.info(f"Task description: {task.get('task', 'No description')}")
            
            result = {
                'task_id': task_id,
                'success': False,
                'error': None,
                'task_description': task.get('task'),
                'timestamp': time.time()
            }
            
            try:
                # Navigate to page
                url = task.get('web')  # Use 'web' field from task
                if not url:
                    raise ValueError("No URL provided in task")
                    
                logging.info(f"Navigating to {url}")
                driver.get(url)
                time.sleep(args.wait_time)  # Wait for page load
                
                # Save before screenshot
                before_screenshot = str(output_dir / f"{task_id}_before.png")
                save_screenshot(driver, before_screenshot)
                result['before_screenshot'] = before_screenshot
                logging.info(f"Saved before screenshot: {before_screenshot}")
                
                # Save accessibility tree before interaction
                if args.save_accessibility_tree:
                    before_tree = get_accessibility_tree(driver)
                    before_tree_path = str(output_dir / f"{task_id}_before_tree.json")
                    save_accessibility_tree(before_tree, before_tree_path)
                    result['before_tree'] = before_tree_path
                    logging.info(f"Saved before accessibility tree: {before_tree_path}")
                
                # Construct and execute interaction
                interaction = construct_interaction(task)
                logging.info(f"Executing interaction: {interaction}")
                success = execute_interaction(driver, interaction)
                time.sleep(args.wait_time)  # Wait for interaction effects
                
                # Save after screenshot
                after_screenshot = str(output_dir / f"{task_id}_after.png")
                save_screenshot(driver, after_screenshot)
                result['after_screenshot'] = after_screenshot
                logging.info(f"Saved after screenshot: {after_screenshot}")
                
                # Save accessibility tree after interaction
                if args.save_accessibility_tree:
                    after_tree = get_accessibility_tree(driver)
                    after_tree_path = str(output_dir / f"{task_id}_after_tree.json")
                    save_accessibility_tree(after_tree, after_tree_path)
                    result['after_tree'] = after_tree_path
                    logging.info(f"Saved after accessibility tree: {after_tree_path}")
                
                result['success'] = success
                logging.info(f"Task completed successfully: {success}")
                
            except Exception as e:
                result['error'] = str(e)
                logging.error(f"Error processing task {task_id}: {str(e)}", exc_info=True)
                
            results.append(result)
        
        # Save results to JSON file
        results_file = output_dir / "results.json"
        save_results(results, str(results_file))
        logging.info(f"Results saved to {results_file}")
        
        # Run evaluation if requested
        if args.evaluate:
            openai_key = os.getenv("OPENAI_API_KEY")
            if not openai_key:
                logging.error("No OpenAI API key found in environment")
                return
            
            eval_output = output_dir / "evaluation.json"
            run_evaluation(
                tasks_file=Path(args.tasks),
                results_dir=results_file,
                output_file=eval_output,
                openai_key=openai_key
            )
            logging.info(f"Evaluation complete. Results saved to {eval_output}")
        
        # Print summary
        successful = sum(1 for r in results if r['success'])
        errors = sum(1 for r in results if r.get('error'))
        logging.info(
            f"\nBenchmark Summary:\n"
            f"Total Tasks: {len(tasks)}\n"
            f"Successful Interactions: {successful}\n"
            f"Failed Tasks: {errors}\n"
            f"Success Rate: {(successful/len(tasks))*100:.1f}%"
        )
        
    finally:
        driver.quit()

if __name__ == '__main__':
    main()
