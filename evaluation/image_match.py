import os
from openai import OpenAI
import http.server
import socketserver
import threading
import time
from pathlib import Path

system_prompt = """
You are evaluating if a web automation task achieved its intended final state. Your goal is to compare the final screenshot with the expected ground truth image.

Guidelines:
1. Focus on the FINAL STATE of the page, not the process
2. Compare key visual elements that indicate task completion:
   - For navigation: correct page/section is shown
   - For form inputs: text appears in the right field
   - For clicks: expected content/menu is visible
3. Ignore temporary visual elements like:
   - Loading indicators
   - Tooltips
   - Hover states
   - Transition animations
4. Don't try to verify the action being taken, only the end result
5. Minor visual differences (e.g., slight layout shifts, different ads) are acceptable

Your output should be in the following format:
Correctness: [True/False]
Reason: [Explain if the final state matches the expected outcome, focusing on key visual indicators of task completion]
"""

class ImageServer:
    def __init__(self, port=8000):
        self.port = port
        self.server = None
        self.thread = None
        
    def start(self):
        # Create a temporary directory for serving images
        self.temp_dir = Path("temp_images")
        self.temp_dir.mkdir(exist_ok=True)
        
        # Set up a simple HTTP server
        handler = http.server.SimpleHTTPRequestHandler
        self.server = socketserver.TCPServer(("", self.port), handler)
        
        # Run server in a separate thread
        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        
    def stop(self):
        if self.server:
            self.server.shutdown()
            self.server.server_close()
        if self.thread:
            self.thread.join()
            
    def get_url(self, image_path):
        # Copy image to temp directory with a unique name
        unique_name = f"{int(time.time())}_{os.path.basename(image_path)}"
        temp_path = self.temp_dir / unique_name
        
        # Copy the file
        with open(image_path, 'rb') as src, open(temp_path, 'wb') as dst:
            dst.write(src.read())
            
        return f"http://localhost:{self.port}/temp_images/{unique_name}"

def get_base64_image(image_path):
    """Convert image to base64 string."""
    import base64
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

def compare_images(prompt, ground_truth_path, agent_image_path, note=None, openai_client=None):
    if openai_client is None:
        raise ValueError("OpenAI client must be provided")
        
    if not os.path.exists(agent_image_path):
        return False, "Agent did not generate an image or wrong path"
    
    try:
        # Convert images to base64
        ground_truth_b64 = get_base64_image(ground_truth_path)
        agent_image_b64 = get_base64_image(agent_image_path)
        
        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user", 
                "content": [
                    {
                        "type": "text", 
                        "text": f"Task: {prompt}\n" + (f"Note: {note}\n" if note else "")
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{ground_truth_b64}",
                            "detail": "low"
                        }
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/png;base64,{agent_image_b64}",
                            "detail": "low"
                        }
                    }
                ]
            }
        ]
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
        )
        
        response_text = response.choices[0].message.content
        if "Correctness: True" in response_text:
            return True, response_text
        else:
            return False, response_text
            
    except Exception as e:
        return False, f"Error comparing images: {str(e)}"
