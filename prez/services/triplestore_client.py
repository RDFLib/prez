from httpx import AsyncClient
from prez.config import settings


class SPARQLAsyncClient:
    def __init__(self, auth, base_url):
        self.client = AsyncClient(auth=auth, base_url=base_url, timeout=9999)

    async def close(self):
        await self.client.aclose()


sparql_clients = {
    "CatPrez": {},
    "VocPrez": {},
    "SpacePrez": {},
}
for prez in settings.enabled_prezs:
    sparql_clients[prez] = AsyncClient(
        auth=(
            settings.sparql_creds[prez].get("username", ""),
            settings.sparql_creds[prez].get("password", ""),
        ),
        base_url=settings.sparql_creds[prez]["endpoint"],
    )
