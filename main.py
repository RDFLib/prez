import uvicorn
from dotenv import load_dotenv

# Load config from .env file.
# See .env-template and prez/config.py for usage.
load_dotenv()

uvicorn.run("prez.app:app", port=4000)
