from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_bcrypt import Bcrypt
from config import Config
from kindo_api import KindoAPI
from hugging_face_client import HuggingFaceClient 
from firebase_handler import FirebaseHandler
from tts import TTS
import time
import re
import threading
import uuid

app = Flask(__name__)
app.config["MONGO_URI"] = Config.MONGO_URI

firebase_cred_path = "morpheus-key.json"
firebase_bucket_name = "morpheus-grin.appspot.com"

# Initialize KindoAPI
mongo = PyMongo(app)
bcrypt = Bcrypt(app)

# Initialize KindoAPI with the API key from the config file
kindo_api = KindoAPI(api_key=Config.KINDO_API_KEY)
hf_client = HuggingFaceClient(Config.HUGGING_FACE_API_KEY)
firebase_handler = FirebaseHandler(firebase_cred_path, firebase_bucket_name)
tts = TTS(Config.TTS_KEY)


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

    # Call Kindo API with RabbitNeo model and the prompt
    model_name = '/models/WhiteRabbitNeo-33B-DeepSeekCoder'
    prompt = f"Give me information on {input_prompt}"
    messages = [{"role": "user", "content": prompt}]
    response = kindo_api.call_kindo_api(model=model_name, messages=messages, max_tokens=500)
    white_rabbit_knowledge_text = ""
    if 'error' not in response:
        white_rabbit_knowledge_text = response.json()['choices'][0]['message']['content']
    else:
        print(f"API call failed: {response['error']}, details: {response.get('details')}")
        time.sleep(5)
        process_slides(input_prompt, course_id, username)
        return

    model_name = 'azure/gpt-4o'
    # Find the user in the MongoDB database
    user = mongo.db.users.find_one({'username': username})

    if not user:
        return jsonify({"error": "User not found"}), 404

    # Extract the user's age and whether they are a cybersecurity professional
    age = user.get('age')
    is_professional = user.get('working_cybersecurity_professional', False)
    professional_status = "a cybersecurity professional" if is_professional else "not a cybersecurity professional"
    prompt = f"Generate a well designed course as paragraphs on topic '{input_prompt}' curated for someone who is {age} years old and {professional_status} based on the following information:\n{white_rabbit_knowledge_text}"
    messages = [{"role": "user", "content": prompt}]

    response = kindo_api.call_kindo_api(model=model_name, messages=messages, max_tokens=500)
    presentation_text = response.json()['choices'][0]['message']['content']
    mongo.db.course_text.insert_one({course_id:presentation_text})
    print(presentation_text)
    
    # Split the presentation text into slides
    slides = presentation_text.split('\n\n')

    # Remove '**' from each slide and filter out slides without any alphabetic characters
    slides = [
    slide.replace('**', '').strip()  # Remove '**' and strip whitespace
    for slide in slides if re.search(r'[a-zA-Z]', slide)  # Keep slides that contain at least one alphabet
    ]

    # Remove empty or whitespace-only strings
    slides = [slide for slide in slides if slide.strip()]

    # Save the course data in MongoDB
    course_data = {
        "courseId": course_id,
        "title": input_prompt.capitalize(),
        "totalSlides": len(slides),
        "slides": [],
    }

    mongo.db.coursecontent.insert_one(
            course_data
    )

    # Update user presentation mapping
    mongo.db.user_presentation.update_one(
        {"username": username},
        {"$addToSet": {"courseIds": course_id}},  # Use $addToSet to avoid duplicates
        upsert=True
    )
    # Process each slide content and update MongoDB
    for slide_number, slide_content in enumerate(slides):
        prompt = f"Create a brief prompt for an image generative model to create an image related to this content with no extra text:'{slide_content}'"
        messages = [{"role": "user", "content": prompt}]
        model_name = 'azure/gpt-4o-mini'
        response = kindo_api.call_kindo_api(model=model_name, messages=messages, max_tokens=50)
        image_prompt = response.json()['choices'][0]['message']['content']
        print("Image prompt generated by gpt-4o-mini: "+str(image_prompt))

        public_url="https://firebasestorage.googleapis.com/v0/b/morpheus-grin.appspot.com/o/istockphoto-1409329028-612x612.jpg?alt=media&token=49ee18cf-7c68-4b0a-b5a1-6b6dcaa99e41"
        
        if image_prompt:
            model_name = "CompVis/stable-diffusion-v1-4"
            image_data = hf_client.generate_image(image_prompt, model_name)
            if image_data:
                # Step 2: Save the image temporarily
                file_name = f"{input_prompt.replace(' ', '_')}{slide_number}.png"
                local_file_path = f"./tmp/{file_name}"

                with open(local_file_path, "wb") as file:
                    file.write(image_data)

                # Step 3: Upload the image to Firebase
                public_url = firebase_handler.upload_to_firebase(file_name, local_file_path)

                # Step 4: Clean up local file
                firebase_handler.delete_local_file(local_file_path)
                
                print(f"Image URL: {public_url}")
            else:
                print("Image generation failed.")
                return None

        # Update course data
        slide_data = {
            "slideNumber": slide_number + 1,
            "content": slide_content,
            "images": [public_url],  # Placeholder for image URLs
            "audio": ""    # Placeholder for audio file URL
        }
        course_data["slides"].append(slide_data)
        # Save to coursecontent collection
        # Update or insert slide data in MongoDB
        # Assuming 'course_id' is defined and uniquely identifies the course
        mongo.db.coursecontent.update_one(
            {"courseId": course_id},  # Filter for the course
            {"$push": {"slides": slide_data}},  # Add the new slide to the slides array
            upsert=True  # Create the course document if it doesn't exist
        )
        
        # Optionally, you can also log or print the slide data for debugging
        print(f"Processed slide {slide_number + 1}: {slide_content}")
    

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

    slides_generated = sum(1 for slide in course_data.get("slides", []) if slide)

    return jsonify({
        "courseId": course_id,
        "slidesGenerated": slides_generated,
        "totalSlides": course_data.get("totalSlides"),
        "status": "Completed" if slides_generated == course_data.get("totalSlides") else "In Progress"
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

@app.route('/api/courseids/<string:username>', methods=['GET'])
def get_course_ids(username):
    """
    Get the list of course IDs and their titles for a given username.

    Parameters:
        username (str): The username to query.

    Returns:
        JSON response containing course IDs and their titles or an error message.
    """
    # Fetch the user presentation document from MongoDB
    user_presentation = mongo.db.user_presentation.find_one({"username": username})

    if user_presentation:
        # Get the course IDs for the user
        course_ids = user_presentation.get("courseIds", [])

        # Retrieve titles for each course ID from coursecontent collection
        courses = []
        for course_id in course_ids:
            course = mongo.db.coursecontent.find_one({"courseId": course_id})
            if course:
                courses.append({
                    "courseId": course_id,
                    "title": course.get("title", "No Title Found")  # Use default message if title is missing
                })
        
        # Return the list of courses with their IDs and titles
        return jsonify(courses), 200
    else:
        # Return an error message if the user is not found
        return jsonify({"error": "User not found"}), 404


@app.route('/generate-tts', methods=['POST'])
def generate_tts():
     # Get the text input from the request
    data = request.json
    text = data.get('text')

    # Truncate text to 1000 characters if necessary
    if text:
        text = text[:1000]  # Keep only the first 1000 characters

    if not text:
        return jsonify({"error": "Text is required."}), 400

    # Generate MP3 using the TTS API
    audio_content = tts.generate_audio(text)

    if audio_content is None:
        return jsonify({"error": "Failed to generate audio."}), 500

    # Save the audio file locally
    file_name = f"{uuid.uuid4()}.mp3"
    local_file_path = f"./tmp/{file_name}"
    with open(local_file_path, 'wb') as f:
        f.write(audio_content)

    # Upload to Firebase and get public URL
    mp3_url = firebase_handler.upload_to_firebase(file_name, local_file_path)

    # Optionally delete the local file after upload
    firebase_handler.delete_local_file(local_file_path)

    return jsonify({"mp3_url": mp3_url}), 200

if __name__ == "__main__":
    app.run(debug=True)