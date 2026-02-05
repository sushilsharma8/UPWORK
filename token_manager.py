#!/usr/bin/env python3
"""
Token Manager Module
Provides token generation and management functionality
"""

import secrets
import string
import logging
from typing import Optional, Dict, List
from token_storage import TokenStorage

logger = logging.getLogger(__name__)

class TokenManager:
    """Manages API access token generation and validation"""
    
    def __init__(self, storage_path: Optional[str] = None):
        """
        Initialize token manager
        
        Args:
            storage_path: Path to token storage file (optional)
        """
        self.storage = TokenStorage(storage_path)
    
    def generate_token(self, length: int = 64) -> str:
        """
        Generate a secure random token
        
        Args:
            length: Length of the token in characters (default: 64)
        
        Returns:
            A secure random token string
        """
        alphabet = string.ascii_letters + string.digits
        token = ''.join(secrets.choice(alphabet) for _ in range(length))
        return token
    
    def create_access_token(self, client_name: str, expires_at: Optional[str] = None,
                            metadata: Optional[Dict] = None) -> Dict:
        """
        Create a new access token for a client.

        expires_at: Expiry date (YYYY-MM-DD or full ISO). None for no expiration.
        """
        token = self.generate_token()
        token_info = self.storage.add_token(
            token=token,
            client_name=client_name,
            expires_at=expires_at,
            metadata=metadata
        )
        
        logger.info(f"Created access token for client: {client_name}")
        return token_info
    
    def validate_token(self, token: str) -> bool:
        """
        Validate if a token is valid and active
        
        Args:
            token: The access token to validate
        
        Returns:
            True if token is valid, False otherwise
        """
        return self.storage.validate_token(token)
    
    def get_token_info(self, token: str) -> Optional[Dict]:
        """
        Get information about a token
        
        Args:
            token: The access token
        
        Returns:
            Token information dictionary or None if not found
        """
        return self.storage.get_token(token)
    
    def revoke_token(self, token: str) -> bool:
        """
        Revoke a token (deactivate it)
        
        Args:
            token: The access token to revoke
        
        Returns:
            True if token was revoked, False if not found
        """
        return self.storage.revoke_token(token)
    
    def list_tokens(self, active_only: bool = False) -> List[Dict]:
        """
        List all tokens
        
        Args:
            active_only: If True, only return active tokens
        
        Returns:
            List of token information dictionaries
        """
        return self.storage.list_tokens(active_only=active_only)
    
    def delete_token(self, token: str) -> bool:
        """
        Permanently delete a token
        
        Args:
            token: The access token to delete
        
        Returns:
            True if token was deleted, False if not found
        """
        return self.storage.delete_token(token)

