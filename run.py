import argparse
import json
import logging
import time
from pathlib import Path
from typing import Dict, List, Any

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

from utils import WebInteractionUtils, load_tasks, save_results, get_accessibility_tree, compute_image_similarity

def setup_logger(output_dir: Path) -> None:
    """Setup logging configuration"""
    log_file = output_dir / "benchmark.log"
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

def setup_driver(
    headless: bool = True,
    download_dir: str = None,
    force_device_scale: bool = True
) -> webdriver.Chrome:
    """Setup Chrome WebDriver with specified options"""
    options = Options()
    
    if force_device_scale:
        options.add_argument("--force-device-scale-factor=1")
    if headless:
        options.add_argument("--headless")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        )
    if download_dir:
        options.add_experimental_option(
            "prefs", {"download.default_directory": download_dir}
        )
    
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    service = Service(ChromeDriverManager().install())
    return webdriver.Chrome(service=service, options=options)

def run_benchmark(
    tasks_file: Path,
    output_dir: Path,
    headless: bool = True,
    force_device_scale: bool = True,
    save_accessibility_tree: bool = True,
    image_match_threshold: float = 0.95
) -> None:
    """Run the DOM benchmark"""
    
    # Setup
    output_dir.mkdir(parents=True, exist_ok=True)
    setup_logger(output_dir)
    
    # Load tasks
    tasks = load_tasks(tasks_file)
    logging.info(f"Loaded {len(tasks)} tasks from {tasks_file}")
    
    # Setup WebDriver
    driver = setup_driver(
        headless=headless,
        download_dir=str(output_dir / "downloads"),
        force_device_scale=force_device_scale
    )
    utils = WebInteractionUtils(driver)
    
    try:
        results = []
        for i, task in enumerate(tasks):
            task_id = task["id"]
            logging.info(f"Running task {i+1}/{len(tasks)}: {task_id}")
            
            # Load webpage
            driver.get(task["web"])
            time.sleep(2)  # Wait for page load
            
            # Get accessibility tree
            if save_accessibility_tree:
                tree_file = output_dir / f"accessibility_tree_{task_id}.json"
                tree = get_accessibility_tree(driver, str(tree_file))
                logging.info(f"Saved accessibility tree to {tree_file}")
            
            # Take before screenshot
            before_screenshot = output_dir / f"before_{task_id}.png"
            driver.save_screenshot(str(before_screenshot))
            
            # Execute interaction
            success = utils.execute_interaction(task)
            time.sleep(1)  # Wait for interaction effect
            
            # Take after screenshot
            after_screenshot = output_dir / f"after_{task_id}.png"
            driver.save_screenshot(str(after_screenshot))
            
            # Compare screenshots
            image_similarity = compute_image_similarity(str(before_screenshot), str(after_screenshot))
            
            # Save result
            result = {
                "task_id": task_id,
                "success": success,
                "image_similarity": image_similarity,
                "passed_threshold": image_similarity >= image_match_threshold,
                "timestamp": time.time(),
                "accessibility_tree": str(tree_file) if save_accessibility_tree else None
            }
            results.append(result)
            
            logging.info(
                f"Task {task_id} completed: success={success}, "
                f"image_similarity={image_similarity:.3f}"
            )
        
        # Save results
        results_file = output_dir / "results.json"
        save_results(results, str(results_file))
        logging.info(f"Results saved to {results_file}")
        
        # Print summary
        successful = sum(1 for r in results if r["success"])
        passed_threshold = sum(1 for r in results if r["passed_threshold"])
        logging.info(
            f"\nBenchmark Summary:\n"
            f"Total Tasks: {len(tasks)}\n"
            f"Successful Interactions: {successful}\n"
            f"Passed Image Threshold: {passed_threshold}\n"
        )
        
    finally:
        driver.quit()

def main():
    parser = argparse.ArgumentParser(description="Run DOM Benchmark")
    parser.add_argument("--tasks", type=Path, required=True, help="Path to tasks JSONL file")
    parser.add_argument("--output", type=Path, required=True, help="Output directory for results")
    parser.add_argument("--headless", action="store_true", help="Run Chrome in headless mode")
    parser.add_argument("--force-device-scale", action="store_true", help="Force device scale factor to 1")
    parser.add_argument("--save-accessibility-tree", action="store_true", help="Save accessibility tree for each task")
    parser.add_argument("--threshold", type=float, default=0.95, help="Image similarity threshold")
    
    args = parser.parse_args()
    
    run_benchmark(
        tasks_file=args.tasks,
        output_dir=args.output,
        headless=args.headless,
        force_device_scale=args.force_device_scale,
        save_accessibility_tree=args.save_accessibility_tree,
        image_match_threshold=args.threshold
    )

if __name__ == "__main__":
    main()
