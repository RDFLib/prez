# Prez
Prez is a Linked Data API presentation tool using the modern Python web framework [FastAPI](https://fastapi.tiangolo.com/). It offers several domain-specific configurations such as:

- _VocPrez_ - for vocabularies
- _CatPrez_ - for catalogues
- _SpacePrez_ - for Semantic Web spatial data

Prez can be deployed according to one or multiple of these configurations.

## Features

- Linked Data delivery of content
    - human (HTML) & machine (RDF) formats
    - multiple data models (profiles) available
- structured according to standardised APIs
    - e.g. [OGC API: Features](http://www.opengis.net/doc/IS/ogcapi-features-1/1.0) for spatial data
- highly customisable UI
- formal data validation methods & tooling
    - Prez uses profile data models to ensure content has all the parts needed for good delivery

A demo installation of a combined Voc and Space Prez is online at <https://prez.surroundaustralia.com>.

## Installing Prez
Install using Poetry (optional), which you can install [here](https://python-poetry.org/docs/#installation) (recommended), or by running:

```bash
pip install poetry 
```

Then run `poetry install` in the root directory, `Prez/`.

Otherwise install using `pip` as normal:

```bash
pip install -r requirements.txt 
```

## Running/Deploying Prez
To get started without any configuration, simply run `python3 app.py` in the `Prez/prez/` directory.

Two additional repos are required to properly update data & customise a Prez instance for deployment:

### 1. Updating Prez Data
Each *Prez expects data to conform to a particular format. For each *Prez used in your instance, fork/clone each of these repos for updating data:

- VocPrez - [surround-prez-vocabs](https://github.com/surroundaustralia/surround-prez-vocabs)
- SpacePrez - [surround-prez-features](https://github.com/surroundaustralia/surround-prez-features)

Each repo contains a validate & update script. Refer to each repo's documentation on how to use them.

### 2. Customisation & Deployment
Prez is designed to run in a containerised environment. Configuring & theming Prez is done by following [surround-prez-theme](https://github.com/surroundaustralia/surround-prez-theme). Fork/clone this repo to run/deploy your own Prez instance. Refer to the repo's documentation on how to configure.

## Application Structure
The standard process for an entity endpoint is as follows:

1. An endpoint within a router is accessed (in `routers/`)
2. Endpoint calls SPARQL service to POST a SPARQL query (in `services/`)
3. The resulting RDFlib Graph is ingested by a model object (in `models/`)
4. A renderer object is created which uses the model object (in `renderers/`)
5. The endpoint returns the renderer's `render()` function
    - The response can be a renderered template (in `templates/`)

## Dev Dependencies

- SASS
    - Run the SASS watcher from the `sass/` folder like so:
        - If using dart-sass: `sass --no-source-map --watch main.scss ../css/index.css`
        - If using node-sass: `sass --source-map=none --watch main.scss ../css/index.css`
