import os
import logging
from openai import OpenAI
from typing import Tuple
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def fuzzy_match_html(
    task_description: str,
    actual_html: str,
    expected_html: str,
    note: str = None,
    openai_client: OpenAI = None
) -> Tuple[bool, str]:
    """Compare HTML elements using GPT-4 for semantic understanding"""
    
    if openai_client is None:
        raise ValueError("OpenAI client must be provided")
    
    print("\n=== HTML Task Evaluation ===")
    print(f"Task Description: {task_description}")
    print("Agent's HTML Output:")
    print(actual_html)
    print("\nExpected HTML:")
    print(expected_html)
    if note:
        print(f"\nAdditional Context: {note}")
    
    # Debug logging for API key handling
    logger.debug("Using provided OpenAI client")
    
    client = openai_client
    
    user_prompt = f"""You are evaluating if an HTML element matches the expected element for the following task: {task_description}

Expected HTML: {expected_html}
Actual HTML: {actual_html}

Consider:
1. Element type (tag name)
2. Key attributes (id, class, etc.)
3. Content and inner HTML
4. Role and accessibility attributes

Your response should be in the following format:

Correctness: [True/False]
Reason: [Detailed explanation of why the elements match or don't match]

Respond True if:
1. The element types match
2. Essential attributes match (even if some dynamic attributes differ)
3. The content serves the same purpose
4. The element would function the same way for users"""

    if note:
        user_prompt += f"\n\nAdditional evaluation criteria: {note}"
    
    messages = [
        {
            "role": "system", 
            "content": "You are an expert in HTML and web accessibility, evaluating if HTML elements match in functionality and purpose."
        },
        {"role": "user", "content": user_prompt},
    ]
    
    response = client.chat.completions.create(
        model="gpt-4",
        messages=messages,
        temperature=0,
        stream=False
    )
    
    print("\n=== Judge's HTML Evaluation ===")
    print(f"Judge's Response: {response.choices[0].message.content}")
    print("==============================\n")
    
    logger.debug("GPT-4 Response for HTML Comparison:")
    logger.debug(f"Task: {task_description}")
    logger.debug(f"Response: {response.choices[0].message.content}")
    
    content = response.choices[0].message.content
    is_match = "true" in content.lower().strip()
    
    return is_match, content
