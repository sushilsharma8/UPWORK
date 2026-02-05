# AWS Lambda Deployment Guide

## Lambda Handler Configuration

The Lambda function handler must be set to:
```
lambda_api_handler.lambda_handler
```

## Important Configuration Settings

### 1. Handler Setting
In AWS Lambda Console → Configuration → Runtime settings:
- **Handler**: `lambda_api_handler.lambda_handler`

### 2. Environment Variables
Set these in Lambda → Configuration → Environment variables:

**Option A – Persistent tokens (recommended for Lambda)**  
Use S3 so tokens survive cold starts and scale-downs:

```
TOKEN_STORAGE_S3_BUCKET=your-bucket-name
TOKEN_STORAGE_S3_KEY=tokens.json
ADMIN_API_KEY=your-secure-admin-key-here
```

Or use an S3 URI for `TOKEN_STORAGE_PATH`:

```
TOKEN_STORAGE_PATH=s3://your-bucket-name/tokens.json
ADMIN_API_KEY=your-secure-admin-key-here
```

Give the Lambda execution role **s3:GetObject** and **s3:PutObject** on that bucket/key.  
**Full steps:** see [S3-TOKEN-STORAGE-SETUP.md](S3-TOKEN-STORAGE-SETUP.md).

**Option B – Ephemeral tokens (not recommended)**  
Tokens are lost when the execution environment is recycled or a new instance starts:

```
TOKEN_STORAGE_PATH=/tmp/tokens.json
ADMIN_API_KEY=your-secure-admin-key-here
```

**Why tokens “disappear” with `/tmp`:**  
Lambda’s `/tmp` is **ephemeral**. It is cleared when an execution environment is recycled or when a new instance starts (cold start). So tokens are not expiring by time—they are lost because the file is stored in non-persistent storage. Use S3 for persistent token storage.

### 3. Timeout Settings
- **Timeout**: 30 seconds (minimum recommended)
- For batch processing, increase to 60-120 seconds

### 4. Memory Settings
- **Memory**: 512 MB (minimum recommended)
- For better performance with NLP models, use 1024 MB or 2048 MB

### 5. Runtime
- **Runtime**: Python 3.11 (or use container image)

## Docker Image Deployment

If using container image deployment:

1. **Build the image:**
   ```bash
   docker build -t resume-parser-api .
   ```

2. **Tag for ECR:**
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
   docker tag resume-parser-api:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/resume-parser-api:latest
   docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/resume-parser-api:latest
   ```

3. **Create/Update Lambda Function:**
   - Use the ECR image URI
   - Handler: `lambda_api_handler.lambda_handler` (or leave empty for container images)
   - Set environment variables as above

## Testing the Lambda Function

### Test Event (API Gateway Proxy)
```json
{
  "httpMethod": "GET",
  "path": "/health",
  "headers": {},
  "body": null
}
```

### Test Event (Function URL)
```json
{
  "version": "2.0",
  "routeKey": "GET /health",
  "rawPath": "/health",
  "headers": {},
  "requestContext": {
    "http": {
      "method": "GET",
      "path": "/health"
    }
  }
}
```

## Common Issues

### Issue: Handler not found
**Solution:** Ensure handler is set to `lambda_api_handler.lambda_handler` in Lambda configuration

### Issue: Module not found (token_manager, token_storage)
**Solution:** Ensure all Python files are included in the deployment package:
- `api.py`
- `lambda_api_handler.py`
- `token_manager.py`
- `token_storage.py`
- `resume_parser_improved.py`

### Issue: Tokens disappear or “expire” after some time
**Cause:** With `TOKEN_STORAGE_PATH=/tmp/tokens.json`, tokens are stored in Lambda’s ephemeral `/tmp`. They are lost when the execution environment is recycled or a new instance starts.  
**Solution:** Use S3 for token storage. Set `TOKEN_STORAGE_S3_BUCKET` (and optionally `TOKEN_STORAGE_S3_KEY`) or `TOKEN_STORAGE_PATH=s3://bucket/key`, and ensure the Lambda role has s3:GetObject and s3:PutObject on that bucket.

### Issue: Token storage file not writable
**Solution:** 
- For persistent tokens: set `TOKEN_STORAGE_S3_BUCKET` (and optional `TOKEN_STORAGE_S3_KEY`) or `TOKEN_STORAGE_PATH=s3://bucket/key`
- For ephemeral tokens only: set `TOKEN_STORAGE_PATH=/tmp/tokens.json`

### Issue: Cold start timeout
**Solution:**
- Increase Lambda timeout to 60+ seconds
- Increase memory allocation
- Consider using provisioned concurrency for production

## API Gateway Integration

1. **Create API Gateway HTTP API**
2. **Add Lambda integration**
3. **Configure routes:**
   - `ANY /{proxy+}` → Lambda function
4. **Deploy to stage**

## Function URL (Alternative to API Gateway)

1. **Enable Function URL** in Lambda console
2. **Set Auth type**: NONE (API Gateway handles auth) or AWS_IAM
3. **CORS**: Configure if needed
4. **Use the Function URL** directly

## Monitoring

- **CloudWatch Logs**: Check for errors and performance
- **CloudWatch Metrics**: Monitor invocations, duration, errors
- **X-Ray**: Enable for detailed tracing (optional)

## Security Best Practices

1. **Admin API Key**: Store in AWS Secrets Manager (not environment variables)
2. **Token Storage**: Use S3 or DynamoDB for persistent storage
3. **IAM Roles**: Use least privilege principle
4. **VPC**: Deploy in VPC if accessing private resources
5. **API Keys**: Use API Gateway API keys for additional security layer

