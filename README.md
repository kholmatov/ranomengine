# 🛠️ RanomEngine - VIN Search & Smart Goal Builder

**RanomEngine** is a modular microservice that automates car case creation from VIN or URL input using search, parsing, and AI. It provides a complete pipeline from vehicle identification to structured goal data ready for case creation.

## ✨ Features

- **VIN-based Search**: Find vehicle listings using DuckDuckGo search with privacy-friendly approach
- **Multi-domain Parsing**: Support for Cars.com, CarFax, and generic domain parsing
- **AI-powered Extraction**: Fallback AI processing for unknown domains using OpenAI or Ollama
- **Headless Web Scraping**: JavaScript-capable page fetching with Selenium
- **REST API Server**: Full FastAPI-based REST API with automatic documentation
- **CLI Interface**: Command-line tool for testing and manual operations
- **API Integration**: Post structured goal data to Ranom API for case creation
- **Modular Architecture**: Extensible design for adding new parsers and AI models

## 🏗️ Architecture

```
[ VIN / URL input ]
        ↓
[ Search via ddgs ] ← (if VIN)
        ↓
[ URL selected ]
        ↓
[ DOM fetch via Selenium ]
        ↓
[ Known domain parser? ]
        ↓                     ↓
[ yes ]                  [ no ]
  ↓                        ↓
[ Parse → goal.json ]   [ Send DOM → AI ]
        ↓
[ POST to /api/cases/create_from_goal/ ]
```

## 📁 Project Structure

```
ranomengine/
├── parsers/
│   ├── cars_com_parser.py      # Cars.com specific parser
│   └── generic_parser.py       # Generic domain parser
│
├── ai/
│   └── goal_extractor.py       # AI-powered extraction
│
├── services/
│   ├── vin_search.py          # VIN search via DuckDuckGo
│   ├── dom_fetcher.py         # Selenium web scraping
│   └── goal_builder.py        # Complete pipeline orchestration
│
├── docs/
│   └── API.md                 # REST API documentation
│
├── examples/
│   └── api_client.py          # Python API client example
│
├── models.py                  # Data models and schemas
├── config.py                  # Configuration management
├── cli.py                     # Command-line interface
├── api.py                     # REST API server
├── test_basic.py              # Basic test suite
├── activate.sh                # Environment activation script
└── requirements.txt           # Dependencies
```

## 🚀 Quick Start

### Installation

1. **Clone the repository**:
```bash
git clone <repository-url>
cd ranomengine
```

2. **Install dependencies**:
```bash
pip install -r requirements.txt
```

3. **Install Chrome/Chromium** for Selenium:
   - **Ubuntu/Debian**: `sudo apt-get install chromium-browser`
   - **macOS**: `brew install chromium`
   - **Windows**: Download from Google Chrome website

4. **Set up configuration** (optional):
```bash
cp .env.example .env
# Edit .env with your API keys and settings
```

### Basic Usage

**Search for a VIN**:
```bash
python cli.py search-vin 5TDGZRBHXMS103005
```

**Process a VIN through complete pipeline**:
```bash
python cli.py process 5TDGZRBHXMS103005
```

**Process a URL directly**:
```bash
python cli.py process "https://www.cars.com/vehicledetail/12345/"
```

**Start the REST API server**:
```bash
python api.py
# API available at: http://localhost:8000
# Interactive docs at: http://localhost:8000/docs
```

**Use the Python API client**:
```bash
python examples/api_client.py
```

## ⚙️ Configuration

Configuration is managed through environment variables and the `config.py` file. Create a `.env` file to override defaults:

```bash
# DuckDuckGo Search
DDGS_MAX_RESULTS=10
DDGS_TIMEOUT=30

# Selenium WebDriver
WEBDRIVER_HEADLESS=True
WEBDRIVER_TIMEOUT=30

# AI Models (choose one)
AI_MODEL=ollama  # or 'openai'

# OpenAI (if using OpenAI)
OPENAI_API_KEY=sk-your-key-here
OPENAI_MODEL=gpt-4

# Ollama (if using Ollama)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama2

# Ranom API
BACKEND_URL=https://api.ranom.com
API_KEY=your-api-key-here

# Logging
LOG_LEVEL=INFO
```

## 🧠 AI Models Setup

### Using Ollama (Recommended for local development)

1. **Install Ollama**:
```bash
# macOS
brew install ollama

# Linux
curl -fsSL https://ollama.ai/install.sh | sh

# Windows - download from https://ollama.ai
```

2. **Pull a model**:
```bash
ollama pull llama2
# or for better performance:
ollama pull codellama
```

3. **Start Ollama server**:
```bash
ollama serve
```

### Using OpenAI

1. **Get API key** from OpenAI dashboard
2. **Set environment variable**:
```bash
export OPENAI_API_KEY=sk-your-key-here
```

## 🚀 REST API

### Start the API Server

```bash
# Activate environment and start server
source activate.sh
python api.py

# Server starts at http://localhost:8000
# Interactive API docs at http://localhost:8000/docs
```

### API Endpoints

- **`GET /health`** - Health check
- **`GET /config`** - Configuration info
- **`POST /validate/vin`** - Validate VIN format
- **`POST /search/vin`** - Search for VIN listings
- **`POST /fetch/page`** - Fetch webpage content
- **`POST /parse/page`** - Parse vehicle listing
- **`POST /extract/ai`** - AI-powered extraction
- **`POST /process/complete`** - Full pipeline processing
- **`POST /process/vin`** - Process VIN (convenience)
- **`POST /process/url`** - Process URL (convenience)

### Quick API Example

```bash
# Health check
curl -X GET "http://localhost:8000/health"

# Validate VIN
curl -X POST "http://localhost:8000/validate/vin" \
  -H "Content-Type: application/json" \
  -d '{"vin": "5TDGZRBHXMS103005"}'

# Process VIN through complete pipeline
curl -X POST "http://localhost:8000/process/vin?vin=5TDGZRBHXMS103005&create_case=false"
```

### Python Client

```python
from examples.api_client import RanomEngineClient

client = RanomEngineClient()
print(client.validate_vin("5TDGZRBHXMS103005"))
```

**📖 Full API Documentation**: [docs/API.md](docs/API.md)

## 🔧 CLI Commands

### VIN Operations
```bash
# Validate VIN format
python cli.py validate-vin 5TDGZRBHXMS103005

# Search for VIN listings
python cli.py search-vin 5TDGZRBHXMS103005 --limit 10

# Process VIN through complete pipeline
python cli.py process 5TDGZRBHXMS103005 --no-api
```

### URL Operations
```bash
# Fetch page content
python cli.py fetch-page "https://www.cars.com/vehicledetail/12345/"

# Parse a specific page
python cli.py parse-page "https://www.cars.com/vehicledetail/12345/" --parser cars.com

# Process URL through pipeline
python cli.py process "https://www.cars.com/vehicledetail/12345/" --type url
```

### AI Extraction
```bash
# Extract from HTML file using AI
python cli.py extract-ai page.html "https://example.com" --model openai

# Save processing trace
python cli.py process 5TDGZRBHXMS103005 --save-trace trace.json
```

### Utilities
```bash
# Show configuration
python cli.py config-info

# Get help for any command
python cli.py --help
python cli.py process --help
```

## 🔍 Supported Domains

### Native Parsers
- **Cars.com** - Full structured extraction
- **Generic** - Pattern-based extraction for unknown domains

### Coming Soon
- CarFax.com
- AutoTrader.com
- CapitalOne.com (Auto Navigator)
- Toyota.com

## 📊 Data Models

### VehicleData
Core data structure for vehicle information:
```python
{
  "vin": "5TDGZRBHXMS103005",
  "make": "Toyota",
  "model": "Highlander XLE",
  "year": 2021,
  "price": 31650,
  "mileage": 56630,
  "color": "Blue",
  "dealer_name": "Riverside Nissan",
  "dealer_phone": "(888) 814-6567",
  "location": "New Bern, NC",
  "features": [...],
  "images": [...],
  "accidents": true
}
```

### Goal JSON
Output format for case creation:
```python
{
  "vin": "5TDGZRBHXMS103005",
  "goal": "Buy a 2021 Toyota Highlander XLE for $31,650",
  "price": 31650,
  "dealer": {
    "name": "Riverside Nissan of New Bern",
    "phone": "(888) 814-6567",
    "address": "3315 US Highway 70 E, New Bern, NC 28560"
  },
  "location": "New Bern, NC",
  "mileage": 56630,
  "accidents": true,
  ...
}
```

## 🧪 Development

### Adding New Domain Parsers

1. **Create parser file** in `parsers/`:
```python
# parsers/autotrader_parser.py
from models import VehicleData
from bs4 import BeautifulSoup

class AutoTraderParser:
    def __init__(self):
        self.domain = 'autotrader.com'
    
    def parse(self, html: str, url: str) -> VehicleData:
        soup = BeautifulSoup(html, 'html.parser')
        # Implement extraction logic
        return VehicleData(...)
```

2. **Register parser** in `services/goal_builder.py`:
```python
self.domain_parsers = {
    'cars.com': self.cars_parser,
    'autotrader.com': AutoTraderParser(),  # Add here
}
```

### Testing

```bash
# Test VIN search
python cli.py search-vin 1HGCM82633A123456 --json

# Test parsing without API calls
python cli.py process "https://example.com/car/123" --no-api

# Test AI extraction
echo "<html>...</html>" | python cli.py extract-ai - "https://example.com"
```

## 🚨 Error Handling

The system includes comprehensive error handling:

- **Search failures**: Automatic fallback queries
- **Fetch failures**: Timeout and retry logic
- **Parser failures**: Fallback to generic parser → AI extraction
- **API failures**: Detailed error reporting with status codes

## 📝 Logging

Logging is configurable via `LOG_LEVEL` environment variable:

```bash
# Development
export LOG_LEVEL=DEBUG

# Production
export LOG_LEVEL=INFO
```

Logs include:
- Search results and timing
- DOM fetch success/failure
- Parser confidence scores
- AI extraction results
- API response codes

## 🛡️ Privacy & Security

- **No personal data storage**: All data is processed in memory
- **Privacy-first search**: Uses DuckDuckGo instead of Google
- **Configurable user agents**: Avoid detection/blocking
- **API key security**: Environment variable based configuration
- **Headless operation**: No GUI dependencies in production

## 📋 To-Do / Roadmap

- [ ] Add CarFax.com parser
- [ ] Implement AutoTrader.com parser
- [ ] Add proxy/rotating IP support
- [ ] Chrome extension for browser integration
- [ ] Docker containerization
- [ ] Rate limiting and retry mechanisms
- [ ] Vehicle history integration
- [ ] Price analysis and market comparison

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🆘 Support

For issues, questions, or feature requests:

1. Check the [Issues](issues) page
2. Search existing documentation
3. Create a new issue with detailed information

## 🔗 Related Projects

- [DuckDuckGo Search](https://pypi.org/project/ddgs/) - Privacy-focused search
- [Selenium](https://selenium.dev/) - Web browser automation
- [Beautiful Soup](https://www.crummy.com/software/BeautifulSoup/) - HTML parsing
- [Pydantic](https://pydantic-docs.helpmanual.io/) - Data validation
- [Click](https://click.palletsprojects.com/) - CLI framework 