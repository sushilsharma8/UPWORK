# Resume Parser API — Deployment Process

> **How to use this in Notion:** Create a new page in Notion, then paste this entire document. Notion will convert the Markdown (headings, code blocks, lists) into blocks. You can also use **Import** → **Markdown** to bring in the file.

---

## Overview

This document explains how to deploy the **Resume Parser API** (FastAPI on AWS Lambda) end-to-end: building the Docker image, pushing to ECR, configuring Lambda, setting up token storage (S3), and connecting API Gateway or Function URL.

---

## 1. Prerequisites

- **AWS account** with CLI configured (`aws configure`)
- **Docker** installed
- **Python 3.11** (for local token creation and scripts)
- Project files in `docker_build_context/` (or project root) including:
  - `api.py`, `lambda_api_handler.py`, `resume_parser_improved.py`
  - `token_manager.py`, `token_storage.py`
  - `requirements.txt`, `Dockerfile`

---

## 2. Build the Docker Image

Build from the directory that contains the Dockerfile (e.g. `docker_build_context/` or project root):

```bash
cd docker_build_context   # or project root if Dockerfile is there
docker build -t resume-parser-api .
```

This image includes:
- Python 3.11 Lambda base
- System deps (gcc, gcc-c++, make)
- Python dependencies from `requirements.txt`
- SpaCy model `en_core_web_sm`
- NLTK data (punkt, stopwords)
- Application code

---

## 3. Push Image to Amazon ECR

1. **Create an ECR repository** (if needed):

   ```bash
   aws ecr create-repository --repository-name resume-parser-api --region us-east-1
   ```

2. **Log in to ECR:**

   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com
   ```

   Replace `<ACCOUNT_ID>` with your AWS account ID.

3. **Tag and push:**

   ```bash
   docker tag resume-parser-api:latest <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/resume-parser-api:latest
   docker push <ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/resume-parser-api:latest
   ```

---

## 4. Create or Update the Lambda Function

### 4.1 Create function (container image)

- **Function name:** e.g. `resume-parser-api`
- **Container image:** use the ECR image URI from the push step
- **Architecture:** x86_64 or arm64 as needed

### 4.2 Lambda configuration

| Setting | Value |
|--------|--------|
| **Handler** | `lambda_api_handler.lambda_handler` (or leave empty for container) |
| **Timeout** | 30 s minimum; 60–120 s for batch |
| **Memory** | 512 MB minimum; 1024–2048 MB for NLP |
| **Runtime** | N/A when using container image |

### 4.3 Environment variables

**Required for token auth:**

- `ADMIN_API_KEY` — secret key for admin/token management endpoints.

**Token storage (choose one):**

- **Option A – S3 (recommended):**
  - `TOKEN_STORAGE_S3_BUCKET` = your bucket name
  - `TOKEN_STORAGE_S3_KEY` = `tokens.json` (optional; default)
- **Option B – S3 URI:**
  - `TOKEN_STORAGE_PATH` = `s3://your-bucket/tokens.json`
- **Option C – Ephemeral (not recommended):**
  - `TOKEN_STORAGE_PATH` = `/tmp/tokens.json`  
  Tokens are lost on cold start or when the execution environment is recycled.

---

## 5. S3 Token Storage Setup (Recommended)

For persistent tokens across cold starts:

1. **Create an S3 bucket** in the same region as Lambda (e.g. `us-east-1`).
2. **Block public access**; use default encryption (e.g. SSE-S3).
3. **Lambda execution role:** add inline policy with `s3:GetObject` and `s3:PutObject` on `arn:aws:s3:::YOUR-BUCKET/tokens.json`.
4. **Lambda env:** set `TOKEN_STORAGE_S3_BUCKET` (and optional `TOKEN_STORAGE_S3_KEY`) or `TOKEN_STORAGE_PATH=s3://bucket/tokens.json`.
5. **Verify:** create a token via admin API; confirm `tokens.json` appears in the bucket and tokens persist after cold start.

See **S3-TOKEN-STORAGE-SETUP.md** in the repo for detailed steps and IAM policy JSON.

---

## 6. Expose the API

### Option A: API Gateway HTTP API

1. **API Gateway** → Create API → **HTTP API** → Build.
2. **Integrations** → Add integration → **Lambda** → select your function.
3. **Routes:** e.g. `ANY /{proxy+}` → your Lambda.
4. **Deploy** to a stage (e.g. `prod`).
5. Use the **Invoke URL** as the base for all API calls.

### Option B: Lambda Function URL

1. **Lambda** → Your function → **Configuration** → **Function URL** → Create.
2. **Auth type:** NONE (if API Gateway is not in front) or AWS_IAM.
3. Configure **CORS** if needed.
4. Use the generated Function URL as the API base.

---

## 7. Post-deploy: Token Management

Create and manage tokens locally, then rely on S3 for persistence in Lambda.

**Create token:**

```bash
python scripts/create_token.py --client "ClientName" --expires-days 365
```

**List / revoke / delete:**

```bash
python scripts/create_token.py --list
python scripts/create_token.py --revoke <token_string>
python scripts/create_token.py --delete <token_string>
```

Clients call the API with header: `X-API-Key: <token>`.

---

## 8. Testing

**Health check (API Gateway proxy):**

```json
{
  "httpMethod": "GET",
  "path": "/health",
  "headers": {},
  "body": null
}
```

**Health check (Function URL):**

```json
{
  "version": "2.0",
  "routeKey": "GET /health",
  "rawPath": "/health",
  "headers": {},
  "requestContext": { "http": { "method": "GET", "path": "/health" } }
}
```

**Example API call:**

```bash
curl -X POST "https://YOUR_API_ENDPOINT/parse/upload" \
  -H "X-API-Key: YOUR_CLIENT_TOKEN" \
  -F "file=@resume.pdf"
```

---

## 9. Common Issues

| Issue | What to do |
|--------|-------------|
| Handler not found | Set handler to `lambda_api_handler.lambda_handler` in Lambda config. |
| Module not found | Ensure all required Python files are in the image/package (api, lambda_api_handler, token_manager, token_storage, resume_parser_improved). |
| Tokens “disappear” | Use S3 for token storage; avoid `/tmp` for production. |
| Token file not writable | Configure S3 bucket + IAM and env vars (see section 5). |
| Cold start timeout | Increase timeout (e.g. 60+ s) and/or memory; consider provisioned concurrency. |

---

## 10. Security Checklist

- [ ] Store `ADMIN_API_KEY` in Secrets Manager (or similar) in production.
- [ ] Use S3 (or DynamoDB) for token storage, not `/tmp`.
- [ ] Lambda role has least privilege (e.g. only the S3 key or prefix needed).
- [ ] Use API Gateway or Function URL with appropriate auth (e.g. IAM or API keys) if needed.
- [ ] Enable encryption on the S3 bucket used for tokens.

---

## 11. Monitoring

- **CloudWatch Logs:** Lambda log group for errors and performance.
- **CloudWatch Metrics:** Invocations, duration, errors.
- **X-Ray:** Enable on Lambda for tracing (optional).

---

## Summary

1. Build Docker image from `docker_build_context` (or project root).
2. Push image to ECR and create/update Lambda from that image.
3. Set Lambda handler, timeout, memory, and env vars (`ADMIN_API_KEY`, S3 token storage).
4. Set up S3 bucket and IAM so Lambda can read/write `tokens.json`.
5. Expose via API Gateway or Function URL.
6. Create and manage tokens with `scripts/create_token.py`; clients use `X-API-Key`.
7. Test with health and upload endpoints; monitor via CloudWatch.

For more detail, see in the repo: **LAMBDA-DEPLOYMENT.md**, **GUIDE.md**, **S3-TOKEN-STORAGE-SETUP.md**.
