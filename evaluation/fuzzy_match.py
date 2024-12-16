import os
from openai import OpenAI
from typing import Tuple

def fuzzy_match_html(
    task_description: str,
    actual_html: str,
    expected_html: str,
    note: str = None,
) -> Tuple[bool, str]:
    """Compare HTML elements using GPT-4 for semantic understanding"""
    openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
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
    
    response = openai.chat.completions.create(
        model="gpt-4",
        messages=messages,
        max_tokens=400,
        temperature=0.0,
        stream=False
    )
    
    content = response.choices[0].message.content
    is_match = "true" in content.lower().strip()
    
    return is_match, content
