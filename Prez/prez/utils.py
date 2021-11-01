import jinja2
from starlette_core.templating import Jinja2Templates

from config import *

def get_config(var):
    import config
    return getattr(config, var)

templates = Jinja2Templates(
    loader=jinja2.ChoiceLoader(
        [jinja2.FileSystemLoader(TEMPLATE_PLUGIN_DIRS + ["templates"])]
    )
)
templates.env.filters["get_config"] = get_config