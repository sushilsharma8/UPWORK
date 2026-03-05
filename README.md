# Resume Parser API

Production-ready REST API for parsing resumes (PDF/DOCX) and extracting structured information using NLP. Runs as FastAPI locally or on AWS Lambda.

## Project structure

```
├── api.py                    # FastAPI app and routes
├── resume_parser_improved.py # Resume parsing logic
├── lambda_api_handler.py     # AWS Lambda entry (Mangum)
├── token_manager.py         # API token management
├── token_storage.py         # Token storage (file / S3)
├── requirements.txt
├── Dockerfile                # Build for Lambda (use project root as context)
├── openapi.json              # OpenAPI spec
├── docs/                     # All documentation
├── scripts/
│   └── create_token.py       # CLI to create/list/revoke API tokens (run from repo root)
├── postman/                  # Postman collection and environment
└── docker_build_context/     # Optional: copy of app files for Lambda build context
```

## Quick start

- **Run locally:** `uvicorn api:app --reload`
- **Create a token:** `python scripts/create_token.py --client "My Client"`
- **Build Docker image:** `docker build -t resume-parser-api .` (from this directory)

## Documentation

See **[docs/](docs/)** for:

| Doc | Description |
|-----|-------------|
| [API-DOCUMENTATION.md](docs/API-DOCUMENTATION.md) | API reference and usage |
| [API-GUIDE.md](docs/API-GUIDE.md) | Detailed API guide |
| [GUIDE.md](docs/GUIDE.md) | API Gateway and token setup |
| [LAMBDA-DEPLOYMENT.md](docs/LAMBDA-DEPLOYMENT.md) | Deploy to AWS Lambda |
| [DEPLOYMENT-PROCESS-NOTION.md](docs/DEPLOYMENT-PROCESS-NOTION.md) | Deployment process |
| [POSTMAN-GUIDE.md](docs/POSTMAN-GUIDE.md) | Postman testing |
| [S3-TOKEN-STORAGE-SETUP.md](docs/S3-TOKEN-STORAGE-SETUP.md) | S3 token storage |
| [Guide_for_keys.md](docs/Guide_for_keys.md) | API keys guide |

## Token storage

- Default: `tokens.json` in project root (or set `TOKEN_STORAGE_PATH`).
- Lambda: use `TOKEN_STORAGE_S3_BUCKET` for S3; see [docs/S3-TOKEN-STORAGE-SETUP.md](docs/S3-TOKEN-STORAGE-SETUP.md).
