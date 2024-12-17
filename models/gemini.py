import json
import time
from typing import Dict, Any, Optional, Tuple
import google.generativeai as genai
from .base import BaseModel, WebInteraction, TaskResult

class GeminiModel(BaseModel):
    """Gemini model implementation for the DOM benchmark."""
    
    def __init__(self, api_key: str, model_config: Dict[str, Any] = None):
        super().__init__("gemini-pro", model_config or {})
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-pro')
        self.max_retries = 10
        self.temperature = model_config.get("temperature", 0)
        
        # Enhanced system prompt based on WebVoyager's approach
        self.system_prompt = """You are an AI assistant that helps users interact with web elements.
Your task is to understand the user's intent and generate precise web element interactions.

For each task, analyze:
1. The user's goal and required interaction (click, type, scroll, wait)
2. The target element's properties and accessibility
3. Any constraints or special conditions

Key Guidelines:
1. Prefer stable selectors (id, unique class names) over dynamic ones
2. Consider element visibility and interactability
3. Handle dynamic content and loading states
4. Pay attention to timing and wait states
5. Validate success criteria for each interaction

Generate interactions in this JSON format:
{
    "action": "click|type|scroll|wait",
    "selector_type": "css|xpath|id",
    "selector_value": "string",
    "input_text": "string",  # For type actions
    "wait_time": integer,    # For wait actions in seconds
    "scroll_direction": "up|down",  # For scroll actions
    "validation": {
        "expected_state": "visible|hidden|text_present|text_absent",
        "validation_selector": "string",  # Element to validate
        "expected_text": "string"  # For text validation
    }
}"""

    def _call_api(self, prompt: str, retry_count: int = 0) -> Tuple[Optional[str], bool]:
        """Helper method to call Gemini API with retry logic."""
        try:
            response = self.model.generate_content(prompt, temperature=self.temperature)
            return response.text, False
        except Exception as e:
            if retry_count >= self.max_retries:
                print(f"Max retries ({self.max_retries}) exceeded. Error: {str(e)}")
                return None, True
                
            wait_time = min(2 ** retry_count, 60)  # Exponential backoff
            if hasattr(e, "__class__"):
                if e.__class__.__name__ == "RateLimitError":
                    wait_time = max(wait_time, 10)
                elif e.__class__.__name__ == "ServerError":
                    wait_time = max(wait_time, 15)
                
            print(f"API call failed, retrying in {wait_time}s. Error: {str(e)}")
            time.sleep(wait_time)
            return self._call_api(prompt, retry_count + 1)
        
    def parse_task(self, task: Dict[str, Any]) -> WebInteraction:
        """Parse task using Gemini to understand the interaction."""
        prompt = f"""System: {self.system_prompt}

Task Description: {task['task']}
Target Element: {json.dumps(task['target_element'], indent=2)}
Page Context: {task.get('page_context', '')}
Previous Actions: {task.get('previous_actions', [])}

Consider:
1. Is this a multi-step interaction?
2. Are there any loading or dynamic states to handle?
3. What validation should be performed?

Generate the optimal web interaction instruction as a JSON object."""

        response_text, error = self._call_api(prompt)
        if error or not response_text:
            return self._create_fallback_interaction(task)
            
        try:
            # Find and parse JSON in response
            start_idx = response_text.find('{')
            end_idx = response_text.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx]
                interaction_data = json.loads(json_str)
                
                return WebInteraction(
                    action=interaction_data.get('action', task.get('interaction', 'click')),
                    selector_type=interaction_data.get('selector_type', task['target_element']['type']),
                    selector_value=interaction_data.get('selector_value', task['target_element']['value']),
                    input_text=interaction_data.get('input_text'),
                    description=task['task'],
                    wait_time=interaction_data.get('wait_time', 0),
                    validation=interaction_data.get('validation', {})
                )
        except Exception as e:
            print(f"Error parsing Gemini response: {str(e)}")
            return self._create_fallback_interaction(task)
    
    def _create_fallback_interaction(self, task: Dict[str, Any]) -> WebInteraction:
        """Create a fallback interaction when API calls or parsing fails."""
        return WebInteraction(
            action=task.get('interaction', 'click'),
            selector_type=task['target_element']['type'],
            selector_value=task['target_element']['value'],
            input_text=task.get('input_text'),
            description=task['task']
        )
    
    def handle_error(self, task: Dict[str, Any], error: str) -> Optional[WebInteraction]:
        """Use Gemini to understand and handle errors with enhanced error analysis."""
        prompt = f"""System: {self.system_prompt}

Task: {task['task']}
Original Error: {error}
Previous Interaction: {json.dumps(task.get('previous_interaction', {}), indent=2)}

Analyze the error and suggest a solution considering:
1. Is this a timing/loading issue?
2. Is the selector still valid?
3. Is the element interactive?
4. Are there any prerequisite steps missing?

Generate a modified interaction as a JSON object or respond with "GIVE UP" if unrecoverable."""

        response_text, api_error = self._call_api(prompt)
        if api_error or not response_text:
            return self.parse_task(task)
            
        suggestion = response_text.strip()
        if suggestion == "GIVE UP":
            return None
            
        try:
            # Find and parse JSON in response
            start_idx = suggestion.find('{')
            end_idx = suggestion.rfind('}') + 1
            if start_idx != -1 and end_idx != -1:
                json_str = suggestion[start_idx:end_idx]
                interaction_data = json.loads(json_str)
                
                return WebInteraction(
                    action=interaction_data['action'],
                    selector_type=interaction_data['selector_type'],
                    selector_value=interaction_data['selector_value'],
                    input_text=interaction_data.get('input_text'),
                    description=f"Error recovery: {task['task']}",
                    wait_time=interaction_data.get('wait_time', 0),
                    validation=interaction_data.get('validation', {})
                )
        except Exception as e:
            print(f"Error in error handling: {str(e)}")
            return self.parse_task(task)
    
    def validate_result(self, task: Dict[str, Any], result: TaskResult) -> bool:
        """Enhanced validation using Gemini with detailed success criteria."""
        if result.error:
            return False
            
        prompt = f"""System: {self.system_prompt}

Task: {task['task']}
Target Element: {json.dumps(result.html_element, indent=2)}
Before State: {result.before_screenshot}
After State: {result.after_screenshot}
Validation Rules: {json.dumps(task.get('validation_rules', {}), indent=2)}

Evaluate the interaction success based on:
1. Element state changes (visibility, content, attributes)
2. Page state changes (URL, dynamic content)
3. Error messages or warnings
4. Expected outcomes from validation rules

Respond with:
- "YES" if all success criteria are met
- "NO" with a brief explanation if any criteria fail"""

        response_text, error = self._call_api(prompt)
        if error or not response_text:
            return False
            
        validation_result = response_text.strip()
        
        if validation_result.startswith("YES"):
            return True
        else:
            failure_reason = validation_result.replace("NO", "").strip()
            if failure_reason:
                print(f"Validation failed: {failure_reason}")
            return False
