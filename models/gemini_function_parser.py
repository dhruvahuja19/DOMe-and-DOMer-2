import re
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

    @staticmethod
    def extract_web_interaction(text: str) -> Optional[Dict[str, Any]]:
        """
        Extract web interaction details from Gemini's text output.
        Expected format:
        <interaction>
        {
            "action": "click|type|hover",
            "selector_type": "css|xpath|id|class",
            "selector_value": "string",
            "input_text": "string",
            "description": "string"
        }
        </interaction>
        """
        pattern = r'<interaction>\s*(\{[\s\S]*?\})\s*</interaction>'
        
        match = re.search(pattern, text)
        if not match:
            return None
            
        try:
            interaction_str = match.group(1).strip()
            return eval(interaction_str)  # Using eval since the dict might contain single quotes
        except Exception as e:
            print(f"Error parsing interaction: {str(e)}")
            return None
