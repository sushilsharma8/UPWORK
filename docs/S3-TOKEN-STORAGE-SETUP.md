# S3 Bucket Setup Guide for Token Storage (Lambda)

This guide walks you through creating an S3 bucket and configuring your Lambda function so API tokens are stored persistently (no more tokens disappearing after cold starts or instance recycling).

---

## 1. Create an S3 Bucket

### Option A: AWS Console

1. Open **AWS Console** → **S3** → **Create bucket**.
2. **Bucket name**: Choose a unique name (e.g. `my-app-tokens-prod`). Note it for step 4.
3. **Region**: Use the same region as your Lambda function (e.g. `us-east-1`).
4. **Block Public Access**: Leave all four options **on** (recommended). Tokens are sensitive; only Lambda should access the bucket via IAM.
5. **Bucket Versioning**: Optional. Enable if you want to recover previous token state.
6. **Default encryption**: Recommended. Enable **SSE-S3** (or SSE-KMS if you use KMS).
7. Click **Create bucket**.

### Option B: AWS CLI

```bash
# Replace REGION and BUCKET_NAME with your values
aws s3api create-bucket \
  --bucket YOUR-BUCKET-NAME \
  --region us-east-1

# Optional: enable default encryption
aws s3api put-bucket-encryption \
  --bucket YOUR-BUCKET-NAME \
  --server-side-encryption-configuration '{
    "Rules": [{
      "ApplyServerSideEncryptionByDefault": {
        "SSEAlgorithm": "AES256"
      }
    }]
  }'
```

---

## 2. Create the Token Object Key (Optional)

The app uses the key `tokens.json` by default. You do **not** need to create the file in S3 first—the first time you create a token via the admin API, the code will create the object. If you prefer to pre-create an empty file:

**Console:** Bucket → **Create folder** is not needed. Just leave the bucket empty.

**CLI (optional empty file):**

```bash
echo '{}' | aws s3 cp - s3://YOUR-BUCKET-NAME/tokens.json
```

---

## 3. Grant Lambda Permission to Read/Write the Bucket

Your Lambda function runs with an **execution role**. That role must be allowed to get and put the token file.

### Option A: AWS Console (IAM)

1. Go to **IAM** → **Roles** → open the role used by your Lambda function (e.g. `resume-parser-lambda-role`).
2. Click **Add permissions** → **Create inline policy** (or attach a policy).
3. **JSON** tab, use a policy like this (replace `YOUR-BUCKET-NAME` and optional `tokens.json` key):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "TokenStorageS3",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject"
      ],
      "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/tokens.json"
    }
  ]
}
```

For a key prefix (e.g. all objects under `api/`):

```json
"Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/api/*"
```

4. **Next** → Name the policy (e.g. `TokenStorageS3`) → **Create policy**.

### Option B: AWS CLI (attach inline policy)

1. Save the policy to a file, e.g. `token-s3-policy.json`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "TokenStorageS3",
      "Effect": "Allow",
      "Action": ["s3:GetObject", "s3:PutObject"],
      "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/tokens.json"
    }
  ]
}
```

2. Attach it to the Lambda execution role (replace `LAMBDA_EXECUTION_ROLE_NAME`):

```bash
aws iam put-role-policy \
  --role-name LAMBDA_EXECUTION_ROLE_NAME \
  --policy-name TokenStorageS3 \
  --policy-document file://token-s3-policy.json
```

---

## 4. Configure Lambda Environment Variables

In **Lambda** → Your function → **Configuration** → **Environment variables** → **Edit**:

**Option A – Bucket + key (recommended)**

| Key | Value |
|-----|--------|
| `TOKEN_STORAGE_S3_BUCKET` | `YOUR-BUCKET-NAME` |
| `TOKEN_STORAGE_S3_KEY` | `tokens.json` *(optional; this is the default)* |
| `ADMIN_API_KEY` | *your existing admin key* |

**Option B – S3 URI**

| Key | Value |
|-----|--------|
| `TOKEN_STORAGE_PATH` | `s3://YOUR-BUCKET-NAME/tokens.json` |
| `ADMIN_API_KEY` | *your existing admin key* |

Remove or leave `TOKEN_STORAGE_PATH=/tmp/tokens.json` **unset** when using S3 so the app uses S3, not `/tmp`.

Save the configuration.

---

## 5. Verify

1. **Invoke Lambda** (e.g. call the admin token-create endpoint with your `ADMIN_API_KEY`).
2. In **S3** → your bucket, you should see `tokens.json` after creating a token.
3. Call an API endpoint that requires a client token; it should succeed. Restart or cold-start Lambda and call again—the token should still work (persistent storage).

---

## Summary Checklist

- [ ] S3 bucket created in the same region as Lambda.
- [ ] Bucket is private (block public access on).
- [ ] Lambda execution role has `s3:GetObject` and `s3:PutObject` on `arn:aws:s3:::BUCKET/tokens.json` (or your key).
- [ ] Lambda env: `TOKEN_STORAGE_S3_BUCKET` (and optional `TOKEN_STORAGE_S3_KEY`) **or** `TOKEN_STORAGE_PATH=s3://bucket/key`.
- [ ] No `TOKEN_STORAGE_PATH=/tmp/tokens.json` when using S3 (or ensure S3 env vars take precedence per `token_storage.py` logic).

---

## Security Notes

- **Restrict the IAM policy** to the specific object (or prefix) you use, not the whole bucket, as in the examples above.
- Store `ADMIN_API_KEY` in **AWS Secrets Manager** and load it at runtime for production instead of plain env vars.
- Enable **bucket encryption** (SSE-S3 or SSE-KMS) so token data is encrypted at rest.
