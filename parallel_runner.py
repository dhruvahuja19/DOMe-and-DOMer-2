import os
import time
import queue
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Any, Optional
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    TimeoutException, 
    ElementNotInteractableException,
    StaleElementReferenceException,
    ElementClickInterceptedException
)
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
            
            interaction_result = execute_interaction(driver, interaction['action'], interaction['target_element'], interaction['input_text'])
            if interaction_result['success']:
                result['success'] = True
                result['html_element'] = interaction_result['html_element']
            else:
                result['error'] = interaction_result['error']
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
            
        finally:
            if driver:
                driver.quit()
            
        return result
    
    def run_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run tasks in parallel using ThreadPoolExecutor"""
        results = []
        
        # Process tasks in smaller batches to avoid overwhelming the system
        batch_size = min(self.max_workers, 20)  # Process at most 5 tasks at a time
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i + batch_size]
            
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
                    except Exception as e:
                        error_msg = f"Task {task_id} failed with error: {str(e)}"
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

def execute_interaction(driver, interaction_type, target_element, input_text=None, timeout=10):
    """Execute a single interaction with better error handling and logging"""
    selector_type = target_element.get("type")
    selector_value = target_element.get("value")
    result = {
        "success": False,
        "html_element": None,
        "error": None
    }
    
    selector_map = {
        "id": By.ID,
        "class": By.CLASS_NAME,
        "text": By.LINK_TEXT,
        "css": By.CSS_SELECTOR,
        "xpath": By.XPATH
    }
    
    try:
        by_type = selector_map.get(selector_type)
        if not by_type:
            raise ValueError(f"Invalid selector type: {selector_type}")
            
        wait = WebDriverWait(driver, timeout)
        
        # First wait for presence
        element = wait.until(
            EC.presence_of_element_located((by_type, selector_value))
        )
        
        # Store HTML as soon as we find the element
        result["html_element"] = element.get_attribute('outerHTML')
        
        # Different wait conditions based on interaction type
        if interaction_type in ["type", "type_submit"]:
            element = wait.until(
                EC.and_((
                    EC.visibility_of_element_located((by_type, selector_value)),
                    EC.element_to_be_clickable((by_type, selector_value))
                ))
            )
        else:
            element = wait.until(
                EC.element_to_be_clickable((by_type, selector_value))
            )
            driver.execute_script("arguments[0].scrollIntoView(true);", element)
            time.sleep(0.5)
        
        # Execute interaction based on type
        if interaction_type == "click":
            try:
                element.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", element)
        elif interaction_type == "type":
            element.clear()
            element.send_keys(input_text)
        elif interaction_type == "type_submit":
            element.clear()
            element.send_keys(input_text)
            element.send_keys(Keys.RETURN)
        else:
            raise ValueError(f"Invalid interaction type: {interaction_type}")
            
        result["success"] = True
        return result
        
    except TimeoutException:
        result["error"] = f"Element not found: {selector_type}={selector_value}"
        return result
    except ElementNotInteractableException:
        result["error"] = f"Element not interactable: {selector_type}={selector_value}"
        return result
    except StaleElementReferenceException:
        result["error"] = f"Element became stale: {selector_type}={selector_value}"
        return result
    except ElementClickInterceptedException:
        result["error"] = f"Click blocked: {selector_type}={selector_value}"
        return result
    except Exception as e:
        result["error"] = str(e)
        return result

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
