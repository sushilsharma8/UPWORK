# IAM: Allow Deploy User to Update Lambda

If the deploy script fails with:

```text
User: ... web-app-docker-admin is not authorized to perform: lambda:UpdateFunctionCode on resource: ... function:resume-parser
```

the IAM user used by the CLI (e.g. `web-app-docker-admin`) needs permission to update the Lambda function’s code.

**Important:** The deploy user cannot grant itself IAM permissions. An **account admin** (or a user with IAM access) must add the policy—via the Console below or via CLI using admin credentials.

---

## Option 1: Add permissions in the AWS Console (recommended)

Use an account that has IAM access (e.g. root or an admin user):

1. **IAM** → **Users** → **web-app-docker-admin** → **Add permissions** → **Create inline policy**.
2. Open the **JSON** tab and paste the contents of `docs/iam-deploy-lambda-policy.json` (adjust the `Resource` ARN if your function name or region is different).
3. **Next** → name the policy (e.g. `ResumeParserDeployLambda`) → **Create policy**.

---

## Option 2: Attach inline policy via AWS CLI (admin only)

This requires credentials for a user/role that has `iam:PutUserPolicy` (e.g. an admin). The deploy user `web-app-docker-admin` does **not** have this permission and will get `AccessDenied` if you run it with that user.

From the project root, using **admin** credentials:

```bash
aws iam put-user-policy \
  --user-name web-app-docker-admin \
  --policy-name ResumeParserDeployLambda \
  --policy-document file://docs/iam-deploy-lambda-policy.json
```

The policy allows:

- `lambda:UpdateFunctionCode` – update the function’s container image
- `lambda:GetFunction` – used when waiting for the update to complete

---

After the policy is attached (via Console or CLI), run the deploy script again:

```bash
./scripts/deploy-api-lambda.sh us-east-1
```
