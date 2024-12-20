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

class RequestPool:
    def __init__(self, max_requests_per_minute=3500):
        self.requests = []
        self.max_requests = max_requests_per_minute
        self.window = 60  # 1 minute window

    def can_make_request(self):
        now = time.time()
        # Remove old requests
        self.requests = [t for t in self.requests if now - t < self.window]
        return len(self.requests) < self.max_requests

    def add_request(self):
        self.requests.append(time.time())

class GPT4Model(BaseModel):
    """GPT-4 model implementation for the DOM benchmark."""
    
    def __init__(self, api_key: str = None):
        """Initialize GPT4Model with OpenAI API key"""
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        if not self.api_key:
            raise ValueError("OpenAI API key not provided")
        
        self.client = OpenAI(api_key=self.api_key)
        self.max_retries = 10
        self.model = "gpt-4-turbo"  # Switched to gpt-4 model
        self.temperature = 0
        self.tokenizer = tiktoken.encoding_for_model("gpt-4-turbo")
        self.request_pool = RequestPool()  # Add request pooling
        
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

IMPORTANT: You MUST respond with ONLY a valid JSON object. No other text, explanations, or formatting.
The JSON object MUST follow this exact schema:
{
    "action": "click" | "type" | "hover",
    "selector_type": "css" | "xpath" | "id" | "class",
    "selector_value": "string",
    "input_text": "string"  // Only required for type actions
}

Guidelines for generating selectors:
1. Prefer stable selectors (id, unique class names) over dynamic ones
2. Consider element visibility and interactability
3. Handle dynamic content and loading states
4. Pay attention to timing and wait states

Example valid response:
{
    "action": "click",
    "selector_type": "css",
    "selector_value": "#submit-button",
    "input_text": null
}"""

    def _call_api(self, messages: list, retry_count: int = 0) -> Tuple[Optional[dict], bool]:
        """Helper method to call OpenAI API with retry logic."""
        if not self.request_pool.can_make_request():
            wait_time = 1
            print(f"Rate limit exceeded, waiting {wait_time}s before retrying.")
            time.sleep(wait_time)
            return self._call_api(messages, retry_count)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature
            )
            self.request_pool.add_request()
            return response, False
        except Exception as e:
            if retry_count >= self.max_retries:
                print(f"Max retries ({self.max_retries}) exceeded. Error: {str(e)}")
                return None, True
                
            wait_time = min(2 ** retry_count, 60)  # Exponential backoff
            if hasattr(e, "__class__"):
                if e.__class__.__name__ == "RateLimitError":
                    wait_time = max(wait_time, 10)  # Back to original wait time
                elif e.__class__.__name__ == "APIError":
                    wait_time = max(wait_time, 15)
                
            print(f"API call failed, retrying in {wait_time}s. Error: {str(e)}")
            time.sleep(wait_time)
            return self._call_api(messages, retry_count + 1)
        
    def _clean_html(self, html: str) -> str:
        """Keep only relevant semantic HTML elements and attributes for content analysis."""
        # Count tokens before cleaning
        initial_tokens = len(self.tokenizer.encode(html))
        print(f"[GPT-4] Initial HTML context length: {initial_tokens} tokens")
        
        # Use BeautifulSoup for robust HTML parsing
        soup = BeautifulSoup(html, "html.parser")
        
        # Define elements we want to keep
        allowed_elements = {
            # Text content elements
            'p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6',
            'ul', 'ol', 'li', 'a', 'table', 'tr', 'td', 'th',
            'div', 'span', 'strong', 'em', 'code', 'pre',
            'blockquote', 'article', 'section', 'main',
            
            # Interactive elements
            'button', 'input', 'select', 'option', 'textarea', 'form',
            'label', 'fieldset', 'legend', 'datalist', 'output',
            
            # Media elements that might be clickable
            'img', 'svg', 'canvas', 'video', 'audio',
            
            # Navigation elements
            'nav', 'header', 'footer', 'menu', 'menuitem',
            
            # Interactive containers
            'dialog', 'details', 'summary'
        }
        
        # Define attributes we want to keep
        allowed_attributes = {
            'a': ['href', 'title'],
            'img': ['alt', 'src'],
            '*': ['id', 'class']  # Allow these on any element
        }
        
        # Function to clean a tag
        def clean_tag(tag):
            if tag.name not in allowed_elements:
                tag.unwrap()  # Keep content but remove the tag
                return
                
            # Remove all attributes except allowed ones
            allowed_for_tag = allowed_attributes.get(tag.name, []) + allowed_attributes['*']
            attrs = dict(tag.attrs)  # Create a copy since we're modifying
            for attr in attrs:
                if attr not in allowed_for_tag:
                    del tag[attr]
        
        # Clean all tags in the document
        for tag in soup.find_all(True):
            clean_tag(tag)
            
        cleaned_html = str(soup)
        final_tokens = len(self.tokenizer.encode(cleaned_html))
        print(f"[GPT-4] Final HTML context length: {final_tokens} tokens")
        print(f"[GPT-4] Reduced by: {initial_tokens - final_tokens} tokens ({((initial_tokens - final_tokens) / initial_tokens * 100):.1f}%)")
        
        return cleaned_html

    def parse_task(self, task: Dict[str, Any], page_html: str = None) -> Optional[WebInteraction]:
        """Parse task using GPT-4 to understand the interaction."""
        # Clean HTML if provided
        if page_html:
            page_html = self._clean_html(page_html)
            
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": f"""Task: {task['task']}
Current Page HTML: {page_html if page_html else 'Not available'}

Based on the task description and current page HTML, generate a web interaction as a JSON object."""}
        ]
        
        try:
            # Wait for rate limit if needed
            while not self.request_pool.can_make_request():
                time.sleep(1)
            self.request_pool.add_request()
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            interaction_data = json.loads(response.choices[0].message.content)
            return WebInteraction(
                action=interaction_data.get('action', 'click'),
                selector_type=interaction_data.get('selector_type', 'css'),
                selector_value=interaction_data.get('selector_value'),
                input_text=interaction_data.get('input_text'),
                description=task['task']
            )
        except Exception as e:
            print(f"Error in GPT-4 task parsing: {str(e)}")
            return None

    def _create_fallback_interaction(self, task: Dict[str, Any]) -> Optional[WebInteraction]:
        """Create a fallback interaction when API calls or parsing fails."""
        # Don't use ground truth, just skip the task
        return None
    
    def handle_error(self, task: Dict[str, Any], error: str) -> Optional[WebInteraction]:
        """Use GPT-4 to understand and handle errors."""
        error_prompt = f"""Task: {task['task']}
Error: {error}

Based on the task and error message, suggest a new web interaction that might work better.
Respond with a JSON object following the same schema as before."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": error_prompt}
                ],
                temperature=self.temperature,
                response_format={"type": "json_object"}
            )
            
            interaction_data = json.loads(response.choices[0].message.content)
            return WebInteraction(
                action=interaction_data.get('action', 'click'),
                selector_type=interaction_data.get('selector_type', 'css'),
                selector_value=interaction_data.get('selector_value'),
                input_text=interaction_data.get('input_text'),
                description=task['task']
            )
        except Exception as e:
            print(f"Error in GPT-4 error handling: {str(e)}")
            return None

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
