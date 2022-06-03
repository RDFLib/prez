# Prez
Prez is a Linked Data API framework tool that delivers read-only access to Knowledge Graph data according to particular domain _profiles_.

Prez comes in two main profile flavours:

- _VocPrez_ - for vocabularies, based on the [SKOS](https://www.w3.org/TR/skos-reference/) data model
- _SpacePrez_ - for spatial data, based on [OGC API](https://docs.ogc.org/is/17-069r3/17-069r3.html) specification and the [GeoSPARQL](https://opengeospatial.github.io/ogc-geosparql/geosparql11/spec.html) data model

Prez is pretty straight-forward to install and operate and all while being high-performance. It uses the modern [FastAPI](https://fastapi.tiangolo.com/) Python web framework. 

Prez is quite simple and expects "high quality" data to work well. By requiring that you create high quality data for it, Prez can remain relatively simple and this ensures value is retained in the data and not in hidden code.

## Documentation

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
