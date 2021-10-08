from typing import Dict


class FastAPIRequest(object):
    """
    A mock class to imitate a Request object from FastAPI,
    containing the minimal attributes required to run tests
    """

    def __init__(self, headers: Dict, query_params: Dict) -> None:
        self.headers = headers
        self.query_params = query_params


class FlaskRequest(object):
    """
    A mock class to imitate a Request object from Flask,
    containing the minimal attributes required to run tests
    """

    def __init__(self, headers: Dict, args: Dict) -> None:
        self.headers = headers
        self.args = args


class InvalidHeadersRequest(object):
    """
    A mock class to imitate a Request object, but containing
    an unsupported header attribute name
    """

    def __init__(self, header: Dict, args: Dict) -> None:
        self.header = header
        self.args = args


class InvalidQSARequest(object):
    """
    A mock class to imitate a Request object, but containing
    an unsupported QSA attribute name
    """

    def __init__(self, headers: Dict, params: Dict) -> None:
        self.headers = headers
        self.params = params
