#!/usr/bin/env python3
"""
AWS Lambda Handler for FastAPI using Mangum
Allows FastAPI to run on AWS Lambda seamlessly
"""

from mangum import Mangum
from api import app

# Create Lambda handler from FastAPI app
lambda_handler = Mangum(app, lifespan="off")

# For local testing
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

