<p align="center"><img src="assets/banner.jpg" alt="Braided cables plugged into brass sockets on a dark patch panel" width="100%"></p>

# Python-Azure-AI-REST-APIs

---

## Building APIs with Python using the FastAPI and Microsoft Azure Cognitive Services

This project is a simple demonstration of how to deploy a FastAPI model on Microsoft Azure, complete with CI/CD functionality. This repo also contains 2 mini applications. One of them runs FastAPI locally with PyTesseract to perform Optical Character Recognition, and the other uses the Azure CognitiveServices Python SDK to perform Text Analytics, using key and endpoint acquired from the Azure Cognitive Services Resource.

---

<div align="center">
<img src="https://github.com/ovokpus/Python-AI-REST-APIs/blob/main/images/azure-cognitive-services.png">
</div>

### Deploying REST API on Microsoft Azure

After pushing the code to GitHub, the following steps are followed to get the model deployed on Azure

---

#### Create an App Service Resource and connect to GitHub for Continuous Integration/ Continuous Deployment

A WSGI server is needed to deploy a FastAPI project on Azure App Service. I used `gunicorn` in this project. The startup script can thus have the gunicorn command to spin up the FastAPI app with the help of Gunicorn's worker class `uvicorn.workers.UvicornWorker`. The startup command is given as:

```
gunicorn -w 2 -k uvicorn.workers.UvicornWorker main:app
```

---

#### Check the GitHub Actions and Test the App Service

A workflow file, `/.github/workflows/main_text_analytics-fastapi.yml`, is added automatically by Azure, and used to configure the CI/CD with GitHub for Authentication, Build and Deployment jobs required for this model pipeline. Once the deployment is successful, the API is ready to be used from the url

---

#### Create An Application Insights Resource on Azure and Implement logging in the API source code

This resource helps us log data from the API. An additional python package, `opencensus-ext-azure` is required to implement logging in the API. Once the code is commited and pushed to GitHub, the API is automatically redeployed, and if successful, then the logs can be viewed on Azure.
