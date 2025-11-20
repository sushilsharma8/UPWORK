#!/usr/bin/env python3
"""
Token Storage Module
Handles storage and retrieval of API access tokens
Supports JSON file storage (can be extended to DynamoDB, database, etc.)
"""

import os
import json
import logging
from typing import Dict, Optional, List
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

class TokenStorage:
    """Token storage backend - supports JSON file storage"""
    
    def __init__(self, storage_path: str = None):
        """
        Initialize token storage
        
        Args:
            storage_path: Path to JSON file for storing tokens. 
                         If None, uses environment variable or default location.
        """
        if storage_path is None:
            # Try environment variable first
            storage_path = os.environ.get("TOKEN_STORAGE_PATH")
            if storage_path is None:
                # Default to tokens.json in current directory
                storage_path = os.path.join(os.path.dirname(__file__), "tokens.json")
        
        self.storage_path = Path(storage_path)
        self._ensure_storage_file()
    
    def _ensure_storage_file(self):
        """Ensure the storage file exists"""
        if not self.storage_path.exists():
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)
            self._write_tokens({})
            logger.info(f"Created new token storage file at {self.storage_path}")
    
    def _read_tokens(self) -> Dict:
        """Read tokens from storage"""
        try:
            with open(self.storage_path, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.warning(f"Could not read token storage: {e}. Creating new storage.")
            return {}
    
    def _write_tokens(self, tokens: Dict):
        """Write tokens to storage"""
        try:
            with open(self.storage_path, 'w') as f:
                json.dump(tokens, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to write token storage: {e}")
            raise
    
    def add_token(self, token: str, client_name: str, expires_days: Optional[int] = None, 
                  metadata: Optional[Dict] = None) -> Dict:
        """
        Add a new token to storage
        
        Args:
            token: The access token string
            client_name: Name/identifier for the client
            expires_days: Number of days until token expires (None for no expiration)
            metadata: Additional metadata to store with the token
        
        Returns:
            Token information dictionary
        """
        tokens = self._read_tokens()
        
        expires_at = None
        if expires_days:
            expires_at = (datetime.utcnow() + timedelta(days=expires_days)).isoformat()
        
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
        """
        Get token information
        
        Args:
            token: The access token string
        
        Returns:
            Token information dictionary or None if not found
        """
        tokens = self._read_tokens()
        return tokens.get(token)
    
    def validate_token(self, token: str) -> bool:
        """
        Validate if a token is valid and active
        
        Args:
            token: The access token string
        
        Returns:
            True if token is valid and active, False otherwise
        """
        token_info = self.get_token(token)
        
        if not token_info:
            return False
        
        if not token_info.get("is_active", False):
            return False
        
        # Check expiration
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
        """
        Revoke (deactivate) a token
        
        Args:
            token: The access token string
        
        Returns:
            True if token was revoked, False if not found
        """
        tokens = self._read_tokens()
        
        if token not in tokens:
            return False
        
        tokens[token]["is_active"] = False
        tokens[token]["revoked_at"] = datetime.utcnow().isoformat()
        self._write_tokens(tokens)
        
        logger.info(f"Revoked token: {token[:8]}...")
        return True
    
    def list_tokens(self, active_only: bool = False) -> List[Dict]:
        """
        List all tokens
        
        Args:
            active_only: If True, only return active tokens
        
        Returns:
            List of token information dictionaries
        """
        tokens = self._read_tokens()
        token_list = list(tokens.values())
        
        if active_only:
            token_list = [t for t in token_list if t.get("is_active", False)]
        
        return token_list
    
    def delete_token(self, token: str) -> bool:
        """
        Permanently delete a token from storage
        
        Args:
            token: The access token string
        
        Returns:
            True if token was deleted, False if not found
        """
        tokens = self._read_tokens()
        
        if token not in tokens:
            return False
        
        del tokens[token]
        self._write_tokens(tokens)
        
        logger.info(f"Deleted token: {token[:8]}...")
        return True

