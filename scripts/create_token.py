#!/usr/bin/env python3
"""
CLI Script for Creating Access Tokens
Run this script to generate new access tokens for your clients
"""

import argparse
import sys
import json
from datetime import datetime
from token_manager import TokenManager

def main():
    parser = argparse.ArgumentParser(
        description="Create and manage API access tokens for Resume Parser API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Create a token for TCS (no expiration)
  python create_token.py --client TCS

  # Create a token with expiry date
  python create_token.py --client Salesforce --expires-at 2026-09-15

  # Create a token with metadata
  python create_token.py --client "Acme Corp" --expires-at 2026-12-31 --metadata '{"contact":"john@acme.com"}'

  # List all tokens
  python create_token.py --list

  # List only active tokens
  python create_token.py --list --active-only

  # Revoke a token
  python create_token.py --revoke <token>

  # Delete a token
  python create_token.py --delete <token>
        """
    )
    
    # Token creation
    parser.add_argument("--client", "-c", type=str, help="Client name/identifier (e.g., TCS, Salesforce)")
    parser.add_argument("--expires-at", "-e", type=str, help="Expiry date YYYY-MM-DD (e.g. 2026-09-15). Omit for no expiration.")
    parser.add_argument("--metadata", "-m", type=str, help="JSON string with additional metadata")
    parser.add_argument("--storage-path", "-s", type=str, help="Path to token storage file (optional)")
    
    # Token management
    parser.add_argument("--list", "-l", action="store_true", help="List all tokens")
    parser.add_argument("--active-only", action="store_true", help="List only active tokens (use with --list)")
    parser.add_argument("--revoke", "-r", type=str, help="Revoke (deactivate) a token")
    parser.add_argument("--delete", "-d", type=str, help="Permanently delete a token")
    
    args = parser.parse_args()
    
    # Initialize token manager
    token_manager = TokenManager(storage_path=args.storage_path)
    
    # Handle list operation
    if args.list:
        tokens = token_manager.list_tokens(active_only=args.active_only)
        
        if not tokens:
            print("No tokens found.")
            return
        
        print(f"\n{'='*80}")
        print(f"Found {len(tokens)} token(s):")
        print(f"{'='*80}\n")
        
        for token_info in tokens:
            status = "✓ ACTIVE" if token_info.get("is_active") else "✗ INACTIVE"
            expires = token_info.get("expires_at", "Never")
            print(f"Client: {token_info['client_name']}")
            print(f"Status: {status}")
            print(f"Token: {token_info['token']}")
            print(f"Created: {token_info['created_at']}")
            print(f"Expires: {expires}")
            if token_info.get("metadata"):
                print(f"Metadata: {json.dumps(token_info['metadata'])}")
            print("-" * 80)
        
        return
    
    # Handle revoke operation
    if args.revoke:
        if token_manager.revoke_token(args.revoke):
            print(f"✓ Token revoked successfully")
        else:
            print(f"✗ Token not found")
            sys.exit(1)
        return
    
    # Handle delete operation
    if args.delete:
        if token_manager.delete_token(args.delete):
            print(f"✓ Token deleted successfully")
        else:
            print(f"✗ Token not found")
            sys.exit(1)
        return
    
    # Handle create operation
    if not args.client:
        parser.error("--client is required when creating a token")
    
    # Parse metadata if provided
    metadata = None
    if args.metadata:
        try:
            metadata = json.loads(args.metadata)
        except json.JSONDecodeError:
            print("Error: Invalid JSON in --metadata argument")
            sys.exit(1)
    
    # Create token
    try:
        token_info = token_manager.create_access_token(
            client_name=args.client,
            expires_at=args.expires_at,
            metadata=metadata
        )
        
        print("\n" + "="*80)
        print("✓ ACCESS TOKEN CREATED SUCCESSFULLY")
        print("="*80)
        print(f"\nClient Name: {token_info['client_name']}")
        print(f"Access Token: {token_info['token']}")
        print(f"Created At: {token_info['created_at']}")
        print(f"Expires At: {token_info['expires_at'] or 'Never'}")
        if token_info.get('metadata'):
            print(f"Metadata: {json.dumps(token_info['metadata'], indent=2)}")
        print("\n" + "="*80)
        print("⚠️  IMPORTANT: Save this token securely. You will not be able to see it again!")
        print("="*80)
        print("\nYour client can use this token in the X-API-Key header:")
        print(f"  X-API-Key: {token_info['token']}")
        print("\n")
        
    except Exception as e:
        print(f"Error creating token: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()

