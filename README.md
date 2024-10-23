# Deploy-API-with-Large-Files-GCP-Cloud-Run

# Loading Files from GCP Storage Into Docker Container, During Cloud Run Deployment, Using GitHub Actions

Imagine you have a relatively large file, for example, a machine learning model. You want to deploy your ML model as an API using GCP Cloud Run. Normally, you would copy all the existing files (including the model) from your GitHub repo into the docker container. However, you may prefer not to store the model in GitHub, but rather in GCP cloud storage. So how can we get the model from GCP cloud storage to our cloud run API? 

The first way is to write a function, which pulls the model from storage and saves it locally, for example using the GCP python sdk. However there are some downsides to this approach, which include: 

1. Slower cold starts. If your API shuts down due to a lul in traffic, the next time it boots up, it will need to reload the model. 
2. Less Reliability: When the model is pulled from GCP as part of the API script, the model is not loaded only once, but rather it is loaded many times during its lifetime, due to the file never existing in memory. The file gets re downloaded when the server starts and the API is made live. This leads to more possible failures, as GCP files, permissions, or tokens could change throughout the lifetime of the API, which could cause the API to fail to load the file. 
3. Git LFS adds additional complexity to version control, and is basically an irreversible addition to the repo. 
4. Models should be there own entity, existing outside the context of a specific repository, allowed to move between them and used in multiple places easily. 

On the other hand, when the model is deployed as a static file that exists in memory, copied during deployment into the docker container, it will not change due to rearrangement of files on GCP, or other accidental breaking changes. In this scenario, the contents of the docker container will stay consistent like a snapshot of the state, which is preferable to improve reliability for the API. 


## GitHub Secrets

### Create new GCP project if needed
1. In top right corner select drop down projects menu. 
2. Select create new project button, and create a new project. 


### Create GCP Credentials JSON
1. Go to GCP console
2. Search for "Service Accounts"
3. Create a new service account called "storage_agent" (Name does not matter)
4. Add the follow permissions:
    - Storage Object Viewer: Grants access to agent to pull the download and list items in a bucket. 
    - Service Account User: Required for deploying to cloud run. 
    - Cloud Run Developer: Grants the agent access to deploy the API to GCP cloud run. 
    - Artifact Registry Administrator Create On Push.
    - Maybe need to add more, TBD
5. Click create
6. Find the triple dots menu on the right and select "manage keys"
7. Select "ADD KEY" and JSON
8. This will download the key locally to your machine
9. Navigate to https://codebeautify.org/json-to-base64-converter
10. Open the downloaded JSON file, and copy its contents into the converter
11. Copy the converted JSON file

### Enable Required APIs
1. Go to console
2. Search artifact registry, enable API
3. Cloud Run Admin API
4. Service Account User

### add GCP_CREDENTIALS to GitHub
Make sure you already have the base64 token created from the previous step. 
1. Go to GitHub
2. Go to the repository
3. Go to settings with the gear icon
4. Go to secrets and variables 
5. Go to actions 
6. Click "Add new repository secret" and name it "GCP_CREDENTIALS":
7. Paste in the base64 credentials JSON

### GCP_PROJECT_ID
1. Go to the GCP console
2. In the top left corner, find teh projects drop down menu
3. Find the project ID in the right column and copy it
4. Go back to GitHub and add the secret in the same way. Except no need to convert it to base64. Name the secret "GCP_PROJECT_ID"

## Adding a test file to GCP storage

### Create new bucket
1. Navigate to the console
2. Search "Cloud Storage"
3. Create a new bucket, name it anything
4. Use the default settings for the bucket (configure however fits your needs)

### Create test file
1. Navigate to your terminal
2. This is very simple create the file however you prefer. But here is what I did:
    - Navigate to desktop
    - touch hello_word.txt
    - vim hello_world.txt
    - "i"
    - type in "Hello world!"
    - press esc
    - ":wq" + press enter

### Upload the test file
1. Navigate back to the new bucket created
2. Select "UPLOAD FILES"
3. Find your new "hello_world.txt" file and upload it. 

Here its important to note, that this does not need to be a simple text file, it could be a large ML model instead. However, if you do have a larger file, this may require adjusting the settings for the servers memory when deploying to cloud run. 

## Creating the Dockerfile
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

## Create the github actions workflow
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
        run: gsutil cp gs://gcp-helpers-and-demos/hello_word.txt ./test_api/hello_word.txt


      - name: Build Docker Image
        run: |
          docker build -t gcr.io/${{ env.GCP_PROJECT_ID }}/${{ env.SERVICE_NAME }}:${{ github.sha }} -f test_api/Dockerfile test_api

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
The API is deployed on pushes to GitHub, so push the changes. 

## Test the API
1. Navigate to cloud run
2. Find the API
3. Copy the URL
4. Open the terminal within the console. Run gcloud auth print-identity-token
5. Copy the token
6. Add the URL to postman
7. Add the Auth bearer token
8. Make the request
9. See the result, with access to the file! 


# Conclusion
This example encapsulates many different aspects of deploying APIs and MLOps,
including handling IAM permissions, service accounts, setting up auto deploy
CI/CD with GitHub Actions, loading files from GCP cloud storage, and containerizing 
the API using Docker. 