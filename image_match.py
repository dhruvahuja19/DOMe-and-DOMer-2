import base64
import requests
from openai import OpenAI
import os


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

def compare_images(prompt, ground_truth_path, agent_image_path, note = None):
    # TODO: if the image is not there (the agent image path), then return False, "The agent did not generate an image"

    print (f"[DEBUG] Debugging the image output of this agent execution.")
    if not os.path.exists(agent_image_path):
        print (f"[DEBUG] The agent did not generate an image or generated the image with the wrong name or the wrong path.")
        return False, "The agent did not generate an image or generated the image with the wrong name or the wrong path."
    
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    image1 = encode_image(ground_truth_path)
    image2 = encode_image(agent_image_path)
    user_prompt = f"The agent was trying to accomplish the following task: {prompt} The first image is the expected image and the second image is the agent's output. Does the image answer the question correctly as the expected image? Don't focus on unnecessary details, like axes titles or colors or image size or labels unless specified in the task."
    if note:
        user_prompt += f"Here are some notes to help you evaluate the images: {note}"
    response = client.chat.completions.create(
        model="gpt-4o",
        temperature=0,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": user_prompt},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image1}"
                        }
                    },
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image2}"
                        }
                    }
                ]
            }
        ],
        max_tokens=300
    )
    print (f"[DEBUG] Response from the image comparison: {response.choices[0].message.content}")
    print (f"[DEBUG] Image Correctness: {response.choices[0].message.content.lower().strip() == 'true'}")
    return "true" in response.choices[0].message.content.lower().strip(), response.choices[0].message.content

