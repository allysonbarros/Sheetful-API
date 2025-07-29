# Sheetful Python API

A FastAPI-based REST API for interacting with Google Sheets, providing the easiest way to turn your Google Sheet into a RESTful API.

## ✨ Features

- **RESTful API**: Full CRUD operations on Google Sheets
- **Authentication**: Support for OAuth2 access tokens and API keys
- **Pagination**: Built-in offset/limit pagination
- **Filtering**: Query parameters for filtering data
- **Bulk operations**: Create and update multiple rows at once
- **FastAPI**: Modern, fast web framework with automatic API documentation
- **Type safety**: Full type hints and Pydantic models
- **Well-organized**: Clean, modular code structure for easy maintenance
- **Development tools**: Comprehensive development utilities and documentation

## 📁 Project Structure

```
sheetful-python/
├── app/                    # Main application package
│   ├── main.py            # FastAPI application setup
│   ├── config.py          # Configuration management
│   ├── models.py          # Pydantic models
│   ├── api/               # API routes
│   └── services/          # Business logic services
├── main.py                # Application entry point
└── Makefile               # Common development commands
```

## 🚀 Quick Start

### Using Make (Recommended)

```bash
# Setup everything at once
make setup

# Activate virtual environment
source .venv/bin/activate

# Configure environment variables
cp .env.example .env
# Edit .env with your Google API credentials

# Run development server
make dev
```

### Manual Setup

1. **Clone and setup:**
   ```bash
   git clone https://github.com/allysonbarros/Sheetful-API.git
   cd Sheetful-API
   python -m venv .venv
   source .venv/bin/activate  # Windows: .venv\Scripts\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your Google API credentials
   ```

4. **Run the application:**
   ```bash
   python main.py
   ```

### Using Docker

```bash
# Using docker-compose (recommended)
docker-compose up -d

# Or build and run manually
docker build -t sheetful-api .
docker run -p 8000:8000 --env-file .env sheetful-api
```

### API Documentation

Once the server is running, you can access:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### API Endpoints

#### Get Rows
```http
GET /{document_id}/{sheet_id}?offset=0&limit=100
```

#### Get Sheet Info
```http
GET /{document_id}/{sheet_id}/info
```

#### Get Single Row
```http
GET /{document_id}/{sheet_id}/{row_id}
```

#### Create Row
```http
POST /{document_id}/{sheet_id}
Content-Type: application/json

{
  "column1": "value1",
  "column2": "value2"
}
```

#### Update Row
```http
PUT /{document_id}/{sheet_id}/{row_id}
Content-Type: application/json

{
  "column1": "new_value1",
  "column2": "new_value2"
}
```

#### Bulk Operations
```http
POST /{document_id}/{sheet_id}/bulk
Content-Type: application/json

[
  {"column1": "value1", "column2": "value2"},
  {"column1": "value3", "column2": "value4"}
]
```

### Authentication

#### Using OAuth2 Access Token
Add the access token to the request headers:
```http
x-google-access-token: your_oauth2_access_token
```

#### Using API Key
Set the `GOOGLE_API_KEY` environment variable. This provides read-only access.

## Configuration

### Environment Variables

- `GOOGLE_API_KEY`: Your Google API key (optional, for read-only access)
- `PORT`: Server port (default: 8000)

### Google Cloud Setup

1. Create a Google Cloud project
2. Enable the Google Sheets API
3. Create credentials (API Key or OAuth2)
4. For OAuth2, download the credentials JSON file

## Examples

### Python Client Example

```python
import requests

# Get rows from a sheet
response = requests.get(
    "http://localhost:8000/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/0",
    headers={"x-google-access-token": "your_token"}
)
data = response.json()
print(data)
```

### JavaScript Client Example

```javascript
const response = await fetch(
    'http://localhost:8000/1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms/0',
    {
        headers: {
            'x-google-access-token': 'your_token'
        }
    }
);
const data = await response.json();
console.log(data);
```

## Development

### Running Tests

```bash
pytest
```

### Code Formatting

```bash
black .
isort .
```

### Type Checking

```bash
mypy .
```

## Migration from Node.js Version

This Python version maintains API compatibility with the original Node.js version while adding:

- Better type safety with Pydantic models
- Automatic API documentation with FastAPI
- Improved error handling
- More robust authentication handling
- Better logging and monitoring capabilities

## License

MIT License - see LICENSE file for details.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Run the test suite
6. Submit a pull request

## Support

For issues and questions, please create an issue on the GitHub repository.
