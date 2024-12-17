import json
import time
import os
import base64
import logging
from typing import Dict, Any, Optional, Tuple
from openai import OpenAI
from .base import BaseModel, WebInteraction, TaskResult

class GPT4Model(BaseModel):
    """GPT-4 model implementation for the DOM benchmark."""
    
    def __init__(self, api_key: str = None):
        """Initialize GPT4Model with OpenAI API key"""
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")
        
        self.client = OpenAI(api_key=self.api_key)
        self.max_retries = 10
        self.model = "gpt-4"
        self.temperature = 0
        self.max_tokens = 1000
        
        # Enhanced system prompt with hover support
        self.system_prompt = """You are an AI assistant that helps users interact with web elements.
Your task is to understand the user's intent and generate precise web element interactions.

For each task, analyze:
1. The user's goal and required interaction (click, type, hover)
2. The target element's properties and accessibility
3. Any constraints or special conditions

Key Guidelines:
1. Prefer stable selectors (id, unique class names) over dynamic ones
2. Consider element visibility and interactability
3. Handle dynamic content and loading states
4. Pay attention to timing and wait states

Generate interactions in this JSON format:
{
    "action": "click|type|hover",
    "selector_type": "css|xpath|id|class",
    "selector_value": "string",
    "input_text": "string",  # For type actions
    "description": "string"  # Optional description of the interaction
}"""

    def _call_api(self, messages: list, retry_count: int = 0) -> Tuple[Optional[dict], bool]:
        """Helper method to call OpenAI API with retry logic."""
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )
            return response, False
        except Exception as e:
            if retry_count >= self.max_retries:
                print(f"Max retries ({self.max_retries}) exceeded. Error: {str(e)}")
                return None, True
                
            wait_time = min(2 ** retry_count, 60)  # Exponential backoff
            if hasattr(e, "__class__"):
                if e.__class__.__name__ == "RateLimitError":
                    wait_time = max(wait_time, 10)
                elif e.__class__.__name__ == "APIError":
                    wait_time = max(wait_time, 15)
                
            print(f"API call failed, retrying in {wait_time}s. Error: {str(e)}")
            time.sleep(wait_time)
            return self._call_api(messages, retry_count + 1)
        
    def parse_task(self, task: Dict[str, Any]) -> WebInteraction:
        """Parse task using GPT-4 to understand the interaction."""
        prompt = f"""Task Description: {task['task']}
Target Element: {json.dumps(task['target_element'], indent=2)}
Page Context: {task.get('page_context', '')}
Previous Actions: {task.get('previous_actions', [])}

Consider:
1. Is this a multi-step interaction?
2. Are there any loading or dynamic states to handle?
3. What validation should be performed?
4. For hover: what effects should we validate?

Generate the optimal web interaction instruction as a JSON object."""

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        response, error = self._call_api(messages)
        if error or not response:
            return self._create_fallback_interaction(task)
            
        try:
            content = response.choices[0].message.content
            interaction_data = json.loads(content)
            
            return WebInteraction(
                action=interaction_data.get('action', task.get('interaction', 'click')).lower(),
                selector_type=interaction_data.get('selector_type', task['target_element']['type']).lower(),
                selector_value=interaction_data.get('selector_value', task['target_element']['value']),
                input_text=interaction_data.get('input_text', task.get('input_text')),
                description=task.get('task')
            )
        except Exception as e:
            print(f"Error parsing GPT-4 response: {str(e)}")
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
        """Use GPT-4 to understand and handle errors with enhanced error analysis."""
        prompt = f"""Task: {task['task']}
Original Error: {error}
Previous Interaction: {json.dumps(task.get('previous_interaction', {}), indent=2)}

Analyze the error and suggest a solution considering:
1. Is this a timing/loading issue?
2. Is the selector still valid?
3. Is the element interactive?
4. For hover: is the element hoverable?
5. Are there any prerequisite steps missing?

Generate a modified interaction as a JSON object or respond with "GIVE UP" if unrecoverable."""

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        response, api_error = self._call_api(messages)
        if api_error or not response:
            return self.parse_task(task)
            
        content = response.choices[0].message.content
        if content.strip() == "GIVE UP":
            return None
            
        try:
            interaction_data = json.loads(content)
            return WebInteraction(
                action=interaction_data['action'],
                selector_type=interaction_data['selector_type'],
                selector_value=interaction_data['selector_value'],
                input_text=interaction_data.get('input_text'),
                description=f"Error recovery: {task['task']}"
            )
        except Exception as e:
            print(f"Error in error handling: {str(e)}")
            return self.parse_task(task)
    
    def validate_result(self, task: Dict[str, Any], result: TaskResult) -> bool:
        """Enhanced validation using GPT-4 with detailed success criteria."""
        if result.error:
            return False
            
        prompt = f"""Task: {task['task']}
Target Element: {json.dumps(result.html_element, indent=2)}
Before State: {result.before_screenshot}
After State: {result.after_screenshot}
Validation Rules: {json.dumps(task.get('validation_rules', {}), indent=2)}

Evaluate the interaction success based on:
1. Element state changes (visibility, content, attributes)
2. Page state changes (URL, dynamic content)
3. Error messages or warnings
4. For hover: validate expected hover effects
5. Expected outcomes from validation rules

Respond with:
- "YES" if all success criteria are met
- "NO" with a brief explanation if any criteria fail"""

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        response, error = self._call_api(messages)
        if error or not response:
            return False
            
        validation_result = response.choices[0].message.content.strip()
        
        if validation_result.startswith("YES"):
            return True
        else:
            failure_reason = validation_result.replace("NO", "").strip()
            if failure_reason:
                print(f"Validation failed: {failure_reason}")
            return False

    def evaluate_image_similarity(self, actual_img: str, expected_img: str) -> Dict[str, Any]:
        """
        Evaluate similarity between actual and expected screenshots
        
        Args:
            actual_img: Path to actual screenshot
            expected_img: Path to expected (ground truth) screenshot
            
        Returns:
            Dict containing similarity score and explanation
        """
        try:
            # Load images
            with open(actual_img, "rb") as actual, open(expected_img, "rb") as expected:
                response = self.client.chat.completions.create(
                    model="gpt-4-vision-preview",
                    messages=[
                        {
                            "role": "system",
                            "content": "You are an expert at comparing web page screenshots to determine if the same interaction was performed."
                        },
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": "Compare these two screenshots and determine if they show the same web interaction was performed. Focus on the relevant UI changes, not minor visual differences."
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{base64.b64encode(actual.read()).decode()}"}
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/png;base64,{base64.b64encode(expected.read()).decode()}"}
                                }
                            ]
                        }
                    ],
                    max_tokens=300
                )
                
            return {
                "score": 1.0 if "same" in response.choices[0].message.content.lower() else 0.0,
                "explanation": response.choices[0].message.content
            }
            
        except Exception as e:
            logging.error(f"Error evaluating image similarity: {str(e)}")
            return {
                "score": 0.0,
                "explanation": f"Error evaluating images: {str(e)}"
            }
            
    def evaluate_html_similarity(self, actual_html: str, expected_html: str) -> Dict[str, Any]:
        """
        Evaluate similarity between actual and expected HTML
        
        Args:
            actual_html: Actual HTML string
            expected_html: Expected HTML string
            
        Returns:
            Dict containing similarity score and explanation
        """
        try:
            response = self.client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at comparing HTML elements to determine if they refer to the same interactive element."
                    },
                    {
                        "role": "user",
                        "content": f"""Compare these two HTML elements and determine if they refer to the same interactive element:
                        
                        Actual HTML:
                        {actual_html}
                        
                        Expected HTML:
                        {expected_html}
                        
                        Focus on key attributes like id, class, role, and text content. Ignore minor differences in formatting or dynamic attributes."""
                    }
                ],
                max_tokens=300
            )
            
            return {
                "score": 1.0 if "same" in response.choices[0].message.content.lower() else 0.0,
                "explanation": response.choices[0].message.content
            }
            
        except Exception as e:
            logging.error(f"Error evaluating HTML similarity: {str(e)}")
            return {
                "score": 0.0,
                "explanation": f"Error comparing HTML: {str(e)}"
            }
