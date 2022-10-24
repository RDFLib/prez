import re
from pathlib import Path
from typing import Dict, List

from prez.config import *


def get_config(var):
    """Gets a config variable from config.py"""
    import prez.config as config

    return getattr(config, var)


def append_qsa(uri: str, qsas: Dict[str, str]) -> str:
    """Appends QSAs to a URL & sorts according to an order"""

    def qsa_sort(key: str) -> int:
        if key == "uri":
            return 0
        elif key == "_profile":
            return 1
        elif key == "_mediatype":
            return 2
        else:
            return 3

    qsa_dict = {}
    if "?" in uri:
        path, qsa_str = uri.split("?")
        for qsa in qsa_str.split("&"):
            key, value = qsa.split("=", maxsplit=1)
            qsa_dict[key] = value
    else:
        path = uri
    qsa_dict.update(qsas)
    qsa_list = [(key, value) for key, value in qsa_dict.items()]
    for i, qsa in enumerate(sorted(qsa_list, key=lambda k: qsa_sort(k[0]))):
        if i == 0:
            path += f"?{qsa[0]}={qsa[1]}"
        else:
            path += f"&{qsa[0]}={qsa[1]}"
    return path


def file_exists(path: str) -> bool:
    """Checks whether a file exists"""
    return os.path.isfile(path)


def match(s: str, pattern: str) -> bool:
    """Matches a string to a regex pattern"""
    if re.match(pattern, s):
        return True
    else:
        return False


def join_list_keys(l: List, key: str, sep: str) -> str:
    """Concatenates a list of dicts into a string of key values with a specified separator"""
    return sep.join([e[key] for e in l])


def commafy(value):
    """Applies thousands separator to integers"""
    return "{:,d}".format(value)
