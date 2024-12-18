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
                 model,
                 output_dir: Path = None,
                 save_accessibility_tree: bool = True,
                 wait_time: float = 2.0):
        """
        Initialize SerialTaskRunner
        
        Args:
            model: Language model to use for task parsing
            output_dir: Directory for results and screenshots
            save_accessibility_tree: Whether to save accessibility trees
            wait_time: Wait time between actions in seconds
        """
        self.model = model
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
    
    def execute_task(self, task: Dict[str, Any], task_num: int, total_tasks: int) -> Dict[str, Any]:
        """Execute a single benchmark task"""
        task_id = task.get('id', 'unknown')
        logging.info(f"\n{'='*50}")
        logging.info(f"Starting task {task_num}/{total_tasks}: {task_id}")
        logging.info(f"Task details: {task}")
        
        result = {
            'task_id': task_id,
            'success': False,
            'error': None,
            'after_screenshot': None,
            'llm_evaluations': {
                'image_similarity': None,
                'html_fuzzy_match': None
            }
        }
        
        try:
            driver = self.setup_driver()
            logging.info(f"Browser initialized for task {task_id}")
            
            # Navigate to URL
            url = task.get('web')
            if not url:
                raise ValueError("No URL provided in task")
                
            logging.info(f"Navigating to URL: {url}")
            driver.get(url)
            time.sleep(self.wait_time)  # Wait for page load
            
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
            result['html_element'] = element_html
            time.sleep(self.wait_time)  # Wait for interaction to complete
            
            # Take after screenshot
            after_screenshot = save_screenshot(driver, self.output_dir / f"{task_id}_after.png")
            result['after_screenshot'] = after_screenshot
            
            if self.save_accessibility_tree:
                after_tree = get_accessibility_tree(driver)
                save_accessibility_tree(after_tree, self.output_dir / f"{task_id}_after_tree.json")
                logging.info("Saved after screenshots and accessibility tree")
            
            # Only mark as success if we have all required data
            if after_screenshot and element_html:
                # We have the data but need to wait for evaluations to determine final success
                # Set to False for now, will be updated after evaluations
                result['success'] = False
                logging.info(f"Task {task_id} completed data collection")
            else:
                result['success'] = False
                result['error'] = "Missing required data (screenshots or HTML element)"
        
        except Exception as e:
            error_msg = f"Error in task {task_id}: {str(e)}"
            logging.error(error_msg, exc_info=True)
            result['error'] = error_msg
            result['success'] = False
        
        finally:
            try:
                if 'driver' in locals():
                    driver.quit()
                    logging.info(f"Browser closed for task {task_id}")
            except Exception as e:
                logging.error(f"Error closing browser: {str(e)}")
        
        logging.info(f"Task {task_id} result: {result}")
        logging.info(f"{'='*50}\n")
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
    model,
    save_accessibility_tree: bool = True,
    wait_time: float = 2.0
) -> List[Dict[str, Any]]:
    """
    Run benchmark tasks serially
    
    Args:
        tasks_file: Path to JSONL file containing tasks
        output_dir: Directory for results and screenshots
        model: Language model to use for task parsing
        save_accessibility_tree: Whether to save accessibility trees
        wait_time: Wait time between actions in seconds
    """
    # Load tasks
    tasks = load_tasks_with_ground_truth(tasks_file)
    logging.info(f"Loaded {len(tasks)} tasks")
    
    # Initialize runner
    runner = SerialTaskRunner(
        model=model,
        output_dir=Path(output_dir),
        save_accessibility_tree=save_accessibility_tree,
        wait_time=wait_time
    )
    
    # Run tasks and return results
    return runner.run_tasks(tasks)
