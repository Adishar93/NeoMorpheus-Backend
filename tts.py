import requests

class TTS:
    def __init__(self, api_token):
        self.api_token = api_token

    def generate_audio(self, text):
        """
        Generate audio using the TTS API.

        Parameters:
            text (str): The text to convert to speech.

        Returns:
            bytes: The audio content if successful.
            None: If the request fails.
        """
        try:
            response = requests.post(
                'https://api.v7.unrealspeech.com/stream',
                headers={
                    'Authorization': f'Bearer {self.api_token}'
                },
                json={
                    'Text': text,
                    'VoiceId': 'Will',  # You can change this as needed
                    'Bitrate': '192k',
                    'Speed': '0',
                    'Pitch': '0.92',
                    'Codec': 'libmp3lame',
                }
            )

            response.raise_for_status()  # Raise an error for bad responses
            return response.content  # Return the audio content

        except Exception as e:
            print(f"Error generating audio: {str(e)}")
            return None
