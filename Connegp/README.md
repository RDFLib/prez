# Connegp

Implements [Content Negotiation by Profile (Connegp)](https://w3c.github.io/dx-connegp/connegp/) for Python web frameworks. Currently supports FastAPI & Flask.

Structure:

- `connegp.py`
    - `Connegp` class
        - Contains parsing functionality from original `connegp` module
        - Does the same stuff as the old `Renderer` class without the render functions (which will be moved to Prez)
- `profile.py`
    - `Profile` class (as before)
- `exceptions.py`
    - Same classes as before
- `consts.py`
    - List & dict constants for RDF mediatypes, etc.
- `mediatype.py` (implement later)
    - `MediaType` class
        - Does the same thing for media types as `Profile` does for profiles