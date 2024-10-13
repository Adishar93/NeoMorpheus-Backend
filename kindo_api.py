import requests

class KindoAPI:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://llm.kindo.ai/v1/chat/completions"

    def call_kindo_api(self, model, messages, max_tokens, **kwargs):
        headers = {
            "api-key": self.api_key,
            "content-type": "application/json",
        }

        # Prepare the request payload
        data = {
            "model": model,
            "messages": messages,
            "max_tokens":max_tokens
        }

        # Add optional parameters if any
        data.update(kwargs)

        try:
            # Send the POST request
            response = requests.post(self.base_url, headers=headers, json=data)

            # Check for HTTP errors
            response.raise_for_status()

            # Return the JSON response if successful
            return response

        except requests.exceptions.HTTPError as http_err:
            # Handle HTTP error responses
            error_details = response.json() if response.content else {}
            print(f"HTTP error occurred: {http_err}, details: {error_details}")
            return {"error": str(http_err), "details": error_details}

        except Exception as err:
            # Handle other errors (network issues, etc.)
            print(f"An error occurred: {err}")
            return {"error": str(err)}
