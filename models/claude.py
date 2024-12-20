import json
import time
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from anthropic import Anthropic
from .base import BaseModel, WebInteraction, TaskResult
from bs4 import BeautifulSoup

class RequestPool:
    def __init__(self, max_requests_per_minute=5):  # Claude has lower rate limits
        self.requests = []
        self.max_requests = max_requests_per_minute
        self.window = 60  # 1 minute window
        self.min_wait = 12  # Minimum 12 seconds between requests (5 per minute)

    def can_make_request(self):
        now = time.time()
        # Remove old requests
        self.requests = [t for t in self.requests if now - t < self.window]
        
        # Check if we've made any requests in the last min_wait seconds
        if self.requests and (now - self.requests[-1]) < self.min_wait:
            return False
            
        return len(self.requests) < self.max_requests

    def add_request(self):
        self.requests.append(time.time())

class ClaudeModel(BaseModel):
    """Claude model implementation for the DOM benchmark."""
    
    def __init__(self, api_key: str = None, model_config: Dict[str, Any] = None):
        """Initialize ClaudeModel with Anthropic API key"""
        super().__init__("claude-3-5-haiku-20241022", model_config or {})
        self.api_key = api_key or os.getenv('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError("Anthropic API key not provided")
            
        self.client = Anthropic(api_key=self.api_key)
        self.temperature = 0
        self.request_pool = RequestPool()  # Add request pooling
        self.model = "claude-3-5-haiku-20241022"  # Set the specific model name
        
        # Setup logging for skipped tasks
        self.output_dir = Path("results/skipped_tasks")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.skipped_logger = logging.getLogger('skipped_tasks')
        handler = logging.FileHandler(self.output_dir / 'skipped_tasks.log')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.skipped_logger.addHandler(handler)
        self.skipped_logger.setLevel(logging.INFO)
        
        # Default system prompt
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
        
    def _clean_html(self, html: str) -> str:
        """Keep only relevant semantic HTML elements and attributes for content analysis."""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Define elements we want to keep
        allowed_elements = {
            'div', 'span', 'p', 'a', 'button', 'input', 'select', 'option',
            'form', 'label', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'nav',
            'header', 'footer', 'main', 'section', 'article', 'aside',
            'ul', 'ol', 'li', 'table', 'tr', 'td', 'th', 'thead', 'tbody',
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
            
        return str(soup)

    def parse_task(self, task: Dict[str, Any], page_html: str = None) -> Optional[WebInteraction]:
        """Parse task using Claude to understand the interaction."""
        # Clean HTML if provided
        if page_html:
            page_html = self._clean_html(page_html)
            
        # Construct prompt
        user_prompt = f"""Task: {task['task']}
Current Page HTML: {page_html if page_html else 'Not available'}

Based on the task description and current page HTML, generate a web interaction as a JSON object."""

        try:
            # Wait for rate limit if needed
            while not self.request_pool.can_make_request():
                time.sleep(1)
            self.request_pool.add_request()
            
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=self.temperature,
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            # Extract and parse the JSON response
            interaction_data = json.loads(response.content)
            return WebInteraction(
                action=interaction_data.get('action', 'click'),
                selector_type=interaction_data.get('selector_type', 'css'),
                selector_value=interaction_data.get('selector_value'),
                input_text=interaction_data.get('input_text'),
                description=task['task']
            )
        except Exception as e:
            print(f"Error in Claude task parsing: {str(e)}")
            return None

    def handle_error(self, task: Dict[str, Any], error: str) -> Optional[WebInteraction]:
        """Use Claude to understand and handle errors."""
        error_prompt = f"""Task: {task['task']}
Error: {error}

Based on the task and error message, suggest a new web interaction that might work better.
Respond with a JSON object following the same schema as before."""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=1024,
                temperature=self.temperature,
                system=self.system_prompt,
                messages=[
                    {"role": "user", "content": error_prompt}
                ]
            )
            
            interaction_data = json.loads(response.content)
            return WebInteraction(
                action=interaction_data.get('action', 'click'),
                selector_type=interaction_data.get('selector_type', 'css'),
                selector_value=interaction_data.get('selector_value'),
                input_text=interaction_data.get('input_text'),
                description=task['task']
            )
        except Exception as e:
            print(f"Error in Claude error handling: {str(e)}")
            return None

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
