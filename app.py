from flask import Flask, request, jsonify
from flask_cors import CORS
import hashlib
import uuid
from datetime import datetime, timedelta
import jwt
from functools import wraps
import random
import os
from dotenv import load_dotenv
import requests  # For AI translation API
import tempfile  # For temporary file handling

# Azure imports
from azure.cosmos import CosmosClient
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions

# Azure AI imports
from azure.ai.textanalytics import TextAnalyticsClient
from azure.core.credentials import AzureKeyCredential

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)

# ============================================
# AZURE COSMOS DB CONNECTION
# ============================================
COSMOS_CONNECTION_STRING = os.getenv('COSMOS_CONNECTION_STRING')
cosmos_client = CosmosClient.from_connection_string(COSMOS_CONNECTION_STRING)
DATABASE_NAME = "pictor"

# Get database
database = cosmos_client.get_database_client(DATABASE_NAME)

# Get container clients
users_container = database.get_container_client("users")
posts_container = database.get_container_client("posts")
comments_container = database.get_container_client("comments")
likes_container = database.get_container_client("likes")
saves_container = database.get_container_client("saves")
follows_container = database.get_container_client("follows")

# ============================================
# AZURE BLOB STORAGE CONNECTION
# ============================================
BLOB_CONNECTION_STRING = os.getenv('BLOB_CONNECTION_STRING')
BLOB_CONTAINER_NAME = os.getenv('BLOB_CONTAINER_NAME', 'media')
blob_service_client = BlobServiceClient.from_connection_string(BLOB_CONNECTION_STRING)
blob_container_client = blob_service_client.get_container_client(BLOB_CONTAINER_NAME)

# ============================================
# AI: SENTIMENT ANALYSIS
# ============================================
AZURE_SENTIMENT_KEY = os.getenv('AZURE_SENTIMENT_KEY')
AZURE_SENTIMENT_ENDPOINT = os.getenv('AZURE_SENTIMENT_ENDPOINT')

def analyze_sentiment(text):
    """Analyze sentiment of a comment using Azure AI Language"""
    if not AZURE_SENTIMENT_KEY or not AZURE_SENTIMENT_ENDPOINT:
        print("Sentiment Analysis keys not configured")
        return {
            'sentiment': 'neutral',
            'confidence_scores': {'positive': 33, 'neutral': 34, 'negative': 33}
        }
    
    try:
        credential = AzureKeyCredential(AZURE_SENTIMENT_KEY)
        client = TextAnalyticsClient(
            endpoint=AZURE_SENTIMENT_ENDPOINT,
            credential=credential
        )
        
        documents = [text]
        response = client.analyze_sentiment(documents=documents)[0]
        
        return {
            'sentiment': response.sentiment,  # 'positive', 'neutral', 'negative', 'mixed'
            'confidence_scores': {
                'positive': round(response.confidence_scores.positive * 100),
                'neutral': round(response.confidence_scores.neutral * 100),
                'negative': round(response.confidence_scores.negative * 100)
            }
        }
    except Exception as e:
        print(f"Sentiment analysis error: {e}")
        return {
            'sentiment': 'neutral',
            'confidence_scores': {'positive': 33, 'neutral': 34, 'negative': 33}
        }


# ============================================
# AI: LANGUAGE TRANSLATION
# ============================================
TRANSLATOR_KEY = os.getenv('TRANSLATOR_KEY')
TRANSLATOR_REGION = os.getenv('TRANSLATOR_REGION', 'global')
TRANSLATOR_ENDPOINT = os.getenv('TRANSLATOR_ENDPOINT', 'https://api.cognitive.microsofttranslator.com')

def translate_text(text, target_language='en'):
    """Translate text to target language using Azure Translator API"""
    if not TRANSLATOR_KEY:
        return text
    
    try:
        url = f"{TRANSLATOR_ENDPOINT}/translate?api-version=3.0&to={target_language}"
        
        headers = {
            'Ocp-Apim-Subscription-Key': TRANSLATOR_KEY,
            'Ocp-Apim-Subscription-Region': TRANSLATOR_REGION,
            'Content-Type': 'application/json'
        }
        
        body = [{'Text': text}]
        
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        
        result = response.json()
        translated_text = result[0]['translations'][0]['text']
        
        return translated_text
    except Exception as e:
        print(f"Translation error: {e}")
        return text


# ============================================
# AI: IMAGE CAPTIONING (Computer Vision)
# ============================================
CV_KEY = os.getenv('CV_KEY')
CV_ENDPOINT = os.getenv('CV_ENDPOINT')

def generate_image_caption(image_url):
    """Generate a caption for an image using Azure Computer Vision API"""
    if not CV_KEY or not CV_ENDPOINT:
        print("Computer Vision keys not configured")
        return None
    
    try:
        endpoint = CV_ENDPOINT.rstrip('/')
        url = f"{endpoint}/vision/v3.2/describe"
        
        headers = {
            'Ocp-Apim-Subscription-Key': CV_KEY,
            'Content-Type': 'application/json'
        }
        
        body = {'url': image_url}
        
        response = requests.post(url, headers=headers, json=body)
        response.raise_for_status()
        
        result = response.json()
        
        if result.get('description', {}).get('captions'):
            caption = result['description']['captions'][0]['text']
            confidence = result['description']['captions'][0]['confidence']
            return {
                'caption': caption,
                'confidence': confidence
            }
        
        return None
    except Exception as e:
        print(f"Image captioning error: {e}")
        return None


# ============================================
# JWT SECRET
# ============================================
app.config['SECRET_KEY'] = os.getenv('JWT_SECRET_KEY', 'your-super-secret-key-change-this')


# ============================================
# HELPER FUNCTIONS
# ============================================
def hash_value(value):
    return hashlib.sha256(value.encode()).hexdigest()

def generate_token(user_id, email, role):
    payload = {
        'user_id': user_id,
        'email': email,
        'role': role,
        'exp': datetime.utcnow() + timedelta(hours=24)
    }
    return jwt.encode(payload, app.config['SECRET_KEY'], algorithm='HS256')

def generate_sas_url(blob_name):
    """Generate SAS URL for frontend to upload directly to blob"""
    sas_token = generate_blob_sas(
        account_name=blob_service_client.account_name,
        container_name=BLOB_CONTAINER_NAME,
        blob_name=blob_name,
        account_key=blob_service_client.credential.account_key,
        permission=BlobSasPermissions(write=True, create=True),
        expiry=datetime.utcnow() + timedelta(hours=1)
    )
    return f"https://{blob_service_client.account_name}.blob.core.windows.net/{BLOB_CONTAINER_NAME}/{blob_name}?{sas_token}"


# ============================================
# DECORATOR TO VERIFY JWT TOKEN
# ============================================
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({'success': False, 'message': 'Token is missing'}), 401
        
        if token.startswith('Bearer '):
            token = token[7:]
        
        try:
            payload = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            request.current_user = payload
        except jwt.ExpiredSignatureError:
            return jsonify({'success': False, 'message': 'Token has expired'}), 401
        except jwt.InvalidTokenError:
            return jsonify({'success': False, 'message': 'Invalid token'}), 401
        
        return f(*args, **kwargs)
    return decorated


# ============================================
# AI TRANSLATION API ENDPOINT
# ============================================
@app.route('/api/translate', methods=['POST'])
@token_required
def translate():
    """Translate text to different language using Azure AI Translator"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Request body is empty'}), 400
    
    text = data.get('text')
    target_language = data.get('target_language', 'en')
    
    if not text:
        return jsonify({'success': False, 'message': 'text is required'}), 400
    
    translated_text = translate_text(text, target_language)
    
    return jsonify({
        'success': True,
        'original': text,
        'translated': translated_text,
        'target_language': target_language
    }), 200


# ============================================
# AI IMAGE CAPTIONING API ENDPOINT (for URL)
# ============================================
@app.route('/api/image/caption', methods=['POST'])
@token_required
def image_caption():
    """Generate caption for an image URL"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Request body is empty'}), 400
    
    image_url = data.get('image_url')
    
    if not image_url:
        return jsonify({'success': False, 'message': 'image_url is required'}), 400
    
    result = generate_image_caption(image_url)
    
    if result:
        return jsonify({
            'success': True,
            'caption': result['caption'],
            'confidence': result['confidence']
        }), 200
    else:
        return jsonify({
            'success': False,
            'message': 'Could not generate caption for this image'
        }), 400


# ============================================
# AI: GENERATE CAPTION FROM DIRECT FILE UPLOAD
# ============================================
@app.route('/api/generate-caption', methods=['POST'])
@token_required
def generate_caption_from_file():
    """Generate caption from uploaded image file"""
    user_role = request.current_user.get('role')
    
    if user_role != 'creator':
        return jsonify({'success': False, 'message': 'Access denied. Creator role required.'}), 403
    
    if 'image' not in request.files:
        return jsonify({'success': False, 'message': 'No image file provided'}), 400
    
    file = request.files['image']
    
    if file.filename == '':
        return jsonify({'success': False, 'message': 'No image selected'}), 400
    
    if not file.content_type.startswith('image/'):
        return jsonify({'success': False, 'message': 'File must be an image'}), 400
    
    temp_path = None
    
    try:
        temp_dir = tempfile.gettempdir()
        temp_path = os.path.join(temp_dir, f"temp_{uuid.uuid4().hex}.jpg")
        file.save(temp_path)
        
        blob_name = f"temp/{uuid.uuid4().hex}.jpg"
        blob_client = blob_service_client.get_blob_client(container=BLOB_CONTAINER_NAME, blob=blob_name)
        
        with open(temp_path, "rb") as data:
            blob_client.upload_blob(data, overwrite=True)
        
        blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{BLOB_CONTAINER_NAME}/{blob_name}"
        
        result = generate_image_caption(blob_url)
        
        try:
            blob_client.delete_blob()
        except:
            pass
        
        if result:
            return jsonify({
                'success': True,
                'caption': result['caption'],
                'confidence': result['confidence']
            }), 200
        else:
            return jsonify({'success': False, 'message': 'Could not generate caption for this image'}), 400
            
    except Exception as e:
        print(f"Caption generation error: {e}")
        return jsonify({'success': False, 'message': f'Failed to process image: {str(e)}'}), 400
    
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass


# ============================================
# API ROUTE: LOGIN
# ============================================
@app.route('/api/login', methods=['POST'])
def login():
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Request body is empty'}), 400
    
    email = data.get('email')
    password = data.get('password')
    role = data.get('role')
    
    if not email or not password:
        return jsonify({'success': False, 'message': 'Email and password are required'}), 400
    
    query = f"SELECT * FROM users WHERE users.email = '{email}'"
    users = list(users_container.query_items(query=query, enable_cross_partition_query=True))
    
    if not users:
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
    
    user = users[0]
    
    if user['password_hash'] != hash_value(password):
        return jsonify({'success': False, 'message': 'Invalid email or password'}), 401
    
    if user['role'] != role:
        return jsonify({'success': False, 'message': f'This account is a {user["role"]}. Please login as {user["role"]}'}), 403
    
    token = generate_token(user['user_id'], email, role)
    
    return jsonify({
        'success': True,
        'message': 'Login successful',
        'token': token,
        'user': {
            'email': email,
            'role': role,
            'user_id': user['user_id']
        }
    }), 200


# ============================================
# CONSUMER REGISTRATION API
# ============================================
@app.route('/api/register', methods=['POST'])
def register_consumer():
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Request body is empty'}), 400
    
    fullname = data.get('fullname')
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not fullname or not username or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required'}), 400
    
    query = f"SELECT * FROM users WHERE users.email = '{email}'"
    existing = list(users_container.query_items(query=query, enable_cross_partition_query=True))
    
    if existing:
        return jsonify({'success': False, 'message': 'Email already registered'}), 409
    
    user_id = f"user_{uuid.uuid4().hex[:8]}"
    
    new_user = {
        'id': user_id,
        'user_id': user_id,
        'email': email,
        'password_hash': hash_value(password),
        'role': 'consumer',
        'fullname': fullname,
        'username': username,
        'created_at': datetime.utcnow().isoformat()
    }
    
    users_container.create_item(body=new_user)
    token = generate_token(user_id, email, 'consumer')
    
    return jsonify({
        'success': True,
        'message': 'Consumer account created successfully',
        'token': token,
        'user': {
            'email': email,
            'role': 'consumer',
            'user_id': user_id,
            'fullname': fullname,
            'username': username
        }
    }), 201


# ============================================
# CREATOR REGISTRATION API
# ============================================
@app.route('/api/creator/register', methods=['POST'])
def register_creator():
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Request body is empty'}), 400
    
    fullname = data.get('fullname')
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')
    
    if not fullname or not username or not email or not password:
        return jsonify({'success': False, 'message': 'All fields are required'}), 400
    
    query = f"SELECT * FROM users WHERE users.email = '{email}'"
    existing = list(users_container.query_items(query=query, enable_cross_partition_query=True))
    
    if existing:
        return jsonify({'success': False, 'message': 'Email already registered'}), 409
    
    user_id = f"creator_{uuid.uuid4().hex[:8]}"
    
    new_user = {
        'id': user_id,
        'user_id': user_id,
        'email': email,
        'password_hash': hash_value(password),
        'role': 'creator',
        'fullname': fullname,
        'username': username,
        'created_at': datetime.utcnow().isoformat()
    }
    
    users_container.create_item(body=new_user)
    token = generate_token(user_id, email, 'creator')
    
    return jsonify({
        'success': True,
        'message': 'Creator account created successfully',
        'token': token,
        'user': {
            'email': email,
            'role': 'creator',
            'user_id': user_id,
            'fullname': fullname,
            'username': username
        }
    }), 201


# ============================================
# GET UPLOAD URL
# ============================================
@app.route('/api/get-upload-url', methods=['GET'])
@token_required
def get_upload_url():
    user_id = request.current_user.get('user_id')
    user_role = request.current_user.get('role')
    
    if user_role != 'creator':
        return jsonify({'success': False, 'message': 'Access denied. Creator role required.'}), 403
    
    file_extension = request.args.get('ext', 'jpg')
    blob_name = f"posts/{user_id}/{uuid.uuid4().hex}.{file_extension}"
    sas_url = generate_sas_url(blob_name)
    blob_url = f"https://{blob_service_client.account_name}.blob.core.windows.net/{BLOB_CONTAINER_NAME}/{blob_name}"
    
    return jsonify({
        'success': True,
        'uploadUrl': sas_url,
        'blobUrl': blob_url
    }), 200


# ============================================
# CREATOR UPLOAD POST METADATA (with AI Captioning)
# ============================================
@app.route('/api/creator/upload', methods=['POST'])
@token_required
def upload_post():
    user_id = request.current_user.get('user_id')
    user_email = request.current_user.get('email')
    user_role = request.current_user.get('role')
    
    if user_role != 'creator':
        return jsonify({'success': False, 'message': 'Access denied. Creator role required.'}), 403
    
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Request body is empty'}), 400
    
    title = data.get('title')
    caption = data.get('caption', '')
    location = data.get('location', '')
    people_tagged = data.get('people_tagged', [])
    tags = data.get('tags', [])
    media_type = data.get('media_type', 'image')
    image_url = data.get('media_url', '')
    
    if not title:
        return jsonify({'success': False, 'message': 'Title is required'}), 400
    
    # AI: Auto-generate caption if not provided
    ai_caption_generated = False
    if not caption and media_type == 'image' and image_url:
        ai_result = generate_image_caption(image_url)
        if ai_result:
            caption = ai_result['caption']
            ai_caption_generated = True
            print(f"🤖 AI Generated Caption: {caption}")
    
    # AI: Auto-generate hashtags from title and caption
    if not tags and (title or caption):
        words = (title + ' ' + caption).lower().split()
        common_words = {'the', 'a', 'an', 'and', 'of', 'to', 'in', 'for', 'on', 'with', 'at', 'by', 'is', 'it', 'this', 'that', 'be', 'are', 'was', 'were', 'as', 'has', 'have', 'from', 'but', 'or', 'not'}
        auto_tags = []
        for word in words:
            word_clean = word.strip('.,!?;:()[]{}"\'')
            if len(word_clean) > 3 and word_clean not in common_words and word_clean.isalpha():
                auto_tags.append(f"#{word_clean}")
        tags = list(dict.fromkeys(auto_tags))[:5]
        if tags:
            print(f"🤖 Auto-generated tags: {tags}")
    
    post_id = f"post_{uuid.uuid4().hex[:8]}"
    
    new_post = {
        'id': post_id,
        'post_id': post_id,
        'creator_id': user_id,
        'creator_name': user_email.split('@')[0],
        'creator_avatar': user_email[0:2].upper(),
        'image_url': image_url,
        'title': title,
        'caption': caption,
        'location': location,
        'people_tagged': people_tagged,
        'tags': tags,
        'media_type': media_type,
        'likes_count': 0,
        'comments_count': 0,
        'saves_count': 0,
        'created_at': datetime.utcnow().isoformat()
    }
    
    posts_container.create_item(body=new_post)
    
    return jsonify({
        'success': True,
        'message': 'Post uploaded successfully',
        'post': new_post,
        'ai_caption_generated': ai_caption_generated
    }), 201


# ============================================
# CONSUMER FEED API ROUTES
# ============================================

@app.route('/api/feed', methods=['GET'])
@token_required
def get_feed():
    """Returns posts for the consumer feed"""
    feed_type = request.args.get('type', 'foryou')
    user_id = request.current_user.get('user_id')
    user_role = request.current_user.get('role')
    
    if user_role != 'consumer':
        return jsonify({'success': False, 'message': 'Access denied. Consumer role required.'}), 403
    
    # Get all posts
    posts_query = "SELECT * FROM posts"
    posts = list(posts_container.query_items(query=posts_query, enable_cross_partition_query=True))
    
    # If following feed, filter posts by creators the user follows
    if feed_type == 'following':
        follows_query = f"SELECT * FROM follows WHERE follows.user_id = '{user_id}'"
        follows = list(follows_container.query_items(query=follows_query, enable_cross_partition_query=True))
        following_ids = [f['creator_id'] for f in follows]
        posts = [post for post in posts if post.get('creator_id') in following_ids]
    
    # Sort by most recent
    posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    # Add like/save status for current user
    for post in posts:
        like_query = f"SELECT * FROM likes WHERE likes.user_id = '{user_id}' AND likes.post_id = '{post['post_id']}'"
        likes = list(likes_container.query_items(query=like_query, enable_cross_partition_query=True))
        post['liked_by_user'] = len(likes) > 0
        
        save_query = f"SELECT * FROM saves WHERE saves.user_id = '{user_id}' AND saves.post_id = '{post['post_id']}'"
        saves = list(saves_container.query_items(query=save_query, enable_cross_partition_query=True))
        post['saved_by_user'] = len(saves) > 0
    
    return jsonify({
        'success': True,
        'posts': posts,
        'feed_type': feed_type
    }), 200


# ============================================
# LIKE/UNLIKE API
# ============================================
@app.route('/api/like', methods=['POST'])
@token_required
def toggle_like():
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Request body is empty'}), 400
    
    post_id = data.get('post_id')
    user_id = request.current_user.get('user_id')
    user_role = request.current_user.get('role')
    
    if user_role != 'consumer':
        return jsonify({'success': False, 'message': 'Only consumers can like posts'}), 403
    
    if not post_id:
        return jsonify({'success': False, 'message': 'post_id is required'}), 400
    
    # Check if already liked
    like_query = f"SELECT * FROM likes WHERE likes.user_id = '{user_id}' AND likes.post_id = '{post_id}'"
    existing = list(likes_container.query_items(query=like_query, enable_cross_partition_query=True))
    
    if existing:
        # Unlike
        for like in existing:
            likes_container.delete_item(item=like['id'], partition_key=post_id)
        liked = False
        # Decrement likes count
        post_query = f"SELECT * FROM posts WHERE posts.post_id = '{post_id}'"
        posts = list(posts_container.query_items(query=post_query, enable_cross_partition_query=True))
        if posts:
            post = posts[0]
            post['likes_count'] = post.get('likes_count', 0) - 1
            posts_container.replace_item(item=post['id'], body=post)
    else:
        # Like
        like_item = {
            'id': f"like_{uuid.uuid4().hex[:8]}",
            'user_id': user_id,
            'post_id': post_id,
            'created_at': datetime.utcnow().isoformat()
        }
        likes_container.create_item(body=like_item)
        liked = True
        # Increment likes count
        post_query = f"SELECT * FROM posts WHERE posts.post_id = '{post_id}'"
        posts = list(posts_container.query_items(query=post_query, enable_cross_partition_query=True))
        if posts:
            post = posts[0]
            post['likes_count'] = post.get('likes_count', 0) + 1
            posts_container.replace_item(item=post['id'], body=post)
    
    return jsonify({
        'success': True,
        'post_id': post_id,
        'liked': liked,
        'message': 'Liked' if liked else 'Unliked'
    }), 200


# ============================================
# SAVE/UNSAVE API
# ============================================
@app.route('/api/save', methods=['POST'])
@token_required
def toggle_save():
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Request body is empty'}), 400
    
    post_id = data.get('post_id')
    user_id = request.current_user.get('user_id')
    user_role = request.current_user.get('role')
    
    if user_role != 'consumer':
        return jsonify({'success': False, 'message': 'Only consumers can save posts'}), 403
    
    if not post_id:
        return jsonify({'success': False, 'message': 'post_id is required'}), 400
    
    # Check if already saved
    save_query = f"SELECT * FROM saves WHERE saves.user_id = '{user_id}' AND saves.post_id = '{post_id}'"
    existing = list(saves_container.query_items(query=save_query, enable_cross_partition_query=True))
    
    if existing:
        # Unsave
        for save in existing:
            saves_container.delete_item(item=save['id'], partition_key=post_id)
        saved = False
        # Decrement saves count
        post_query = f"SELECT * FROM posts WHERE posts.post_id = '{post_id}'"
        posts = list(posts_container.query_items(query=post_query, enable_cross_partition_query=True))
        if posts:
            post = posts[0]
            post['saves_count'] = post.get('saves_count', 0) - 1
            posts_container.replace_item(item=post['id'], body=post)
    else:
        # Save
        save_item = {
            'id': f"save_{uuid.uuid4().hex[:8]}",
            'user_id': user_id,
            'post_id': post_id,
            'created_at': datetime.utcnow().isoformat()
        }
        saves_container.create_item(body=save_item)
        saved = True
        # Increment saves count
        post_query = f"SELECT * FROM posts WHERE posts.post_id = '{post_id}'"
        posts = list(posts_container.query_items(query=post_query, enable_cross_partition_query=True))
        if posts:
            post = posts[0]
            post['saves_count'] = post.get('saves_count', 0) + 1
            posts_container.replace_item(item=post['id'], body=post)
    
    return jsonify({
        'success': True,
        'post_id': post_id,
        'saved': saved,
        'message': 'Saved' if saved else 'Unsaved'
    }), 200


# ============================================
# COMMENTS API (WITH SENTIMENT ANALYSIS)
# ============================================
@app.route('/api/comments/<post_id>', methods=['GET'])
@token_required
def get_comments(post_id):
    """Get comments for a post"""
    comments_query = f"SELECT * FROM comments WHERE comments.post_id = '{post_id}' ORDER BY comments.created_at DESC"
    comments = list(comments_container.query_items(query=comments_query, enable_cross_partition_query=True))
    
    return jsonify({
        'success': True,
        'post_id': post_id,
        'comments': comments,
        'count': len(comments)
    }), 200


@app.route('/api/comments', methods=['POST'])
@token_required
def add_comment():
    """Add a comment to a post with sentiment analysis"""
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Request body is empty'}), 400
    
    post_id = data.get('post_id')
    text = data.get('text')
    user_id = request.current_user.get('user_id')
    user_email = request.current_user.get('email')
    
    if not post_id or not text:
        return jsonify({'success': False, 'message': 'post_id and text are required'}), 400
    
    # Analyze sentiment of the comment
    sentiment_result = analyze_sentiment(text)
    print(f"📊 Sentiment Analysis: '{text[:50]}...' → {sentiment_result['sentiment']} ({sentiment_result['confidence_scores']})")
    
    comment_id = f"cmt_{uuid.uuid4().hex[:8]}"
    
    new_comment = {
        'id': comment_id,
        'comment_id': comment_id,
        'post_id': post_id,
        'user_id': user_id,
        'author': user_email.split('@')[0],
        'author_avatar': user_email[0:2].upper(),
        'text': text,
        'sentiment': sentiment_result['sentiment'],
        'sentiment_scores': sentiment_result['confidence_scores'],
        'created_at': datetime.utcnow().isoformat()
    }
    
    comments_container.create_item(body=new_comment)
    
    # Increment comments count on post
    post_query = f"SELECT * FROM posts WHERE posts.post_id = '{post_id}'"
    posts = list(posts_container.query_items(query=post_query, enable_cross_partition_query=True))
    if posts:
        post = posts[0]
        post['comments_count'] = post.get('comments_count', 0) + 1
        posts_container.replace_item(item=post['id'], body=post)
    
    return jsonify({
        'success': True,
        'message': 'Comment added with sentiment analysis',
        'comment': new_comment
    }), 201


# ============================================
# CREATOR POSTS API
# ============================================
@app.route('/api/creator/posts', methods=['GET'])
@token_required
def get_creator_posts():
    """Returns all posts uploaded by the authenticated creator"""
    user_id = request.current_user.get('user_id')
    user_role = request.current_user.get('role')
    
    if user_role != 'creator':
        return jsonify({'success': False, 'message': 'Access denied. Creator role required.'}), 403
    
    posts_query = f"SELECT * FROM posts WHERE posts.creator_id = '{user_id}'"
    my_posts = list(posts_container.query_items(query=posts_query, enable_cross_partition_query=True))
    my_posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    return jsonify({
        'success': True,
        'posts': my_posts,
        'count': len(my_posts)
    }), 200


@app.route('/api/creator/post/<post_id>', methods=['DELETE'])
@token_required
def delete_post(post_id):
    """Deletes a post owned by the authenticated creator"""
    user_id = request.current_user.get('user_id')
    user_role = request.current_user.get('role')
    
    if user_role != 'creator':
        return jsonify({'success': False, 'message': 'Access denied. Creator role required.'}), 403
    
    post_query = f"SELECT * FROM posts WHERE posts.post_id = '{post_id}'"
    posts = list(posts_container.query_items(query=post_query, enable_cross_partition_query=True))
    
    if not posts:
        return jsonify({'success': False, 'message': 'Post not found'}), 404
    
    post = posts[0]
    
    if post.get('creator_id') != user_id:
        return jsonify({'success': False, 'message': 'You can only delete your own posts'}), 403
    
    posts_container.delete_item(item=post['id'], partition_key=post_id)
    
    # Delete related likes
    likes_query = f"SELECT * FROM likes WHERE likes.post_id = '{post_id}'"
    likes = list(likes_container.query_items(query=likes_query, enable_cross_partition_query=True))
    for like in likes:
        likes_container.delete_item(item=like['id'], partition_key=post_id)
    
    # Delete related saves
    saves_query = f"SELECT * FROM saves WHERE saves.post_id = '{post_id}'"
    saves = list(saves_container.query_items(query=saves_query, enable_cross_partition_query=True))
    for save in saves:
        saves_container.delete_item(item=save['id'], partition_key=post_id)
    
    # Delete related comments
    comments_query = f"SELECT * FROM comments WHERE comments.post_id = '{post_id}'"
    comments = list(comments_container.query_items(query=comments_query, enable_cross_partition_query=True))
    for comment in comments:
        comments_container.delete_item(item=comment['id'], partition_key=post_id)
    
    return jsonify({
        'success': True,
        'message': 'Post deleted successfully',
        'deleted_post_id': post_id
    }), 200


# ============================================
# FOLLOW/UNFOLLOW API
# ============================================
@app.route('/api/follow', methods=['POST'])
@token_required
def follow_creator():
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Request body is empty'}), 400
    
    creator_id = data.get('creator_id')
    user_id = request.current_user.get('user_id')
    user_role = request.current_user.get('role')
    
    if user_role != 'consumer':
        return jsonify({'success': False, 'message': 'Only consumers can follow creators'}), 403
    
    if not creator_id:
        return jsonify({'success': False, 'message': 'creator_id is required'}), 400
    
    # Check if already following
    follow_query = f"SELECT * FROM follows WHERE follows.user_id = '{user_id}' AND follows.creator_id = '{creator_id}'"
    existing = list(follows_container.query_items(query=follow_query, enable_cross_partition_query=True))
    
    if existing:
        return jsonify({'success': False, 'message': 'Already following this creator'}), 409
    
    follow_id = f"follow_{uuid.uuid4().hex[:8]}"
    
    new_follow = {
        'id': follow_id,
        'user_id': user_id,
        'creator_id': creator_id,
        'created_at': datetime.utcnow().isoformat()
    }
    
    follows_container.create_item(body=new_follow)
    
    return jsonify({
        'success': True,
        'following': True,
        'message': 'Now following creator'
    }), 200


@app.route('/api/unfollow', methods=['POST'])
@token_required
def unfollow_creator():
    data = request.get_json()
    
    if not data:
        return jsonify({'success': False, 'message': 'Request body is empty'}), 400
    
    creator_id = data.get('creator_id')
    user_id = request.current_user.get('user_id')
    user_role = request.current_user.get('role')
    
    if user_role != 'consumer':
        return jsonify({'success': False, 'message': 'Only consumers can unfollow creators'}), 403
    
    if not creator_id:
        return jsonify({'success': False, 'message': 'creator_id is required'}), 400
    
    follow_query = f"SELECT * FROM follows WHERE follows.user_id = '{user_id}' AND follows.creator_id = '{creator_id}'"
    existing = list(follows_container.query_items(query=follow_query, enable_cross_partition_query=True))
    
    if not existing:
        return jsonify({'success': False, 'message': 'Not following this creator'}), 404
    
    for follow in existing:
        follows_container.delete_item(item=follow['id'], partition_key=user_id)
    
    return jsonify({
        'success': True,
        'following': False,
        'message': 'Unfollowed creator'
    }), 200


# ============================================
# GET USER'S FOLLOWS (UPDATED - RETURNS CREATOR DETAILS)
# ============================================
@app.route('/api/user/follows', methods=['GET'])
@token_required
def get_user_follows():
    user_id = request.current_user.get('user_id')
    user_role = request.current_user.get('role')
    
    if user_role != 'consumer':
        return jsonify({'success': True, 'follows': []}), 200
    
    follows_query = f"SELECT * FROM follows WHERE follows.user_id = '{user_id}'"
    follows = list(follows_container.query_items(query=follows_query, enable_cross_partition_query=True))
    
    follows_list = []
    for follow in follows:
        creator_id = follow['creator_id']
        # Get creator details from users container
        creator_query = f"SELECT * FROM users WHERE users.user_id = '{creator_id}'"
        creators = list(users_container.query_items(query=creator_query, enable_cross_partition_query=True))
        
        if creators:
            creator = creators[0]
            follows_list.append({
                'creator_id': creator_id,
                'creator_name': creator.get('username', creator.get('fullname', creator['email'].split('@')[0])),
                'creator_avatar': creator.get('username', creator['email'][0:2]).upper(),
                'creator_email': creator['email']
            })
        else:
            follows_list.append({
                'creator_id': creator_id,
                'creator_name': 'Unknown Creator',
                'creator_avatar': 'UC',
                'creator_email': ''
            })
    
    return jsonify({
        'success': True,
        'follows': follows_list
    }), 200


# ============================================
# GET USER'S LIKED POSTS
# ============================================
@app.route('/api/user/liked', methods=['GET'])
@token_required
def get_user_liked_posts():
    """Returns all posts liked by the current user"""
    user_id = request.current_user.get('user_id')
    user_role = request.current_user.get('role')
    
    if user_role != 'consumer':
        return jsonify({'success': True, 'posts': []}), 200
    
    # Get all likes by this user
    likes_query = f"SELECT * FROM likes WHERE likes.user_id = '{user_id}'"
    likes = list(likes_container.query_items(query=likes_query, enable_cross_partition_query=True))
    
    if not likes:
        return jsonify({'success': True, 'posts': []}), 200
    
    # Get the actual posts
    liked_posts = []
    for like in likes:
        post_id = like.get('post_id')
        post_query = f"SELECT * FROM posts WHERE posts.post_id = '{post_id}'"
        posts = list(posts_container.query_items(query=post_query, enable_cross_partition_query=True))
        if posts:
            post = posts[0]
            # Add like/save status
            post['liked_by_user'] = True
            save_query = f"SELECT * FROM saves WHERE saves.user_id = '{user_id}' AND saves.post_id = '{post_id}'"
            saves = list(saves_container.query_items(query=save_query, enable_cross_partition_query=True))
            post['saved_by_user'] = len(saves) > 0
            liked_posts.append(post)
    
    # Sort by most recent like first
    liked_posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    return jsonify({
        'success': True,
        'posts': liked_posts,
        'count': len(liked_posts)
    }), 200


# ============================================
# GET USER'S SAVED POSTS
# ============================================
@app.route('/api/user/saved', methods=['GET'])
@token_required
def get_user_saved_posts():
    """Returns all posts saved by the current user"""
    user_id = request.current_user.get('user_id')
    user_role = request.current_user.get('role')
    
    if user_role != 'consumer':
        return jsonify({'success': True, 'posts': []}), 200
    
    # Get all saves by this user
    saves_query = f"SELECT * FROM saves WHERE saves.user_id = '{user_id}'"
    saves = list(saves_container.query_items(query=saves_query, enable_cross_partition_query=True))
    
    if not saves:
        return jsonify({'success': True, 'posts': []}), 200
    
    # Get the actual posts
    saved_posts = []
    for save in saves:
        post_id = save.get('post_id')
        post_query = f"SELECT * FROM posts WHERE posts.post_id = '{post_id}'"
        posts = list(posts_container.query_items(query=post_query, enable_cross_partition_query=True))
        if posts:
            post = posts[0]
            # Add like/save status
            like_query = f"SELECT * FROM likes WHERE likes.user_id = '{user_id}' AND likes.post_id = '{post_id}'"
            likes = list(likes_container.query_items(query=like_query, enable_cross_partition_query=True))
            post['liked_by_user'] = len(likes) > 0
            post['saved_by_user'] = True
            saved_posts.append(post)
    
    # Sort by most recent save first
    saved_posts.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    
    return jsonify({
        'success': True,
        'posts': saved_posts,
        'count': len(saved_posts)
    }), 200


# ============================================
# SEARCH API ROUTES
# ============================================

@app.route('/api/search/creators', methods=['GET'])
@token_required
def search_creators():
    query = request.args.get('q', '').lower()
    user_id = request.current_user.get('user_id')
    
    if not query:
        return jsonify({'success': True, 'results': []}), 200
    
    users_query = "SELECT * FROM users"
    all_users = list(users_container.query_items(query=users_query, enable_cross_partition_query=True))
    
    results = []
    for user in all_users:
        if user.get('role') == 'creator':
            username = user.get('username', '').lower()
            fullname = user.get('fullname', '').lower()
            
            if query in username or query in fullname:
                # Check if current user follows this creator
                follow_check = f"SELECT * FROM follows WHERE follows.user_id = '{user_id}' AND follows.creator_id = '{user['user_id']}'"
                follows = list(follows_container.query_items(query=follow_check, enable_cross_partition_query=True))
                is_following = len(follows) > 0
                
                results.append({
                    'user_id': user.get('user_id'),
                    'username': user.get('username', user['email'].split('@')[0]),
                    'fullname': user.get('fullname', ''),
                    'email': user['email'],
                    'avatar': user.get('username', user['email'][0:2]).upper(),
                    'is_following': is_following,
                    'posts_count': 0
                })
    
    return jsonify({
        'success': True,
        'results': results,
        'count': len(results)
    }), 200


@app.route('/api/explore/posts', methods=['GET'])
@token_required
def explore_posts():
    # Get all posts
    posts_query = "SELECT * FROM posts"
    all_posts = list(posts_container.query_items(query=posts_query, enable_cross_partition_query=True))
    
    # Shuffle for random order
    random.shuffle(all_posts)
    
    # Add like/save status for current user
    user_id = request.current_user.get('user_id')
    for post in all_posts:
        like_query = f"SELECT * FROM likes WHERE likes.user_id = '{user_id}' AND likes.post_id = '{post['post_id']}'"
        likes = list(likes_container.query_items(query=like_query, enable_cross_partition_query=True))
        post['liked_by_user'] = len(likes) > 0
        
        save_query = f"SELECT * FROM saves WHERE saves.user_id = '{user_id}' AND saves.post_id = '{post['post_id']}'"
        saves = list(saves_container.query_items(query=save_query, enable_cross_partition_query=True))
        post['saved_by_user'] = len(saves) > 0
    
    return jsonify({
        'success': True,
        'posts': all_posts,
        'count': len(all_posts)
    }), 200


@app.route('/api/creator/profile/<creator_id>', methods=['GET'])
@token_required
def get_creator_profile(creator_id):
    user_id = request.current_user.get('user_id')
    
    # Find creator
    creator_query = f"SELECT * FROM users WHERE users.user_id = '{creator_id}'"
    creators = list(users_container.query_items(query=creator_query, enable_cross_partition_query=True))
    
    if not creators:
        return jsonify({'success': False, 'message': 'Creator not found'}), 404
    
    creator = creators[0]
    
    if creator.get('role') != 'creator':
        return jsonify({'success': False, 'message': 'User is not a creator'}), 400
    
    # Get creator's posts
    posts_query = f"SELECT * FROM posts WHERE posts.creator_id = '{creator_id}'"
    creator_posts = list(posts_container.query_items(query=posts_query, enable_cross_partition_query=True))
    
    # Add like/save status
    for post in creator_posts:
        like_query = f"SELECT * FROM likes WHERE likes.user_id = '{user_id}' AND likes.post_id = '{post['post_id']}'"
        likes = list(likes_container.query_items(query=like_query, enable_cross_partition_query=True))
        post['liked_by_user'] = len(likes) > 0
        
        save_query = f"SELECT * FROM saves WHERE saves.user_id = '{user_id}' AND saves.post_id = '{post['post_id']}'"
        saves = list(saves_container.query_items(query=save_query, enable_cross_partition_query=True))
        post['saved_by_user'] = len(saves) > 0
    
    # Check if current user follows this creator
    follow_check = f"SELECT * FROM follows WHERE follows.user_id = '{user_id}' AND follows.creator_id = '{creator_id}'"
    follows = list(follows_container.query_items(query=follow_check, enable_cross_partition_query=True))
    is_following = len(follows) > 0
    
    # Get follower count
    followers_query = f"SELECT * FROM follows WHERE follows.creator_id = '{creator_id}'"
    followers = list(follows_container.query_items(query=followers_query, enable_cross_partition_query=True))
    followers_count = len(followers)
    
    return jsonify({
        'success': True,
        'creator': {
            'user_id': creator.get('user_id'),
            'username': creator.get('username', creator['email'].split('@')[0]),
            'fullname': creator.get('fullname', ''),
            'email': creator['email'],
            'avatar': creator.get('username', creator['email'][0:2]).upper(),
            'bio': creator.get('bio', 'Creator on Pictor'),
            'joined_date': creator.get('created_at', '2026-01-01'),
            'posts_count': len(creator_posts),
            'followers_count': followers_count,
            'is_following': is_following
        },
        'posts': creator_posts
    }), 200


# ============================================
# CREATOR STATS API
# ============================================
@app.route('/api/creator/stats', methods=['GET'])
@token_required
def get_creator_stats():
    user_id = request.current_user.get('user_id')
    user_role = request.current_user.get('role')
    
    if user_role != 'creator':
        return jsonify({'success': False, 'message': 'Access denied. Creator role required.'}), 403
    
    posts_query = f"SELECT * FROM posts WHERE posts.creator_id = '{user_id}'"
    posts = list(posts_container.query_items(query=posts_query, enable_cross_partition_query=True))
    
    total_posts = len(posts)
    total_likes = sum(post.get('likes_count', 0) for post in posts)
    total_comments = sum(post.get('comments_count', 0) for post in posts)
    total_saves = sum(post.get('saves_count', 0) for post in posts)
    
    most_liked_post = max(posts, key=lambda x: x.get('likes_count', 0)) if posts else None
    
    return jsonify({
        'success': True,
        'stats': {
            'total_posts': total_posts,
            'total_likes': total_likes,
            'total_comments': total_comments,
            'total_saves': total_saves,
            'average_likes_per_post': round(total_likes / total_posts, 1) if total_posts > 0 else 0,
            'most_liked_post': {
                'post_id': most_liked_post['post_id'],
                'title': most_liked_post['title'],
                'likes': most_liked_post['likes_count']
            } if most_liked_post else None
        }
    }), 200


# ============================================
# HEALTH CHECK
# ============================================
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'message': 'Flask API is running with Cosmos DB + AI'}), 200


# ============================================
# RUN THE APP
# ============================================
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)