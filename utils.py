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
            tree.role = node.role;
            tree.name = node.name;
            tree.type = node.type;
            if (node.value) tree.value = node.value;
            
            const rect = node.getBoundingClientRect();
            tree.location = {
                x: rect.x,
                y: rect.y,
                width: rect.width,
                height: rect.height
            };
            
            tree.children = [];
            for (let child of node.children) {
                tree.children.push(getAccessibilityTree(child));
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
    def load_and_process(path):
        img = Image.open(path).convert('RGB')
        img = img.resize((224, 224))  # Standard size
        return np.array(img)
    
    img1 = load_and_process(img1_path)
    img2 = load_and_process(img2_path)
    
    # Compute MSE
    mse = np.mean((img1 - img2) ** 2)
    # Convert to similarity score (1 = identical, 0 = completely different)
    similarity = 1 / (1 + mse)
    
    return similarity

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
