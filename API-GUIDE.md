# Resume Parser REST API Guide

## 🚀 Quick Start

### Option 1: Run Locally (Development)

```bash
# Install dependencies
pip install -r requirements.txt

# Run the API
python api.py

# Or with uvicorn directly
uvicorn api:app --reload --port 8000
```

Access the API:
- **API Docs (Swagger)**: http://localhost:8000/docs
- **Alternative Docs (ReDoc)**: http://localhost:8000/redoc
- **Health Check**: http://localhost:8000/health

### Option 2: Run with Docker (Standalone)

```bash
# Build and run
chmod +x deploy-api-standalone.sh
./deploy-api-standalone.sh

# Start the container
docker run -d -p 8000:8000 --name resume-parser-api resume-parser-api:latest

# Test
curl http://localhost:8000/health
```

### Option 3: Deploy to AWS Lambda (Serverless)

```bash
# Deploy with FastAPI on Lambda
chmod +x deploy-api-lambda.sh
./deploy-api-lambda.sh us-east-1

# You'll get a public HTTPS URL automatically!
```

---

## 📚 API Endpoints

### 1. Health Check

**GET** `/health`

Check if the API is running.

```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2025-10-12T10:30:00.000000"
}
```

---

### 2. Parse Resume (File Upload)

**POST** `/parse/upload`

Upload a resume file directly.

**Parameters:**
- `file`: Resume file (PDF or DOCX) - **required**
- `include_raw_text`: Include raw text in response (default: false) - **optional**

```bash
# Upload a file
curl -X POST http://localhost:8000/parse/upload \
  -F "file=@resume.pdf" \
  -F "include_raw_text=false"

# With authentication (if added)
curl -X POST http://localhost:8000/parse/upload \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F "file=@resume.pdf"
```

**Response:**
```json
{
  "success": true,
  "data": {
    "file_path": "/tmp/...",
    "contact": {
      "name": "John Doe",
      "email": "john@example.com",
      "phone": "1234567890",
      "location": "New York",
      "linkedin": null,
      "github": null
    },
    "professional_summary": "Experienced software engineer...",
    "experience": [
      {
        "title": "Senior Software Engineer",
        "company": "Tech Corp",
        "start_date": "January 2020",
        "end_date": "present",
        "responsibilities": [...]
      }
    ],
    "education": [
      {
        "degree": "Bachelor of Science",
        "field": "Computer Science",
        "institution": "University Name",
        "graduation_date": "2019"
      }
    ],
    "skills": ["Python", "JavaScript", "AWS", "Docker", ...],
    "certifications": ["AWS Certified Solutions Architect"],
    "confidence_score": 0.85
  },
  "processing_time_ms": 1234.56
}
```

---

### 3. Parse Resume (Base64)

**POST** `/parse/base64`

Parse resume from base64 encoded content.

**Request Body:**
```json
{
  "file_content": "BASE64_ENCODED_CONTENT_HERE",
  "file_name": "resume.pdf",
  "include_raw_text": false
}
```

```bash
# Encode file to base64
FILE_CONTENT=$(base64 -i resume.pdf)

# Send request
curl -X POST http://localhost:8000/parse/base64 \
  -H "Content-Type: application/json" \
  -d "{
    \"file_content\": \"$FILE_CONTENT\",
    \"file_name\": \"resume.pdf\",
    \"include_raw_text\": false
  }"
```

---

### 4. Parse Resume (S3)

**POST** `/parse/s3`

Parse resume from AWS S3 bucket.

**Request Body:**
```json
{
  "s3_bucket": "my-resume-bucket",
  "s3_key": "resumes/john-doe-resume.pdf",
  "include_raw_text": false
}
```

```bash
curl -X POST http://localhost:8000/parse/s3 \
  -H "Content-Type: application/json" \
  -d '{
    "s3_bucket": "my-resume-bucket",
    "s3_key": "resumes/john-doe-resume.pdf",
    "include_raw_text": false
  }'
```

**Requirements:**
- AWS credentials configured (environment variables or IAM role)
- S3 read permissions

---

### 5. Parse Resume (URL)

**POST** `/parse/url`

Parse resume from a public URL.

**Request Body:**
```json
{
  "url": "https://example.com/resumes/resume.pdf",
  "include_raw_text": false
}
```

```bash
curl -X POST http://localhost:8000/parse/url \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://example.com/resumes/resume.pdf",
    "include_raw_text": false
  }'
```

---

## 🔧 Configuration

### Environment Variables

```bash
# API Configuration
export API_PORT=8000
export API_HOST=0.0.0.0

# AWS Configuration (for S3 parsing)
export AWS_REGION=us-east-1
export AWS_ACCESS_KEY_ID=your_key
export AWS_SECRET_ACCESS_KEY=your_secret

# Logging
export LOG_LEVEL=INFO
```

### CORS Configuration

By default, CORS is enabled for all origins. To restrict:

```python
# In api.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://yourapp.com"],  # Specific domain
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

---

## 🌐 Deployment Options

### Option 1: AWS Lambda (Serverless) ⭐ Recommended

**Pros:**
- ✅ Auto-scaling
- ✅ Pay per use
- ✅ No server management
- ✅ Built-in HTTPS

**Deploy:**
```bash
./deploy-api-lambda.sh us-east-1
```

**Cost:** ~$0.50 for 10,000 requests/month

---

### Option 2: AWS ECS/Fargate (Container Service)

**Pros:**
- ✅ Always warm (no cold starts)
- ✅ Consistent performance
- ✅ Good for high traffic

**Steps:**
1. Build image: `./deploy-api-standalone.sh`
2. Push to ECR
3. Create ECS service
4. Add load balancer

**Cost:** ~$30-50/month for small instance

---

### Option 3: Google Cloud Run

**Pros:**
- ✅ Serverless container
- ✅ Auto-scaling
- ✅ Simple deployment

```bash
# Build and deploy
./deploy-api-standalone.sh
gcloud run deploy resume-parser-api \
  --image resume-parser-api:latest \
  --platform managed \
  --region us-central1 \
  --allow-unauthenticated
```

---

### Option 4: Railway / Render / Fly.io

Simple deployment platforms:

```bash
# Railway
railway up

# Render
render deploy

# Fly.io
fly deploy
```

---

## 📊 Response Schema

### Parsed Resume Data

```typescript
{
  success: boolean;
  data: {
    file_path: string;
    contact: {
      name: string | null;
      email: string | null;
      phone: string | null;
      location: string | null;
      linkedin: string | null;
      github: string | null;
    };
    professional_summary: string | null;
    experience: Array<{
      title: string | null;
      company: string | null;
      location: string | null;
      start_date: string | null;
      end_date: string | null;
      duration: string | null;
      responsibilities: string[];
      achievements: string[];
    }>;
    education: Array<{
      degree: string | null;
      field: string | null;
      institution: string | null;
      location: string | null;
      graduation_date: string | null;
      gpa: string | null;
    }>;
    skills: string[];
    certifications: string[];
    projects: string[];
    awards: string[];
    confidence_score: number;  // 0.0 to 1.0
    raw_text_length?: number;
    raw_text?: string;  // If include_raw_text=true
  };
  processing_time_ms: number;
}
```

---

## 🔒 Security

### Add Authentication

To add API key authentication:

```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

API_KEY = "your-secret-api-key"
api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key

# Add to endpoints
@app.post("/parse/upload", dependencies=[Security(verify_api_key)])
async def parse_upload(...):
    ...
```

Usage:
```bash
curl -X POST http://localhost:8000/parse/upload \
  -H "X-API-Key: your-secret-api-key" \
  -F "file=@resume.pdf"
```

---

## 🧪 Testing

### Test with cURL

```bash
# Health check
curl http://localhost:8000/health

# Upload file
curl -X POST http://localhost:8000/parse/upload \
  -F "file=@test-resume.pdf"

# Base64
curl -X POST http://localhost:8000/parse/base64 \
  -H "Content-Type: application/json" \
  -d "$(cat test-payload.json)"
```

### Test with Python

```python
import requests

# Upload file
with open('resume.pdf', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/parse/upload',
        files={'file': f}
    )
    
print(response.json())

# Base64
import base64
with open('resume.pdf', 'rb') as f:
    content = base64.b64encode(f.read()).decode()
    
response = requests.post(
    'http://localhost:8000/parse/base64',
    json={
        'file_content': content,
        'file_name': 'resume.pdf'
    }
)

print(response.json())
```

### Test with JavaScript

```javascript
// Upload file
const formData = new FormData();
formData.append('file', fileInput.files[0]);

const response = await fetch('http://localhost:8000/parse/upload', {
  method: 'POST',
  body: formData
});

const data = await response.json();
console.log(data);

// Base64
const fileReader = new FileReader();
fileReader.onload = async (e) => {
  const base64 = e.target.result.split(',')[1];
  
  const response = await fetch('http://localhost:8000/parse/base64', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      file_content: base64,
      file_name: 'resume.pdf'
    })
  });
  
  const data = await response.json();
  console.log(data);
};
fileReader.readAsDataURL(file);
```

---

## 📈 Performance

### Metrics

- **Cold Start**: ~3-4 seconds (Lambda)
- **Warm Start**: ~200-500ms
- **Processing Time**: ~1-3 seconds per resume
- **Max File Size**: 10 MB (configurable)
- **Supported Formats**: PDF, DOCX

### Optimization Tips

1. **Use warm instances** - Configure provisioned concurrency for Lambda
2. **Cache dependencies** - Parser is initialized once
3. **Optimize file size** - Compress large PDFs
4. **Use async processing** - For batch operations

---

## 🐛 Troubleshooting

### Common Issues

**1. "Module not found" errors**
```bash
# Reinstall dependencies
pip install -r requirements.txt
```

**2. "SpaCy model not found"**
```bash
# Download model
python -m spacy download en_core_web_sm
```

**3. "NLTK data not found"**
```python
import nltk
nltk.download('punkt')
nltk.download('stopwords')
```

**4. "Port already in use"**
```bash
# Change port
uvicorn api:app --port 8001
```

**5. Docker build fails**
```bash
# Clear cache and rebuild
docker build --no-cache -f Dockerfile.api -t resume-parser-api .
```

---

## 📚 Additional Resources

- **Interactive API Docs**: `/docs` (Swagger UI)
- **Alternative Docs**: `/redoc` (ReDoc)
- **OpenAPI Schema**: `/openapi.json`

---

## 💡 Examples

### Full Python Client

```python
import requests
from typing import Optional

class ResumeParserClient:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
    
    def parse_file(self, file_path: str, include_raw_text: bool = False):
        """Parse resume from file"""
        with open(file_path, 'rb') as f:
            response = requests.post(
                f'{self.base_url}/parse/upload',
                files={'file': f},
                params={'include_raw_text': include_raw_text}
            )
        response.raise_for_status()
        return response.json()
    
    def parse_s3(self, bucket: str, key: str, include_raw_text: bool = False):
        """Parse resume from S3"""
        response = requests.post(
            f'{self.base_url}/parse/s3',
            json={
                's3_bucket': bucket,
                's3_key': key,
                'include_raw_text': include_raw_text
            }
        )
        response.raise_for_status()
        return response.json()
    
    def health(self):
        """Check API health"""
        response = requests.get(f'{self.base_url}/health')
        response.raise_for_status()
        return response.json()

# Usage
client = ResumeParserClient('http://localhost:8000')
result = client.parse_file('resume.pdf')
print(f"Name: {result['data']['contact']['name']}")
print(f"Skills: {', '.join(result['data']['skills'][:5])}")
```

---

## 🎉 You're Ready!

Your FastAPI-based resume parser is ready to deploy. Choose your deployment option:

- **Quick & Cheap**: AWS Lambda (serverless)
- **Always Warm**: AWS ECS/Fargate
- **Simple**: Google Cloud Run
- **Local Dev**: Docker

For questions or issues, check the logs or interactive docs at `/docs`.

