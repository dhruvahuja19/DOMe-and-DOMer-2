import re
import json
from typing import Dict, Any, Optional, List, Tuple

class FunctionParser:
    """Parser for function calls in Gemini's text output"""
    
    @staticmethod
    def extract_function_calls(text: str) -> List[Dict[str, Any]]:
        """
        Extract function calls from Gemini's text output.
        Expected format:
        <tool>function_name</tool>
        <args>
        {
            "arg1": "value1",
            "arg2": "value2"
        }
        </args>
        """
        # Pattern to match function calls
        pattern = r'<tool>(.*?)</tool>\s*<args>\s*(\{[\s\S]*?\})\s*</args>'
        
        matches = re.finditer(pattern, text, re.MULTILINE)
        function_calls = []
        
        for match in matches:
            try:
                function_name = match.group(1).strip()
                args_str = match.group(2).strip()
                # Clean up the args string and parse as dict
                args = eval(args_str)  # Using eval since the args might contain single quotes
                
                function_calls.append({
                    "name": function_name,
                    "args": args
                })
            except Exception as e:
                print(f"Error parsing function call: {str(e)}")
                continue
                
        return function_calls

    def extract_web_interaction(self, response_text: str) -> dict:
        """Extract web interaction details from Gemini model response."""
        try:
            # Attempt to parse the response as JSON
            interaction_data = json.loads(response_text)
            return interaction_data
        except json.JSONDecodeError:
            # Log an error if parsing fails
            print("Failed to parse response as JSON")
            return {}

        # Additional parsing logic can be added here if needed
        return {}