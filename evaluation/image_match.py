import os
from openai import OpenAI
import http.server
import socketserver
import threading
import time
from pathlib import Path

system_prompt = """
A task required an agent to create an image based on a prompt and your task is to compare the image it generated with the image it was supposed to generate. 

Your output should be in the following format:
Correctness: [True/False]
Reason: [Reason for the correctness/incorrectness of the agent's output]
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

def compare_images(prompt, ground_truth_path, agent_image_path, note=None, openai_client=None):
    if openai_client is None:
        raise ValueError("OpenAI client must be provided")
        
    if not os.path.exists(agent_image_path):
        return False, "Agent did not generate an image or wrong path"
    
    # Start temporary image server
    server = ImageServer()
    server.start()
    
    try:
        # Get URLs for both images
        ground_truth_url = server.get_url(ground_truth_path)
        agent_image_url = server.get_url(agent_image_path)
        
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
                            "url": ground_truth_url,
                            "detail": "low"
                        }
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": agent_image_url,
                            "detail": "low"
                        }
                    }
                ]
            }
        ]
        
        response = openai_client.chat.completions.create(
            model="gpt-4-vision-preview",
            messages=messages,
            max_tokens=300,
        )
        
        output = response.choices[0].message.content
        correctness = "True" in output.split("\n")[0]
        reason = "\n".join(output.split("\n")[1:])
        
        return correctness, reason.replace("Reason: ", "").strip()
        
    except Exception as e:
        return False, f"Error comparing images: {str(e)}"
    finally:
        # Clean up
        server.stop()
        # Remove temporary files
        for file in server.temp_dir.glob("*"):
            file.unlink()
        server.temp_dir.rmdir()
