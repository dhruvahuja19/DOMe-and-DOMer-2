import json
from typing import Dict, Any, Optional
from anthropic import Anthropic
from .base import BaseModel, WebInteraction, TaskResult

class ClaudeModel(BaseModel):
    """Claude model implementation for the DOM benchmark."""
    
    def __init__(self, api_key: str, model_config: Dict[str, Any] = None):
        super().__init__("claude-3", model_config or {})
        self.client = Anthropic(api_key=api_key)
        
        # Default system prompt
        self.system_prompt = """You are an AI assistant that helps users interact with web elements.
Your task is to understand the user's intent and generate precise web element interactions.
You should focus on the specific interaction requested, using the provided element selectors.

For each task, you will:
1. Understand the required interaction (click, type, hover)
2. Identify the correct element using the provided selector
3. Generate the appropriate interaction instruction

Respond only with the exact interaction needed, no explanations or additional text.

The response should be a JSON object with the following structure:
{
    "action": "click|type|hover",
    "selector_type": "css|xpath|id",
    "selector_value": "string",
    "input_text": "string" (optional)
}"""
        
    def parse_task(self, task: Dict[str, Any]) -> WebInteraction:
        """Parse task using Claude to understand the interaction."""
        # Construct prompt
        prompt = f"""Task: {task['task']}
Target Element: {json.dumps(task['target_element'])}
Interaction Type: {task.get('interaction', 'click')}
Input Text: {task.get('input_text', '')}

Generate the web interaction instruction as a JSON object."""

        # Get Claude completion
        response = self.client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=150,
            temperature=0,
            system=self.system_prompt,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        # Parse JSON response
        try:
            interaction_data = json.loads(response.content[0].text)
            return WebInteraction(
                action=interaction_data.get('action', task.get('interaction', 'click')),
                selector_type=interaction_data.get('selector_type', task['target_element']['type']),
                selector_value=interaction_data.get('selector_value', task['target_element']['value']),
                input_text=interaction_data.get('input_text', task.get('input_text')),
                description=task['task']
            )
        except json.JSONDecodeError:
            # Fallback to task values if Claude's response isn't valid JSON
            return WebInteraction(
                action=task.get('interaction', 'click'),
                selector_type=task['target_element']['type'],
                selector_value=task['target_element']['value'],
                input_text=task.get('input_text'),
                description=task['task']
            )
    
    def handle_error(self, task: Dict[str, Any], error: str) -> Optional[WebInteraction]:
        """Use Claude to understand and handle errors."""
        prompt = f"""Task: {task['task']}
Error: {error}

Analyze the error and suggest a modified interaction. Respond with a JSON object for the new interaction.
If the error is unrecoverable, respond with exactly "GIVE UP"."""

        response = self.client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=150,
            temperature=0,
            system=self.system_prompt,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        suggestion = response.content[0].text.strip()
        if suggestion == "GIVE UP":
            return None
            
        try:
            # Try to parse Claude's suggestion
            interaction_data = json.loads(suggestion)
            return WebInteraction(
                action=interaction_data['action'],
                selector_type=interaction_data['selector_type'],
                selector_value=interaction_data['selector_value'],
                input_text=interaction_data.get('input_text'),
                description=task['task']
            )
        except (json.JSONDecodeError, KeyError):
            # If Claude's suggestion isn't valid, try one more time with original task
            return self.parse_task(task)
    
    def validate_result(self, task: Dict[str, Any], result: TaskResult) -> bool:
        """Use Claude to validate if the task was successful."""
        if result.error:
            return False
            
        prompt = f"""Task: {task['task']}
Target Element HTML: {result.html_element}
Before Screenshot: {result.before_screenshot}
After Screenshot: {result.after_screenshot}

Analyze if the interaction was successful. Consider:
1. The HTML element matches the expected interaction
2. The screenshots show the expected change
3. No errors occurred

Respond with exactly 'YES' or 'NO'."""

        response = self.client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=10,
            temperature=0,
            system=self.system_prompt,
            messages=[
                {"role": "user", "content": prompt}
            ]
        )
        
        return response.content[0].text.strip() == "YES"
