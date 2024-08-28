# Prez Azure Function-App deployment files

This directory contains the files required to build and start or publish Prez as an Azure Function-App, as well as a Dockerfile that 
can be used to build a container image for deploying the app as an Azure Container App.

## Publishing
There is a publish_or_start.sh script that can be used to either build and run the function app locally, or publish the app to Azure.
To call it, make sure you are not in the "azure" directory, instead run the script from the root of the project.

```bash
./azure/publish_or_start.sh start|publish --extra-options <function-app-name>
```
The FunctionAppName is required for publishing only, and is the name of the Azure Function-App that you want to publish to.
Note, the FunctionAppName must be the second argument to the script, after any optional arguments.

This script will perform the following steps:
1. Create a ./build directory
2. Copy the required azure function files from the ./azure directory into the ./build directory
  * ./azure/function_app.py
  * ./azure/patched_asgi_function_wrapper.py
  * ./azure/host.json
  * ./azure/.funcignore
3. Copy the local prez module source code into the ./build directory
4. Copy the .env file into the ./build directory if it exists
5. Copy the pyproject.toml and poetry.lock files into the ./build directory
6. Generate the requirements.txt file using poetry
7. Start the app locally, or publish the app to the Azure Function-App (using remote build)

**extra-options** can be used to pass additional arguments to the azure publish command. (Eg, the `--subscription` argument)

_Note:_ the script automatically adds the `--build remote` argument to the publish command, you don't need to specify it.

## Building the Docker container image

To build the Docker container image, run the following command from the root of the project:

```bash
docker build -t <image-name> -f azure/azure_functions.Dockerfile .
```
