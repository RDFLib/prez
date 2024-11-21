import os
import time
import requests
import glob

os.system("docker context use default")
response = os.system(
    "docker run -d -v ${PWD}/dev/dev-config.ttl:/fuseki/config.ttl -p 3030:3030 ghcr.io/zazuko/fuseki-geosparql"
)

time.sleep(15)


def setup():
    url = "http://localhost:3030/myds"
    headers = {}

    # Get all TTL files from test_data directory
    ttl_files = glob.glob("test_data/*.ttl")

    # Process each file sequentially
    for i, file_path in enumerate(ttl_files, 1):
        file_name = os.path.basename(file_path)
        print(f"Loading file {i}/{len(ttl_files)}: {file_name}")

        files = [
            (
                "file",
                (
                    file_name,
                    open(file_path, "rb"),
                    "application/octet-stream",
                ),
            )
        ]

        response = requests.request(
            "POST",
            url,
            headers=headers,
            data={},
            files=files,
            params={"graph": "http://exampledatagraph"},
        )

        if response.status_code != 200:
            print(f"Error loading {file_name}: {response.status_code}")
            print(response.text)
        else:
            print(f"Successfully loaded {file_name}")


setup()