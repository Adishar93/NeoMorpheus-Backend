from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from config import Config
from kindo_api import KindoAPI
import re

app = Flask(__name__)
app.config["MONGO_URI"] = Config.MONGO_URI
# Initialize KindoAPI

mongo = PyMongo(app)
bcrypt = Bcrypt(app)

# Initialize KindoAPI with the API key from the config file
kindo_api = KindoAPI(api_key=Config.KINDO_API_KEY)

# Signup API
@app.route('/api/signup', methods=['POST'])
def signup():
    data = request.get_json()
    if mongo.db.users.find_one({"username": data['username']}):
        return jsonify(success=False, message="User already exists"), 400
    
    hashed_password = bcrypt.generate_password_hash(data['password']).decode('utf-8')
    user_data = {
        "username": data['username'],
        "name": data['name'],
        "age": data['age'],
        "language": data['language'],
        "password": hashed_password,
        "working_professional": data['working_professional']
    }
    mongo.db.users.insert_one(user_data)
    return jsonify(success=True, message="Signup successful"), 201

# Login API
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    user = mongo.db.users.find_one({"username": data['username']})
    
    if user and bcrypt.check_password_hash(user['password'], data['password']):
        return jsonify(success=True, message="Login successful"), 200
    
    return jsonify(success=False, message="Invalid credentials"), 401


# Recommended Prompts API
@app.route('/api/recommended-prompts', methods=['GET'])
def get_recommended_prompts():
    # Get the username from query parameters
    username = request.args.get('username')

    # Find the user in the MongoDB database
    user = mongo.db.users.find_one({'username': username})

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Extract the user's age and whether they are a cybersecurity professional
    age = user.get('age')
    is_professional = user.get('working_cybersecurity_professional', False)

    # Create the prompt for Kindo API
    professional_status = "a cybersecurity professional" if is_professional else "not a cybersecurity professional"
    prompt = f"Generate 5 small topic names seperated by commas (make sure no extra text or formatting) in the cybersecurity domain appropriate for someone who is {age} years old and is {professional_status}."

    # Call Kindo API with the model and the prompt
    model_name = 'azure/gpt-4o'
    messages = [{"role": "user", "content": prompt}]
    response = kindo_api.call_kindo_api(model=model_name, messages=messages, max_tokens=50)
    print(response.json())

    # Check if the response is successful
    if response.status_code != 200:
        return {"error": "Failed to fetch recommendations from Kindo AI"}, response.status_code

    # Extract the generated content from Kindo API's response
    content = response.json()['choices'][0]['message']['content']

     # Split the content by commas
    topics = content.split(',')

    # Clean up the topics by trimming extra spaces
    topics = [topic.strip() for topic in topics]

    return {"recommendations": topics}, 200

if __name__ == "__main__":
    app.run(debug=True)
        # Call the Kindo API
    #response = kindo_api.call_kindo_api(model=model, messages=messages)