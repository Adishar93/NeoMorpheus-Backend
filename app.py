from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from config import Config
from kindo_api import KindoAPI
import re
import threading

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
    prompt = f"Generate 3 small topic names then ':' and then their 100 character descriptions. Each seperated by '_' (make sure no extra text or formatting) in the cybersecurity domain appropriate for someone who is {age} years old and is {professional_status}."

    # Call Kindo API with the model and the prompt
    model_name = 'azure/gpt-4o'
    messages = [{"role": "user", "content": prompt}]
    response = kindo_api.call_kindo_api(model=model_name, messages=messages, max_tokens=150)
    print(response.json())

    # Check if the response is successful
    if response.status_code != 200:
        return {"error": "Failed to fetch recommendations from Kindo AI"}, response.status_code

    # Extract the generated content from Kindo API's response
    content = response.json()['choices'][0]['message']['content']

     # Split the content by commas
    topics = content.split('_')
    
    # Clean up the topics by trimming extra spaces
    topics = [topic.strip() for topic in topics]

    # Step 2: Initialize a dictionary to hold the key-value pairs
    key_value_dict = {}

    # Step 3: Iterate through each topic and split into key-value pairs
    for topic in topics:
        # Split each topic by the colon
        if ':' in topic:  # Check if there's a colon in the topic
            key, value = topic.split(':', 1)  # Split into key and value
            key_value_dict[key.strip()] = value.strip()  # Store in the dictionary

    return {"recommendations": key_value_dict}, 200

    # Background task to process slides and save to MongoDB
    def process_slides(input_prompt, course_id, username):
        # Call Kindo API with the model and the prompt
        model_name = '/models/WhiteRabbitNeo-33B-DeepSeekCoder'
        prompt = f"Give me information on {input_prompt}"
        messages = [{"role": "user", "content": prompt}]
        response = kindo_api.call_kindo_api(model=model_name, messages=messages, max_tokens=500)
        presentation_text = response.json()['choices'][0]['message']['content']
        print(presentation_text)
        
        # Split the presentation text into slides
        slides = presentation_text.splitlines()

        # Save the course data in MongoDB
        course_data = {
            "courseId": course_id,
            "slides": [],
        }

        # Process each slide content and update MongoDB
        for slide_number, slide_content in enumerate(slides):
            # Simulate slide processing (e.g., generating images, audio, etc.)
            # In production, you would add actual processing logic here
            # time.sleep(1)  # Simulating processing time for each slide

            # Update course data
            slide_data = {
                "slideNumber": slide_number + 1,
                "content": slide_content,
                "images": [],  # Placeholder for image URLs
                "audio": ""    # Placeholder for audio file URL
            }
            course_data["slides"].append(slide_data)
        
        # Save to coursecontent collection
        mongo.db.coursecontent.insert_one(course_data)
        
        # Update user presentation mapping
        mongo.db.user_presentation.update_one(
            {"username": username},
            {"$addToSet": {"courseIds": course_id}},  # Use $addToSet to avoid duplicates
            upsert=True
        )

    # 4.1 Start Presentation Generation
    @app.route('/api/start-presentation-generation', methods=['POST'])
    def start_presentation():
        data = request.json
        input_prompt = data.get("input")
        username = data.get("username")

        if not input_prompt or not username:
            return jsonify({"error": "Input prompt and username are required."}), 400

        # Generate a unique course ID
        course_id = str(uuid.uuid4())

        # Start background processing of slides
        threading.Thread(target=process_slides, args=(input_prompt, course_id, username)).start()
        
        return jsonify({"courseId": course_id}), 202  # Return immediately

    # 4.2 Get Slide Status
    @app.route('/api/slide-status/<course_id>', methods=['GET'])
    def get_slide_status(course_id):
        course_data = mongo.db.coursecontent.find_one({"courseId": course_id})

        if not course_data:
            return jsonify({"error": "Course not found."}), 404

        total_slides = len(course_data.get("slides", []))
        slides_generated = sum(1 for slide in course_data.get("slides", []) if slide)

        return jsonify({
            "courseId": course_id,
            "slidesGenerated": slides_generated,
            "totalSlides": total_slides,
            "status": "Completed" if slides_generated == total_slides else "In Progress"
        }), 200

    # 4.3 Get Slide
    @app.route('/api/slide/<course_id>/<int:slide_number>', methods=['GET'])
    def get_slide(course_id, slide_number):
        course_data = mongo.db.coursecontent.find_one({"courseId": course_id})

        if not course_data:
            return jsonify({"error": "Course not found."}), 404

        slides = course_data.get("slides", [])
        if slide_number < 1 or slide_number > len(slides):
            return jsonify({"error": "Slide not available."}), 404

        slide_data = slides[slide_number - 1]  # Adjust for zero-indexing
        return jsonify({
            "slideNumber": slide_data["slideNumber"],
            "content": slide_data["content"],
            "images": slide_data["images"],
            "audio": slide_data["audio"]
        }), 200

if __name__ == "__main__":
    app.run(debug=True)
        # Call the Kindo API
    #response = kindo_api.call_kindo_api(model=model, messages=messages)