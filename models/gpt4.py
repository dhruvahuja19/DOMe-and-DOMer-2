import json
import time
import os
import base64
import logging
import re
import tiktoken
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from openai import OpenAI
from bs4 import BeautifulSoup
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
        self.model = "gpt-4"  # Switched to gpt-4 model
        self.temperature = 0
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        
        # Setup logging for skipped tasks
        self.output_dir = Path("results/skipped_tasks")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.skipped_logger = logging.getLogger('skipped_tasks')
        handler = logging.FileHandler(self.output_dir / 'skipped_tasks.log')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.skipped_logger.addHandler(handler)
        self.skipped_logger.setLevel(logging.INFO)
        
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
        
    def _clean_html(self, html: str) -> str:
        """Aggressively clean and truncate HTML to reduce size while keeping key elements."""
        # First use BeautifulSoup for robust HTML parsing
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove all tags except those needed for interaction
        keep_tags = {'input', 'button', 'a', 'select', 'textarea', 'form', 'label'}
        for tag in soup.find_all():
            if tag.name not in keep_tags:
                # Keep the text content but remove the tag
                tag.replace_with(tag.get_text(' ', strip=True))
        
        # Keep only essential attributes
        essential_attrs = {'id', 'class', 'name', 'type', 'value', 'href', 'role', 'aria-label'}
        for tag in soup.find_all():
            attrs = dict(tag.attrs)  # Create a copy since we're modifying
            for attr in attrs:
                if attr not in essential_attrs:
                    del tag[attr]
                elif attr == 'class':  # Truncate long class names
                    classes = tag['class'][:2] if isinstance(tag['class'], list) else tag['class'].split()[:2]
                    tag['class'] = ' '.join(classes)
        
        # Get the cleaned HTML
        cleaned_html = str(soup)
        
        # Remove extra whitespace and newlines
        cleaned_html = ' '.join(cleaned_html.split())
        
        # Truncate very long attribute values
        cleaned_html = re.sub(r'((?:id|class|name)="[^"]{30})[^"]*"', r'\1..."', cleaned_html)
        
        # Remove empty or whitespace-only text nodes
        cleaned_html = re.sub(r'>\s+<', '><', cleaned_html)
        
        return cleaned_html

    def parse_task(self, task: Dict[str, Any], page_html: str = None) -> Optional[WebInteraction]:
        """Parse task using GPT-4 to understand the interaction."""
        if page_html:
            page_html = self._clean_html(page_html)
            
        # Construct messages
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"""Task Description: {task['task']}
Current Page HTML: {page_html if page_html else 'Not available'}

Based on the task description and current page HTML:
1. Determine the type of interaction needed (click, type, hover)
2. Identify the target element using the most reliable selector
3. Extract any input text if needed for type interactions"""}
        ]
        
        # Check total token count before making API call
        total_tokens = sum(len(self.tokenizer.encode(msg["content"])) for msg in messages)
        if total_tokens > 128000:  # GPT-4 Turbo's context limit
            self.skipped_logger.info(
                f"Task skipped due to length - URL: {task.get('url', 'N/A')}, "
                f"Task: {task.get('task', 'N/A')}, "
                f"Token count: {total_tokens} (limit: 128000)"
            )
            return None  # Skip the task instead of using ground truth
            
        response, error = self._call_api(messages)
        if error or not response:
            return None  # Skip on API errors instead of using ground truth
            
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
    
    def _create_fallback_interaction(self, task: Dict[str, Any]) -> Optional[WebInteraction]:
        """Create a fallback interaction when API calls or parsing fails."""
        # Don't use ground truth, just skip the task
        return None
    
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
                    model="gpt-4o",
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
