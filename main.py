from os import environ

import uvicorn
from dotenv import load_dotenv

if __name__ == "__main__":
    # Load config from .env file.
    # See .env-template and prez/config.py for usage.
    load_dotenv()

    port = int(environ.get("PREZ_DEV_SERVER_PORT", 8000))

    uvicorn.run("prez.app:assemble_app", factory=True, port=port, reload=True,
                proxy_headers=True, forwarded_allow_ips='*')
