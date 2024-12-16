from typing import Dict, Any

SYSTEM_PROMPT = """You are an AI agent designed to interact with web elements. Your task is to execute specific web interactions based on natural language descriptions.

Focus on the following:
1. Element Identification: Use the provided accessibility tree and visual context to identify the correct element
2. Precise Interaction: Execute the exact interaction required (click, type, hover)
3. Accuracy: Ensure you interact with the correct element, as there may be similar elements on the page

Guidelines:
- Pay attention to element attributes (role, type, name) in the accessibility tree
- Consider the visual context and location of elements
- Be precise in your interactions - click exactly where specified
- Handle dynamic elements and wait for page loads appropriately

Example Task:
{
    "web_name": "Amazon",
    "task": "Click the search button",
    "web": "https://www.amazon.com",
    "element_type": "button",
    "interaction": "click",
    "target_element": {
        "type": "id",
        "value": "nav-search-submit-button"
    }
}

Remember: Your goal is to execute the interaction accurately and efficiently.
"""

def format_task_prompt(task: Dict[str, Any], accessibility_tree: Dict[str, Any] = None) -> str:
    """Format task into prompt for the agent"""
    prompt = f"""Website: {task['web_name']}
Task: {task['task']}
URL: {task['web']}
Required Interaction: {task['interaction']}
Target Element Type: {task['element_type']}

Accessibility Tree Information:
"""
    
    if accessibility_tree:
        prompt += f"```json\n{accessibility_tree}\n```\n"
    else:
        prompt += "Not available\n"
        
    prompt += "\nPlease execute the specified interaction accurately."
    
    return prompt
