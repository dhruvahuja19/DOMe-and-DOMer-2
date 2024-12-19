import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

system_prompt = """
You are evaluating if a web automation task was completed successfully. Compare the HTML elements and determine if the task's goal was achieved, focusing on the relevant HTML changes that indicate success.

Your output should be in the following format:
Correctness: [True/False]
Reason: [Reason for the correctness/incorrectness of the agent's output]
"""

def fuzzy_match_html(
    task_description: str,
    actual_html: str,
    expected_html: str,
    note: str = None,
    openai_client: OpenAI = None
) -> tuple[bool, str]:
    """Compare HTML elements using GPT-4 for semantic understanding"""
    
    if openai_client is None:
        raise ValueError("OpenAI client must be provided")
    
    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user", 
                "content": f"""Task: {task_description}

Expected HTML:
{expected_html}

Actual HTML:
{actual_html}

Additional Context: {note}"""
            } if note else {
                "role": "user", 
                "content": f"""Task: {task_description}

Expected HTML:
{expected_html}

Actual HTML:
{actual_html}"""
            }
        ]
        
        # Truncate inputs if too long
        max_html_length = 2000  # Characters per HTML string
        max_task_length = 500   # Characters for task description
        
        if len(actual_html) > max_html_length:
            actual_html = actual_html[:max_html_length] + "..."
            
        if len(expected_html) > max_html_length:
            expected_html = expected_html[:max_html_length] + "..."
            
        if len(task_description) > max_task_length:
            task_description = task_description[:max_task_length] + "..."
            
        response = openai_client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            max_tokens=300,
        )
        
        output = response.choices[0].message.content
        correctness = "True" in output.split("\n")[0]
        reason = "\n".join(output.split("\n")[1:])
        
        return correctness, reason.replace("Reason: ", "").strip()
        
    except Exception as e:
        return False, f"Error comparing HTML: {str(e)}"
