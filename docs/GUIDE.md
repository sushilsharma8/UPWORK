# API Gateway Deployment Guide with Custom Token Management

This guide provides instructions on how to connect your Lambda function to an API Gateway and use a custom token-based authentication system managed entirely in your code.

## Overview

Instead of using AWS API Gateway's built-in API keys, this system uses a custom token management solution where you can:
- Generate access tokens programmatically using a simple CLI script
- Store tokens in a JSON file (or extend to DynamoDB/database)
- Manage token lifecycle (create, revoke, delete) through code
- Set expiration dates for tokens
- Track token metadata (client names, contact info, etc.)

## 1. Create an API Gateway

First, you'll create an HTTP API, which is a simpler and more cost-effective option for this use case.

1.  **Navigate to API Gateway** in the AWS Management Console.
2.  Click **Create API**.
3.  Find the **HTTP API** card and click **Build**.
4.  Under **Integrations**, click **Add integration**.
5.  Select **Lambda**.
6.  In the **Lambda function** dropdown, choose your resume parser Lambda function.
7.  Give your API a name, like `ResumeParserAPI`.
8.  Click **Next**.
9.  For **Configure routes**, the default `ANY` method for the `/{proxy+}` resource is fine for now. This will forward all requests to your Lambda.
10. Click **Next**.
11. Review the stage settings (a default stage is fine) and click **Next**.
12. Click **Create**.

**Note:** You do NOT need to configure API keys or usage plans in AWS API Gateway. Our custom token system handles authentication.

## 2. Configure Token Storage

The token system stores tokens in a JSON file by default. You can configure where this file is stored:

### Option A: Default Location (Recommended for Lambda)
The tokens will be stored in `tokens.json` in the same directory as your Lambda function code. This file will be included in your Lambda deployment package.

### Option B: Custom Location (S3 for Production)
For production, you may want to store tokens in S3 or DynamoDB. You can set the `TOKEN_STORAGE_PATH` environment variable in your Lambda function:

1.  **Navigate to your Lambda function** in the AWS Management Console.
2.  Go to the **Configuration** tab and select **Environment variables**.
3.  Click **Edit** and then **Add environment variable**.
4.  Create a new variable:
    *   **Key**: `TOKEN_STORAGE_PATH`
    *   **Value**: Path to your token storage file (e.g., `/tmp/tokens.json` for Lambda, or S3 path if using S3 storage)
5.  **Save** the changes.

**Note:** For Lambda, `/tmp` is the only writable directory. If you need persistent storage, consider using S3 or DynamoDB (extend `token_storage.py` to support these).

## 3. Create Access Tokens for Your Clients

Use the `scripts/create_token.py` script to generate access tokens for your clients (run from project root).

### Installation & Setup

Make sure you have the token management files in your project (run commands from the project root):
- `token_manager.py`
- `token_storage.py`
- `scripts/create_token.py`

### Creating Tokens

#### Basic Token (No Expiration)
```bash
python scripts/create_token.py --client "TCS"
```

#### Token with Expiration (365 days)
```bash
python scripts/create_token.py --client "Salesforce" --expires-days 365
```

#### Token with Metadata
```bash
python scripts/create_token.py --client "Acme Corp" \
  --expires-days 180 \
  --metadata '{"contact_email":"john@acme.com","contact_name":"John Doe"}'
```

**Important:** The script will display the generated token. **Save it securely** - you won't be able to see it again! Provide this token to your client.

### Managing Tokens

#### List All Tokens
```bash
python scripts/create_token.py --list
```

#### List Only Active Tokens
```bash
python scripts/create_token.py --list --active-only
```

#### Revoke a Token (Deactivate)
```bash
python scripts/create_token.py --revoke <token_string>
```

#### Delete a Token (Permanent)
```bash
python scripts/create_token.py --delete <token_string>
```

### Token File Structure

Tokens are stored in `tokens.json` with the following structure:
```json
{
  "token_string_here": {
    "token": "token_string_here",
    "client_name": "TCS",
    "created_at": "2024-01-01T00:00:00",
    "expires_at": "2024-12-31T23:59:59",
    "is_active": true,
    "metadata": {
      "contact_email": "client@example.com"
    }
  }
}
```

## 4. Deploy Your Lambda Function

Make sure to include the token management files in your Lambda deployment package:

1. Include these files in your Lambda zip:
   - `api.py`
   - `lambda_api_handler.py`
   - `token_manager.py`
   - `token_storage.py`
   - `resume_parser_improved.py`
   - `tokens.json` (if you've pre-created tokens)
   - All other dependencies

2. If you're using a deployment tool, ensure these files are included in the package.

3. Deploy the Lambda function.

## 5. How Your Clients Will Use the API

Your clients can now make requests to the API Gateway endpoint by including their assigned access token in the `X-API-Key` header.

The invoke URL for your API can be found on the API Gateway page for your API.

### Example using `curl`:

```bash
curl -X POST "https://YOUR_API_GATEWAY_ENDPOINT/parse/upload" \
-H "Content-Type: multipart/form-data" \
-H "X-API-Key: YOUR_CLIENTS_ACCESS_TOKEN" \
-F "file=@/path/to/resume.pdf"
```

### Example using Python:

```python
import requests

url = "https://YOUR_API_GATEWAY_ENDPOINT/parse/upload"
headers = {
    "X-API-Key": "YOUR_CLIENTS_ACCESS_TOKEN"
}

with open("resume.pdf", "rb") as f:
    files = {"file": ("resume.pdf", f, "application/pdf")}
    response = requests.post(url, headers=headers, files=files)
    print(response.json())
```

### Example using JavaScript/Node.js:

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

const form = new FormData();
form.append('file', fs.createReadStream('resume.pdf'));

axios.post('https://YOUR_API_GATEWAY_ENDPOINT/parse/upload', form, {
  headers: {
    ...form.getHeaders(),
    'X-API-Key': 'YOUR_CLIENTS_ACCESS_TOKEN'
  }
})
.then(response => console.log(response.data))
.catch(error => console.error(error));
```

### Batch Processing (Up to 10 Resumes)

For processing multiple resumes at once, use the `/parse/batch` endpoint:

#### Example using `curl`:

```bash
curl -X POST "https://YOUR_API_GATEWAY_ENDPOINT/parse/batch" \
-H "X-API-Key: YOUR_CLIENTS_ACCESS_TOKEN" \
-F "files=@resume1.pdf" \
-F "files=@resume2.pdf" \
-F "files=@resume3.pdf"
```

#### Example using Python:

```python
import requests

url = "https://YOUR_API_GATEWAY_ENDPOINT/parse/batch"
headers = {
    "X-API-Key": "YOUR_CLIENTS_ACCESS_TOKEN"
}

files = [
    ("files", ("resume1.pdf", open("resume1.pdf", "rb"), "application/pdf")),
    ("files", ("resume2.pdf", open("resume2.pdf", "rb"), "application/pdf")),
    ("files", ("resume3.pdf", open("resume3.pdf", "rb"), "application/pdf")),
]

response = requests.post(url, headers=headers, files=files)
result = response.json()

print(f"Processed {result['total_files']} files")
print(f"Successful: {result['successful']}, Failed: {result['failed']}")

for item in result['results']:
    if item['success']:
        print(f"✓ {item['filename']}: {item['processing_time_ms']:.2f}ms")
    else:
        print(f"✗ {item['filename']}: {item['error']}")
```

#### Batch Response Format:

```json
{
  "success": true,
  "total_files": 3,
  "successful": 2,
  "failed": 1,
  "total_processing_time_ms": 1250.5,
  "results": [
    {
      "filename": "resume1.pdf",
      "success": true,
      "data": { ... },
      "processing_time_ms": 450.2
    },
    {
      "filename": "resume2.pdf",
      "success": true,
      "data": { ... },
      "processing_time_ms": 380.1
    },
    {
      "filename": "resume3.pdf",
      "success": false,
      "error": "Invalid file type. Only PDF and DOCX files are supported.",
      "processing_time_ms": 10.5
    }
  ]
}
```

**Batch Processing Notes:**
- Maximum 10 files per batch request
- Each file is processed independently - if one fails, others will still be processed
- Results include success/failure status for each file
- Total processing time is tracked for the entire batch
- Useful for bulk processing of resumes from job portals or batch uploads

Replace `YOUR_API_GATEWAY_ENDPOINT` with your actual API Gateway invoke URL and `YOUR_CLIENTS_ACCESS_TOKEN` with the token you generated for them.

## 6. Token Management Best Practices

1. **Store tokens securely**: Keep the `tokens.json` file secure and backed up. Consider using AWS Secrets Manager or S3 for production.

2. **Set expiration dates**: Always set reasonable expiration dates for tokens to limit exposure if compromised.

3. **Use descriptive client names**: Use clear, identifiable client names when creating tokens.

4. **Monitor token usage**: Periodically review active tokens and revoke unused ones.

5. **Rotate tokens**: Consider implementing a token rotation policy for long-term clients.

6. **For Production**: Extend `token_storage.py` to use DynamoDB or a database for better scalability and persistence.

## 7. Troubleshooting

### Token Not Working
- Verify the token exists: `python scripts/create_token.py --list`
- Check if the token is active (not revoked)
- Verify the token hasn't expired
- Ensure the token is being sent in the `X-API-Key` header

### Token Storage Issues in Lambda
- Lambda only has write access to `/tmp` directory
- For persistent storage, use S3 or DynamoDB
- Set `TOKEN_STORAGE_PATH` environment variable to `/tmp/tokens.json` for Lambda

### Cannot Create Tokens
- Ensure `token_manager.py` and `token_storage.py` are in the same directory
- Check file permissions for the token storage file
- Verify Python dependencies are installed

## Summary

This custom token management system gives you full control over API access:
- ✅ No AWS API Gateway API key management needed
- ✅ Programmatic token creation and management
- ✅ Token expiration and revocation support
- ✅ Client metadata tracking
- ✅ Simple file-based storage (extensible to databases)
- ✅ Easy integration with existing Lambda functions
