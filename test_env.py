from dotenv import load_dotenv, find_dotenv
import os
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def test_api_key():
    # Check if OPENAI_API_KEY is already in environment before loading .env
    api_key_before = os.getenv("OPENAI_API_KEY")
    print(f"API key before loading .env: {api_key_before}")
    
    # Find all possible .env files
    env_path = find_dotenv()
    print(f"\nFound .env file at: {env_path}")
    
    # Load the .env file
    load_dotenv(env_path)
    
    # Get API key after loading .env
    api_key_after = os.getenv("OPENAI_API_KEY")
    print(f"\nAPI key after loading .env: {api_key_after}")
    
    # Check for .env in different directories
    possible_locations = [
        os.path.join(os.getcwd(), '.env'),
        os.path.join(os.path.expanduser('~'), '.env'),
        os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env')
    ]
    
    print("\nChecking possible .env locations:")
    for loc in possible_locations:
        if os.path.exists(loc):
            print(f"Found .env at: {loc}")
            with open(loc, 'r') as f:
                content = f.read().strip()
                print(f"Content starts with: {content[:50]}...")
        else:
            print(f"No .env at: {loc}")
    
    # Print all environment variables starting with OPENAI
    print("\nAll OPENAI-related environment variables:")
    for key, value in os.environ.items():
        if 'OPENAI' in key:
            print(f"{key}: {value}")

if __name__ == "__main__":
    test_api_key()
