# Business case: Python Azure AI REST APIs (Text & OCR Workbench)

**Review sentiment, key phrases and image-to-text behind one small API.**

## Who buys this

The buyer is the customer-experience or operations manager at a hotel group, retailer or service business that collects free-text reviews and scanned documents. They want a quick read on what customers are saying and a way to pull text out of images. The users are CX analysts and the developers who connect other systems to the API.

## The problem and what it costs

Reading reviews by hand doesn't scale, and unread reviews are wasted signal. Managed language services are cheap at small volumes. Azure AI Language includes **5,000 free text records a month** shared across sentiment, key phrases and related features, and a text record is up to 1,000 characters ([Azure AI Language pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/language-service/)). Paid tier prices vary by region and agreement, so check the pricing page for your own rate.

## How the repo solves it

| Need | What in the repo does it |
|---|---|
| Sentiment and key phrases | FastAPI routes over Azure AI Language (`app/`), with confidence scores |
| Text from images | OCR with Tesseract inside the API image. It works without Azure keys. |
| Batch processing | The original batch script over sample hotel reviews (`text-analytics-sdk/`, `samples/`) |
| A UI for non-developers | A Streamlit workbench (`frontend/`) |
| Runs safely without keys | Keys live in an uncommitted `.env`. The app still starts and tells you what is missing. |
| Deployable | Dockerfiles, Compose, and the original Azure App Service CI/CD with Application Insights |

## Use-case scenarios

All of these organisations are fictional.

1. **A boutique hotel group's weekly review digest.** The CX analyst pastes the week's reviews into the batch route. Negative reviews with key phrases like "check-in" or "noise" go to the property manager.
2. **A property-management office** photographs paper maintenance forms. OCR pulls the text so a clerk can file the request without retyping it.
3. **A retailer's support team** calls the sentiment route from the helpdesk, so angry tickets are sorted to the top of the queue.

## ROI: a worked model (illustrative)

These figures are **illustrative assumptions**, apart from the free allowance.

| Input | Value | Basis |
|---|---|---|
| Reviews a month | 3,000 | Assumption. Each review is under 1,000 characters, so one text record per feature. |
| Features per review (sentiment + key phrases) | 2 | Design of the repo |
| Text records a month | 6,000 | 3,000 × 2. That is 1,000 above the 5,000 free records ([Azure](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/language-service/)). |
| Analyst minutes to read and tag one review by hand | 1 | Assumption |
| Analyst hourly cost | US$49 | BLS May 2024 median for compliance officers, $37.70 an hour, used as a proxy for an office analyst ([BLS](https://www.bls.gov/news.release/archives/ocwage_04022025.pdf)). Multiplied by an assumed 1.3. |

Labour avoided: 3,000 min = 50 hours a month, about **US$29,000 a year**, against the cost of the 1,000 paid records a month (check your rate) and App Service hosting. In practice an analyst still reads the flagged reviews, so count only the triage time as saved.

## Path to production

1. Move secrets to Azure Key Vault or managed identity, instead of `.env`.
2. Add authentication and request limits to the API.
3. Store results so trends can be charted over time.
4. For OCR at volume, compare Tesseract with Azure AI Document Intelligence on your own documents.

`PRODUCTIONIZING.md` lists the engineering work.

## Risks and limits

- Sentiment models miss sarcasm and domain language, so spot-check them against human labels.
- Reviews can contain personal data. Check the data-processing terms before sending them to a cloud API.
- **The case is fair but modest.** This is a thin layer over managed services. Its value is a quick, working start, not unique technology.

## Sources

- Microsoft Azure, AI Language pricing: https://azure.microsoft.com/en-us/pricing/details/cognitive-services/language-service/
- U.S. Bureau of Labor Statistics, OEWS May 2024 (Compliance Officers): https://www.bls.gov/news.release/archives/ocwage_04022025.pdf
