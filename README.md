📸 Pictor - Social Media Platform with Azure AI
Pictor is a full-stack social media platform that connects creators with consumers, powered by Azure cloud services and AI capabilities.

🚀 Live Demo
The application is deployed on Azure App Service: https://pictor-app-byaadwf8awd0ach8.francecentral-01.azurewebsites.net

⚠️ Note: The Azure deployment is temporary for demonstration purposes.

✨ Features
For Consumers
Browse content feed (For You / Following)

Like and save posts

Follow creators

Comment with AI sentiment analysis

Search for creators

Dark/Light theme toggle

For Creators
Upload images with AI-generated captions

Auto-generate hashtags

Manage posts (edit/delete)

View engagement statistics

Track likes, comments, and saves

AI-Powered Features
🤖 Auto Image Captioning - Azure Computer Vision generates captions for uploaded images

📊 Sentiment Analysis - Comments are analyzed for positive/negative sentiment

🌐 Language Translation - Translate comments to your preferred language

Security Features
🔐 JWT Authentication - Secure token-based authentication

⏰ Token Expiry - Tokens expire after 24 hours for security

🔒 Role-Based Access - Separate endpoints for consumers and creators

🧂 Password Hashing - Passwords hashed using SHA-256

🛠️ Tech Stack
Component	Technology
Backend	Flask (Python)
Database	Azure Cosmos DB
Storage	Azure Blob Storage
Authentication	JWT (JSON Web Tokens)
AI Services	Azure Cognitive Services
Deployment	Azure App Service
📋 Prerequisites
Before running this project, you need:

Python 3.9+

Azure account with active subscription

Azure services (see environment variables below)

🔧 Environment Variables
Create a .env file in the root directory with the following variables:

env
# Azure Cosmos DB
COSMOS_CONNECTION_STRING=your_cosmos_connection_string

# Azure Blob Storage
BLOB_CONNECTION_STRING=your_blob_connection_string
BLOB_CONTAINER_NAME=media

# Azure AI Services
AZURE_SENTIMENT_KEY=your_sentiment_key
AZURE_SENTIMENT_ENDPOINT=your_sentiment_endpoint

# Azure Translator
TRANSLATOR_KEY=your_translator_key
TRANSLATOR_REGION=global
TRANSLATOR_ENDPOINT=https://api.cognitive.microsofttranslator.com

# Azure Computer Vision
CV_KEY=your_computer_vision_key
CV_ENDPOINT=your_computer_vision_endpoint

# JWT Authentication (IMPORTANT)
JWT_SECRET_KEY=your_super_secret_jwt_key_here

# Flask
FLASK_ENV=development
PORT=5000
📝 Copy .env.example to .env and fill in your own Azure credentials

🌐 Important: API Base URL Configuration
For Local Development
The frontend automatically detects the backend URL using:

javascript
const API_BASE_URL = window.location.origin;
This works because:

Localhost: http://127.0.0.1:5000

Same origin: Frontend and backend are served from the same address

For Azure Deployment
This project uses Flask to serve both frontend (HTML templates) and backend APIs from the same origin. Therefore, window.location.origin works without changes.

✅ No changes needed when deploying to Azure App Service - Flask serves everything from the same domain.

If you separate frontend and backend (React + Flask)
If you deploy frontend and backend to different domains, you MUST change API_BASE_URL in all HTML files:

javascript
// Change from:
const API_BASE_URL = window.location.origin;

// To:
const API_BASE_URL = 'https://your-backend.azurewebsites.net';
Deployment Scenarios
Deployment Type	API_BASE_URL Setting	Change Required
Local development (Flask serves both)	window.location.origin	❌ No
Azure App Service (Flask serves both)	window.location.origin	❌ No
Frontend (static hosting) + Backend (Azure) separate	'https://your-api.azurewebsites.net'	✅ Yes
Different ports (React on 3000, Flask on 5000)	'http://localhost:5000'	✅ Yes
Quick Find & Replace for All Files
If you need to change the API URL, run this PowerShell command:

powershell
Get-ChildItem -Path "Templates\*.html" | ForEach-Object {
    (Get-Content $_.FullName -Raw) -replace "window\.location\.origin", "'https://your-new-url.azurewebsites.net'" | Set-Content $_.FullName -NoNewline
}
🔐 How JWT Works in This Project
What is JWT?
JSON Web Token (JWT) is used for secure authentication between frontend and backend.

How it's implemented:
Step	Description
1. Registration/Login	User credentials are verified
2. Token Generation	Server creates a signed JWT with user info
3. Token Storage	Frontend stores token in localStorage
4. API Requests	Token sent in Authorization: Bearer <token> header
5. Verification	Server validates token before processing requests
6. Expiry	Token expires after 24 hours, requiring re-login
Token Payload Structure:
json
{
    "user_id": "user_abc123",
    "email": "user@example.com",
    "role": "consumer",
    "exp": 1735689600
}
Why JWT?
✅ Stateless authentication

✅ No session storage needed

✅ Works across multiple servers

✅ Secure with secret key signing

✅ Built-in expiration

🏃 Local Development
1. Clone the repository
bash
git clone https://github.com/Eru0705/Scalable.git
cd Scalable
2. Create virtual environment
bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
3. Install dependencies
bash
pip install -r requirements.txt
4. Set up environment variables
bash
cp .env.example .env
# Edit .env with your Azure credentials
# IMPORTANT: Generate a strong JWT_SECRET_KEY
5. Generate a secure JWT Secret Key (optional but recommended)
python
python -c "import secrets; print(secrets.token_urlsafe(32))"
6. Run the application
bash
python app.py
7. Open your browser
Navigate to http://127.0.0.1:5000

☁️ Azure Deployment
Deploy to Azure App Service
Create Azure resources:

App Service (Linux or Windows)

Cosmos DB (NoSQL API)

Blob Storage account

Cognitive Services (Language, Translator, Computer Vision)

Set environment variables in Azure App Service:

Go to Configuration → Application settings

Add all variables from .env.example

Important: Set JWT_SECRET_KEY in Azure App Settings

Deploy using Git:

bash
git remote add azure https://your-app-name.scm.azurewebsites.net/pictor-app.git
git push azure main
📁 Project Structure
text
SASS/
├── Templates/           # Frontend HTML files
│   ├── login.html
│   ├── consumer.html
│   ├── consumer_registration.html
│   ├── consumer_profile.html
│   ├── consumer_search.html
│   ├── creator.html
│   └── creator_registration.html
├── app.py              # Main Flask application
├── requirements.txt    # Python dependencies
├── .env.example        # Environment variables template
└── README.md           # This file
🔒 Security Notes
Aspect	Implementation
Authentication	JWT with 24-hour expiration
Passwords	Hashed using SHA-256
Secrets	Stored as environment variables, never in code
API Security	Token validation on protected endpoints
Role-Based Access	Consumers and creators have different permissions
CORS	Configured for cross-origin requests
.gitignore	.env excluded from version control
Important Security Reminders:
⚠️ Never commit .env to version control

⚠️ Change the default JWT_SECRET_KEY in production

⚠️ Use HTTPS in production (Azure provides this by default)

⚠️ Rotate JWT secret periodically

## 🔄 API Endpoints (JWT Protected)

| Endpoint | Method | JWT Required | Role |
|----------|--------|--------------|------|
| `/api/login` | POST | ❌ No | All |
| `/api/register` | POST | ❌ No | All |
| `/api/feed` | GET | ✅ Yes | Consumer |
| `/api/like` | POST | ✅ Yes | Consumer |
| `/api/save` | POST | ✅ Yes | Consumer |
| `/api/follow` | POST | ✅ Yes | Consumer |
| `/api/creator/upload` | POST | ✅ Yes | Creator |
| `/api/creator/posts` | GET | ✅ Yes | Creator |
| `/api/user/profile` | GET | ✅ Yes | Both |
| `/api/user/saved` | GET | ✅ Yes | Consumer |
| `/api/user/liked` | GET | ✅ Yes | Consumer |

## ⚠️ Troubleshooting

| Issue | Solution |
|-------|----------|
| API calls failing | Check `API_BASE_URL` is set to `window.location.origin` |
| Cosmos DB connection error | Verify connection string in `.env` |
| Blob upload fails | Check container name and permissions |
| Sentiment analysis not working | Ensure Azure Language service key is valid |
| JWT invalid error | Verify `JWT_SECRET_KEY` matches between login and verification |
| Token expired | User needs to log in again (24-hour expiry) |

---

## 📝 License

This project was developed as part of coursework at Ulster University.

---

## 👨‍💻 Author

**Eru0705**

---


