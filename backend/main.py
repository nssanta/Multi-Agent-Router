"""FastAPI application entry point"""

import uvicorn
import logging
from dotenv import load_dotenv
from backend.api.routes import app

# Load environment variables from .env file
load_dotenv()

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

if __name__ == "__main__":
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_excludes=["workspace/*", "*.log", "*.json"]
    )