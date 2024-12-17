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
from selenium.webdriver.chrome.service import Service as ChromeService

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
                 model,
                 max_workers: int = 4,
                 output_dir: Path = None,
                 save_accessibility_tree: bool = True,
                 wait_time: float = 2.0):
        """
        Initialize TaskRunner
        
        Args:
            model: Language model to use for task parsing
            max_workers: Maximum number of concurrent Chrome instances
            output_dir: Directory for results and screenshots
            save_accessibility_tree: Whether to save accessibility trees
            wait_time: Wait time between actions in seconds
        """
        self.model = model
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
    
    def setup_driver(self):
        """Create and configure Chrome WebDriver instance"""
        chrome_options = Options()
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--force-device-scale-factor=1')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-gpu')   # Disable GPU hardware acceleration
        chrome_options.add_argument('--start-maximized')  # Start maximized
        chrome_options.add_argument('--disable-extensions')  # Disable extensions
        chrome_options.add_argument('--disable-popup-blocking')  # Disable popup blocking
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.140 Safari/537.36'
        )
        
        # Use Selenium Manager instead of ChromeDriverManager
        service = Service()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Navigate to about:blank first to ensure a clean start
        driver.get("about:blank")
        return driver
    
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
            url = task.get('web')  # Changed from 'url' to 'web' to match task data
            if not url:
                raise ValueError("No URL provided in task")
                
            logging.info(f"Task {task_id}: Navigating to {url}")
            driver.get(url)
            time.sleep(self.wait_time)
            
            # Save accessibility tree before interaction
            if self.save_accessibility_tree:
                before_tree = get_accessibility_tree(driver)
                before_tree_path = self.output_dir / f"{task_id}_before_tree.json"
                save_accessibility_tree(before_tree, str(before_tree_path))
                result['before_tree'] = str(before_tree_path)
            
            # Execute interaction
            web_interaction = self.model.parse_task(task)
            interaction = {
                'action': web_interaction.action,
                'target_element': {
                    'type': web_interaction.selector_type,
                    'value': web_interaction.selector_value
                },
                'input_text': web_interaction.input_text
            }
            
            logging.info(f"Task {task_id}: Executing interaction: {interaction}")
            success, element_html = execute_interaction(driver, interaction)
            if not success:
                raise ValueError("Interaction failed")
            result['success'] = True
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
        
        # Process tasks in smaller batches to avoid overwhelming the system
        batch_size = min(self.max_workers, 5)  # Process at most 5 tasks at a time
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            logging.info(f"Processing task batch {i//batch_size + 1}/{(len(tasks) + batch_size - 1)//batch_size}")
            
            with ThreadPoolExecutor(max_workers=batch_size) as executor:
                # Submit batch of tasks
                future_to_task = {
                    executor.submit(self.execute_task, task): task
                    for task in batch
                }
                
                # Process completed tasks
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    task_id = task.get('id', 'unknown')
                    try:
                        result = future.result(timeout=120)  # 2 minute timeout per task
                        results.append(result)
                        logging.info(f"Completed task {task_id}")
                    except Exception as e:
                        error_msg = f"Task {task_id} failed with error: {str(e)}"
                        logging.error(error_msg)
                        results.append({
                            'task_id': task_id,
                            'success': False,
                            'error': error_msg,
                            'task_description': task.get('task'),
                            'timestamp': time.time()
                        })
            
            # Add a small delay between batches
            if i + batch_size < len(tasks):
                time.sleep(1)
        
        return results

def run_parallel_benchmark(
    tasks_file: str,
    output_dir: str,
    model,
    max_workers: int = 4,
    save_accessibility_tree: bool = True,
    wait_time: float = 2.0
) -> List[Dict[str, Any]]:
    """
    Run benchmark tasks in parallel
    
    Args:
        tasks_file: Path to JSONL file containing tasks
        output_dir: Directory for results and screenshots
        model: Language model to use for task parsing
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
        model=model,
        max_workers=max_workers,
        output_dir=Path(output_dir),
        save_accessibility_tree=save_accessibility_tree,
        wait_time=wait_time
    )
    
    # Run tasks and return results
    return runner.run_tasks(tasks)
