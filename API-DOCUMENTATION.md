## Deployment & Infrastructure

This section describes deployment options, services used by the project, required environment variables, and production recommendations.

### Services & Components used

- FastAPI — web framework used for routing and OpenAPI generation
- Uvicorn (ASGI server) — used for local development and standalone deployments
- Docker — containerization for standalone or image-based Lambda deployments
- AWS Lambda — serverless deployment option (adapter included: `lambda_api_handler.py`)
- AWS ECR — container registry for pushing images (if using container images with Lambda/ECS)
- AWS S3 — optional source storage for resumes (S3 parsing uses `boto3`)
- boto3 — AWS SDK used by `/parse/s3`
- requests — used to download remote files for `/parse/url`
- spaCy & NLTK — NLP models/data used by `resume_parser_improved.py` (installed in Dockerfiles)
- Token storage: local JSON (`tokens.json`) via `token_storage.py` (use persistent store in prod)
- Logging: Python logging; CloudWatch/other logging collectors recommended in production

### Important files related to deployment

- `Dockerfile` and `docker_build_context/Dockerfile` — container images for Lambda/standalone
- `lambda_api_handler.py` — Lambda adapter (works with Mangum or container image entrypoint)
- `deploy-api-lambda.sh`, `deploy-api-standalone.sh` — deployment helper scripts (see `API-DEPLOYMENT-SUMMARY.md` / `API-GUIDE.md`)
- `requirements.txt` — Python dependencies

### Environment Variables

Set these in your environment, container settings, or cloud service configuration:

- `TOKEN_STORAGE_PATH` — Path to token storage JSON. For AWS Lambda set to `/tmp/tokens.json` or use persistent store (S3/DynamoDB).
- `ADMIN_API_KEY` — Administrative key used to manage client tokens via admin endpoints.
- `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` — Required for S3 parsing when not using instance/IAM roles.
- `API_HOST` / `API_PORT` — (optional) Host and port for standalone runs (defaults shown in `api.py` / uvicorn startup)
- `LOG_LEVEL` — Logging verbosity (INFO, DEBUG, etc.)

Secrets (admin key, AWS credentials) should be stored in a secrets manager (AWS Secrets Manager, Parameter Store, Vault) — do not commit them to the repository or to `tokens.json`.

### Deployment options (summary)

1) AWS Lambda (recommended for variable traffic)
	- Use the included Lambda handler and either:
	  - Deploy as a ZIP / package including Python files and dependencies; or
	  - Build a container image with the provided `Dockerfile` and push to ECR; configure Lambda to use the image.
	- Recommended settings: Runtime Python 3.11 (or container image), memory 512–2048 MB depending on workload, timeout 30–120s for batch operations.
	- Use `/tmp` for writable paths in Lambda (set `TOKEN_STORAGE_PATH=/tmp/tokens.json`).

2) Standalone Docker (ECS/Fargate, Cloud Run, Render, Fly.io)
	- Build the image (scripts exist in repo). Push to your registry (ECR/GCR/DockerHub) and deploy to the service of your choice.
	- Ensure environment variables and secrets are configured in the service.

3) Bare VM / Managed host (systemd, Docker Compose)
	- Run `uvicorn api:app --host 0.0.0.0 --port 8000` behind a reverse proxy (NGINX) and place a TLS certificate (Let's Encrypt).

### Example: build & push Docker image (ECR quick example)

```bash
# Build locally
docker build -t resume-parser-api:latest .

# Tag + push to ECR (example)
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker tag resume-parser-api:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/resume-parser-api:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/resume-parser-api:latest
```

### Persistence & tokens

- Current token storage implementation uses a JSON file (`token_storage.py`). This is fine for single-instance/local deployments, but not suitable for horizontally scaled production systems.
- Recommended production stores:
  - DynamoDB or RDS for token metadata
  - AWS S3 (for backups) or DynamoDB for persistence
  - Store admin secrets in AWS Secrets Manager or environment-specific secret store

### Monitoring, logging & observability

- Logs: Ship Python logs to CloudWatch, Papertrail, or another centralized log system.
- Metrics: Export basic metrics (request counts, latencies, error rates) to CloudWatch / Prometheus.
- Tracing: Optionally enable AWS X-Ray or OpenTelemetry for distributed tracing.

### Security & production hardening

- Use HTTPS/TLS for all external traffic. For containerized deployments use a load balancer or API Gateway with TLS.
- Rotate `ADMIN_API_KEY` and client tokens regularly.
- Apply least-privilege IAM roles for any AWS resources (S3, ECR, Lambda).
- When exposing public endpoints, consider rate-limiting and WAF rules to block abuse.

### Backups & recovery

- Backup `tokens.json` regularly if using file storage (or migrate to persistent DB).
- For database-backed storage, implement point-in-time recovery and automated snapshots.

### CI/CD suggestions

- Build Docker images in CI and push to a registry.
- Run unit tests and linting before deployment.
- Use infrastructure-as-code (CloudFormation / Terraform) to manage Lambda, API Gateway, ECS services, and IAM.

### Zero-downtime & scaling notes

- For container services, use rolling deployments and health checks to achieve zero-downtime releases.
- For Lambda, consider provisioned concurrency for latency-sensitive endpoints to avoid cold starts.

---

If you'd like, I can:
- generate an `openapi.json` file from the app and add it to the repo,
- produce a Postman collection from the OpenAPI spec and commit it to `postman/`, or
- add example CI pipeline steps (GitHub Actions) for building/pushing Docker images and deploying to Lambda/ECS.

