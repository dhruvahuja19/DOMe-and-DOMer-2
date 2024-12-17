"""Example usage of different models in the DOM benchmark."""

import os
from dotenv import load_dotenv
from models import GPT4Model, ClaudeModel
from utils import TaskExecutor

# Load environment variables
load_dotenv()

def run_example_task(model, task):
    """Run a single task with the given model and print results."""
    executor = TaskExecutor()
    print(f"\nRunning task with {model.__class__.__name__}:")
    print(f"Task: {task['task']}")
    
    result = model.run_task(task, executor)
    
    print(f"Success: {result.success}")
    if result.error:
        print(f"Error: {result.error}")
    print(f"Time taken: {result.time_taken:.2f}s")
    return result

def main():
    # Initialize models
    gpt4_model = GPT4Model(api_key=os.getenv("OPENAI_API_KEY"))
    claude_model = ClaudeModel(api_key=os.getenv("ANTHROPIC_API_KEY"))
    
    # Example task
    task = {
        "task": "Click the 'Sign In' button",
        "target_element": {
            "type": "css",
            "value": "#signin-button"
        },
        "interaction": "click"
    }
    
    # Run with both models
    gpt4_result = run_example_task(gpt4_model, task)
    claude_result = run_example_task(claude_model, task)
    
    # Compare results
    print("\nComparison:")
    print(f"GPT-4 success: {gpt4_result.success}")
    print(f"Claude success: {claude_result.success}")
    print(f"GPT-4 time: {gpt4_result.time_taken:.2f}s")
    print(f"Claude time: {claude_result.time_taken:.2f}s")

if __name__ == "__main__":
    main()
