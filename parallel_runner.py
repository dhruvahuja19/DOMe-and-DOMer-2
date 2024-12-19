import os
import time
import queue
import logging
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
    load_tasks_with_ground_truth
)

class TaskRunner:
    """Handles parallel execution of benchmark tasks"""
    
    def __init__(self, 
                 model,
                 max_workers: int = 4,
                 output_dir: Path = None,
                 wait_time: float = 2.0,
                 page_load_timeout: int = 300,  # 5 minutes
                 element_timeout: int = 300):   # 5 minutes
        """
        Initialize TaskRunner
        
        Args:
            model: Language model to use for task parsing
            max_workers: Maximum number of concurrent Chrome instances
            output_dir: Directory for results and screenshots
            wait_time: Wait time between actions in seconds
            page_load_timeout: Timeout for page loads in seconds
            element_timeout: Timeout for element interactions in seconds
        """
        self.model = model
        self.max_workers = max_workers
        self.output_dir = Path(output_dir) if output_dir else Path.cwd() / "results"
        self.wait_time = wait_time
        self.page_load_timeout = page_load_timeout
        self.element_timeout = element_timeout
        
        # Setup logging
        self.output_dir.mkdir(parents=True, exist_ok=True)
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
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--start-maximized')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--disable-popup-blocking')
        # Add stability options
        chrome_options.add_argument('--disable-background-networking')
        chrome_options.add_argument('--disable-background-timer-throttling')
        chrome_options.add_argument('--disable-backgrounding-occluded-windows')
        chrome_options.add_argument('--disable-breakpad')
        chrome_options.add_argument('--disable-client-side-phishing-detection')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--disable-hang-monitor')
        chrome_options.add_argument('--disable-prompt-on-repost')
        chrome_options.add_argument('--disable-sync')
        chrome_options.add_argument('--disable-web-resources')
        chrome_options.add_argument('--metrics-recording-only')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--safebrowsing-disable-auto-update')
        chrome_options.add_argument('--password-store=basic')
        chrome_options.add_argument('--use-mock-keychain')
        chrome_options.add_argument('--disable-renderer-backgrounding')
        chrome_options.add_argument('--disable-ipc-flooding-protection')
        
        chrome_options.add_argument(
            'user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.6778.140 Safari/537.36'
        )
        
        # Use Selenium Manager instead of ChromeDriverManager
        service = Service()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set timeouts
        driver.set_page_load_timeout(300)  # 5 minutes for page load
        driver.set_script_timeout(300)     # 5 minutes for scripts
        driver.implicitly_wait(300)        # 5 minutes implicit wait
        
        # Navigate to about:blank first to ensure a clean start
        driver.get("about:blank")
        return driver
    
    def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a single benchmark task"""
        task_id = task.get('id', 'unknown')
        logging.info(f"Starting task {task_id}")
        
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
            logging.info(f"Browser initialized for task {task_id}")
            
            # Navigate to page
            url = task.get('web')  # Changed from 'url' to 'web' to match task data
            if not url:
                raise ValueError("No URL provided in task")
                
            logging.info(f"Navigating to URL: {url}")
            driver.get(url)
            time.sleep(self.wait_time)
            
            # Take before screenshot
            before_screenshot_path = self.output_dir / f"{task_id}_before.png"
            driver.save_screenshot(str(before_screenshot_path))
            result['before_screenshot'] = str(before_screenshot_path)
            
            # Get page HTML and accessibility tree before interaction
            page_html = driver.page_source
            
            # Parse task using model
            interaction = self.model.parse_task(task, page_html)
            if not interaction:
                logging.info(f"Task {task_id}: Model unable to parse task")
                return result
                
            logging.info(f"Task {task_id}: Executing interaction: {interaction}")
            
            # Create target element dict from interaction
            target_element = {
                'type': interaction.selector_type,
                'value': interaction.selector_value
            }
            
            interaction_result = execute_interaction(
                driver, 
                interaction.action, 
                target_element, 
                interaction.input_text, 
                timeout=self.element_timeout
            )
            if interaction_result['success']:
                result['success'] = True
                result['html_element'] = interaction_result['html_element']
            else:
                result['error'] = interaction_result['error']
                return result
            
            # Take after screenshot
            time.sleep(self.wait_time)  # Wait for any animations/changes to complete
            after_screenshot_path = self.output_dir / f"{task_id}_after.png"
            driver.save_screenshot(str(after_screenshot_path))
            result['after_screenshot'] = str(after_screenshot_path)
            
        except Exception as e:
            error_msg = f"Error executing task {task_id}: {str(e)}"
            logging.error(error_msg, exc_info=True)
            result['error'] = str(e)
            
        finally:
            if driver:
                try:
                    driver.quit()
                    logging.info(f"Browser closed for task {task_id}")
                except Exception as e:
                    logging.error(f"Error closing browser for task {task_id}: {str(e)}")
                    
        return result
    
    def run_tasks(self, tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run tasks in parallel using ThreadPoolExecutor"""
        
        results = []
        
        # Process tasks in smaller batches to avoid overwhelming the system
        batch_size = self.max_workers # Process at most 5 tasks at a time
        total_tasks = len(tasks)
        logging.info(f"Starting parallel execution of {total_tasks} tasks with {self.max_workers} workers")
        
        for i in range(0, total_tasks, batch_size):
            batch = tasks[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total_tasks + batch_size - 1) // batch_size
            logging.info(f"Processing batch {batch_num}/{total_batches} ({len(batch)} tasks)")
            
            with ThreadPoolExecutor(max_workers=batch_size) as executor:
                future_to_task = {
                    executor.submit(self.execute_task, task): task
                    for task in batch
                }
                
                for future in as_completed(future_to_task):
                    task = future_to_task[future]
                    try:
                        result = future.result()
                        results.append(result)
                        logging.info(f"Task {task.get('id', 'unknown')} completed with success={result['success']}")
                    except Exception as e:
                        error_msg = f"Error processing task {task.get('id', 'unknown')}: {str(e)}"
                        logging.error(error_msg, exc_info=True)
                        results.append({
                            "task_id": task.get("id", "unknown"),
                            "success": False,
                            "error": str(e)
                        })
        
        logging.info(f"Completed all {total_tasks} tasks")
        return results

def execute_interaction(driver, interaction_type, target_element, input_text=None, timeout=15):
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
    wait_time: float = 2.0,
    page_load_timeout: int = 300,  # 5 minutes
    element_timeout: int = 300     # 5 minutes
) -> List[Dict[str, Any]]:
    """
    Run benchmark tasks in parallel
    
    Args:
        tasks_file: Path to JSONL file containing tasks
        output_dir: Directory for results and screenshots
        model: Language model to use for task parsing
        max_workers: Maximum number of concurrent Chrome instances
        wait_time: Wait time between actions in seconds
        page_load_timeout: Timeout for page loads in seconds
        element_timeout: Timeout for element interactions in seconds
    
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
        wait_time=wait_time,
        page_load_timeout=page_load_timeout,
        element_timeout=element_timeout
    )
    
    # Run tasks and return results
    return runner.run_tasks(tasks)
