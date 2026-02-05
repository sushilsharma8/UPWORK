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
        self.storage = TokenStorage(storage_path)

    def generate_token(self, length: int = 64) -> str:
        """Generate a secure random token."""
        alphabet = string.ascii_letters + string.digits
        return ''.join(secrets.choice(alphabet) for _ in range(length))

    def create_access_token(self, client_name: str, expires_at: Optional[str] = None,
                            metadata: Optional[Dict] = None) -> Dict:
        """Create a new access token for a client. expires_at: YYYY-MM-DD or full ISO. None for no expiration."""
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
        """Validate if a token is valid and active."""
        return self.storage.validate_token(token)

    def get_token_info(self, token: str) -> Optional[Dict]:
        """Get information about a token."""
        return self.storage.get_token(token)

    def revoke_token(self, token: str) -> bool:
        """Revoke a token (deactivate it)."""
        return self.storage.revoke_token(token)

    def list_tokens(self, active_only: bool = False) -> List[Dict]:
        """List all tokens."""
        return self.storage.list_tokens(active_only=active_only)

    def delete_token(self, token: str) -> bool:
        """Permanently delete a token."""
        return self.storage.delete_token(token)
