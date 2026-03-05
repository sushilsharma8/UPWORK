#!/usr/bin/env bash
# Deploy Resume Parser API to AWS Lambda (container image)
# Usage: ./scripts/deploy-api-lambda.sh [REGION]
# Example: ./scripts/deploy-api-lambda.sh us-east-1

set -e

REGION="${1:-us-east-1}"
REPO_NAME="resume-parser-api"
IMAGE_TAG="latest"
FUNCTION_NAME="resume-parser"

# Project root = parent of scripts/
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "==> Deploying Resume Parser API to AWS Lambda (region: $REGION)"
echo "    Project root: $ROOT_DIR"
echo ""

# 1. Build Docker image from project root (linux/amd64 for Lambda x86_64)
echo "==> Building Docker image (linux/amd64 for Lambda)..."
cd "$ROOT_DIR"
DOCKER_BUILDKIT=1 docker build --platform linux/amd64 --provenance=false -t "$REPO_NAME:$IMAGE_TAG" .
echo "    Build complete."
echo ""

# 2. Get AWS account ID and ECR URI
echo "==> Getting AWS account ID..."
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$REPO_NAME:$IMAGE_TAG"
echo "    Account: $ACCOUNT_ID  ECR URI: $ECR_URI"
echo ""

# 3. Create ECR repository if it doesn't exist
echo "==> Ensuring ECR repository exists..."
aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$REGION" 2>/dev/null || \
  aws ecr create-repository --repository-name "$REPO_NAME" --region "$REGION" --output text
echo ""

# 4. Log in to ECR and push
echo "==> Logging in to ECR and pushing image..."
aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
docker tag "$REPO_NAME:$IMAGE_TAG" "$ECR_URI"
docker push "$ECR_URI"
echo "    Push complete."
echo ""

# 5. Update Lambda function to use new image
echo "==> Updating Lambda function code..."
aws lambda update-function-code \
  --function-name "$FUNCTION_NAME" \
  --image-uri "$ECR_URI" \
  --region "$REGION" \
  --output table
echo ""
echo "==> Waiting for Lambda to be updated..."
aws lambda wait function-updated --function-name "$FUNCTION_NAME" --region "$REGION"
echo "    Lambda updated successfully."

echo ""
echo "==> Done. Image URI: $ECR_URI"
