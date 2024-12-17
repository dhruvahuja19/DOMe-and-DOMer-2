import os
import time
import logging
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

from utils import (
    execute_interaction,
    save_screenshot,
    get_accessibility_tree,
    save_accessibility_tree,
    load_tasks_with_ground_truth
)

class TaskRunner:
    """Handles parallel execution of benchmark tasks"""
    
    def __init__(self, 
                 max_workers: int = 4,
                 output_dir: Path = None,
                 save_accessibility_tree: bool = True,
                 wait_time: float = 2.0):
        """
        Initialize TaskRunner
        
        Args:
            max_workers: Maximum number of concurrent Chrome instances
            output_dir: Directory for results and screenshots
            save_accessibility_tree: Whether to save accessibility trees
            wait_time: Wait time between actions in seconds
        """
        self.max_workers = max_workers
        self.output_dir = output_dir or Path("results")
        self.save_accessibility_tree = save_accessibility_tree
        self.wait_time = wait_time
        
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(self.output_dir / "benchmark.log"),
                logging.StreamHandler()
            ]
        )
        
        # Thread-safe queue for results
        self.results_queue = queue.Queue()
    
    def setup_driver(self) -> webdriver.Chrome:
        """Create and configure Chrome WebDriver instance"""
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--force-device-scale-factor=1')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36'
        )
        
        service = Service(ChromeDriverManager().install())
        return webdriver.Chrome(service=service, options=chrome_options)
    
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single benchmark task"""
        task_id = task.get('id', 'unknown')
        result = {
            'task_id': task_id,
            'success': False,
            'error': None,
            'task_description': task.get('task'),
            'timestamp': time.time()
        }
        
        driver = None
        try:
            driver = self.setup_driver()
            
            # Navigate to page
            url = task.get('web')
            if not url:
                raise ValueError("No URL provided in task")
                
            logging.info(f"Task {task_id}: Navigating to {url}")
            driver.get(url)
            time.sleep(self.wait_time)
            
            # Save before screenshot
            before_screenshot = self.output_dir / f"{task_id}_before.png"
            save_screenshot(driver, str(before_screenshot))
            result['before_screenshot'] = str(before_screenshot)
            
            # Save accessibility tree before interaction
            if self.save_accessibility_tree:
                before_tree = get_accessibility_tree(driver)
                before_tree_path = self.output_dir / f"{task_id}_before_tree.json"
                save_accessibility_tree(before_tree, str(before_tree_path))
                result['before_tree'] = str(before_tree_path)
            
            # Execute interaction
            interaction = {
                "action": task.get("interaction", "click"),
                "selector": f"{task['target_element']['type']}={task['target_element']['value']}" if task.get('target_element') else "",
                "value": task.get("input_text", "")
            }
            
            success, element_html = execute_interaction(driver, interaction)
            result['success'] = success
            result['html_element'] = element_html
            time.sleep(self.wait_time)
            
            # Save after screenshot
            after_screenshot = self.output_dir / f"{task_id}_after.png"
            save_screenshot(driver, str(after_screenshot))
            result['after_screenshot'] = str(after_screenshot)
            
            # Save accessibility tree after interaction
            if self.save_accessibility_tree:
                after_tree = get_accessibility_tree(driver)
                after_tree_path = self.output_dir / f"{task_id}_after_tree.json"
                save_accessibility_tree(after_tree, str(after_tree_path))
                result['after_tree'] = str(after_tree_path)
            
        except Exception as e:
            result['error'] = str(e)
            logging.error(f"Error in task {task_id}: {str(e)}", exc_info=True)
            
        finally:
            if driver:
                driver.quit()
            
        return result
    
    def run_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run tasks in parallel using ThreadPoolExecutor"""
        results = []
        
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            future_to_task = {
                executor.submit(self.execute_task, task): task
                for task in tasks
            }
            
            # Process completed tasks
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    result = future.result()
                    results.append(result)
                    logging.info(f"Completed task {task.get('id', 'unknown')}")
                except Exception as e:
                    logging.error(f"Task failed: {str(e)}", exc_info=True)
        
        return results

def run_parallel_benchmark(
    tasks_file: str,
    output_dir: str,
    max_workers: int = 4,
    save_accessibility_tree: bool = True,
    wait_time: float = 2.0
) -> List[Dict[str, Any]]:
    """
    Run benchmark tasks in parallel
    
    Args:
        tasks_file: Path to JSONL file containing tasks
        output_dir: Directory for results and screenshots
        max_workers: Maximum number of concurrent Chrome instances
        save_accessibility_tree: Whether to save accessibility trees
        wait_time: Wait time between actions in seconds
    
    Returns:
        List of task results
    """
    # Load tasks
    tasks = load_tasks_with_ground_truth(tasks_file)
    logging.info(f"Loaded {len(tasks)} tasks")
    
    # Initialize runner
    runner = TaskRunner(
        max_workers=max_workers,
        output_dir=Path(output_dir),
        save_accessibility_tree=save_accessibility_tree,
        wait_time=wait_time
    )
    
    # Run tasks and return results
    return runner.run_tasks(tasks)
