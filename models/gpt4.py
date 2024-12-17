import json
from typing import Dict, Any, Optional
from openai import OpenAI
from .base import BaseModel, WebInteraction, TaskResult

class GPT4Model(BaseModel):
    """GPT-4 model implementation for the DOM benchmark."""
    
    def __init__(self, api_key: str, model_config: Dict[str, Any] = None):
        super().__init__("gpt-4", model_config or {})
        self.client = OpenAI(api_key=api_key)
        
        # Default system prompt
        self.system_prompt = """You are an AI assistant that helps users interact with web elements.
Your task is to understand the user's intent and generate precise web element interactions.
You should focus on the specific interaction requested, using the provided element selectors.

For each task, you will:
1. Understand the required interaction (click, type, hover)
2. Identify the correct element using the provided selector
3. Generate the appropriate interaction instruction

Respond only with the exact interaction needed, no explanations or additional text."""
        
    def parse_task(self, task: Dict[str, Any]) -> WebInteraction:
        """Parse task using GPT-4 to understand the interaction."""
        # Construct prompt
        prompt = f"""Task: {task['task']}
Target Element: {json.dumps(task['target_element'])}
Interaction Type: {task.get('interaction', 'click')}
Input Text: {task.get('input_text', '')}

Generate the web interaction instruction."""

        # Get GPT-4 completion
        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        # Parse response into WebInteraction
        return WebInteraction(
            action=task.get('interaction', 'click'),
            selector_type=task['target_element']['type'],
            selector_value=task['target_element']['value'],
            input_text=task.get('input_text'),
            description=task['task']
        )
    
    def handle_error(self, task: Dict[str, Any], error: str) -> Optional[WebInteraction]:
        """Use GPT-4 to understand and handle errors."""
        prompt = f"""Task: {task['task']}
Error: {error}

How should we modify the interaction to handle this error?
If the error is unrecoverable, respond with "GIVE UP"."""

        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        suggestion = response.choices[0].message.content
        if suggestion == "GIVE UP":
            return None
            
        # Try to generate a new interaction based on GPT-4's suggestion
        return self.parse_task(task)
    
    def validate_result(self, task: Dict[str, Any], result: TaskResult) -> bool:
        """Use GPT-4 to validate if the task was successful."""
        if result.error:
            return False
            
        prompt = f"""Task: {task['task']}
Target Element HTML: {result.html_element}
Was this interaction successful? Answer with just 'YES' or 'NO'."""

        response = self.client.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )
        
        return response.choices[0].message.content == "YES"
