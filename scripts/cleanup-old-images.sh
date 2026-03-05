#!/usr/bin/env bash
# Remove old ECR images (keep current 'latest') and prune unused local Docker images.
# Usage: ./scripts/cleanup-old-images.sh [REGION]

set -e

REGION="${1:-us-east-1}"
REPO_NAME="resume-parser-api"
IMAGE_TAG="latest"

echo "==> Cleaning up old images (region: $REGION)"
echo ""

# --- ECR: delete old images, keep the one tagged 'latest' ---
echo "==> ECR: Listing images in $REPO_NAME..."
if ! aws ecr describe-repositories --repository-names "$REPO_NAME" --region "$REGION" &>/dev/null; then
  echo "    Repository $REPO_NAME not found; skipping ECR."
else
  # Keep the most recently pushed image; delete all older ones.
  # Use describe-images so we only delete top-level image manifests (not layer digests).
  # Deleting layer digests fails with ImageReferencedByManifestList.
  DIGEST_LATEST=$(aws ecr describe-images --repository-name "$REPO_NAME" --region "$REGION" \
    --query "sort_by(imageDetails, &imagePushedAt) | [-1].imageDigest" --output text 2>/dev/null || true)
  if [[ -z "$DIGEST_LATEST" || "$DIGEST_LATEST" == "None" ]]; then
    echo "    No images in repository; skipping ECR delete."
  else
    echo "    Keeping digest: $DIGEST_LATEST"
    # Digests of older images only (all but the newest)
    TO_DELETE=$(aws ecr describe-images --repository-name "$REPO_NAME" --region "$REGION" \
      --query "sort_by(imageDetails, &imagePushedAt) | [:-1].imageDigest" --output text 2>/dev/null || true)
    TO_DELETE=(${TO_DELETE// / })
    if [[ ${#TO_DELETE[@]} -gt 0 && -n "${TO_DELETE[0]}" && "${TO_DELETE[0]}" != "None" ]]; then
      echo "    Deleting ${#TO_DELETE[@]} old image manifest(s)..."
      for d in "${TO_DELETE[@]}"; do
        [[ -z "$d" || "$d" == "None" ]] && continue
        aws ecr batch-delete-image --repository-name "$REPO_NAME" --region "$REGION" \
          --image-ids imageDigest="$d" --no-cli-pager --output text >/dev/null 2>&1 || true
      done
      echo "    ECR cleanup done."
    else
      echo "    No other images to delete in ECR."
    fi
  fi
fi
echo ""

# --- Local Docker: prune dangling images ---
echo "==> Local Docker: Removing dangling images..."
docker image prune -f
echo "    Done."
echo ""
echo "==> Cleanup finished."
