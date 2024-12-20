import json
import os
from pathlib import Path
from typing import Dict, List, Any, Optional
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

class DatasetCleaner:
    def __init__(self, results_file: str, api_key: Optional[str] = None):
        """Initialize the dataset cleaner.
        
        Args:
            results_file: Path to results.json file
            api_key: OpenAI API key (optional, will use environment variable if not provided)
        """
        self.results_file = Path(results_file)
        self.client = OpenAI(api_key=api_key)
        
    def analyze_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze a single result entry to determine if it's valid."""
        response = self.client.chat.completions.create(
            model="gpt-4-turbo",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert at analyzing web automation test results to determine if a test case is invalid.
A test case should be considered invalid if it encounters issues that make it unsuitable for benchmarking, such as:
1. CAPTCHA or verification challenges
2. Network or connection issues
3. Page timeouts or loading failures
4. Security blocks or authentication requirements
5. Missing or broken page elements
6. Browser crashes
7. Rate limiting or API errors
8. Geolocation restrictions"""
                },
                {
                    "role": "user",
                    "content": f"""Analyze this test result and determine if it should be excluded from benchmarking:

Task ID: {result['task_id']}
Success: {result['success']}
Error: {result.get('error', 'None')}
Task Description: {result['task_description']}
HTML Element: {result.get('html_element', 'None')}

Respond with a JSON object containing:
{{
    "is_valid": boolean,
    "reason": string explaining why the test case is invalid (if applicable),
    "confidence": float between 0 and 1
}}"""
                }
            ],
            response_format={"type": "json_object"}
        )
        
        return json.loads(response.choices[0].message.content)
        
    def clean_dataset(self, min_confidence: float = 0.8) -> Dict[str, List[str]]:
        """Clean the dataset by analyzing results.json entries.
        
        Args:
            min_confidence: Minimum confidence threshold for filtering (default: 0.8)
            
        Returns:
            Dictionary containing lists of valid and invalid test cases
        """
        results = {
            "valid": [],
            "invalid": []
        }
        
        # Load and process results.json
        with open(self.results_file) as f:
            test_results = json.load(f)
            
        for result in test_results:
            analysis = self.analyze_result(result)
            
            if analysis["is_valid"] or analysis["confidence"] < min_confidence:
                results["valid"].append(result["task_id"])
            else:
                results["invalid"].append({
                    "task_id": result["task_id"],
                    "reason": analysis["reason"],
                    "confidence": analysis["confidence"]
                })
        
        # Save results
        output_path = self.results_file.parent / "dataset_cleaning_results.json"
        with open(output_path, "w") as f:
            json.dump(results, f, indent=2)
            
        print(f"Dataset cleaning results saved to {output_path}")
        print(f"Valid test cases: {len(results['valid'])}")
        print(f"Invalid test cases: {len(results['invalid'])}")
        print("\nInvalid test cases and reasons:")
        for invalid in results["invalid"]:
            print(f"- {invalid['task_id']}: {invalid['reason']} (confidence: {invalid['confidence']:.2f})")
        
        return results

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Clean benchmark dataset by filtering invalid test cases")
    parser.add_argument("results_file", help="Path to results.json file")
    parser.add_argument("--min-confidence", type=float, default=0.8,
                       help="Minimum confidence threshold for filtering (default: 0.8)")
    parser.add_argument("--api-key", help="OpenAI API key (optional)")
    
    args = parser.parse_args()
    
    cleaner = DatasetCleaner(args.results_file, os.getenv("OPENAI_API_KEY"))
    results = cleaner.clean_dataset(min_confidence=args.min_confidence)
