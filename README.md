![](https://github.com/RDFLib/prez/raw/main/prez-logo.png)

# Prez

Prez is a data-configurable Linked Data API framework that delivers _profiles_ of Knowledge Graph data according to the [Content Negotiation by Profile](https://w3c.github.io/dx-connegp/connegp/) standard.

> **Where's the UI?**
>
> Prez delivers data only - usually [RDF](https://en.wikipedia.org/wiki/Resource_Description_Framework) but could be GeoJSON, XML etc. - and it delivers a special form of RDF which includes labels for all objects and predicates Prez can find in its database.
>
> If you want a UI that can render Prez' labelled RDF as HTML and other fancy graphical widgets, see the [Prez UI](https://github.com/RDFLib/prez-ui).

## Contents

- [Installation](#installation)
- [Configuration](#configuration)
- [Running](#running)
- [Redirect Service](#redirect-service)
- [Data Validation](#data-validation)
- [Contact](#contact)
- [Contributing](#contributing)
- [License](#license)

## Installation

To get a copy of Prez on your computer, run:

```bash
git clone https://github.com/RDFLib/prez
```

Prez is developed with [Poetry](https://python-poetry.org/), a Python packaging and dependency tool.
Poetry presents all of Prez's dependencies (other Python packages) in the `pyproject.toml` file located in the project root directory.

To install the Python dependencies run:

```bash
poetry install
```

> **Note:** Poetry must be installed on the system. To check if you have Poetry installed run `poetry --version`. For tips on installing and managing specific dependency groups check the [documentation](https://python-poetry.org/docs/managing-dependencies/).

## Running a demonstration instance

[Docker Compose](https://docs.docker.com/compose/) can be used to run a demonstration instance. The compose files comprises three services: Prez (Prez API), Prez UI, and Fuseki. To run the stack, change directory into the `demo` directory and run: `docker compose up`.

The Fuseki instance is empty, but can have data added to it, such as the test data under `test_data`.

## Endpoints

Prez delivers the following endpoints:

### Core Endpoints

**Endpoint** | **Default MT**
--- | ---
/ | text/anot+turtle
/docs | text/html
/catalogs/{catalogId} | text/anot+turtle
/catalogs/{catalogId}/collections | text/anot+turtle
/catalogs/{catalogId}/collections/{recordsCollectionId} | text/anot+turtle
/catalogs/{catalogId}/collections/{recordsCollectionId}/items | text/anot+turtle
/catalogs/{catalogId}/collections/{recordsCollectionId}/items/{itemId} | text/anot+turtle
/purge-tbox-cache | application/json
/tbox-cache | application/json
/health | application/json
/prefixes | text/anot+turtle
/concept-hierarchy/{parent_curie}/narrowers | text/anot+turtle
/concept-hierarchy/{parent_curie}/top-concepts | text/anot+turtle
/cql | text/anot+turtle
/profiles | text/anot+turtle
/search | text/anot+turtle
/profiles/{profile_curie} | text/anot+turtle
/object | text/anot+turtle
/identifier/redirect | N/A
/identifier/curie/{iri} | text/plain
/identifier/iri/{curie} | text/plai

### OGC Features API Endpoints

**The OGC Features API Endpoints are based at the ROOT `/catalogs/{catalogId}/collections/{recordsCollectionId}/`**

**Endpoint** | **Default MT**
--- | ---
{ROOT}/features | application/json
{ROOT}/features/docs | text/html
{ROOT}/features/conformance | application/json
{ROOT}/features/collections | application/json
{ROOT}/features/collections/{collectionId} | application/json
{ROOT}/features/collections/{collectionId}/items | application/geo+json
{ROOT}/features/collections/{collectionId}/items/{featureId} | application/geo+jso

## Configuration

The following Environment Variables can be used to configure Prez:
**In most cases all that is required is the SPARQL_ENDPOINT variable.**

These can be set in a '.env' file which will get read in via python-dotenv.
Alternatively, set them directly in the environment from which Prez is run.

An example .env file with the minimum required variables is in the repo as [`.env-required-template`](./.env-required-template), and an example .env file with all possible configuration variables, showing defaults, is in the repo as [`.env-full-template`](./.env-full-template).

#### SPARQL Endpoint Configuration

- **`SPARQL_ENDPOINT`**: Read-only SPARQL endpoint for Prez. Default is `None`.
- **`SPARQL_USERNAME`**: A username for the Prez SPARQL endpoint, if required by the RDF DB. Default is `None`.
- **`SPARQL_PASSWORD`**: A password for the Prez SPARQL endpoint, if required by the RDF DB. Default is `None`.
- **`ENABLE_SPARQL_ENDPOINT`**: Whether to enable the SPARQL endpoint. I.e. whether prez exposes the remote repository's SPARQL endpoint (typically a triplestore). Default is `False`. NB the SPARQL endpoint when enabled supports POST requests. Prez itself does not make any updates to the remote repository (e.g. the remote Triplestore), however, if the remote SPARQL endpoint is enabled it is then possible that users can make updates to the remote repository using the SPARQL endpoint.


#### Network Configuration

- **`PROTOCOL`**: The protocol used to deliver Prez. Default is `"http"`.
- **`HOST`**: Prez's host domain name. Default is `"localhost"`.
- **`PORT`**: The port Prez is made accessible on. Default is `8000`.

#### System URI

- **`SYSTEM_URI`**: The URL where prez is deployed. This is utilised only by the OGC Features API to generate links. Non OGC Features endpoints provided by prez provide prez:link relative links and so do not use this SYSTEM_URI. Default is `f"{protocol}://{host}:{port}"`.

#### Logging Configuration

- **`LOG_LEVEL`**: Logging level. Default is `"INFO"`.
- **`LOG_OUTPUT`**: Logging output destination. Default is `"stdout"`.

#### Prez Metadata

- **`PREZ_TITLE`**: Title for the Prez instance. Default is `"Prez"`.
- **`PREZ_DESC`**: Description of the Prez instance. Default is a description of the Prez web framework API.
- **`PREZ_VERSION`**: Version of the Prez instance. Default is `None`.

#### CURIE Separator

- **`CURIE_SEPARATOR`**: Separator used in CURIEs. Default is `":"`. This separator appears in links generated by Prez, and in turn in URL paths.

#### Predicate Configuration
Used for displaying RDF with human readable labels.
- **`LABEL_PREDICATES`**: List of predicates used for labels. Default includes:
    - `skos:prefLabel`
    - `dcterms:title`
    - `rdfs:label`
    - `sdo:name`
> When an annotated (`+anot`) mediatype is used, Prez includes triples for *every* URI in the initial response which has one of the above properties. These annotation triples are then cached. The annotations are used for display purposes, for example HTML pages. 
##### Description Predicates
Similar to label predicates above.
- **`DESCRIPTION_PREDICATES`**: List of predicates used for descriptions. Default includes:
    - `skos:definition`
    - `dcterms:description`
    - `sdo:description`
##### Provenance Predicates
Similar to provenance predicates above.
- **`PROVENANCE_PREDICATES`**: List of predicates used for provenance. Default includes:
    - `dcterms:provenance`

##### Other Predicates
The annotation mechanism can further be used to generally return certain properties wherever present.
- **`OTHER_PREDICATES`**: List of other predicates. Default includes:
    - `sdo:color`
    - `reg:status`
    - `skos:narrower`
    - `skos:broader`

#### SPARQL Repository Configuration

- **`SPARQL_REPO_TYPE`**: Type of SPARQL repository. Default is `"remote"`. Options are `"remote"`, `"pyoxigraph"`, and `"oxrdflib"`
- **`SPARQL_TIMEOUT`**: Timeout for SPARQL queries. Default is `30`.

#### Contact Information

- **`PREZ_CONTACT`**: Contact information for Prez. Default is `None`.

#### Prefix Generation

- **`DISABLE_PREFIX_GENERATION`**: Whether to disable prefix generation. **It is recommended to disable prefix generation for large data repositories**, further, it is recommended to always specify prefixes in the `prez/reference_data/prefixes/` directory. Default is `False`.
#### Language and Search Configuration

- **`DEFAULT_LANGUAGE`**: Default language for Prez. Default is `"en"`.
- **`DEFAULT_SEARCH_PREDICATES`**: Default search predicates. Default includes:
    - `rdfs:label`
    - `skos:prefLabel`
    - `sdo:name`
    - `dcterms:title`

#### Local RDF Directory
Used in conjunction with the Pyoxigraph repo. Specifies a directory (from the repository root) to load into the Pyoxigraph in memory data graph. Not used for other repository types.
- **`LOCAL_RDF_DIR`**: Directory for local RDF files. Default is `"rdf"`.

#### Endpoint Structure

- **`ENDPOINT_STRUCTURE`**: Default structure of the endpoints, used to generate links. Default is `("catalogs", "collections", "items")`.

#### System Endpoints

- **`SYSTEM_ENDPOINTS`**: List of system endpoints. Default includes:
    - `ep:system/profile-listing`
    - `ep:system/profile-object`

#### Listing and Search Configuration

- **`LISTING_COUNT_LIMIT`**: The maximum number of items to count for a listing endpoint. Counts greater than this limit will be returned as ">N" where N is the limit. Default is `100`.
- **`SEARCH_COUNT_LIMIT`**: The maximum number of items to return in a search result. Default is `10`.

#### Temporal Configuration

- **`TEMPORAL_PREDICATE`**: The predicate used for temporal properties. Default is `sdo:temporal`.

## Running

This section is for developing Prez locally. See the [Running](#running) options below for running Prez in production.

To run the development server (with auto-reload on code changes):

```bash
poetry run python main.py
```

### Running in a Container

Prez container images are built using a GitHub Action and are available [here](https://github.com/RDFLib/prez/pkgs/container/prez).

The Dockerfile in the repository can also be used to build a Docker image.

#### Image variants

The image name is `ghcr.io/rdflib/prez`.

The `latest` tag points to the latest stable release of Prez. All latest stable releases have a `major`, `major.minor`, and `major.minor.patch` tag pointing to it.

For example, for a release with a git tag of 3.2.4, the following tags will be on the container image:

- `3`
- `3.2`
- `3.2.4`
- `latest`

The full version is automatically created/incremented using the [Semantic Release GitHub Action](https://github.com/cycjimmy/semantic-release-action), which automatically increments the version based on commits to the `main`
branch.

### Testing

Prez uses [PyTest](https://pypi.org/project/pytest/) and [Coverage](https://pypi.org/project/coverage/) for testing and test coverage reports.

To run all available tests:

```bash
poetry run pytest tests
```

To run all available tests for coverage analysis:

```bash
poetry run coverage run -m pytest tests
```

To generate a coverage report:

```bash
poetry run coverage report
```

## Redirect Service

As a Linked Data server, Prez provides a redirect service at `/identifier/redirect` that accepts a query parameter `iri`, looks up the `iri` in the database for a `foaf:homepage` predicate with a value, and if it exists, return a redirect response to the value.

This functionality is useful for institutions who issue their own persistent identifiers under a domain name that they control. The mapping from the persistent identifier to the target web resource is stored in the backend SPARQL store.

This is an alternative solution to persistent identifier services such as the [w3id.org](https://w3id.org/). In some cases, it can be used together with such persistent identifier services to avoid the need to provide the redirect mapping in webserver config (NGINX, Apache HTTP, etc.) and instead, define the config as RDF data.

## Data Validation

For Prez to deliver data via its various subsystems, the data needs to conform to some minimum requirements: you can't, for instance, run VocPrez without any SKOS ConceptSchemes defined!

### Validation

All the profiles listed above provide validators that can be used with RDF data to test to see if it's valid. If it is, Prez will be just fine with it.

The profiles' validators are all available from the profiles themselves (navigate to the listings of other profile resources via the specification links above) and they are also loaded into the _KurrawongAI SHACL Validator_ online tool which you can use without downloading or installing anything:

- <https://tools.kurrawong.ai/validate>

Look for the _VocPrez Compounded_ and similar validators. The 'compounded' bit means that validator will validate data against all VocPrez and inherited requirements.

## Contact

> **NOTE**: This open source tool is actively developed and supported by [KurrawongAI](https://kurrawong.ai), a small Australian Knowledge Graph company, developers at the [University of Melbourne](https://www.unimelb.edu.au) and by open source contributors too.
>
> To flag problems or raise questions, please create issues in the [Issue Tracker](https://github.com/RDFLib/prez/issues) or you can contact developers using their details below.

Here are the lead developers:

**KurrawongAI**
<https://kurrawong.ai>

_David Habgood_
<david@kurrawong.ai>

_Nicholas Car_
<nick@kurrawong.ai>

_Edmond Chuc_
<edmond@kurrawong.ai>

**University of Melbourne** - Prez UI mainly
_Jamie Feiss_
<jamie.feiss@unimelb.edu.au>

## Contributing

We love contributions to this tool and encourage you to create Issues in this repository's Issue Tracker or to submit a Pull Requests!

There is documentation on contributing to Prez, see [README-Dev.md](README-Dev.md).

## License

This version of Prez and the contents of this repository are also available under the [BSD-3-Clause License](https://opensource.org/licenses/BSD-3-Clause). See [this repository's LICENSE](LICENSE) file for details.
