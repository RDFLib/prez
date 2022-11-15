![](https://github.com/RDFLib/prez/raw/main/prez/static/img/prez-logo.png)

# Prez
Prez is a web framework API for delivering Linked Data. It provides read-only access to Knowledge Graph data which can be subset according to information _profiles_.

Prez comes in three main flavours:

- _VocPrez_ - for vocabularies, based on the [SKOS](https://www.w3.org/TR/skos-reference/) data model
- _SpacePrez_ - for spatial data, based on [OGC API](https://docs.ogc.org/is/17-069r3/17-069r3.html) specification and the [GeoSPARQL](https://opengeospatial.github.io/ogc-geosparql/geosparql11/spec.html) data model
- _CatPrez_ - for [DCAT](https://www.w3.org/TR/vocab-dcat/) data catalogs

## Outline

* [Installation & Use]()
  * [Installation](#installation)
    * [As a Python application](#as-a-python-application)
    * [As a Docker container](#as-a-docker-container)
  * [Use](#use) 
    * [Environment Variables](#environment-variables)
    * [Running](#running)
      * [As a Python Application](#run-as-a-python-application)
      * [As a Docker container](#run-as-a-docker-container)
* [Data](#data)
  * [Catalogue Data](#catalogue-data)
  * [Spatial Data](#spatial-data)
  * [Vocabulary Data](#vocabulary-data)
* [Contact](#contact)
* [Contributing](#contributing)
* [License](#license)

## Installation & Use

Prez is pretty straight-forward to install and operate and all while being high-performance. It is implemented as a [Python](https://www.python.org/) s [FastAPI](https://fastapi.tiangolo.com/) web framework and uses Python's [RDFLib](https://pypi.org/project/rdflib/) to access RDF data.

## Installation

To install Prez, you need to either install Python and run Prez as a Python application or as a Docker container.

In either case, you will need to provide access to an RDF database (a "triplestore") via a [SPARQL Protocol](https://www.w3.org/TR/sparql11-protocol/) endpoint for Prez to lodge SPARQL queries with.

### As a Python application

1. Clone this Git repository to your local system
    * A good guide: <https://devconnected.com/how-to-clone-a-git-repository/>
2. Follow the main steps for installation of a generic FastAPI application
    * <https://realpython.com/fastapi-python-web-apis/>

Python's [PIP](https://pypi.org/project/pip/) or the more modern [Poetry](https://python-poetry.org/) can be used for installation of FastAPI and its dependencies.

Once you have this repository cloned locally, and Python, FastAPI and its dependencies are installed, you are ready to use, see _Use --> As a Python Application_ below.

### As a Docker container

This repository, set up with dependencies, is available on GitHub's public Docker Hub, via this repository:

* <https://github.com/RDFLib/prez/pkgs/container/prez>

Follow normal public Docker container steps for use.

## Use

Use of Prez requires Prez either installed as a Python application or as a Docker image.

Once Prez is available, it needs to be configured for use with environment variables. 

### Environment Variables

The full set of Environment Variables that can be set are given as variables in the file `config.py`. Prez will overwrite the default values in the file with any set as Environment Variables.

A minimal set of Environment Variables, set using [BASH shell](https://www.educba.com/bash-shell-in-linux/) commands, to configure Prez to run just the VocPrez subsystem for vocabularies could be:

```
ENABLED_PREZS='["VocPrez"]'
VOCPREZ_SPARQL_ENDPOINT=http://some-sparql-endpoint.com/sparql
```

To title the Prez system overall, to enable VocPrez & SpacePrez, to give each different titles but the same SPARQL endpoints:

```
PREZ_TITLE="A Great Prez Instance"
ENABLED_PREZS='["SpacePrez","VocPrez"]'
SPACEPREZ_SPARQL_ENDPOINT=http://some-sparql-endpoint.com/sparql
VOCPREZ_SPARQL_ENDPOINT=http://some-sparql-endpoint.com/sparql
VOCPREZ_TITLE="A VocPrez Instance"
SPACEPREZ_TITLE="A SpacePrez Instance"
```

### Running 

#### Run as a Python Application

Prez can be run directly using python by running:
`python run prez/app.py`, NB though, Prez won't start unless the specified SPARQL endpoint(s) is/are found.
To run a mock SPARQL endpoint, with some example data, you can run the following command:
`python tests/local_sparql_store/store.py`
You can then run prez against the local mock SPARQL endpoint by setting the SPACEPREZ_SPARQL_ENDPOINT environment variable to `http://localhost:3030/spaceprez`.

#### run as a Docker container

With the public Prez Docker image, Prez can be run with Docker commands like this:

```
docker run -p 8000:8000 \
    -e ENABLED_PREZS=["SpacePrez", "VocPrez"] \
    -e VOCPREZ_SPARQL_ENDPOINT=http://some-sparql-endpoint.com/sparql \
    ghcr.io/rdflib/prez:latest
```

Alternatively, you can build your own image from the Dockerfile that is also included in this repo like this, within the `prez/` folder:

```
docker build -t prez .
```

...and then run the resultant image. 


## Data

Prez reads [RDF](https://www.w3.org/RDF/) from an RDF database, often called a "triplestore" which it accesses through a [SPARQL Protocol](https://www.w3.org/TR/sparql11-protocol/) endpoint with [SPARQL queries](https://www.w3.org/TR/sparql11-query/).

Even though it can handle all kinds of data variability - as per RDF graphs in general - there are minimal requirements.

The minimum requirements are _per type_ where the _types_ are catalogue, spatial & vocabulary (for the moment!).

### Validation

Data can be assessed as to whether it meets the minimal catalogue, spatial & vocabulary requirements or not by using [SHACL](https://www.w3.org/TR/shacl/) validation techniques outside of Prez. 

* [RDFTools](http://rdftools.kurrawong.net/validate)

We suggest use of the online [RDFTools](http://rdftools.kurrawong.net/validate) system which uses SHACL validators via the RDFLib [pySHACL](https://github.com/RDFLib/pySHACL) SHACL engine. It also includes all the relevant validators for Prez data (see subsections below), pre-loaded.

### Catalogue Data

Catalogue data for Prez' CatPrez must conform to the [CatPrez Profile of DCAT](https://w3id.org/profile/catprez).

Mandates the use of a DCAT [`Catalog`](https://www.w3.org/TR/vocab-dcat/#Class:Catalog), with basic metadata, to contain [`Resource`](https://www.w3.org/TR/vocab-dcat/#Class:Resource) instances which maybe subtypes to indicate "dataset", rather than the use of [`Dataset`](https://www.w3.org/TR/vocab-dcat/#Class:Dataset) directly.

### Spatial Data

Spatial data for Prez' SpacePrez must conform to the [SpacePrez Profile of GeoSPARQL & DCAT](https://w3id.org/profile/spaceprez).

Mandates data objects to meet the [OGC API: Features Core](http://www.opengis.net/doc/IS/ogcapi-features-1/1.0) standard's data model. This includes:

* Dataset
  * instances of DCAT's [`Dataset`](https://www.w3.org/TR/vocab-dcat/#Class:Dataset)
    * top-level container
    * basic metadata required
* Feature Collection
  * instances of GeoSPARQL's [`FeatureCollection`](https://opengeospatial.github.io/ogc-geosparql/geosparql11/spec.html#_class_geofeaturecollection)

### Vocabulary Data

Vocabulary data for Prez' VocPrez must conform to the [VocPrez Profile of SKOS](https://w3id.org/profile/vocprez).

Mandates use of `dcterms:identifier` properties, basic labelling and vocabulary links per `skos:Concept`. Really only ensures `skos:Concept` instances are uniquely identified & linked to their vocabulary(ies).

Mandates basic metadata for `skos:ConceptScheme` instances, similar to `dcat:Resource` for CatPrez, such as who, what, where, when.

## Contact

This tool is actively developed and supported by [KurrawongAI](https://kurrawong.net) and the [Indigenous Data Network](https://idnau.org/) but it is a community-led, open source project. Please contact the maintainers either by creating issues in the [Issue Tracker](https://github.com/RDFLib/prez/issues) or directly emailing the lead developers:

**Nicholas Car**  
<nick@kurrawong.net>  

**Jamie Feiss**  
<jamie.feiss@unimelb.edu.au>

**David Habgood**  
<dcchabgood@gmail.com>

## Contributing

We love contributions to this tool and encourage you to create Issues in this repositories Issue Tracker as well as submitting Pull Requests with your own updates.

## License

This version of Prez and the contents of this repository are also available under the [BSD-3-Clause License](https://opensource.org/licenses/BSD-3-Clause). See [this repository's LICENSE](LICENSE) file for details.
