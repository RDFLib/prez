# NVS VocPrez
A custom implementation of [VocPrez](https://github.com/RDFLib/VocPrez/) for the [NERC Vocabulary Service (NVS)](https://vocab.nerc.ac.uk/).

This version of VocPrez is a complete reimplementation of the Python API using [FastAPI](https://fastapi.tiangolo.com/) and is the lead instance of VocPrez v3.


## Installation & Running
This version of VocPrez uses [FastAPI](https://fastapi.tiangolo.com/), not Flask, as it's Python Framework. It can be run using [uvicorn](https://www.uvicorn.org/) in a manner similar to Flask running on GUnicorn.

To install (Linux):

1. clone the repo - <https://github.com/surroundaustralia/NvsVocPrez>
2. (optional) create a Python virtual environment & activate it
    * `~$ python3 -m venv venv`
    * `~$ source venv/bin/activate`
3. install required packages
    * `~$ pip install -r requirements.txt`
4. run API with uvicorn package
    * path here is for running within the `NvsVocPrez/nvsvocprez` directory
    * `~$ uvicorn app:api --reload --port 5007 --log-level debug` (or other port, other log level etc)

There is no test v. production difference in the running of FastAPI, as there is with Flask, so the above works for any form of deployment.

### Config
* all configuration variables are in `config.py` and have required default set
* when run with `uvicorn`, `PORT` is usually set on the command line and `HOST` and `SYSTEM_URI` need not be changed from `config.py`
* `SPARQL_ENDPOINT` in `config.py` is correct for NVS production deployment and is used by the <http://nvs.surroundaustralia.com> deployment and Nick's localhost testing too


## Contacts
Lead Developer:  

**Nicholas Car**  
_Data Systems Architect_  
[SURROUND Australia Pty Ltd](http://surroundaustralia.com)  
<nicholas.car@surroundaustralia.com>