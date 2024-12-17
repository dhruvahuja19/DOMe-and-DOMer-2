from dotenv import load_dotenv
import os
from openai import OpenAI
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_openai_connection():
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logger.error("No API key found in environment")
        return
    
    logger.debug(f"Found API key starting with: {api_key[:7]}")
    
    try:
        client = OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": "Say hello"}],
            max_tokens=10
        )
        logger.info("Successfully connected to OpenAI API")
        logger.debug(f"Response: {response.choices[0].message.content}")
    except Exception as e:
        logger.error(f"Failed to connect to OpenAI API: {str(e)}")

if __name__ == "__main__":
    test_openai_connection()
