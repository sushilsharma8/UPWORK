````markdown
# API Authentication and Deployment Guide

This guide provides instructions on how to configure your AWS environment to use API key authentication for the Resume Parser API.

## 1. Update Lambda Environment Variables

Your Lambda function needs to know which API keys are valid. You'll set this using an environment variable.

1.  **Navigate to your Lambda function** in the AWS Management Console.
2.  Go to the **Configuration** tab and select **Environment variables**.
3.  Click **Edit** and then **Add environment variable**.
4.  Create a new variable:
    *   **Key**: `VALID_API_KEYS`
    *   **Value**: A comma-separated list of the API keys you will create in API Gateway. For example: `key1_for_tcs,key2_for_salesforce,key3_for_another_client`

    **Note:** There should be no spaces between the keys.

5.  **Save** the changes. Your Lambda function will now be able to validate incoming API keys.

## 2. Configure API Gateway to Require API Keys

Next, you need to configure the API Gateway endpoint to require an API key on incoming requests.

1.  **Navigate to your API** in the API Gateway service in the AWS Management Console.
2.  In the **Resources** pane, select the method for your parsing endpoint (e.g., `POST` under `/parse/upload`).
3.  Click on **Method Request**.
4.  Under **Settings**, find **API Key Required** and select `true` from the dropdown menu.
5.  **Deploy your API** for the changes to take effect. Go to **Actions** -> **Deploy API** and select your deployment stage (e.g., `prod`).

Repeat this for all parsing endpoints you want to protect (`/parse/base64`, `/parse/s3`, `/parse/url`).

## 3. Create API Keys and a Usage Plan

Now you will create the actual API keys for your clients (TCS, Salesforce, etc.) and group them into a usage plan to manage throttling and quotas.

### a. Create API Keys

1.  In the API Gateway console, navigate to **API Keys**.
2.  Click **Create API key**.
3.  Give the key a descriptive name (e.g., `TCS-API-Key`).
4.  Choose **Auto Generate** for the API key.
5.  Click **Save**.
6.  **Important:** Copy the generated API key and save it somewhere secure. You will provide this key to your client.
7.  Repeat this process for each client company.

### b. Create a Usage Plan

1.  In the API Gateway console, navigate to **Usage Plans**.
2.  Click **Create**.
3.  **Name** the plan (e.g., `Resume-Parser-Client-Plan`). 
4.  You can set **Throttling** (rate limit) and **Quota** (number of requests per day/week/month) if you wish. This is useful for managing client usage.
5.  Click **Next**.
6.  **Associate your API and Stage** with this usage plan. Select your Resume Parser API and the stage you deployed it to (e.g., `prod`).
7.  Click **Next**.
8.  **Add API Keys to Usage Plan**. Select all the API keys you created for your clients and click **Done**.

## 4. How Your Clients Will Use the API

Your clients can now make requests to the protected endpoints by including their assigned API key in the `X-API-Key` header.

Here is an example using `curl`:

```bash
curl -X POST "https://YOUR_API_GATEWAY_ENDPOINT/parse/upload" \
-H "Content-Type: multipart/form-data" \
-H "X-API-Key: YOUR_CLIENTS_API_KEY" \
-F "file=@/path/to/resume.pdf"
````

Replace `YOUR_API_GATEWAY_ENDPOINT` with your actual API Gateway invoke URL and `YOUR_CLIENTS_API_KEY` with the key you generated for them.

By following these steps, you have successfully secured your Resume Parser API, allowing you to provide controlled access to your clients.


DEMO-API-Key = "74J8VzY8926MASeb17eSp76qY7Tq9oun8duyD01W"