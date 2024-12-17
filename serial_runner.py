import os
import time
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
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

class SerialTaskRunner:
    """Handles serial execution of benchmark tasks"""
    
    def __init__(self,
                 output_dir: Path = None,
                 save_accessibility_tree: bool = True,
                 wait_time: float = 2.0):
        """
        Initialize SerialTaskRunner
        
        Args:
            output_dir: Directory for results and screenshots
            save_accessibility_tree: Whether to save accessibility trees
            wait_time: Wait time between actions in seconds
        """
        self.output_dir = output_dir or Path("results")
        self.save_accessibility_tree = save_accessibility_tree
        self.wait_time = wait_time
        self.driver = None
        
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
    
    def execute_task(self, task: Dict[str, Any], task_num: int, total_tasks: int) -> Dict[str, Any]:
        """Execute a single benchmark task"""
        task_id = task.get('id', 'unknown')
        logging.info(f"\nProcessing task {task_num}/{total_tasks}: {task_id}")
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
            url = task.get('web')
            if not url:
                raise ValueError("No URL provided in task")
                
            logging.info(f"Task {task_id}: Navigating to {url}")
            self.driver.get(url)
            time.sleep(self.wait_time)
            
            # Save before screenshot
            before_screenshot = self.output_dir / f"{task_id}_before.png"
            save_screenshot(self.driver, str(before_screenshot))
            result['before_screenshot'] = str(before_screenshot)
            logging.info(f"Saved before screenshot: {before_screenshot}")
            
            # Save accessibility tree before interaction
            if self.save_accessibility_tree:
                before_tree = get_accessibility_tree(self.driver)
                before_tree_path = self.output_dir / f"{task_id}_before_tree.json"
                save_accessibility_tree(before_tree, str(before_tree_path))
                result['before_tree'] = str(before_tree_path)
                logging.info(f"Saved before accessibility tree: {before_tree_path}")
            
            # Execute interaction
            interaction = {
                "action": task.get("interaction", "click"),
                "selector": f"{task['target_element']['type']}={task['target_element']['value']}" if task.get('target_element') else "",
                "value": task.get("input_text", "")
            }
            
            logging.info(f"Executing interaction: {interaction}")
            success, element_html = execute_interaction(self.driver, interaction)
            result['success'] = success
            result['html_element'] = element_html
            time.sleep(self.wait_time)
            
            # Save after screenshot
            after_screenshot = self.output_dir / f"{task_id}_after.png"
            save_screenshot(self.driver, str(after_screenshot))
            result['after_screenshot'] = str(after_screenshot)
            logging.info(f"Saved after screenshot: {after_screenshot}")
            
            # Save accessibility tree after interaction
            if self.save_accessibility_tree:
                after_tree = get_accessibility_tree(self.driver)
                after_tree_path = self.output_dir / f"{task_id}_after_tree.json"
                save_accessibility_tree(after_tree, str(after_tree_path))
                result['after_tree'] = str(after_tree_path)
                logging.info(f"Saved after accessibility tree: {after_tree_path}")
            
            logging.info(f"Task completed successfully: {success}")
            
        except Exception as e:
            result['error'] = str(e)
            logging.error(f"Error in task {task_id}: {str(e)}", exc_info=True)
            
        return result
    
    def run_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run tasks serially using a single Chrome instance"""
        results = []
        
        try:
            self.driver = self.setup_driver()
            
            for i, task in enumerate(tasks, 1):
                result = self.execute_task(task, i, len(tasks))
                results.append(result)
                
        finally:
            if self.driver:
                self.driver.quit()
        
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
        
        return results

def run_serial_benchmark(
    tasks_file: str,
    output_dir: str,
    save_accessibility_tree: bool = True,
    wait_time: float = 2.0
) -> List[Dict[str, Any]]:
    """
    Run benchmark tasks serially
    
    Args:
        tasks_file: Path to JSONL file containing tasks
        output_dir: Directory for results and screenshots
        save_accessibility_tree: Whether to save accessibility trees
        wait_time: Wait time between actions in seconds
    
    Returns:
        List of task results
    """
    # Load tasks
    tasks = load_tasks_with_ground_truth(tasks_file)
    logging.info(f"Loaded {len(tasks)} tasks")
    
    # Initialize runner
    runner = SerialTaskRunner(
        output_dir=Path(output_dir),
        save_accessibility_tree=save_accessibility_tree,
        wait_time=wait_time
    )
    
    # Run tasks and return results
    return runner.run_tasks(tasks)
