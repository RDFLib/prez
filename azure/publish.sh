#!/bin/bash
DEFAULT_FUNC=$(which func)
DEFAULT_POETRY=$(which poetry)
FUNC_CLI=${FUNC_CLI:-"$DEFAULT_FUNC"}
POETRY=${POETRY:-"$DEFAULT_POETRY"}

ARG_COUNT="$#"
if [[ "$ARG_COUNT" -lt 1 ]] ; then
  # Publishes the function app code to the remote FunctionAppName on Azure
  echo "Usage: $0 [optional publish arguments] <FunctionAppName>"
  exit 1
fi

FUNC_APP_NAME="${@: -1}"
# Set args to all args minus the function app name
set -- "${@:1:$(($#-1))}"
CWD="$(pwd)"
BASE_CWD="${CWD##*/}"
if [[ "$BASE_CWD" = "azure" ]] ; then
  echo "Do not run this script from within the azure directory"
  echo "Run from the root of the repo"
  echo "eg: ./azure/build.sh"
  exit 1
fi

if [[ -z "$FUNC_CLI" ]] ; then
    echo "func cli not found, specify the location using env FUNC_CLI"
    exit 1
fi

if [[ -z "$POETRY" ]] ; then
    echo "poetry not found. Local poetry>=1.8.2 is required to generate the requirements.txt file"
    echo "specify the location using env POETRY"
    exit 1
fi

mkdir -p build
rm -rf build/*
cp ./azure/function_app.py ./azure/patched_asgi_function_wrapper.py ./azure/.funcignore ./azure/host.json ./azure/local.settings.json build/
cp ./pyproject.toml ./poetry.lock ./build
cp -r ./prez ./build
if [[ -f "./.env" ]] ; then
    cp ./.env ./build
fi
cd ./build
"$POETRY" export --without-hashes --format=requirements.txt > requirements.txt
echo "generated requirements.txt"
cat ./requirements.txt
"$FUNC_CLI" azure functionapp publish "$FUNC_APP_NAME" --build remote "$@"
cd ..
echo "You can now delete the build directory if you wish."