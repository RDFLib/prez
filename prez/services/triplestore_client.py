from httpx import AsyncClient
from prez.config import settings

sparql_client = AsyncClient(
    auth=(settings.sparql_username, settings.sparql_password),
)
