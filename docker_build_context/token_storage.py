#!/usr/bin/env python3
"""
Token Storage Module
Handles storage and retrieval of API access tokens
Supports JSON file storage and S3 (for Lambda persistence).
"""

import os
import json
import logging
import re
from typing import Dict, Optional, List, Tuple
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

_S3_URI_PATTERN = re.compile(r"^s3://([^/]+)/(.*)$")


def _is_lambda() -> bool:
    return bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or os.environ.get("LAMBDA_TASK_ROOT"))


def _parse_s3_path(storage_path: str) -> Optional[Tuple[str, str]]:
    """Return (bucket, key) if path is S3 URI or env points to S3; else None."""
    if storage_path and storage_path.startswith("s3://"):
        m = _S3_URI_PATTERN.match(storage_path.strip())
        if m:
            bucket, key = m.group(1), m.group(2) or "tokens.json"
            return (bucket, key)
    if os.environ.get("TOKEN_STORAGE_S3_BUCKET"):
        bucket = os.environ.get("TOKEN_STORAGE_S3_BUCKET")
        key = os.environ.get("TOKEN_STORAGE_S3_KEY", "tokens.json")
        return (bucket, key)
    return None


class TokenStorage:
    """Token storage backend - supports JSON file and S3 storage"""

    def __init__(self, storage_path: str = None):
        """
        Initialize token storage.

        Args:
            storage_path: Path to JSON file, or S3 URI (s3://bucket/key).
                         If None, uses TOKEN_STORAGE_PATH or TOKEN_STORAGE_S3_BUCKET
                         (with optional TOKEN_STORAGE_S3_KEY). Use S3 in Lambda so tokens persist.
        """
        path_env = storage_path if storage_path is not None else os.environ.get("TOKEN_STORAGE_PATH")
        s3_bucket_env = os.environ.get("TOKEN_STORAGE_S3_BUCKET")
        self._s3 = None
        if s3_bucket_env:
            self._s3 = (s3_bucket_env, os.environ.get("TOKEN_STORAGE_S3_KEY", "tokens.json"))
        elif path_env and str(path_env).strip().lower().startswith("s3://"):
            self._s3 = _parse_s3_path(path_env)

        if self._s3:
            self._s3_bucket, self._s3_key = self._s3
            self.storage_path = None
            logger.info(f"Token storage using S3: s3://{self._s3_bucket}/{self._s3_key}")
        else:
            self._s3_bucket = self._s3_key = None
            if path_env and not str(path_env).strip().lower().startswith("s3://"):
                path = path_env
            elif _is_lambda():
                path = "/tmp/tokens.json"
                logger.info("Token storage using /tmp/tokens.json (Lambda default; set TOKEN_STORAGE_S3_BUCKET for persistence)")
            else:
                path = os.path.join(os.path.dirname(__file__), "tokens.json")
            path_str = str(Path(path).resolve())
            if path_str.startswith("/var/task"):
                path = "/tmp/tokens.json"
                logger.warning("Token path was under /var/task (read-only); using /tmp/tokens.json. Set TOKEN_STORAGE_S3_BUCKET for persistence.")
            self.storage_path = Path(path)
            self._ensure_storage_file()

    def _ensure_storage_file(self):
        """Ensure the storage file exists (file backend only)."""
        if self.storage_path is None:
            return
        if not self.storage_path.exists():
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_tokens({})
            logger.info(f"Created new token storage file at {self.storage_path}")

    def _read_tokens(self) -> Dict:
        """Read tokens from storage (file or S3)."""
        if self._s3_bucket:
            return self._read_tokens_s3()
        try:
            with open(self.storage_path, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not read token storage: {e}. Creating new storage.")
            return {}

    def _read_tokens_s3(self) -> Dict:
        """Read tokens from S3."""
        try:
            import boto3
            from botocore.exceptions import ClientError
            s3 = boto3.client("s3")
            resp = s3.get_object(Bucket=self._s3_bucket, Key=self._s3_key)
            return json.loads(resp["Body"].read().decode("utf-8"))
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") == "NoSuchKey":
                return {}
            logger.warning(f"S3 error reading token storage: {e}. Using empty store.")
            return {}
        except Exception as e:
            logger.warning(f"Could not read token storage from S3: {e}. Using empty store.")
            return {}

    def _write_tokens(self, tokens: Dict):
        """Write tokens to storage (file or S3)."""
        if self._s3_bucket:
            self._write_tokens_s3(tokens)
            return
        try:
            with open(self.storage_path, "w") as f:
                json.dump(tokens, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write token storage: {e}")
            raise

    def _write_tokens_s3(self, tokens: Dict):
        """Write tokens to S3."""
        try:
            import boto3
            s3 = boto3.client("s3")
            body = json.dumps(tokens, indent=2)
            s3.put_object(Bucket=self._s3_bucket, Key=self._s3_key, Body=body, ContentType="application/json")
        except Exception as e:
            logger.error(f"Failed to write token storage to S3: {e}")
            raise

    def add_token(self, token: str, client_name: str, expires_at: Optional[str] = None,
                  metadata: Optional[Dict] = None) -> Dict:
        """Add a new token to storage. expires_at: YYYY-MM-DD or full ISO. None for no expiration."""
        tokens = self._read_tokens()
        if expires_at and expires_at.strip():
            expires_at = expires_at.strip()
            if len(expires_at) == 10 and expires_at.count("-") == 2:
                expires_at = expires_at + "T23:59:59"
        else:
            expires_at = None
        token_info = {
            "token": token,
            "client_name": client_name,
            "created_at": datetime.utcnow().isoformat(),
            "expires_at": expires_at,
            "is_active": True,
            "metadata": metadata or {}
        }
        tokens[token] = token_info
        self._write_tokens(tokens)
        logger.info(f"Added token for client: {client_name}")
        return token_info

    def get_token(self, token: str) -> Optional[Dict]:
        """Get token information."""
        tokens = self._read_tokens()
        return tokens.get(token)

    def validate_token(self, token: str) -> bool:
        """Validate if a token is valid and active."""
        token_info = self.get_token(token)
        if not token_info or not token_info.get("is_active", False):
            return False
        expires_at = token_info.get("expires_at")
        if expires_at:
            try:
                expires_datetime = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
                if datetime.utcnow() > expires_datetime:
                    logger.warning(f"Token expired: {token[:8]}...")
                    return False
            except Exception as e:
                logger.error(f"Error parsing expiration date: {e}")
                return False
        return True

    def revoke_token(self, token: str) -> bool:
        """Revoke (deactivate) a token."""
        tokens = self._read_tokens()
        if token not in tokens:
            return False
        tokens[token]["is_active"] = False
        tokens[token]["revoked_at"] = datetime.utcnow().isoformat()
        self._write_tokens(tokens)
        logger.info(f"Revoked token: {token[:8]}...")
        return True

    def list_tokens(self, active_only: bool = False) -> List[Dict]:
        """List all tokens."""
        tokens = self._read_tokens()
        token_list = list(tokens.values())
        if active_only:
            token_list = [t for t in token_list if t.get("is_active", False)]
        return token_list

    def delete_token(self, token: str) -> bool:
        """Permanently delete a token from storage."""
        tokens = self._read_tokens()
        if token not in tokens:
            return False
        del tokens[token]
        self._write_tokens(tokens)
        logger.info(f"Deleted token: {token[:8]}...")
        return True
