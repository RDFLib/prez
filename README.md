![](https://raw.githubusercontent.com/RDFLib/prez/main/prez-logo.png)

# Prez
Prez is a data-configurable Linked Data API framework that delivers _profiles_ of Knowledge Graph data according to the [Content Negotiation by Profile](https://w3c.github.io/dx-connegp/connegp/) standard.

> **Where's the UI?**
> 
> Prez delivers data only - usually [RDF](https://en.wikipedia.org/wiki/Resource_Description_Framework) but could be GeoJSON, XML etc. - and it delivers a special form of RDF which includes labels for all objects and predicates Prez can find in its database.   
> 
> If you want a UI that can render Prez' labelled RDF as HTML and other fancy graphical widgets, see the [Prez UI](https://github.com/RDFLib/prez-ui).

## Contents

* [Subsystems](#subsystems)
* [Installation](#installation)
* [Running](#running)
* [Data Validation](#data-validation)
* [Contact](#contact)
* [Contributing](#contributing)
* [License](#license)


## Subsystems

Prez comes with several pre-configures subsystems:

* _VocPrez_ - for vocabularies, based on the [SKOS](https://www.w3.org/TR/skos-reference/) data model
* _SpacePrez_ - for spatial data, based on [OGC API](https://docs.ogc.org/is/17-069r3/17-069r3.html) specification and the [GeoSPARQL](https://opengeospatial.github.io/ogc-geosparql/geosparql11/spec.html) data model
* _CatPrez_ - for [DCAT](https://www.w3.org/TR/vocab-dcat/) data catalogs

Prez uses the modern [FastAPI](https://fastapi.tiangolo.com/) Python web framework, so it's fast! It also has few requirements beyond FastAPI so should be pretty easy to install and run in most cases.

It expects "high quality" data to work well: Prez itself won't patch up bad or missing data. In this way it remains relatively simple and this ensures value is retained in the data and not in hidden code.

> **NOTE**: There are a number of data quality assessment tools and processes you can run to ensure that the data you want Prez to access is fit for purpose. See [Data Validation](#data-validation) below.

Prez accesses data stored in an RDF database - a 'triplestore' - and uses the SPARQL Protocol to do so. Any SPARQL Protocol-compliant DB may be used.


## Installation

_You don't have to 'install' Prez to use it, see the [Running](#running) options below. You may want to install Prez to develop with it._

### Poetry 

Prez is developed with [Poetry](https://python-poetry.org/) which is a Python packaging and dependency tool. Poetry presents all of Prez' dependencies (other Python packages) in the `pyproject.toml` file in this directory which can be used by Poetry to establish the environment you need to run Prez.

> Executing `poetry update` within this directory within a Python virtual environment will probably be all you need to do!

### PIP

We also provide a standard `requirements.txt` file for use with the common [PIP](https://pypi.org/project/pip/) package installer. We build this file using Poetry too.

> Executing `pip install -r requirements.txt` within a Python virtual environment will probably be all you need to do!


## Running

Prez runs as a standard FastAPI application so for all the normal HOW TO running questions, see FastAPI's documentation:

* <https://fastapi.tiangolo.com>

### Environment Variables

You do need to configure at least a couple of environment variables for Prez to run. The full set of available variables are found in `prez/config.py`.

#### Minimal

A minimal set of environment variables with example values to run prez is listed below:

`ENABLED_PREZS=["SpacePrez"]`  
`SPACEPREZ_SPARQL_ENDPOINT=http://localhost:3030/spaceprez`

Yes, you really only need to tell Prez which subsystems to enable - here it's SpacePrez for spatial data - and point Prez at a SPARQL endpoint for it to get data from!

#### Details

Of course, there are many other variables you may want to set. Here are some details.

See the `Settings` class within prez/config.py. You don't need to worry about the functions, just the variables there.

Have a look at the `Settings` class documentation for information about each variable.

Variable types (string, int etc.) are all indicated using Python type hinting, e.g.:

```python
port: int = 8000
```

So the `port` variable must be an `int` and its default value is 8000.

### Using Docker

To run Prez within a Docker container, first build the Docker image using the Dockerfile in this repo, or pull from Dockerhub:

build: `docker build -t prez .`

or

pull: `docker pull surroundaustralia/prez`

Then run the image:
```
docker run -p 8000:8000 \
    -e ENABLED_PREZS=["SpacePrez", "VocPrez"] \
    -e SPACEPREZ_SPARQL_ENDPOINT=http://localhost:3030/spatial \
    -e VOCPREZ_SPARQL_ENDPOINT=http://localhost:3030/other \
    rdflib/prez
```

The above command will run a Docker container with Prez in it on Port 8000 with SpacePrez & VocPrez subsystems enabled and different SPARQL endpoints given for each.


## Data Validation

For Prez to deliver data via its various subsystems, the data needs to conform to some minimum requirements: you can't, for instance, run VocPrez without an SKOS ConceptSchemes defined!

### Profiles

Formal RDF data profiles - standards that constrain other standards - are specified for Space, Voc & CatPrez. See:

* [SpacePrez Profile Specification](https://w3id.org/profile/spaceprez/spec)
* [VocPrez Profile Specification](https://w3id.org/profile/vocprez/spec)
* [CatPrez Profile Specification](https://w3id.org/profile/catprez/spec)
  * _yes yes, we know this one is offline for the moment. To be fixed shortly!_

The specifications of the various profiles _should_ be straightforward to read. Just be aware that they profile - inherit from and further constrain - other profiles so that there are quite a few 'background' data rules that must be met.

### Validation

All of the profiles listed above provide validators that can be used with RDF data to test to see if it's valid. If it is, Prez will be just fine with it.

The profiles' validators are all available from the profiles themselves (navigate to the listings of other profile resources via the specification links above) and they are also loaded into the _RDFTools_ online tool which you can use without downloading or installing anything:

* <http://rdftools.kurrawong.net/validate>

Look for the _VocPrez Compounded_ and similar validators. The 'compounded' bit means that validator will validate data against all VocPrez and inherited requirements. 


## Contact

> **NOTE**: This open source tool is actively developed and supported by [KurrawongAI](https://kurrawong.net), a small Australian Knowledge Graph company, developers at the [University of Melbourne](https://www.unimelb.edu.au) and by open source contributors too.
> 
> To flag problems or raise questions, please create issues in the [Issue Tracker](https://github.com/RDFLib/prez/issues) or you can contact developers using their details below.

Here are the lead developers:

**KurrawongAI**  
<https://kurrawong.net>

_David Habgood_  
<dcchabgood@gmail.com>  

_Nicholas Car_  
<nick@kurrawong.net>  

**University of Melbourne** - Prez UI mainly  
_Jamie Feiss_  
<jamie.feiss@unimelb.edu.au>

## Contributing

We love contributions to this tool and encourage you to create Issues in this repository's Issue Tracker or to submit a Pull Requests!

## License

This version of Prez and the contents of this repository are also available under the [BSD-3-Clause License](https://opensource.org/licenses/BSD-3-Clause). See [this repository's LICENSE](LICENSE) file for details.
