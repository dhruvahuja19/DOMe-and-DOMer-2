import base64
import requests
from openai import OpenAI
import os
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

from dotenv import load_dotenv
load_dotenv()

system_prompt = """
A task required an agent to create an image based on a prompt and your task is to compare the image it generated with the image it was supposed to generate. 

Your output should be in the following format:
Correctness: [True/False]
Reason: [Reason for the correctness/incorrectness of the agent's output]

"""

def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        image_data = image_file.read()
        # Check file size (max 20MB)
        if len(image_data) > 20 * 1024 * 1024:
            raise ValueError(f"Image {image_path} is too large (>20MB)")
        return base64.b64encode(image_data).decode('utf-8')

def compare_images(prompt, ground_truth_path, agent_image_path, note = None, openai_client = None):
    if openai_client is None:
        raise ValueError("OpenAI client must be provided")
        
    print("\n=== Visual Task Evaluation ===")
    print(f"Task Description: {prompt}")
    if note:
        print(f"Additional Context: {note}")
    print(f"Agent's Image: {agent_image_path}")
    print(f"Ground Truth Image: {ground_truth_path}")
    
    print (f"[DEBUG] Debugging the image output of this agent execution.")
    if not os.path.exists(agent_image_path):
        print (f"[DEBUG] The agent did not generate an image or generated the image with the wrong name or the wrong path.")
        return False, "The agent did not generate an image or generated the image with the wrong name or the wrong path."
    
    logger.debug("Using provided OpenAI client")
    client = openai_client

    try:
        image1 = encode_image(ground_truth_path)
        image2 = encode_image(agent_image_path)
    except ValueError as e:
        logger.error(f"Image encoding error: {str(e)}")
        return False, f"Image processing error: {str(e)}"
        
    # Truncate prompt if too long
    max_prompt_length = 500
    if len(prompt) > max_prompt_length:
        prompt = prompt[:max_prompt_length] + "..."
        
    user_prompt = f"The agent was trying to accomplish the following task: {prompt} The first image is the expected image and the second image is the agent's output. Does the image answer the question correctly as the expected image? Don't focus on unnecessary details, like axes titles or colors or image size or labels unless specified in the task."
    if note:
        # Truncate note if too long
        if len(note) > 200:
            note = note[:200] + "..."
        user_prompt += f"Here are some notes to help you evaluate the images: {note}"
    messages = [
        {
            "role": "system",
            "content": """You are evaluating if a web automation task was completed successfully. Compare the screenshots and determine if the task's goal was achieved, focusing on the relevant UI changes that indicate success.

Return a JSON object with:
- correctness (boolean): Whether the task was completed successfully
- reason (string): Clear explanation of your evaluation"""
        },
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": user_prompt
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image1}"}
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/jpeg;base64,{image2}"}
                }
            ]
        }
    ]
    response = client.chat.completions.create(
        model="gpt-4-turbo", 
        messages=messages,
    )
    
    print("\n=== Judge's Visual Evaluation ===")
    print(f"Judge's Response: {response.choices[0].message.content}")
    print("===============================\n")
    
    logger.debug("GPT-4V Response for Image Comparison:")
    logger.debug(f"Prompt: {prompt}")
    logger.debug(f"Response: {response.choices[0].message.content}")
    print (f"[DEBUG] Response from the image comparison: {response.choices[0].message.content}")
    print (f"[DEBUG] Image Correctness: {response.choices[0].message.content.lower().strip() == 'true'}")
    return "true" in response.choices[0].message.content.lower().strip(), response.choices[0].message.content
