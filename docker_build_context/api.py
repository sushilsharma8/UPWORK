#!/usr/bin/env python3
"""
Resume Parser FastAPI Application
A production-ready REST API for parsing resumes
"""

import os
import io
import base64
import tempfile
import logging
import html as html_module
from typing import Optional, Dict, Any, List
from datetime import datetime

# When raw data (HTML format) exceeds this length, split into raw_data_1, raw_data_2, ...
RAW_DATA_MAX_CHARS = 130_000

from fastapi import FastAPI, File, UploadFile, HTTPException, Body, Query, Security, Depends
from fastapi.security import APIKeyHeader
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, ConfigDict
import uvicorn

from resume_parser_improved import ResumeParser
from token_manager import TokenManager

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Resume Parser API",
    description="Parse resumes (PDF/DOCX) and extract structured information using NLP",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

parser = ResumeParser()

API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

# Token storage: use env path, or /tmp in Lambda (read-only /var/task)
_token_path = os.environ.get("TOKEN_STORAGE_PATH")
if _token_path is None and (os.environ.get("AWS_LAMBDA_FUNCTION_NAME") or os.environ.get("LAMBDA_TASK_ROOT")):
    _token_path = "/tmp/tokens.json"
token_manager = TokenManager(storage_path=_token_path)

async def get_api_key(api_key: str = Security(api_key_header)):
    """Dependency to validate API access token"""
    if not token_manager.validate_token(api_key):
        raise HTTPException(
            status_code=403, 
            detail="Invalid or expired API access token. Please contact API administrator."
        )
    return api_key

# Pydantic models for request/response
class Base64FileRequest(BaseModel):
    """Request model for base64 encoded files"""
    file_content: str = Field(..., description="Base64 encoded file content")
    file_name: str = Field(..., description="Original filename")
    include_raw_text: bool = Field(False, description="Include raw text in response")

class S3FileRequest(BaseModel):
    """Request model for S3 file references"""
    s3_bucket: str = Field(..., description="S3 bucket name")
    s3_key: str = Field(..., description="S3 object key")
    include_raw_text: bool = Field(False, description="Include raw text in response")

class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    version: str
    timestamp: str

class ParseResponse(BaseModel):
    """Response model for parsed resume. Resume fields (contact, experience, etc.) are at top level."""
    model_config = ConfigDict(extra="allow")
    success: bool = True
    error: Optional[str] = None
    processing_time_ms: Optional[float] = None

class BatchParseItem(BaseModel):
    """Individual result in batch parse response. Resume fields are at top level per item."""
    model_config = ConfigDict(extra="allow")
    filename: str
    success: bool
    error: Optional[str] = None
    processing_time_ms: Optional[float] = None

class BatchParseResponse(BaseModel):
    """Response model for batch parsed resumes"""
    success: bool
    total_files: int
    successful: int
    failed: int
    total_processing_time_ms: float
    results: List[BatchParseItem]


def _raw_text_to_html(raw_text: str) -> str:
    """Wrap raw extracted text as a minimal HTML document for 'Raw data' response."""
    escaped = html_module.escape(raw_text or "")
    return (
        "<!DOCTYPE html><html><head><meta charset=\"UTF-8\">"
        "<title>Resume raw text</title></head><body><pre>"
        f"{escaped}</pre></body></html>"
    )


def apply_raw_data_response(resume_dict: Dict[str, Any], include_raw_text: bool) -> None:
    """
    Apply raw data handling to resume_dict in place.
    - If include_raw_text is False: set raw_text_length, remove raw_text.
    - If include_raw_text is True and content <= RAW_DATA_MAX_CHARS: send as single 'raw_text' (HTML format).
    - If include_raw_text is True and content > RAW_DATA_MAX_CHARS: split into raw_data_1, raw_data_2, ... (HTML chunks).
    """
    raw_text_value = resume_dict.get("raw_text") or ""
    resume_dict["raw_text_length"] = len(raw_text_value)

    if not include_raw_text:
        resume_dict.pop("raw_text", None)
        return

    html_content = _raw_text_to_html(raw_text_value)

    if len(html_content) <= RAW_DATA_MAX_CHARS:
        resume_dict["raw_text"] = html_content
        return

    # Split HTML content into chunks of at most RAW_DATA_MAX_CHARS
    chunks = []
    for i in range(0, len(html_content), RAW_DATA_MAX_CHARS):
        chunks.append(html_content[i : i + RAW_DATA_MAX_CHARS])

    resume_dict.pop("raw_text", None)
    resume_dict["raw_data_count"] = len(chunks)
    for idx, chunk in enumerate(chunks, start=1):
        resume_dict[f"raw_data_{idx}"] = chunk


@app.get("/", tags=["General"])
async def root():
    """Root endpoint with API information"""
    return {
        "message": "Resume Parser API",
        "version": "1.0.0",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "parse_upload": "/parse/upload",
            "parse_base64": "/parse/base64",
            "parse_s3": "/parse/s3",
            "parse_url": "/parse/url",
            "parse_batch": "/parse/batch",
            "admin_tokens_create": "/admin/tokens/create",
            "admin_tokens_list": "/admin/tokens",
            "admin_tokens_get": "/admin/tokens/{token}",
            "admin_tokens_revoke": "/admin/tokens/revoke",
            "admin_tokens_delete": "/admin/tokens/{token}"
        }
    }

@app.get("/health", response_model=HealthResponse, tags=["General"])
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.post("/parse/upload", response_model=ParseResponse, tags=["Parse"])
async def parse_upload(
    file: UploadFile = File(..., description="Resume file (PDF or DOCX)"),
    include_raw_text: bool = Query(False, description="Include raw text in response"),
    # api_key: str = Depends(get_api_key)
):
    """
    Parse resume from uploaded file
    
    Supports:
    - PDF files
    - DOCX files
    
    Returns structured data including:
    - Contact information
    - Professional summary
    - Work experience
    - Education
    - Skills
    - Certifications
    """
    start_time = datetime.now()
    
    try:
        # Validate file extension
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in ['.pdf', '.docx']:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only PDF and DOCX files are supported."
            )
        
        # Read file content
        content = await file.read()
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            tmp_file.write(content)
            tmp_file_path = tmp_file.name
        
        try:
            # Parse resume
            parsed_resume = parser.parse_resume(tmp_file_path)
            resume_dict = parser.to_dict(parsed_resume)
            apply_raw_data_response(resume_dict, include_raw_text)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(f"Successfully parsed {file.filename} in {processing_time:.2f}ms")
            
            return {
                "success": True,
                **resume_dict,
                "processing_time_ms": processing_time
            }
        
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing resume: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse resume: {str(e)}"
        )

@app.post("/parse/base64", response_model=ParseResponse, tags=["Parse"])
async def parse_base64(
    request: Base64FileRequest = Body(...),
    api_key: str = Depends(get_api_key)
):
    """
    Parse resume from base64 encoded content
    
    Useful for:
    - Client-side file encoding
    - API integrations
    - Mobile applications
    """
    start_time = datetime.now()
    
    try:
        # Determine file extension
        file_extension = os.path.splitext(request.file_name)[1].lower()
        if file_extension not in ['.pdf', '.docx']:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only PDF and DOCX files are supported."
            )
        
        # Decode base64 content
        try:
            file_bytes = base64.b64decode(request.file_content)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid base64 encoding: {str(e)}"
            )
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            tmp_file.write(file_bytes)
            tmp_file_path = tmp_file.name
        
        try:
            # Parse resume
            parsed_resume = parser.parse_resume(tmp_file_path)
            resume_dict = parser.to_dict(parsed_resume)
            apply_raw_data_response(resume_dict, request.include_raw_text)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(f"Successfully parsed base64 file in {processing_time:.2f}ms")
            
            return {
                "success": True,
                **resume_dict,
                "processing_time_ms": processing_time
            }
        
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing resume: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse resume: {str(e)}"
        )

@app.post("/parse/s3", response_model=ParseResponse, tags=["Parse"])
async def parse_s3(
    request: S3FileRequest = Body(...),
    api_key: str = Depends(get_api_key)
):
    """
    Parse resume from S3 bucket
    
    Requires:
    - AWS credentials configured
    - S3 read permissions
    """
    start_time = datetime.now()
    
    try:
        import boto3
        
        # Determine file extension from S3 key
        file_extension = os.path.splitext(request.s3_key)[1].lower()
        if file_extension not in ['.pdf', '.docx']:
            raise HTTPException(
                status_code=400,
                detail="Invalid file type. Only PDF and DOCX files are supported."
            )
        
        # Download from S3
        s3_client = boto3.client('s3')
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            try:
                s3_client.download_fileobj(request.s3_bucket, request.s3_key, tmp_file)
                tmp_file_path = tmp_file.name
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to download from S3: {str(e)}"
                )
        
        try:
            # Parse resume
            parsed_resume = parser.parse_resume(tmp_file_path)
            resume_dict = parser.to_dict(parsed_resume)
            apply_raw_data_response(resume_dict, request.include_raw_text)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(f"Successfully parsed S3 file in {processing_time:.2f}ms")
            
            return {
                "success": True,
                **resume_dict,
                "processing_time_ms": processing_time
            }
        
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing resume: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse resume: {str(e)}"
        )

@app.post("/parse/url", response_model=ParseResponse, tags=["Parse"])
async def parse_url(
    url: str = Body(..., embed=True, description="URL to resume file"),
    include_raw_text: bool = Body(False, embed=True, description="Include raw text in response"),
    api_key: str = Depends(get_api_key)
):
    """
    Parse resume from public URL
    
    Downloads and parses resume from a publicly accessible URL
    """
    start_time = datetime.now()
    
    try:
        import requests
        
        # Validate URL
        if not url.startswith(('http://', 'https://')):
            raise HTTPException(
                status_code=400,
                detail="Invalid URL. Must start with http:// or https://"
            )
        
        # Determine file extension from URL
        file_extension = os.path.splitext(url)[1].lower()
        if file_extension not in ['.pdf', '.docx']:
            # Try to detect from content-type
            file_extension = '.pdf'  # default
        
        # Download file
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            file_bytes = response.content
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to download file: {str(e)}"
            )
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
            tmp_file.write(file_bytes)
            tmp_file_path = tmp_file.name
        
        try:
            # Parse resume
            parsed_resume = parser.parse_resume(tmp_file_path)
            resume_dict = parser.to_dict(parsed_resume)
            apply_raw_data_response(resume_dict, include_raw_text)

            processing_time = (datetime.now() - start_time).total_seconds() * 1000

            logger.info(f"Successfully parsed URL file in {processing_time:.2f}ms")
            
            return {
                "success": True,
                **resume_dict,
                "processing_time_ms": processing_time
            }
        
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_file_path):
                os.unlink(tmp_file_path)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error parsing resume: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse resume: {str(e)}"
        )

@app.post("/parse/batch", response_model=BatchParseResponse, tags=["Parse"])
async def parse_batch(
    files: List[UploadFile] = File(..., description="Resume files (PDF or DOCX). Maximum 10 files."),
    include_raw_text: bool = Query(False, description="Include raw text in response"),
    api_key: str = Depends(get_api_key)
):
    """
    Parse multiple resumes in a single request (up to 10 files)
    
    This endpoint allows you to process multiple resumes at once, which is useful for:
    - Bulk processing of resumes
    - Batch uploads from job portals
    - Processing multiple candidates at once
    
    Supports:
    - PDF files
    - DOCX files
    - Maximum 10 files per request
    
    Returns structured data for each resume including:
    - Contact information
    - Professional summary
    - Work experience
    - Education
    - Skills
    - Certifications
    
    Each file is processed independently - if one fails, others will still be processed.
    """
    start_time = datetime.now()
    
    # Validate file count
    MAX_FILES = 10
    if len(files) > MAX_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Too many files. Maximum {MAX_FILES} files allowed per batch request."
        )
    
    if len(files) == 0:
        raise HTTPException(
            status_code=400,
            detail="At least one file is required for batch processing."
        )
    
    results = []
    successful_count = 0
    failed_count = 0
    temp_files = []  # Track temp files for cleanup
    
    # Process each file
    for file in files:
        file_start_time = datetime.now()
        temp_file_path = None
        
        try:
            # Validate file extension
            file_extension = os.path.splitext(file.filename)[1].lower()
            if file_extension not in ['.pdf', '.docx']:
                raise ValueError("Invalid file type. Only PDF and DOCX files are supported.")
            
            # Read file content
            content = await file.read()
            
            # Create temporary file
            with tempfile.NamedTemporaryFile(delete=False, suffix=file_extension) as tmp_file:
                tmp_file.write(content)
                temp_file_path = tmp_file.name
                temp_files.append(temp_file_path)
            
            # Parse resume
            parsed_resume = parser.parse_resume(temp_file_path)
            resume_dict = parser.to_dict(parsed_resume)
            
            apply_raw_data_response(resume_dict, include_raw_text)

            processing_time = (datetime.now() - file_start_time).total_seconds() * 1000

            logger.info(f"Successfully parsed {file.filename} in {processing_time:.2f}ms")
            
            results.append(BatchParseItem(
                filename=file.filename,
                success=True,
                processing_time_ms=processing_time,
                **resume_dict
            ))
            successful_count += 1
        
        except Exception as e:
            processing_time = (datetime.now() - file_start_time).total_seconds() * 1000
            error_message = str(e)
            
            logger.error(f"Error parsing {file.filename}: {error_message}", exc_info=True)
            
            results.append(BatchParseItem(
                filename=file.filename or "unknown",
                success=False,
                error=error_message,
                processing_time_ms=processing_time
            ))
            failed_count += 1
        
        finally:
            # Clean up temporary file immediately after processing
            if temp_file_path and os.path.exists(temp_file_path):
                try:
                    os.unlink(temp_file_path)
                except Exception as e:
                    logger.warning(f"Failed to delete temp file {temp_file_path}: {e}")
    
    # Clean up any remaining temp files (safety measure)
    for temp_file_path in temp_files:
        if os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception as e:
                logger.warning(f"Failed to delete temp file {temp_file_path}: {e}")
    
    total_processing_time = (datetime.now() - start_time).total_seconds() * 1000
    
    logger.info(f"Batch processing completed: {successful_count} successful, {failed_count} failed in {total_processing_time:.2f}ms")
    
    return BatchParseResponse(
        success=successful_count > 0,  # True if at least one file succeeded
        total_files=len(files),
        successful=successful_count,
        failed=failed_count,
        total_processing_time_ms=total_processing_time,
        results=results
    )

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc)
        }
    )


ADMIN_API_KEY = os.environ.get("ADMIN_API_KEY", "")

async def get_admin_key(api_key: str = Security(api_key_header)):
    """Dependency to validate admin API key"""
    if not ADMIN_API_KEY:
        raise HTTPException(
            status_code=500,
            detail="Admin API key not configured. Please set ADMIN_API_KEY environment variable."
        )
    if api_key != ADMIN_API_KEY:
        raise HTTPException(
            status_code=403,
            detail="Invalid admin API key. Access denied."
        )
    return api_key

# Request/Response models for token management
class CreateTokenRequest(BaseModel):
    """Request model for creating a token"""
    client_name: str = Field(..., description="Client name/identifier")
    expires_at: Optional[str] = Field(None, description="Expiry date (YYYY-MM-DD or full ISO datetime). Omit for no expiration.")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")

class TokenResponse(BaseModel):
    """Response model for token information"""
    token: str
    client_name: str
    created_at: str
    expires_at: Optional[str]
    is_active: bool
    metadata: Dict[str, Any]

class TokenListResponse(BaseModel):
    """Response model for listing tokens"""
    total: int
    active: int
    tokens: List[TokenResponse]

class RevokeTokenRequest(BaseModel):
    """Request model for revoking a token"""
    token: str = Field(..., description="Token to revoke")

class DeleteTokenRequest(BaseModel):
    """Request model for deleting a token"""
    token: str = Field(..., description="Token to delete")

class TokenOperationResponse(BaseModel):
    """Response model for token operations"""
    success: bool
    message: str

# Token Management Endpoints
@app.post("/admin/tokens/create", response_model=TokenResponse, tags=["Admin"])
async def create_token(
    request: CreateTokenRequest,
    admin_key: str = Depends(get_admin_key)
):
    """
    Create a new access token for a client
    
    Requires admin authentication.
    """
    try:
        token_info = token_manager.create_access_token(
            client_name=request.client_name,
            expires_at=request.expires_at,
            metadata=request.metadata
        )
        return TokenResponse(**token_info)
    except Exception as e:
        logger.error(f"Error creating token: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create token: {str(e)}"
        )

@app.get("/admin/tokens", response_model=TokenListResponse, tags=["Admin"])
async def list_tokens(
    active_only: bool = Query(False, description="List only active tokens"),
    admin_key: str = Depends(get_admin_key)
):
    """
    List all access tokens
    
    Requires admin authentication.
    """
    try:
        tokens = token_manager.list_tokens(active_only=active_only)
        active_count = sum(1 for t in tokens if t.get("is_active", False))
        
        return TokenListResponse(
            total=len(tokens),
            active=active_count,
            tokens=[TokenResponse(**token) for token in tokens]
        )
    except Exception as e:
        logger.error(f"Error listing tokens: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list tokens: {str(e)}"
        )

@app.get("/admin/tokens/{token}", response_model=TokenResponse, tags=["Admin"])
async def get_token_info(
    token: str,
    admin_key: str = Depends(get_admin_key)
):
    """
    Get information about a specific token
    
    Requires admin authentication.
    """
    try:
        token_info = token_manager.get_token_info(token)
        if not token_info:
            raise HTTPException(
                status_code=404,
                detail="Token not found"
            )
        return TokenResponse(**token_info)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting token info: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get token info: {str(e)}"
        )

@app.post("/admin/tokens/revoke", response_model=TokenOperationResponse, tags=["Admin"])
async def revoke_token(
    request: RevokeTokenRequest,
    admin_key: str = Depends(get_admin_key)
):
    """
    Revoke (deactivate) an access token
    
    Requires admin authentication.
    """
    try:
        success = token_manager.revoke_token(request.token)
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Token not found"
            )
        return TokenOperationResponse(
            success=True,
            message="Token revoked successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error revoking token: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to revoke token: {str(e)}"
        )

@app.delete("/admin/tokens/{token}", response_model=TokenOperationResponse, tags=["Admin"])
async def delete_token(
    token: str,
    admin_key: str = Depends(get_admin_key)
):
    """
    Permanently delete an access token
    
    Requires admin authentication.
    """
    try:
        success = token_manager.delete_token(token)
        if not success:
            raise HTTPException(
                status_code=404,
                detail="Token not found"
            )
        return TokenOperationResponse(
            success=True,
            message="Token deleted successfully"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting token: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to delete token: {str(e)}"
        )


if __name__ == "__main__":
    # Run with uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes (dev only)
        log_level="info"
    )
