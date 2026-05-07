# TDEI-python-osw-incline
Service that accepts queue requests and adds incline values to an OSW dataset.

## What It Does
- Listens to `REQUEST_TOPIC` / `REQUEST_SUBSCRIPTION`.
- Downloads the input OSW zip from `data.dataset_url`.
- Extracts files and reads `edges` + `nodes` GeoJSON.
- Resolves DEM tiles (NED 1/3 arc-second), computes incline via `osw-incline`.
- Updates edges with incline values.
- Creates a result zip and uploads to storage.
- Publishes success/failure status to `RESPONSE_TOPIC`.

## Actual Use Cases
- Enriching street/path networks with incline for accessibility routing.
- Batch processing city-scale OSW datasets through queue-driven jobs.
- Running one-message-per-container jobs in CI/data pipelines, then auto-stopping the service.
- Processing very large GeoJSON inputs where zip validation is required before upload.

## Processing Lifecycle
1. Request received from queue.
2. Request validated (`dataset_url` must exist).
3. Incline processing executed.
4. Output uploaded to storage.
5. Response message published (with `success`, `message`, `file_upload_path`, package versions).
6. Temporary files cleaned up.
7. If `MAX_RECEIVABLE_MESSAGES > 0`, service triggers graceful shutdown after processing available messages.

## Getting Started
The project is built with Python + FastAPI.

### System requirements
| Software   | Version |
|------------|---------|
| Python     | 3.10+   |


### Required `.env` configuration
```bash
PROVIDER=Azure
QUEUECONNECTION=xxx
STORAGECONNECTION=xxx
REQUEST_TOPIC=xxx
REQUEST_SUBSCRIPTION=xxx
RESPONSE_TOPIC=xxx
CONTAINER_NAME=xxx
MAX_CONCURRENT_MESSAGES=1       # Optional, default: 1
MAX_RECEIVABLE_MESSAGES=-1      # Optional, default: -1 (no receive limit)
```

`QUEUECONNECTION` is used for queue consume/publish.  
`STORAGECONNECTION` is used to download input and upload processed zip.

### How to Set up and Build
1. Setup virtual environment:
```bash
python3.10 -m venv .venv
source .venv/bin/activate
```
2. Install dependencies:
```bash
pip install -r requirements.txt
```

### How to Run
```bash
uvicorn src.main:app --reload
```

Health endpoints:
- `GET /`
- `GET /health`
- `GET|POST /ping`
- `GET|POST /health/ping`

#### Request Format
```json
{
  "messageId": "tdei_record_id",
  "messageType": "workflow_identifier",
  "data": {
    "dataset_url": "https://.../input_osw.zip",
    "user_id": "optional",
    "jobId": "optional-job-id"
  }
}
```

#### Response Format
```json
{
  "messageId": "tdei_record_id",
  "messageType": "workflow_identifier",
  "data": {
    "message": "Successfully added inclination to the dataset.",
    "success": true,
    "file_upload_path": "https://.../jobs/<jobId>/<output>.zip",
    "package": {
      "python-ms-core": "x.y.z",
      "osw-incline": "x.y.z"
    }
  }
}
```

On failure, `data.success=false` and `data.message` contains the error reason.

### How to Set up and run the Tests
`.env` is not required for unit tests.

Run tests:
```bash
python -m unittest discover -s tests
```

Run coverage:
```bash
python -m coverage run --source=src -m unittest discover -s tests
coverage report
coverage html
```
