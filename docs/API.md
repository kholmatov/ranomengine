# 🚀 RanomEngine REST API Documentation

The RanomEngine REST API provides programmatic access to all VIN search and goal extraction functionality. Built with FastAPI, it offers automatic OpenAPI documentation, request/response validation, and easy integration.

## 🏃 Quick Start

### Start the API Server

```bash
# Activate virtual environment
source venv/bin/activate

# Start the server
python api.py

# Or using uvicorn directly
uvicorn api:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at:
- **API Base URL**: `http://localhost:8000`
- **Interactive Docs**: `http://localhost:8000/docs` (Swagger UI)
- **ReDoc**: `http://localhost:8000/redoc`

## 📊 API Endpoints

### System Endpoints

#### `GET /health`
Health check endpoint with service status.

**Response:**
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "1703123456.789",
  "services": {
    "vin_validator": "healthy",
    "configuration": "healthy"
  }
}
```

#### `GET /config`
Get current configuration (excluding sensitive data).

**Response:**
```json
{
  "success": true,
  "data": {
    "ddgs_max_results": 10,
    "webdriver_headless": true,
    "ai_model": "ollama",
    "supported_domains": ["cars.com", "carfax.com", ...],
    "log_level": "INFO",
    "backend_url": "https://api.ranom.com"
  }
}
```

### Validation Endpoints

#### `POST /validate/vin`
Validate VIN format.

**Request:**
```json
{
  "vin": "5TDGZRBHXMS103005"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "vin": "5TDGZRBHXMS103005",
    "cleaned_vin": "5TDGZRBHXMS103005",
    "is_valid": true,
    "message": "VIN is valid"
  },
  "processing_time": 0.002
}
```

### Search Endpoints

#### `POST /search/vin`
Search for vehicle listings using VIN number.

**Request:**
```json
{
  "vin": "5TDGZRBHXMS103005",
  "limit": 5,
  "prioritize_supported": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "vin": "5TDGZRBHXMS103005",
    "results_count": 3,
    "results": [
      {
        "title": "2021 Toyota Highlander XLE",
        "url": "https://www.cars.com/vehicledetail/12345/",
        "domain": "cars.com",
        "is_supported": true,
        "snippet": "Great condition Toyota Highlander..."
      }
    ]
  },
  "processing_time": 2.1
}
```

### Fetching Endpoints

#### `POST /fetch/page`
Fetch webpage content using Selenium.

**Request:**
```json
{
  "url": "https://www.cars.com/vehicledetail/12345/",
  "wait_for_element": ".vehicle-title",
  "save_html": false
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "url": "https://www.cars.com/vehicledetail/12345/",
    "final_url": "https://www.cars.com/vehicledetail/12345/",
    "load_time": 3.2,
    "html_size": 45632,
    "is_valid": true,
    "page_analysis": {
      "is_listing": true,
      "has_vehicle_data": true,
      "domain_indicators": ["cars.com"]
    }
  },
  "processing_time": 3.5
}
```

### Parsing Endpoints

#### `POST /parse/page`
Parse a vehicle listing page.

**Request:**
```json
{
  "url": "https://www.cars.com/vehicledetail/12345/",
  "parser": "auto"
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "success": true,
    "parser_used": "cars.com",
    "vehicle_data": {
      "vin": "5TDGZRBHXMS103005",
      "make": "Toyota",
      "model": "Highlander XLE",
      "year": 2021,
      "price": 31650,
      "mileage": 56630,
      "dealer_name": "Riverside Nissan"
    },
    "confidence_score": 0.9
  },
  "processing_time": 4.1
}
```

### AI Endpoints

#### `POST /extract/ai`
Extract vehicle data using AI.

**Request:**
```json
{
  "html_content": "<html>...</html>",
  "url": "https://example.com/car/123",
  "existing_data": {
    "vin": "5TDGZRBHXMS103005"
  }
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "extracted_data": {
      "vin": "5TDGZRBHXMS103005",
      "make": "Toyota",
      "model": "Highlander",
      "year": 2021,
      "price": 31650
    },
    "confidence": 0.85,
    "model_used": "ollama-llama2",
    "tokens_used": 1245
  },
  "processing_time": 5.3
}
```

### Processing Endpoints

#### `POST /process/complete`
Process VIN or URL through complete pipeline.

**Request:**
```json
{
  "input_value": "5TDGZRBHXMS103005",
  "input_type": "vin",
  "create_case": true
}
```

**Response:**
```json
{
  "success": true,
  "data": {
    "input_value": "5TDGZRBHXMS103005",
    "input_type": "vin",
    "trace": {
      "search_results": [...],
      "selected_url": "https://www.cars.com/vehicledetail/12345/",
      "fetch_success": true,
      "parse_result": {...},
      "final_goal": {...}
    },
    "case_creation": {
      "success": true,
      "case_data": {...}
    }
  },
  "processing_time": 12.5
}
```

#### `POST /process/vin` (Convenience)
Process VIN through complete pipeline.

**Query Parameters:**
- `vin` (string): VIN number to process
- `create_case` (boolean): Whether to create case (default: true)

**Example:**
```bash
curl -X POST "http://localhost:8000/process/vin?vin=5TDGZRBHXMS103005&create_case=true"
```

#### `POST /process/url` (Convenience)
Process URL through complete pipeline.

**Query Parameters:**
- `url` (string): URL to process
- `create_case` (boolean): Whether to create case (default: true)

## 🔧 Usage Examples

### Python Client Example

```python
import requests
import json

# API base URL
BASE_URL = "http://localhost:8000"

# 1. Validate VIN
response = requests.post(f"{BASE_URL}/validate/vin", json={
    "vin": "5TDGZRBHXMS103005"
})
print("VIN Validation:", response.json())

# 2. Search for VIN
response = requests.post(f"{BASE_URL}/search/vin", json={
    "vin": "5TDGZRBHXMS103005",
    "limit": 5
})
print("VIN Search:", response.json())

# 3. Process VIN (complete pipeline)
response = requests.post(f"{BASE_URL}/process/complete", json={
    "input_value": "5TDGZRBHXMS103005",
    "input_type": "vin",
    "create_case": False  # Just extract data, don't create case
})
result = response.json()
print("Processing Result:", result)
```

### cURL Examples

```bash
# Health check
curl -X GET "http://localhost:8000/health"

# Validate VIN
curl -X POST "http://localhost:8000/validate/vin" \
  -H "Content-Type: application/json" \
  -d '{"vin": "5TDGZRBHXMS103005"}'

# Process VIN (convenience endpoint)
curl -X POST "http://localhost:8000/process/vin?vin=5TDGZRBHXMS103005&create_case=false"

# Search for VIN
curl -X POST "http://localhost:8000/search/vin" \
  -H "Content-Type: application/json" \
  -d '{
    "vin": "5TDGZRBHXMS103005",
    "limit": 3,
    "prioritize_supported": true
  }'
```

### JavaScript/Node.js Example

```javascript
const axios = require('axios');

const BASE_URL = 'http://localhost:8000';

async function processVIN(vin) {
  try {
    // Process VIN through complete pipeline
    const response = await axios.post(`${BASE_URL}/process/complete`, {
      input_value: vin,
      input_type: 'vin',
      create_case: false
    });
    
    console.log('Processing successful:', response.data);
    return response.data;
  } catch (error) {
    console.error('Error processing VIN:', error.response?.data || error.message);
  }
}

// Usage
processVIN('5TDGZRBHXMS103005');
```

## 🔒 Authentication & Security

### Production Considerations

1. **API Keys**: Add authentication middleware
2. **Rate Limiting**: Implement rate limiting for public endpoints
3. **CORS**: Configure CORS origins appropriately
4. **HTTPS**: Use HTTPS in production
5. **Input Validation**: All inputs are validated with Pydantic

### Environment Variables

```bash
# API Configuration
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4

# Security
API_KEY=your-secret-api-key
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com
```

## 📊 Response Format

All API responses follow a consistent format:

```json
{
  "success": boolean,
  "data": object | null,
  "error": string | null,
  "processing_time": number,
  "timestamp": string
}
```

### HTTP Status Codes

- `200` - Success
- `400` - Bad Request (invalid input)
- `404` - Not Found
- `422` - Validation Error
- `500` - Internal Server Error

## 🚀 Production Deployment

### Using Docker

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
```

### Using Uvicorn with Gunicorn

```bash
# Install gunicorn
pip install gunicorn

# Run with multiple workers
gunicorn api:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

## 🔍 Monitoring & Logging

The API includes structured logging and timing information:

- Request/response logging
- Processing time tracking
- Error tracking with stack traces
- Service health monitoring

Access logs and metrics at:
- Application logs: Check console output
- Health status: `GET /health`
- Configuration: `GET /config`

## 🐛 Troubleshooting

### Common Issues

1. **Port already in use**: Change port with `--port 8001`
2. **Dependencies missing**: Run `pip install -r requirements.txt`
3. **Selenium driver**: Install Chrome/Chromium browser
4. **AI model**: Configure Ollama or OpenAI API key
5. **Memory usage**: Monitor for large HTML responses

### Debug Mode

```bash
# Enable debug logging
export LOG_LEVEL=DEBUG

# Run with auto-reload
uvicorn api:app --reload --log-level debug
``` 