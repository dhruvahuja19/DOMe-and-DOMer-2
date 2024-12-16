import selenium
from selenium import webdriver
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import time
import os
import base64
from pathlib import Path

def setup_driver():
    """Initialize Chrome driver with appropriate settings"""
    chrome_options = Options()
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    return webdriver.Chrome(options=chrome_options)

def take_element_screenshot(driver, element, output_path):
    """Take a screenshot of a specific element"""
    element_png = element.screenshot_as_png
    with open(output_path, "wb") as f:
        f.write(element_png)

def take_full_page_screenshot(driver, url, output_path):
    """Take a full page screenshot with consistent rendering"""
    try:
        driver.get(url)
        time.sleep(3)  # Wait for page load and any animations
        
        # Normalize color scheme and rendering
        driver.execute_script("""
            document.documentElement.style.colorScheme = 'normal';
            document.documentElement.style.forcedColorAdjust = 'none';
        """)
        
        # Get page metrics and capture full page
        metrics = driver.execute_cdp_cmd('Page.getLayoutMetrics', {})
        screenshot_config = {
            'captureBeyondViewport': True,
            'fromSurface': True,
            'clip': {
                'x': 0,
                'y': 0,
                'width': metrics['cssContentSize']['width'],
                'height': metrics['cssContentSize']['height'],
                'scale': 1
            }
        }
        screenshot_data = driver.execute_cdp_cmd('Page.captureScreenshot', screenshot_config)
        
        # Save screenshot
        with open(output_path, 'wb') as f:
            f.write(base64.b64decode(screenshot_data['data']))
        print(f"Screenshot saved successfully as {output_path}")
        
    except Exception as e:
        print(f"Screenshot failed: {str(e)}")
        raise

def capture_task_screenshots(task_data, ground_truth_dir):
    """Capture before and after screenshots for a task"""
    driver = setup_driver()
    try:
        # Create screenshot paths
        task_id = task_data["id"]
        before_path = Path(ground_truth_dir) / f"{task_id}_before.png"
        after_path = Path(ground_truth_dir) / f"{task_id}_gt.png"
        
        # Take before screenshot
        take_full_page_screenshot(driver, task_data["web"], str(before_path))
        
        # Perform task action
        if task_data["element_type"] == "input":
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.ID, task_data["target_element"]["value"]))
            )
            element.click()
            if "input_text" in task_data:
                element.send_keys(task_data["input_text"])
        
        elif task_data["element_type"] == "button":
            element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CLASS_NAME, task_data["target_element"]["value"]))
            )
            element.click()
        
        # Wait for any transitions/loading
        time.sleep(2)
        
        # Take after screenshot
        take_full_page_screenshot(driver, driver.current_url, str(after_path))
        
    finally:
        driver.quit()

if __name__ == "__main__":
    # Example usage
    from pathlib import Path
    import json
    
    # Load tasks
    tasks_file = Path("data/dom_tasks.jsonl")
    ground_truth_dir = Path("data/ground_truth")
    ground_truth_dir.mkdir(exist_ok=True)
    
    with open(tasks_file) as f:
        for line in f:
            task = json.loads(line)
            capture_task_screenshots(task, ground_truth_dir)
