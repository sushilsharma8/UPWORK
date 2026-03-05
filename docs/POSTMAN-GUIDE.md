# Postman Collection Guide

## Import Instructions

### 1. Import Collection
1. Open Postman
2. Click **Import** button (top left)
3. Select `Resume_Parser_API.postman_collection.json`
4. Click **Import**

### 2. Import Environment (Optional but Recommended)
1. Click **Import** button
2. Select `Resume_Parser_API.postman_environment.json`
3. Click **Import**
4. Select the environment from the dropdown (top right)

### 3. Configure Environment Variables

Update these variables in your Postman environment:

- **`base_url`**: Your API Gateway endpoint (e.g., `https://abc123.execute-api.us-east-1.amazonaws.com`)
- **`api_key`**: Client API access token (for parse endpoints)
- **`admin_api_key`**: Admin API key (for token management endpoints)
- **`token`**: Token to test (for get/delete token endpoints)

## Collection Structure

### 📁 General
- **Root - API Info**: Get API information and available endpoints
- **Health Check**: Check API health status

### 📁 Parse
- **Parse Upload**: Upload a PDF/DOCX file to parse
- **Parse Base64**: Parse resume from base64 encoded content
- **Parse S3**: Parse resume from S3 bucket
- **Parse URL**: Parse resume from public URL
- **Parse Batch**: Parse up to 10 resumes at once

### 📁 Admin - Token Management
- **Create Token**: Create a new access token for a client
- **List All Tokens**: Get all tokens (active and inactive)
- **List Active Tokens Only**: Get only active tokens
- **Get Token Info**: Get information about a specific token
- **Revoke Token**: Deactivate a token (keeps it in system)
- **Delete Token**: Permanently delete a token

## Usage Examples

### 1. Test Health Check
1. Select **General → Health Check**
2. Click **Send**
3. Should return: `{"status": "healthy", "version": "1.0.0", "timestamp": "..."}`

### 2. Parse a Resume (File Upload)
1. Select **Parse → Parse Upload**
2. In the **Body** tab, click **Select Files** next to `file`
3. Choose a PDF or DOCX resume file
4. Set `include_raw_text` to `false` (or `true` if you want raw text)
5. Make sure `X-API-Key` header has your client API key
6. Click **Send**

### 3. Create a Token
1. Select **Admin - Token Management → Create Token**
2. Update the request body:
   ```json
   {
     "client_name": "TCS",
     "expires_days": 365,
     "metadata": {
       "contact_email": "client@example.com"
     }
   }
   ```
3. Make sure `X-API-Key` header has your admin API key
4. Click **Send**
5. **IMPORTANT**: Copy the `token` from the response - you won't see it again!

### 4. List All Tokens
1. Select **Admin - Token Management → List All Tokens**
2. Make sure `X-API-Key` header has your admin API key
3. Click **Send**
4. You'll see all tokens with their status, creation date, expiration, etc.

### 5. Parse Batch (Multiple Files)
1. Select **Parse → Parse Batch (Up to 10 files)**
2. In the **Body** tab, add multiple `files` entries
3. Click **Select Files** for each file entry
4. Choose up to 10 PDF or DOCX files
5. Make sure `X-API-Key` header has your client API key
6. Click **Send**
7. Response will show results for each file

## Request Examples

### Parse Base64
```json
{
  "file_content": "JVBERi0xLjQKJeLjz9MKMy...",
  "file_name": "resume.pdf",
  "include_raw_text": false
}
```

### Parse S3
```json
{
  "s3_bucket": "my-resume-bucket",
  "s3_key": "resumes/john-doe-resume.pdf",
  "include_raw_text": false
}
```

### Parse URL
```json
{
  "url": "https://example.com/resumes/john-doe.pdf",
  "include_raw_text": false
}
```

### Create Token
```json
{
  "client_name": "Salesforce",
  "expires_days": 180,
  "metadata": {
    "contact_email": "api@salesforce.com",
    "contact_name": "John Doe",
    "notes": "Production API key"
  }
}
```

### Revoke Token
```json
{
  "token": "abc123xyz789..."
}
```

## Authentication

### Client API Key (for Parse endpoints)
- Header: `X-API-Key`
- Value: Client access token (created via admin endpoints)
- Used for: All `/parse/*` endpoints

### Admin API Key (for Admin endpoints)
- Header: `X-API-Key`
- Value: Admin API key (set in Lambda environment variable)
- Used for: All `/admin/*` endpoints

## Tips

1. **Save Responses**: Use Postman's "Save Response" feature to save token responses
2. **Tests Tab**: Add tests to automatically extract tokens from responses
3. **Pre-request Scripts**: Automate token extraction and reuse
4. **Environments**: Create separate environments for dev/staging/production
5. **Variables**: Use collection variables for commonly used values

## Troubleshooting

### 403 Forbidden
- Check that your API key is correct
- Verify the key hasn't expired
- Ensure you're using the right key type (client vs admin)

### 404 Not Found
- Verify the `base_url` is correct
- Check the endpoint path
- Ensure API Gateway is deployed

### 500 Internal Server Error
- Check CloudWatch logs for detailed error messages
- Verify all required files are in the Lambda package
- Check environment variables are set correctly

### File Upload Issues
- Ensure file is PDF or DOCX format
- Check file size (Lambda has limits)
- Verify `Content-Type` header is set correctly

## Next Steps

1. Import the collection and environment
2. Configure environment variables
3. Test health check endpoint
4. Create a token using admin endpoints
5. Use the token to test parse endpoints
6. Explore batch processing for multiple resumes

Happy testing! 🚀

