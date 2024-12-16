from typing import Dict, Any, List, Optional
import os
from pathlib import Path
import base64
import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from selenium.webdriver.common.action_chains import ActionChains

from .accessibility_utils import get_accessibility_tree, format_accessibility_tree

class WebExecutor:
    def __init__(self, headless: bool = True):
        self.driver = None
        self.headless = headless
        self.timeout = 10
        self.screenshot_counter = 0
        self.element_map = {}  # Maps numerical labels to element selectors
        
    def setup(self):
        """Initialize Chrome driver with CDP for accessibility tree access."""
        if self.driver is None:
            options = webdriver.ChromeOptions()
            if self.headless:
                options.add_argument('--headless')
            
            # Enable CDP for accessibility tree
            options.add_argument('--remote-debugging-port=9222')
            
            self.driver = webdriver.Chrome(options=options)
            self.driver.set_window_size(1024, 768)
            
    def _add_element_labels(self):
        """Add numerical labels to interactive elements using JavaScript."""
        js_code = """
        // Remove existing labels
        document.querySelectorAll('.element-label').forEach(el => el.remove());
        
        // Find all interactive elements
        const elements = document.querySelectorAll('button, input, a, [role="button"], [role="link"], [role="textbox"]');
        let counter = 1;
        
        elements.forEach(el => {
            // Create label
            const label = document.createElement('div');
            label.className = 'element-label';
            label.textContent = counter;
            label.style.cssText = `
                position: absolute;
                background: black;
                color: white;
                padding: 2px 5px;
                border-radius: 3px;
                font-size: 12px;
                z-index: 10000;
            `;
            
            // Position label at top-left of element
            const rect = el.getBoundingClientRect();
            label.style.left = rect.left + 'px';
            label.style.top = rect.top + 'px';
            
            // Store mapping
            el.setAttribute('data-label', counter);
            
            document.body.appendChild(label);
            counter++;
        });
        
        // Return element mapping
        const mapping = {};
        elements.forEach(el => {
            const label = el.getAttribute('data-label');
            mapping[label] = {
                tag: el.tagName.toLowerCase(),
                type: el.getAttribute('type'),
                role: el.getAttribute('role'),
                id: el.id,
                class: el.className,
                text: el.textContent.trim()
            };
        });
        return mapping;
        """
        
        # Execute JavaScript and get element mapping
        self.element_map = self.driver.execute_script(js_code)
        
    def get_page_state(self) -> Dict[str, Any]:
        """Get current page state including accessibility tree, screenshot, and element mapping."""
        # Add numerical labels to elements
        self._add_element_labels()
        
        # Get accessibility tree
        accessibility_tree = get_accessibility_tree(self.driver)
        tree_text = format_accessibility_tree(accessibility_tree)
        
        # Take screenshot
        screenshot_path = f"screenshot_{self.screenshot_counter}.png"
        self.driver.save_screenshot(screenshot_path)
        self.screenshot_counter += 1
        
        return {
            "accessibility_tree": tree_text,
            "screenshot": screenshot_path,
            "url": self.driver.current_url,
            "title": self.driver.title,
            "element_map": self.element_map
        }
        
    def _find_element_by_label(self, label: str):
        """Find element using its numerical label."""
        return self.driver.find_element(By.CSS_SELECTOR, f'[data-label="{label}"]')
        
    def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a web action and return the result."""
        try:
            # Get before state
            before_state = self.get_page_state()
            
            # Execute action
            if action == "navigate":
                self.driver.get(params["url"])
                
            elif action == "click":
                element = self._find_element_by_label(params["label"])
                element.click()
                
            elif action == "type":
                element = self._find_element_by_label(params["label"])
                element.clear()
                element.send_keys(params["text"])
                element.send_keys(Keys.RETURN)
                
            elif action == "scroll":
                if params.get("element_label"):
                    element = self._find_element_by_label(params["element_label"])
                    ActionChains(self.driver).move_to_element(element).perform()
                
                scroll_amount = 300 if params["direction"] == "down" else -300
                self.driver.execute_script(f"window.scrollBy(0, {scroll_amount})")
                
            elif action == "wait":
                import time
                time.sleep(5)  # Fixed 5-second wait
                
            elif action == "back":
                self.driver.back()
                
            # Get after state
            after_state = self.get_page_state()
            
            return {
                "success": True,
                "before_state": before_state,
                "after_state": after_state,
                "action": action,
                "params": params
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "action": action,
                "params": params
            }
            
    def cleanup(self):
        """Clean up resources."""
        if self.driver:
            self.driver.quit()
            self.driver = None
