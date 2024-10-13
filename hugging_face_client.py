# huggingface_client.py

import requests

class HuggingFaceClient:
    def __init__(self, api_key):
        """
        Initializes the HuggingFaceClient class with the provided API key.
        
        Parameters:
            api_key (str): The API key for authenticating with Hugging Face.
        """
        self.api_key = api_key
        self.base_url = "https://api-inference.huggingface.co/models"

    def generate_image(self, input_text, model_name):
        """
        Generate an image using a Hugging Face model API.
        
        Parameters:
            input_text (str): The input prompt for image generation.
            model_name (str): The name of the Hugging Face model to use.
        
        Returns:
            bytes: The image data if the request is successful.
            None: If the request fails.
        """
        # Set the authorization headers
        headers = {
            'Authorization': f'Bearer {self.api_key}'
        }

        # Prepare the request payload
        json_data = {
            'inputs': input_text,
        }

        try:
            # Send a POST request to the Hugging Face model API
            response = requests.post(
                f'{self.base_url}/{model_name}',
                headers=headers,
                json=json_data
            )

            # Check for successful response
            if response.status_code == 200:
                # Return the image data if successful
                return response.content
            else:
                # Log error message if the request fails
                print(f"Error: Received status code {response.status_code}")
                print(f"Response: {response.json()}")
                return None
        except Exception as e:
            # Handle exceptions and log error message
            print(f"An error occurred: {str(e)}")
            return None