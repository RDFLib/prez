from os import environ

from dotenv import load_dotenv

if __name__ == "__main__":
    try:
        import uvicorn
    except ImportError:
        print(
            'Error: Uvicorn is not installed. Install it with \'poetry install --extras "server".'
        )
        import sys

        sys.exit(1)

    # Load config from .env file.
    # See .env-template and prez/config.py for usage.
    load_dotenv()

    port = int(environ.get("PREZ_DEV_SERVER_PORT", 8000))

    uvicorn.run(
        "prez.app:assemble_app",
        factory=True,
        port=port,
        reload=True,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
