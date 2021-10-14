from pathlib import Path

import httpx

DB_URI = "http://localhost:7200/repositories/vocprez-test"
DB_USERNAME = "user"
DB_PASSWORD = "password"
DB_TYPE = "graphdb"  # fuseki | graphdb

index = {
    "dataset.ttl": "http://example.com/dataset/1",
    "scheme.ttl": "http://example.com/scheme/1",
}

# set endpoint
endpoint = DB_URI
if DB_TYPE == "fueski":
    endpoint += "/update"
elif DB_TYPE == "graphdb":
    endpoint += "/statements"
else:
    raise ValueError("Unsupported DB type. Supported types are: 'fuseki', 'graphdb'.")

# delete all
for graph in index.values():
    r = httpx.post(
        endpoint,
        data={"update": f"DROP GRAPH <{graph}>"},
        auth=(DB_USERNAME, DB_PASSWORD),
    )
    assert 200 <= r.status_code <= 300, f"Status code was {r.status_code}"

# drop default
r = httpx.post(
    endpoint,
    data={"update": f"DROP DEFAULT"},
    auth=(DB_USERNAME, DB_PASSWORD),
)
assert 200 <= r.status_code <= 300, f"Status code was {r.status_code}"

# add all
for file, graph in index.items():
    with open(file, "rb") as f:
        content = f.read()
    params = {}
    if DB_TYPE == "fueski":
        params = {"graph": f"{graph}"}
    elif DB_TYPE == "graphdb":
        params = {"context": f"<{graph}>"}
    r = httpx.post(
        endpoint,
        params=params,
        headers={"Content-Type": "text/turtle"},
        content=content,
        auth=(DB_USERNAME, DB_PASSWORD),
    )
    assert 200 <= r.status_code <= 300, f"Status code was {r.status_code}"

# add to default
for graph in index.values():
    r = httpx.post(
        endpoint,
        data={"update": f"ADD <{graph}> TO DEFAULT"},
        auth=(DB_USERNAME, DB_PASSWORD),
    )
    assert 200 <= r.status_code <= 300, f"Status code was {r.status_code}"