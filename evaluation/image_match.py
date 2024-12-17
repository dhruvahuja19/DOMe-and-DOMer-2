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
        return base64.b64encode(image_file.read()).decode('utf-8')

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

    image1 = encode_image(ground_truth_path)
    image2 = encode_image(agent_image_path)
    user_prompt = f"The agent was trying to accomplish the following task: {prompt} The first image is the expected image and the second image is the agent's output. Does the image answer the question correctly as the expected image? Don't focus on unnecessary details, like axes titles or colors or image size or labels unless specified in the task."
    if note:
        user_prompt += f"Here are some notes to help you evaluate the images: {note}"
    messages = [
        {"role": "system", "content": system_prompt},
        {
            "role": "user",
            "content": [
                {"type": "text", "text": user_prompt},
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
        max_tokens=500
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
