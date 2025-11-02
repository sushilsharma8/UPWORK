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
from typing import Optional, Dict, Any
from datetime import datetime

from fastapi import FastAPI, File, UploadFile, HTTPException, Body, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import uvicorn

from resume_parser_improved import ResumeParser

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

# Initialize parser (singleton)
parser = ResumeParser()

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
    """Response model for parsed resume"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    processing_time_ms: Optional[float] = None

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
            "parse_url": "/parse/url"
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
    include_raw_text: bool = Query(False, description="Include raw text in response")
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
            
            # Optionally remove raw text
            if not include_raw_text and "raw_text" in resume_dict:
                resume_dict["raw_text_length"] = len(resume_dict["raw_text"])
                del resume_dict["raw_text"]
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            logger.info(f"Successfully parsed {file.filename} in {processing_time:.2f}ms")
            
            return {
                "success": True,
                "data": resume_dict,
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
async def parse_base64(request: Base64FileRequest = Body(...)):
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
            
            # Optionally remove raw text
            if not request.include_raw_text and "raw_text" in resume_dict:
                resume_dict["raw_text_length"] = len(resume_dict["raw_text"])
                del resume_dict["raw_text"]
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            logger.info(f"Successfully parsed base64 file in {processing_time:.2f}ms")
            
            return {
                "success": True,
                "data": resume_dict,
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
async def parse_s3(request: S3FileRequest = Body(...)):
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
            
            # Optionally remove raw text
            if not request.include_raw_text and "raw_text" in resume_dict:
                resume_dict["raw_text_length"] = len(resume_dict["raw_text"])
                del resume_dict["raw_text"]
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            logger.info(f"Successfully parsed S3 file in {processing_time:.2f}ms")
            
            return {
                "success": True,
                "data": resume_dict,
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
    include_raw_text: bool = Body(False, embed=True, description="Include raw text in response")
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
            
            # Optionally remove raw text
            if not include_raw_text and "raw_text" in resume_dict:
                resume_dict["raw_text_length"] = len(resume_dict["raw_text"])
                del resume_dict["raw_text"]
            
            processing_time = (datetime.now() - start_time).total_seconds() * 1000
            
            logger.info(f"Successfully parsed URL file in {processing_time:.2f}ms")
            
            return {
                "success": True,
                "data": resume_dict,
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

if __name__ == "__main__":
    # Run with uvicorn
    uvicorn.run(
        "api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,  # Auto-reload on code changes (dev only)
        log_level="info"
    )

