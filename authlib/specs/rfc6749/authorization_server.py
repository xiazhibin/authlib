from authlib.common.urls import add_params_to_uri
from .errors import InvalidGrantError, OAuth2Error


class AuthorizationServer(object):
    """Authorization server that handles Authorization Endpoint and Token
    Endpoint.

    :param query_client: A function to get client by client_id. The client
        model class MUST implement the methods described by
        :class:`~authlib.specs.rfc6749.ClientMixin`.
    :param token_generator: A method to generate tokens.
    """
    def __init__(self, query_client, token_generator):
        self.query_client = query_client
        self.token_generator = token_generator
        self._authorization_endpoints = set()
        self._token_endpoints = set()

    def register_grant_endpoint(self, grant_cls):
        """Register a grant class into the endpoint registry. Developers
        can implement the grants in ``authlib.specs.rfc6749.grants`` and
        register with this method::

            class MyImplicitGrant(ImplicitGrant):
                def create_access_token(self, token, client, grant_user):
                    # ...

            authorization_server.register_grant_endpoint(MyImplicitGrant)

        :param grant_cls: a grant class.
        """
        if grant_cls.AUTHORIZATION_ENDPOINT:
            self._authorization_endpoints.add(grant_cls)
        if grant_cls.ACCESS_TOKEN_ENDPOINT:
            self._token_endpoints.add(grant_cls)

    def get_authorization_grant(self, request):
        """Find the authorization grant for current request.

        :param request: OAuth2Request instance.
        :return: grant instance
        """
        for grant_cls in self._authorization_endpoints:
            if grant_cls.check_authorization_endpoint(request):
                return grant_cls(
                    request, self.query_client, self.token_generator)
        raise InvalidGrantError()

    def get_token_grant(self, request):
        """Find the token grant for current request.

        :param request: OAuth2Request instance.
        :return: grant instance
        """
        for grant_cls in self._token_endpoints:
            if grant_cls.check_token_endpoint(request):
                if request.method in grant_cls.ACCESS_TOKEN_METHODS:
                    return grant_cls(
                        request, self.query_client, self.token_generator)
        raise InvalidGrantError()

    def create_valid_authorization_response(self, request, grant_user):
        """Validate authorization request and create authorization response.

        :param request: OAuth2Request instance.
        :param grant_user: if granted, it is resource owner. If denied,
            it is None.
        :returns: (status_code, body, headers)
        """
        try:
            grant = self.get_authorization_grant(request)
        except InvalidGrantError as error:
            body = dict(error.get_body())
            return error.status_code, body, error.get_headers()
        try:
            grant.validate_authorization_request()
            return grant.create_authorization_response(grant_user)
        except OAuth2Error as error:
            params = error.get_body()
            loc = add_params_to_uri(grant.redirect_uri, params)
            headers = [('Location', loc)]
            return 302, '', headers

    def create_valid_token_response(self, request):
        """Validate token request and create token response.

        :param request: OAuth2Request instance
        """
        try:
            grant = self.get_token_grant(request)
        except InvalidGrantError as error:
            payload = dict(error.get_body())
            return error.status_code, payload, error.get_headers()
        try:
            grant.validate_access_token_request()
            return grant.create_access_token_response()
        except OAuth2Error as error:
            status = error.status_code
            payload = dict(error.get_body())
            headers = error.get_headers()
            return status, payload, headers
