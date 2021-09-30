import fastapi
import uvicorn

from config import *

api = fastapi.FastAPI()


def configure():
    configure_routing()


def configure_routing():
    pass


if __name__ == "__main__":
    configure()
    uvicorn.run(api, port=8000, host="127.0.0.1")
else:
    configure()
