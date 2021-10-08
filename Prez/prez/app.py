import fastapi
import uvicorn

from config import *
from routers import vocprez_router

app = fastapi.FastAPI()


def configure():
    configure_routing()


def configure_routing():
    app.include_router(vocprez_router.router)


@app.get("/")
async def index():
    return "index"


# docs

# sparql

# search

# about

# get prezs

# object?

if __name__ == "__main__":
    configure()
    uvicorn.run("app:app", port=PORT, host=SYSTEM_URI, reload=True)
else:
    configure()
