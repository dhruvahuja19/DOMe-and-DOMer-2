from typing import Dict, Any

SYSTEM_PROMPT = """You are an AI agent designed to interact with web elements. Your task is to:
1. Execute the specified web interaction (click, type, etc.)
2. Return the exact HTML element you interacted with

Guidelines:
- Execute the interaction precisely as specified
- Return the complete HTML element including all attributes and content
- Use the accessibility tree to help identify the correct element
- Consider both visual context and element attributes

Your response MUST be in this exact JSON format:
{
    "action": {
        "type": "click|type|hover|etc",
        "value": "text to type if applicable"
    },
    "html_element": "<complete html element you interacted with>",
    "confidence": 0.95  # How confident you are in your selection
}

Example:
Task: "Click the search button"
Response:
{
    "action": {
        "type": "click",
        "value": null
    },
    "html_element": "<button type=\"submit\" class=\"nav-search-submit\" aria-label=\"Search\"><i class=\"nav-icon-search\"></i></button>",
    "confidence": 0.95
}"""

def format_task_prompt(task: Dict[str, Any], accessibility_tree: Dict[str, Any] = None) -> str:
    """Format task into prompt for the agent"""
    prompt = f"""Website: {task['web_name']}
Task: {task['task']}
URL: {task['web']}

Accessibility Tree:
```json
{accessibility_tree if accessibility_tree else 'Not available'}
```

Execute the task and return both your action and the HTML element you interacted with."""
    
    return prompt
