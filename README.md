NOTICE: the open source community now maintains Prez at [RDFLib/Prez](https://github.com/RDFLib/Prez)

# Prez
Prez is a Linked Data API framework tool that delivers read-only access to Knowledge Graph data according to particular domain _profiles_.

Prez comes in two main profile flavours:

- _VocPrez_ - for vocabularies, based on the [SKOS](https://www.w3.org/TR/skos-reference/) data model
- _SpacePrez_ - for spatial data, based on [OGC API](https://docs.ogc.org/is/17-069r3/17-069r3.html) specification and the [GeoSPARQL](https://opengeospatial.github.io/ogc-geosparql/geosparql11/spec.html) data model

Prez is pretty straight-forward to install and operate and all while being high-performance. It uses the modern [FastAPI](https://fastapi.tiangolo.com/) Python web framework.

Prez is quite simple and expects "high quality" data to work well. By requiring that you create high quality data for it, Prez can remain relatively simple and this ensures value is retained in the data and not in hidden code.

## Running Prez
Environment variables for configuring prez are found in `prez/config.py`. A minimal set of environment variables with example values to run prez is listed below:

`ENABLED_PREZS=["SpacePrez"]`
`SPACEPREZ_SPARQL_ENDPOINT=http://localhost:3030/spaceprez`

### Using Python
Prez can be run directly using python by running:
`python run prez/app.py`, NB though, Prez won't start unless the specified SPARQL endpoint(s) is/are found.
To run a mock SPARQL endpoint, with some example data, you can run the following command:
`python tests/local_sparql_store/store.py`
You can then run prez against the local mock SPARQL endpoint by setting the SPACEPREZ_SPARQL_ENDPOINT environment variable to `http://localhost:3030/spaceprez`.

### Using Docker
First build the docker image using the Dockerfile in this repo, or pull from Dockerhub:
build: `docker build -t prez .`
or
pull: `docker pull surroundaustralia/prez`

Then run the image:
```
docker run -p 8000:8000 \
    -e ENABLED_PREZS=["SpacePrez", "VocPrez"] \
    -e SPACEPREZ_SPARQL_ENDPOINT=http://localhost:3030/spaceprez \
    -e VOCPREZ_SPARQL_ENDPOINT=http://localhost:3030/vocprez \
    surroundaustralia/prez
```
Installation, use development schedule and more are documented at https://surroundaustralia.github.io/Prez/.

## Contact

This tool is actively developed and supported by [SURROUND Australia Pty Ltd](https://surroundaustalia.com). Please contact SURROUND either by creating issues in the [Issue Tracker](https://github.com/surroundaustralia/Prez/issues) or directly emailing the lead developers:

**Jamie Feiss**
<jamie.feiss@surroundaustralia.com>

**David Habgood**
<david.habgood@surroundaustralia.com>

## Contributing

We love contributions to this tool and encourage you to create Issues in this repositories Issue Tracker as well as submitting Pull Requests with your own updates.

## License

This version of Prez and the contents of this repository are also available under the [BSD-3-Clause License](https://opensource.org/licenses/BSD-3-Clause). See [this repository's LICENSE](LICENSE) file for details.
