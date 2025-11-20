# Dockerfile for AWS Lambda with FastAPI
FROM public.ecr.aws/lambda/python:3.11

# Set working directory
WORKDIR ${LAMBDA_TASK_ROOT}

# Install system dependencies
RUN yum update -y && \
    yum install -y gcc gcc-c++ make && \
    yum clean all

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Download SpaCy model
RUN pip install --no-cache-dir https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1.tar.gz

# Download NLTK data
RUN python -c "import nltk; nltk.download('punkt'); nltk.download('stopwords')"

# Copy application code
COPY resume_parser_improved.py .
COPY api.py .
COPY lambda_api_handler.py .
COPY token_manager.py .
COPY token_storage.py .

# Set the CMD to FastAPI Lambda handler
CMD ["lambda_api_handler.lambda_handler"]
