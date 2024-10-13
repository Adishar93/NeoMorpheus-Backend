# firebase_handler.py
import firebase_admin
from firebase_admin import credentials, storage
import os

class FirebaseHandler:
    def __init__(self, firebase_cred_path, firebase_bucket_name):
        """
        Initializes the FirebaseHandler with the provided credentials and bucket name.
        
        Parameters:
            firebase_cred_path (str): Path to Firebase Service Account JSON.
            firebase_bucket_name (str): Name of the Firebase Storage bucket.
        """
        # Initialize Firebase Admin SDK
        cred = credentials.Certificate(firebase_cred_path)
        firebase_admin.initialize_app(cred, {
            'storageBucket': firebase_bucket_name
        })
        self.bucket = storage.bucket()

    def upload_to_firebase(self, file_name, file_path):
        """
        Uploads a file to Firebase Storage and returns the public URL.
        
        Parameters:
            file_name (str): The name to give the file in Firebase.
            file_path (str): The local path to the file to upload.
        
        Returns:
            str: The public URL of the uploaded file.
        """
        blob = self.bucket.blob(file_name)
        blob.upload_from_filename(file_path)
        blob.make_public()  # Make the file publicly accessible

        return blob.public_url

    def delete_local_file(self, file_path):
        """
        Deletes a local file after it has been uploaded to Firebase.
        
        Parameters:
            file_path (str): The local path of the file to delete.
        """
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"Deleted local file: {file_path}")
        else:
            print(f"File not found: {file_path}")