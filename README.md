# Prez
Prez is a Linked Data API presentation tool using FastAPI. It is a combination of VocPrez, CatPrez, TimePrez & SpacePrez (previously OGC LD API).

## Features

- Cross-system search
- Configure which *Prezs to activate
- Acts as the *Prez at the top-level if only 1 is active
- SPARQL endpoint
- Modular templating
- Mobile view

## Running Prez
Install using Poetry, which you can install [here](https://python-poetry.org/docs/#installation).

Then run `poetry install` in the root directory, `Prez/`.

To simply run locally without configuration outside of Docker, run `python3 app.py` in the `Prez/prez/` directory.

Prez is designed to run in a containerised environment. Configuring & theming Prez is done in [theme-template](../theme-template). Updating triplestore data (e.g. vocabs) is done in [vocabs-template](../vocabs-template). To deploy your own instance of Prez, fork both of the above repos & configure.

## Dev Dependencies

- SASS
    - Run the SASS watcher from the `sass/` folder like so:
        - If using dart-sass: `sass --no-source-map --watch main.scss ../css/index.css`
        - If using node-sass: `sass --source-map=none --watch main.scss ../css/index.css`
