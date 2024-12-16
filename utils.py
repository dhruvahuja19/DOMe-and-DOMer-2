from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import json
import base64
import time
import logging
from typing import Dict, List, Any, Optional
from PIL import Image
import numpy as np

def get_accessibility_tree(driver: webdriver.Chrome, save_file: Optional[str] = None) -> Dict:
    """Get accessibility tree of the current page"""
    js_script = """
        function getAccessibilityTree(node, tree = {}) {
            tree.role = node.role || '';
            tree.name = node.tagName || '';
            tree.type = node.type || '';
            tree.value = node.value || '';
            tree.textContent = node.textContent ? node.textContent.trim() : '';
            
            const rect = node.getBoundingClientRect();
            tree.location = {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height
            };
            
            tree.children = [];
            const children = node.children;
            for (let i = 0; i < children.length; i++) {
                tree.children.push(getAccessibilityTree(children[i]));
            }
            return tree;
        }
        return getAccessibilityTree(document.documentElement);
    """
    tree = driver.execute_script(js_script)
    
    if save_file:
        with open(save_file, 'w') as f:
            json.dump(tree, f, indent=2)
    
    return tree

class WebInteractionUtils:
    def __init__(self, driver: webdriver.Chrome):
        self.driver = driver
        self.wait = WebDriverWait(driver, 10)
        
    def find_element(self, locator_type: str, locator: str) -> Optional[Any]:
        """Find element with wait and retry logic"""
        try:
            element = self.wait.until(
                EC.presence_of_element_located((getattr(By, locator_type.upper()), locator))
            )
            return element
        except Exception as e:
            logging.error(f"Failed to find element {locator_type}={locator}: {str(e)}")
            return None
    
    def execute_interaction(self, task: Dict[str, Any]) -> bool:
        """Execute web interaction based on task definition"""
        try:
            # Find element
            element = self.find_element(
                task["target_element"].get("type", "XPATH"),
                task["target_element"].get("value")
            )
            if not element:
                return False
                
            # Execute interaction
            interaction = task["interaction"].lower()
            if interaction == "click":
                element.click()
            elif interaction == "type":
                element.clear()
                element.send_keys(task.get("input_text", ""))
            elif interaction == "hover":
                ActionChains(self.driver).move_to_element(element).perform()
            else:
                logging.error(f"Unknown interaction type: {interaction}")
                return False
                
            return True
            
        except Exception as e:
            logging.error(f"Failed to execute interaction: {str(e)}")
            return False

def compute_image_similarity(img1_path: str, img2_path: str) -> float:
    """Compute similarity between two images"""
    img1 = np.array(Image.open(img1_path))
    img2 = np.array(Image.open(img2_path))
    
    # Ensure same size
    if img1.shape != img2.shape:
        img2 = np.array(Image.open(img2_path).resize((img1.shape[1], img1.shape[0])))
    
    # Compute MSE
    mse = np.mean((img1 - img2) ** 2)
    
    # Convert to similarity score (0 to 1)
    similarity = 1 / (1 + mse)
    
    # Convert numpy float to Python float
    return float(similarity)

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
    # Convert any numpy types to Python types
    serializable_results = []
    for result in results:
        serializable_result = {}
        for key, value in result.items():
            if isinstance(value, np.floating):
                serializable_result[key] = float(value)
            elif isinstance(value, np.integer):
                serializable_result[key] = int(value)
            else:
                serializable_result[key] = value
        serializable_results.append(serializable_result)
    
    with open(output_file, 'w') as f:
        json.dump(serializable_results, f, indent=2)
