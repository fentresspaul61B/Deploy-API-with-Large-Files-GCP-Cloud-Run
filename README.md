# Loading Files from GCP Storage Into Docker Container, During Cloud Run Deployment, Using GitHub Actions

This repo shows the steps to deploy an API using GitHub actions, GCP Cloud Run, and Docker. Specifically this example also includes how to download a file from GCP storage during the deployment in the GitHub actions workflow, add it into the docker container, and then deploy to GCP cloud run with that file. 

**Why is this useful?**

Pulling files down and adding them into the Docker container during deployment can be useful when you prefer not to store the file in your GitHub repo, which is often the case for large ML models for example. Also, when the file is deployed within the Docker container, you don't need to pull it from GCP when starting the API, which could lead to slower cold starts, and a less reliable service. 

# Steps


## Part 1: Variables/Alerts/APIs

### 1. Create new GCP project if needed
1. In top right corner select drop down projects menu. 
2. Select create new project button, and create a new project. 

### 2. Set budget alerts
I think its a good idea always to set budget alerts for any GCP project, as mistakes can be costly. 

1. Navigate to search bar and search for "billing"
2. In the left menu find, "Billing and alerts"
3. Select "Create Budget"
4. Set an amount that you are comfortable with. 
5. Set up alert threshold. I like to have more, to better understand how fast 
I am spending. Alerts will be sent to your email. You can also decide who receives 
the messages. 
6. Click finish when done. 

### 3. Enable Required APIs
1. Go to console
2. Search artifact registry, enable API
3. Cloud Run Admin API. An API which enables you to programmatically control cloud 
run services. 
4. Service Account User


### 4. Create GCP Credentials JSON
1. Go to GCP console: https://console.cloud.google.com/ 
2. Search for "Service Accounts"
3. Create a new service account called "storage_agent" (name is arbitrary)
4. Add the following permissions:
    | **Role Name**                     | **Description**                                                                                                             |
    |-----------------------------------|-----------------------------------------------------------------------------------------------------------------------------|
    | **Storage Object Viewer**         |    Grants access to agent to download and list items in a bucket.                                                           |
    | **Service Account User**          |    Required for deploying to Cloud Run; allows the deploying service account to act as the runtime service account.         |
    | **Cloud Run Developer**           |    Grants the agent access to deploy the API to Google Cloud Run.                                                           |
    | **Artifact Registry Create-on-Push Writer**      |    Used to create an artifact, which is the stored Docker image in GCP.                                                     |
5. Click create
6. Find the triple dots menu on the right and select "manage keys"
7. Select "ADD KEY" and JSON
8. This will download the key locally to your machine
9. Navigate to https://codebeautify.org/json-to-base64-converter
10. Open the downloaded JSON file, and copy its contents into the converter
11. Copy the converted JSON file

### 4. Add GCP_CREDENTIALS to GitHub secrets
Make sure you already have the base64 token created from the previous step. 
1. Go to GitHub
2. Go to the repository
3. Go to settings with the gear icon
4. Go to secrets and variables 
5. Go to actions 
6. Click "Add new repository secret" and name it "GCP_CREDENTIALS":
7. Paste in the base64 credentials JSON

### 5. Add GCP_PROJECT_ID to GitHub secrets
1. Go to the GCP console
2. In the top left corner, find the projects drop down menu
3. Find the project ID in the right column and copy it
4. Go back to GitHub and add the secret in the same way. Except no need to convert it to base64. Name the secret "GCP_PROJECT_ID"

### 6. Create new bucket
1. Navigate to the console
2. Search "Cloud Storage"
3. Create a new bucket, name it anything
4. Use the default settings for the bucket (configure however fits your needs)

### 7. Create test file
1. Navigate to your terminal
2. This is very simple create the file however you prefer. But here is what I did:
    - Navigate to desktop
    - ```touch hello_word.txt```
    - ```vim hello_world.txt```
    - Press ```i``` to "insert" to start typing.
    - type in your message: "Hello world!"
    - Press esc
    - Save and exit vim: ```":wq" + press enter```


### 8. Upload the test file
1. Navigate back to the new bucket created
2. Select "UPLOAD FILES"
3. Find your new "hello_world.txt" file and upload it. 

Here its important to note, that this does not need to be a simple text file, it could be a large ML model instead. However, if you do have a larger file, this may require adjusting the settings for the servers memory when deploying to cloud run. 

## Creating the Dockerfile

Here, we use a boiler plate Dockerfile to deploy and run the API using Uvicorn and FastAPI. 
Uvicorn handles the server layer, while FastAPI handles the application layer. 

```Docker
# Use an official Python runtime as a parent image
FROM python:3.10

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file into the container
COPY requirements.txt .

# Install the required packages
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application code into the container
COPY main.py .

# Copy the file from the build context into the container
COPY hello_word.txt .

# Expose port 8080
EXPOSE 8080

# Command to run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]

```

## Create simple Python API
Here, I will use a bare-bones API which just checks if the file exists, and reads it contents to confirm that it exists, and the file is not corrupted. 

Make sure to change the API logic if your file is not named "hello_world.txt" or you are using a different type of file.

```python
from fastapi import FastAPI
import os

app = FastAPI()
@app.get("/")
def check_file():
    filepath = "hello_word.txt"
    if os.path.exists(filepath):
        with open(filepath) as f:
            contents = f.read().strip("\n")
            message = f"Your file exists. Its contents are: '{contents}'"
            return {"message": message}
    else:
        return {"message": "File is missing."}
```

## Create the github actions workflow
The GitHub actions workflow is used to automate the deployment, by orchestrating different defined steps in a cloud environment provided by GitHub. 

### GitHub Actions Workflow overview
The steps in the workflow are as follows: 
1. Checkout the recent changes from GitHub
2. Authenticate in GCP using the service account created earlier.
3. Install the cloud SDK in the GitHub actions environment, to enable running GCP terminal commands to pull data from GCP bucket. 
4. Validate service account
5. Authenticate the Docker Container: This command configures Docker to use your Google Cloud credentials when interacting with Google Container Registry.
6. Pull file from GCP bucket
7. Build the docker image: The Docker image has a command to copy the file into the container. Here if you have a file with a different name, make sure to change the Dockerfile accordingly. 
8. Push Docker Image: Push the image to the GCP artifact registry. This is where all the docker images are stored, and later used for creating the containers.
9. Deploy to GCP Cloud Run: Using the gcloud CLI, deploy the API to the managed server. 

Here it is important to note you may want to change some of the settings on the final step. For example, you may want to add more memory to the server before deploying. Or maybe set the min instances to greater than 0, such that you can avoid cold starts. 

There are many options to explore in the docs
https://cloud.google.com/sdk/gcloud/reference/run/deploy 

### Workflow .yaml
```yaml
name: Deploy to Cloud Run

on:
  push:
    branches:
      - main

env:
  GCP_PROJECT_ID: ${{ secrets.GCP_PROJECT_ID }}
  REGION: "us-central1"
  SERVICE_NAME: download-api

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout Code
        uses: actions/checkout@v3

      - name: Google Auth
        id: auth
        uses: 'google-github-actions/auth@v2'
        with:
          credentials_json: ${{ secrets.GCP_CREDENTIALS }}

      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v1
        with:
          project_id: ${{ env.GCP_PROJECT_ID }}
      
      - name: Who am I?
        run: |
          service_account=$(gcloud config get-value account)
          echo "Active Service Account: $service_account"

      - name: Authenticate Docker with Google Container Registry
        run: gcloud auth configure-docker

      - name: Pull File from Google Cloud Storage
        run: gsutil cp gs://delete-later-demo/hello_word.txt hello_word.txt


      - name: Build Docker Image
        run: |
          docker build -t gcr.io/${{ env.GCP_PROJECT_ID }}/${{ env.SERVICE_NAME }}:${{ github.sha }} -f Dockerfile .

      - name: Push Docker Image
        run: |
          docker push gcr.io/${{ env.GCP_PROJECT_ID }}/${{ env.SERVICE_NAME }}:${{ github.sha }}

      - name: Deploy to Cloud Run
        run: |
          gcloud run deploy ${{ env.SERVICE_NAME }} \
            --image gcr.io/${{ env.GCP_PROJECT_ID }}/${{ env.SERVICE_NAME }}:${{ github.sha }} \
            --region ${{ env.REGION }} 

```

## Deploy the API
The API is deployed on pushes to the main branch on to GitHub, so push the changes, and this should start the deployment.

## Test the API
1. Navigate to cloud run
2. Find the API
3. Copy the APIs URL with the clipboard button
4. Get an ID token: Open the terminal within the GCP console. Run gcloud auth print-identity-token
5. Copy the token
6. Navigate to Post https://www.postman.com/, make an account if required.
7. Click on the "new request button"
8. Paste the URL into the text box
9. Select "Auth"
10. Change the auth auth type to "Bearer Token"
11. Paste the token into text box
12. Double check the URL, and click "send"
13. See the result, with access to the file! 

You should see a ```200 OK``` response with:
```JSON
{
    "message": "Your file exists. Its contents are: 'Hello World!'"
}
```


# Conclusion
This example encapsulates many different aspects of deploying APIs and MLOps,
including handling IAM permissions, service accounts, setting up auto deploy
CI/CD with GitHub Actions, adding billing alerts, loading files from GCP cloud storage, and containerizing the API using Docker. 

## Next steps
Many of these steps are completed manually through the GCP UI; however, I would like to be able to automate this entire process. This is know as "Infrastructure as Code". This can be done through tools like Terraform or Ansible.