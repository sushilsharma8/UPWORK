# Docker build context for Lambda

This directory contains a **copy** of the application files used as the Docker build context for the Lambda image. Keep it in sync with the project root when you change:

- `api.py`
- `resume_parser_improved.py`
- `lambda_api_handler.py`
- `token_manager.py`
- `token_storage.py`
- `requirements.txt`
- `Dockerfile`

You can build from either:

- **Project root:** `docker build -t resume-parser-api .` (uses root Dockerfile and root files)
- **This directory:** `cd docker_build_context && docker build -t resume-parser-api .` (uses this copy)
