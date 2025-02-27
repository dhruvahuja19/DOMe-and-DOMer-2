import json
import time
import re
import logging
import tiktoken
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import google.generativeai as genai
from bs4 import BeautifulSoup
from .base import BaseModel, WebInteraction, TaskResult
from .gemini_function_parser import FunctionParser

class GeminiModel(BaseModel):
    """Gemini model implementation for the DOM benchmark."""
    
    def __init__(self, api_key: str, model_config: Dict[str, Any] = None):
        super().__init__("gemini-1.5-pro", model_config or {})
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel('gemini-1.5-pro')
        self.max_retries = 10
        self.temperature = model_config.get("temperature", 0)
        self.max_tokens = 32000
        # Use GPT-4 tokenizer as an approximation since Gemini uses similar tokenization
        self.tokenizer = tiktoken.encoding_for_model("gpt-4")
        self.function_parser = FunctionParser()
        
        # Setup logging for skipped tasks
        self.output_dir = Path("results/skipped_tasks")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.skipped_logger = logging.getLogger('skipped_tasks_gemini')
        handler = logging.FileHandler(self.output_dir / 'skipped_tasks_gemini.log')
        handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.skipped_logger.addHandler(handler)
        self.skipped_logger.setLevel(logging.INFO)
        
        # Enhanced system prompt for function-like output
        self.system_prompt = """You are an AI assistant that helps users interact with web elements.
Your task is to understand the user's intent and generate precise web element interactions.

For each task, analyze:
1. The user's goal and required interaction (click, type, hover)
2. The target element's properties and accessibility
3. Any constraints or special conditions

Generate your response in the following format:
<interaction>
{
    "action": "click|type|hover",
    "selector_type": "css|xpath|id|class",
    "selector_value": "string",
    "input_text": "string",  # For type actions
    "description": "string"  # Optional description of the interaction
}
</interaction>

If you need to perform additional actions, use the following format:
<tool>function_name</tool>
<args>
{
    "argument1": "value1",
    "argument2": "value2"
}
</args>"""

    def _clean_html(self, html: str) -> str:
        """Remove all JavaScript and CSS from HTML to reduce size."""
        # First use BeautifulSoup for robust HTML parsing
        soup = BeautifulSoup(html, "html.parser")
        
        # Remove script tags and their contents
        for script in soup.find_all('script'):
            script.decompose()
        
        # Remove style tags and their contents
        for style in soup.find_all('style'):
            style.decompose()
            
        # Remove link tags for stylesheets
        for link in soup.find_all('link', rel="stylesheet"):
            link.decompose()
            
        # Remove all style attributes
        for tag in soup.find_all():
            if tag.has_attr('style'):
                del tag['style']
                
        # Get the cleaned HTML
        cleaned_html = str(soup)
        
        # Additional regex-based cleaning for things BeautifulSoup might miss
        # Remove noscript tags and their contents
        cleaned_html = re.sub(r'<noscript\b[^<]*(?:(?!<\/noscript>)<[^<]*)*<\/noscript>', '', cleaned_html)
        
        # Remove template tags (often used by JS frameworks)
        cleaned_html = re.sub(r'<template\b[^<]*(?:(?!<\/template>)<[^<]*)*<\/template>', '', cleaned_html)
        
        # Remove preloaded resources
        cleaned_html = re.sub(r'<link[^>]*rel="preload"[^>]*>', '', cleaned_html)
        
        # Remove meta tags with CSS/JS content
        cleaned_html = re.sub(r'<meta[^>]*http-equiv="Content-Style-Type"[^>]*>', '', cleaned_html)
        cleaned_html = re.sub(r'<meta[^>]*http-equiv="Content-Script-Type"[^>]*>', '', cleaned_html)
        
        # Remove inline event handlers
        cleaned_html = re.sub(r'\son\w+="[^"]*"', '', cleaned_html)
        
        # Remove javascript: URLs
        cleaned_html = re.sub(r'href="javascript:[^"]*"', '', cleaned_html)
        
        # Remove data attributes (often used for JS functionality)
        cleaned_html = re.sub(r'\sdata-[a-zA-Z0-9\-_]+="[^"]*"', '', cleaned_html)
        
        # Remove framework-specific attributes
        cleaned_html = re.sub(r'\s(?:ng|v|x)-[a-zA-Z0-9\-_]+="[^"]*"', '', cleaned_html)
        
        # Remove old-style HTML styling attributes
        attrs_to_remove = ['align', 'bgcolor', 'border', 'cellpadding', 'cellspacing', 
                          'color', 'face', 'height', 'hspace', 'marginheight', 'marginwidth',
                          'size', 'valign', 'vspace', 'width']
        for attr in attrs_to_remove:
            cleaned_html = re.sub(fr'\s{attr}="[^"]*"', '', cleaned_html)
        
        return cleaned_html

    def _call_api(self, messages: list, retry_count: int = 0) -> Tuple[Optional[dict], bool]:
        """Helper method to call Gemini API with retry logic."""
        try:
            # Convert messages to Gemini format
            prompt = ""
            for msg in messages:
                role_prefix = "System: " if msg["role"] == "system" else "User: " if msg["role"] == "user" else "Assistant: "
                prompt += f"{role_prefix}{msg['content']}\n\n"

            # Add explicit instruction for JSON output
            prompt += "\nPlease respond with a valid JSON object following the specified format."

            response = self.model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=self.temperature,
                    max_output_tokens=self.max_tokens
                )
            )
            
            # Ensure the response was generated successfully
            if not response.parts:
                raise Exception("Empty response from Gemini")
                
            return response, False
        except Exception as e:
            if any(err in str(e).lower() for err in ["too_long", "length", "token limit"]):
                # Count tokens in the messages
                total_tokens = len(self.tokenizer.encode(prompt))
                self.skipped_logger.info(
                    f"Context length exceeded - Token count: {total_tokens} (limit: 2000000), "
                    f"Error: {str(e)}"
                )
            
            if retry_count >= self.max_retries:
                print(f"Max retries ({self.max_retries}) exceeded. Error: {str(e)}")
                return None, True
                
            wait_time = min(2 ** retry_count, 8)
            print(f"API call failed, retrying in {wait_time}s. Error: {str(e)}")
            time.sleep(wait_time)
            return self._call_api(messages, retry_count + 1)

    def parse_task(self, task: Dict[str, Any], page_html: str = None) -> Optional[WebInteraction]:
        """Parse task using Gemini to understand the interaction."""
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
        if total_tokens > 2000000:  
            self.skipped_logger.info(
                f"Task skipped due to length - URL: {task.get('url', 'N/A')}, "
                f"Task: {task.get('task', 'N/A')}, "
                f"Token count: {total_tokens} (limit: 2000000)"
            )
            return None  # Skip the task instead of using ground truth
            
        response, error = self._call_api(messages)
        if error or not response:
            return None  # Skip on API errors instead of using ground truth
            
        try:
            # Parse the response text to extract interaction details
            interaction_data = self.function_parser.extract_web_interaction(response.text)
            if not interaction_data:
                raise ValueError("No valid interaction found in response")
            
            return WebInteraction(
                action=interaction_data.get('action', task.get('interaction', 'click')).lower(),
                selector_type=interaction_data.get('selector_type', task['target_element']['type']).lower(),
                selector_value=interaction_data.get('selector_value', task['target_element']['value']),
                input_text=interaction_data.get('input_text', task.get('input_text')),
                description=task.get('task')
            )
        except Exception as e:
            print(f"Error parsing Gemini response: {str(e)}")
            return self._create_fallback_interaction(task)

    def _create_fallback_interaction(self, task: Dict[str, Any]) -> Optional[WebInteraction]:
        """Create a fallback interaction when API calls or parsing fails."""
        # Don't use ground truth, just skip the task
        return None

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
4. For hover: is the element hoverable?
5. Are there any prerequisite steps missing?

Generate a modified interaction as a JSON object or respond with "GIVE UP" if unrecoverable."""

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        response, error = self._call_api(messages)
        if error or not response:
            return self.parse_task(task)
            
        suggestion = response.text.strip()
        if suggestion == "GIVE UP":
            return None
            
        try:
            interaction_data = json.loads(suggestion)
            
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
            
        validation_result = response.text.strip()
        
        if validation_result.startswith("YES"):
            return True
        else:
            failure_reason = validation_result.replace("NO", "").strip()
            if failure_reason:
                print(f"Validation failed: {failure_reason}")
            return False