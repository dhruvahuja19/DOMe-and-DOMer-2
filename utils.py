import os
import json
import time
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional, Union, Tuple
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains

def execute_interaction(driver: webdriver.Chrome, interaction: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    """Execute a single interaction on the webpage and return success status and element HTML"""
    try:
        action = interaction.get("action", "").lower()
        selector = interaction.get("selector", "")
        value = interaction.get("value", "")
        
        if not selector:
            logging.warning("No selector provided for interaction")
            return False, None
            
        # Parse selector in format "type=value"
        selector_parts = selector.split('=', 1)
        if len(selector_parts) != 2:
            logging.error(f"Invalid selector format: {selector}")
            return False, None
            
        selector_type, selector_value = selector_parts
        
        # Map selector type to Selenium By
        selector_map = {
            'id': By.ID,
            'class': By.CLASS_NAME,
            'css': By.CSS_SELECTOR,
            'xpath': By.XPATH,
            'name': By.NAME,
            'tag': By.TAG_NAME
        }
        
        by_type = selector_map.get(selector_type.lower())
        if not by_type:
            logging.error(f"Unsupported selector type: {selector_type}")
            return False, None
        
        # Wait for element to be present and interactable
        wait = WebDriverWait(driver, 10)
        element = wait.until(EC.presence_of_element_located((by_type, selector_value)))
        wait.until(EC.element_to_be_clickable((by_type, selector_value)))
        
        # Get element's outer HTML
        element_html = element.get_attribute('outerHTML')
        
        # Execute the interaction
        if action == "click":
            element.click()
        elif action == "type":
            element.clear()
            element.send_keys(value)
        elif action == "hover":
            actions = ActionChains(driver)
            actions.move_to_element(element).perform()
        else:
            logging.error(f"Unsupported action: {action}")
            return False, element_html
            
        return True, element_html
        
    except Exception as e:
        logging.error(f"Error executing interaction: {str(e)}")
        return False, None

def save_screenshot(driver: webdriver.Chrome, filepath: str) -> bool:
    """Save screenshot of the current page state"""
    try:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        driver.save_screenshot(filepath)
        logging.info(f"Screenshot saved to {filepath}")
        return True
    except Exception as e:
        logging.error(f"Error saving screenshot: {str(e)}")
        return False

def get_accessibility_tree(driver: webdriver.Chrome) -> Dict[str, Any]:
    """Get accessibility tree of the current page"""
    try:
        # Inject axe-core script if not already present
        axe_script = """
            if (!window.axe) {
                var script = document.createElement('script');
                script.src = 'https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.7.0/axe.min.js';
                script.type = 'text/javascript';
                document.getElementsByTagName('head')[0].appendChild(script);
                
                // Wait for script to load
                return new Promise((resolve) => {
                    script.onload = () => {
                        axe.configure({
                            allowedOrigins: ['<same_origin>'],
                            rules: []
                        });
                        resolve(true);
                    };
                });
            }
            return Promise.resolve(true);
        """
        driver.execute_async_script(axe_script)
        time.sleep(1)  # Give a moment for axe to initialize
        
        # Now get the accessibility tree
        return driver.execute_script("""
            return {
                url: window.location.href,
                title: document.title,
                tree: axe.utils.getSelector(document.documentElement)
            };
        """)
    except Exception as e:
        logging.error(f"Error getting accessibility tree: {str(e)}")
        return {}

def save_accessibility_tree(tree: Dict[str, Any], filepath: str) -> bool:
    """Save accessibility tree to file"""
    try:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(tree, f, indent=2)
        logging.info(f"Accessibility tree saved to {filepath}")
        return True
    except Exception as e:
        logging.error(f"Error saving accessibility tree: {str(e)}")
        return False

def load_tasks_with_ground_truth(tasks_file: str) -> List[Dict[str, Any]]:
    """Load tasks from JSONL file. Ground truth paths are now included in the tasks file."""
    tasks = []
    with open(tasks_file) as f:
        for line in f:
            if line.strip():
                task = json.loads(line)
                tasks.append(task)
    return tasks

def load_tasks(tasks_file: str) -> List[Dict[str, Any]]:
    """Load tasks from JSONL file"""
    tasks = []
    with open(tasks_file) as f:
        for line in f:
            if line.strip():
                tasks.append(json.loads(line))
    return tasks

def save_results(results: List[Dict[str, Any]], output_file: str) -> None:
    """Save benchmark results to JSON file"""
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
