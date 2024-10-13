import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Load MongoDB password from .env file
    MONGO_DB_PASSWORD = os.getenv('MONGO_DB_PASSWORD')
    
    # Create MongoDB connection URI using the password
    MONGO_URI = f"mongodb+srv://adishar93:{MONGO_DB_PASSWORD}@cluster0.jwcsneo.mongodb.net/morpheus?retryWrites=true&w=majority"
    
    # Load other configuration settings
    KINDO_API_KEY = os.getenv('KINDO_API_KEY')

    HUGGING_FACE_API_KEY = os.getenv('HUGGING_FACE_API_KEY')
