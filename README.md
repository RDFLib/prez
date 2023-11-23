![](https://github.com/RDFLib/prez/raw/main/prez-logo.png)

# Prez

Prez is a data-configurable Linked Data API framework that delivers _profiles_ of Knowledge Graph data according to the [Content Negotiation by Profile](https://w3c.github.io/dx-connegp/connegp/) standard.

> **Where's the UI?**
>
> Prez delivers data only - usually [RDF](https://en.wikipedia.org/wiki/Resource_Description_Framework) but could be GeoJSON, XML etc. - and it delivers a special form of RDF which includes labels for all objects and predicates Prez can find in its database.
>
> If you want a UI that can render Prez' labelled RDF as HTML and other fancy graphical widgets, see the [Prez UI](https://github.com/RDFLib/prez-ui).

## Contents

- [Subsystems](#subsystems)
- [Installation](#installation)
- [Running](#running)
- [Data Validation](#data-validation)
- [Contact](#contact)
- [Contributing](#contributing)
- [License](#license)

## Subsystems

Prez comes with several pre-configured subsystems:

- _VocPrez_ - for vocabularies, based on the [SKOS](https://www.w3.org/TR/skos-reference/) data model
- _SpacePrez_ - for spatial data, based on [OGC API](https://docs.ogc.org/is/17-069r3/17-069r3.html) specification and the [GeoSPARQL](https://opengeospatial.github.io/ogc-geosparql/geosparql11/spec.html) data model
- _CatPrez_ - for [DCAT](https://www.w3.org/TR/vocab-dcat/) data catalogs

Prez uses the modern [FastAPI](https://fastapi.tiangolo.com/) Python web framework, so it's fast! It also has few requirements beyond FastAPI so should be pretty easy to install and run in most cases.

It expects "high quality" data to work well: Prez itself won't patch up bad or missing data. In this way it remains relatively simple and this ensures value is retained in the data and not in hidden code.

> **NOTE**: There are a number of data quality assessment tools and processes you can run to ensure that the data you want Prez to access is fit for purpose. See [Data Validation](#data-validation) below.

Prez accesses data stored in an RDF database - a 'triplestore' - and uses the SPARQL Protocol to do so. Any SPARQL Protocol-compliant DB may be used.

## Redirect Service

As a Linked Data server, Prez provides a redirect service at `/identifier/redirect` that accepts a query parameter `iri`, looks up the `iri` in the database for a `foaf:homepage` predicate with a value, and if it exists, return a redirect response to the value.

This functionality is useful for institutions who issue their own persistent identifiers under a domain name that they control. The mapping from the persistent identifier to the target web resource is stored in the backend SPARQL store.

This is an alternative solution to persistent identifier services such as the [w3id.org](https://w3id.org/). In some cases, it can be used together with such persistent identifier services to avoid the need to provide the redirect mapping in webserver config (NGINX, Apache HTTP, etc.) and instead, define the config as RDF data.

## Installation

To get a copy of Prez on your computer, run:

```bash
git clone https://github.com/RDFLib/prez
```

Prez is developed with [Poetry](https://python-poetry.org/), a Python packaging and dependency tool.
Poetry presents all of Prez's
dependencies (other Python packages)
in the `pyproject.toml` file located in the project root directory.

To install the Python dependencies run:

```bash
poetry install
```

> **Note:** Poetry must be installed on the system. To check if you have Poetry installed run `poetry --version`. For tips on installing and managing specific dependency groups check the [documentation](https://python-poetry.org/docs/managing-dependencies/).

## Running

This section is for developing Prez locally. See the [Running](#running) options below for running Prez in production.

To run the development server (with auto-reload on code changes):

```bash
poetry run python main.py
```



Prez runs as a standard FastAPI application, so for all the normal HOW TO running questions, see FastAPI's documentation:

- <https://fastapi.tiangolo.com>

### Environment Variables

You need to configure at least 1 environment variable for Prez to run. The full set of available variables are found in `prez/config.py`.

#### Minimal

The minimal set of environment variables with example values to run prez is listed below:

`SPARQL_ENDPOINT=http://localhost:3030/mydataset`

If the SPARQL endpoint requires authentication, you must also set:

`SPARQL_USERNAME=myusername`, and
`SPARQL_PASSWORD=mypassword`

To run Prez using [Pyoxigraph](https://pypi.org/project/pyoxigraph/) as the sparql store (useful for testing and development) set:

`SPARQL_REPO_TYPE=pyoxigraph`

In this case, you do not need to set the SPARQL_ENDPOINT

#### Details

Further configuration can be done via environment variables. These can be set in a '.env' file which will get read in
via python-dotenv.
Alternatively, set them directly in the environment from which Prez is run.
The environment variables are used to
instantiate a Pydantic `Settings` object which is used throughout Prez to configure its behavior. To see how prez
interprets/uses these environment variables check the `prez/config.py` file.

| Environment Variable      | Description                                                                                                                                                                                              |
| ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| SPARQL_ENDPOINT           | Read-only SPARQL endpoint for SpacePrez                                                                                                                                                                  |
| SPARQL_USERNAME           | A username for Basic Auth against the SPARQL endpoint, if required by the SPARQL endpoint.                                                                                                               |
| SPARQL_PASSWORD           | A password for Basic Auth against the SPARQL endpoint, if required by the SPARQL endpoint.                                                                                                               |
| PROTOCOL                  | The protocol used to deliver Prez. Usually 'http'.                                                                                                                                                       |
| HOST                      | The host on which to server prez, typically 'localhost'.                                                                                                                                                 |
| PORT                      | The port Prez is made accessible on. Default is 8000, could be 80 or anything else that your system has permission to use                                                                                |
| SYSTEM_URI                | Documentation property. An IRI for the Prez system as a whole. This value appears in the landing page RDF delivered by Prez ('/')                                                                        |
| LOG_LEVEL                 | One of CRITICAL, ERROR, WARNING, INFO, DEBUG. Defaults to INFO.                                                                                                                                          |
| LOG_OUTPUT                | "file", "stdout", or "both" ("file" and "stdout"). Defaults to stdout.                                                                                                                                   |
| PREZ_TITLE                | The title to use for Prez instance                                                                                                                                                                       |
| PREZ_DESC                 | A description to use for the Prez instance                                                                                                                                                               |
| DISABLE_PREFIX_GENERATION | Default value is `false`. Very large datasets may want to disable this setting and provide a predefined set of prefixes for namespaces as described in [Link Generation](README-Dev.md#link-generation). |

### Running in a Container

Prez container images are available as github packages [here](https://github.com/RDFLib/prez/pkgs/container/prez).

#### Image variants

The image name is `ghcr.io/rdflib/prez`.

The `latest` tag points to the latest stable release of Prez. All latest stable releases have a major, major and minor, and major, minor and patch tag pointing to it.

For example, for a release with a git tag of 3.2.4, the following tags will be on the container image:

- `3`
- `3.2`
- `3.2.4`
- `latest`

New commits to the `main` branch creates a rolling dev image with the `dev` tag. The dev builds will also include a tag in the form of major.minor.{patch+1}-dev.{commits-since-last-release}.{short-commit-sha}. This conforms to semantic versioning and will be recognized by orchestration systems to perform automatic releases.

For example, if the latest release is 3.2.4 and there have been 7 new commits since the release and the short commit SHA is fc82562, then the container image tag will be:

- `3.2.5-dev.7.fc82562`

To run the pulled docker image:

```
docker run -p 8000:8000 \
    -e SPARQL_ENDPOINT=<your_sparql_endpoint> \
    <your_image_id>
```

The above command starts a Docker container running Prez on port 8000, connected to the specified sparql endpoint.

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


## Data Validation

For Prez to deliver data via its various subsystems, the data needs to conform to some minimum requirements: you can't, for instance, run VocPrez without an SKOS ConceptSchemes defined!

### Profiles

Formal RDF data profiles - standards that constrain other standards - are specified for Space, Voc & CatPrez. See:

- [SpacePrez Profile Specification](https://w3id.org/profile/spaceprez/spec)
- [VocPrez Profile Specification](https://w3id.org/profile/vocprez/spec)
- [CatPrez Profile Specification](https://w3id.org/profile/catprez/spec)
  - _yes yes, we know this one is offline for the moment. To be fixed shortly!_

The specifications of the various profiles _should_ be straightforward to read. Just be aware that they profile - inherit from and further constrain - other profiles so that there are quite a few 'background' data rules that must be met.

### Validation

All the profiles listed above provide validators that can be used with RDF data to test to see if it's valid. If it is, Prez will be just fine with it.

The profiles' validators are all available from the profiles themselves (navigate to the listings of other profile resources via the specification links above) and they are also loaded into the _RDFTools_ online tool which you can use without downloading or installing anything:

- <http://rdftools.kurrawong.net/validate>

Look for the _VocPrez Compounded_ and similar validators. The 'compounded' bit means that validator will validate data against all VocPrez and inherited requirements.

## Contact

> **NOTE**: This open source tool is actively developed and supported by [KurrawongAI](https://kurrawong.net), a small Australian Knowledge Graph company, developers at the [University of Melbourne](https://www.unimelb.edu.au) and by open source contributors too.
>
> To flag problems or raise questions, please create issues in the [Issue Tracker](https://github.com/RDFLib/prez/issues) or you can contact developers using their details below.

Here are the lead developers:

**KurrawongAI**
<https://kurrawong.net>

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
