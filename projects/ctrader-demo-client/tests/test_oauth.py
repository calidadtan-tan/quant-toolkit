import json
import unittest
import urllib.parse
import urllib.request

from ctrader_demo.constants import AUTHORIZE_ENDPOINT, TOKEN_ENDPOINT
from ctrader_demo.errors import ApiError, DemoGuardError
from ctrader_demo.oauth import (
    RefuseRedirectHandler,
    build_authorize_url,
    build_token_request,
    fetch_token,
    parse_token_response,
)


class FakeResponse:
    def __init__(self, body: bytes, url: str):
        self._body = body
        self._url = url

    def read(self) -> bytes:
        return self._body

    def geturl(self) -> str:
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class OAuthTests(unittest.TestCase):
    def test_authorize_url_uses_documented_endpoint(self):
        url = build_authorize_url(
            client_id="app-1",
            redirect_uri="https://localhost",
            scope="trading",
        )
        parsed = urllib.parse.urlparse(url)
        query = urllib.parse.parse_qs(parsed.query)
        self.assertTrue(url.startswith(AUTHORIZE_ENDPOINT))
        self.assertEqual(parsed.hostname, "id.ctrader.com")
        self.assertEqual(query["client_id"], ["app-1"])
        self.assertEqual(query["redirect_uri"], ["https://localhost"])
        self.assertEqual(query["scope"], ["trading"])
        self.assertEqual(query["product"], ["web"])
        self.assertNotIn("live.ctraderapi.com", url)
        self.assertNotIn("demo.ctraderapi.com", url)

    def test_redirect_to_live_proxy_refused(self):
        with self.assertRaises(DemoGuardError):
            build_authorize_url(
                client_id="app-1",
                redirect_uri="https://live.ctraderapi.com/cb",
                scope="trading",
            )

    def test_token_requests_stay_on_openapi_host(self):
        auth_code = build_token_request(
            grant_type="authorization_code",
            client_id="app-1",
            client_secret="secret",
            code="one-time-code",
            redirect_uri="https://localhost",
        )
        refresh = build_token_request(
            grant_type="refresh_token",
            client_id="app-1",
            client_secret="secret",
            refresh_token="refresh-1",
        )
        self.assertEqual(auth_code.get_method(), "GET")
        self.assertEqual(refresh.get_method(), "POST")
        for request in (auth_code, refresh):
            parsed = urllib.parse.urlparse(request.full_url)
            self.assertEqual(parsed.hostname, "openapi.ctrader.com")
            self.assertEqual(parsed.path, "/apps/token")
            self.assertTrue(request.full_url.startswith(TOKEN_ENDPOINT + "?"))
            self.assertNotIn("live.ctraderapi.com", request.full_url)
            self.assertNotIn("demo.ctraderapi.com", request.full_url)
        refresh_query = urllib.parse.parse_qs(urllib.parse.urlparse(refresh.full_url).query)
        self.assertEqual(refresh_query["grant_type"], ["refresh_token"])
        self.assertEqual(refresh_query["refresh_token"], ["refresh-1"])

    def test_parse_success_and_error_code(self):
        parsed = parse_token_response(
            json.dumps(
                {
                    "accessToken": "access-1",
                    "tokenType": "bearer",
                    "expiresIn": 2628000,
                    "refreshToken": "refresh-1",
                    "errorCode": None,
                    "description": None,
                }
            ).encode()
        )
        self.assertEqual(parsed["accessToken"], "access-1")
        self.assertEqual(parsed["expiresIn"], 2628000)
        with self.assertRaises(ApiError) as caught:
            parse_token_response(
                json.dumps(
                    {"errorCode": "CH_CLIENT_AUTH_FAILURE", "description": "rejected", "accessToken": "nope"}
                ).encode()
            )
        self.assertEqual(caught.exception.error_code, "CH_CLIENT_AUTH_FAILURE")
        self.assertNotIn("nope", str(caught.exception))

    def test_fetch_refuses_final_url_that_left_the_token_host(self):
        request = build_token_request(
            grant_type="refresh_token",
            client_id="app-1",
            client_secret="secret",
            refresh_token="refresh-1",
        )

        def urlopen(req, timeout=30):
            del req, timeout
            body = json.dumps(
                {"accessToken": "access-1", "refreshToken": "refresh-2", "expiresIn": 1, "tokenType": "bearer"}
            ).encode()
            return FakeResponse(body, "https://live.ctraderapi.com/apps/token")

        with self.assertRaises(DemoGuardError):
            fetch_token(request, urlopen=urlopen)

    def test_redirect_handler_refuses_without_keeping_query(self):
        handler = RefuseRedirectHandler()
        with self.assertRaises(DemoGuardError) as caught:
            handler.redirect_request(
                None,
                None,
                302,
                "Found",
                {},
                "https://live.ctraderapi.com/apps/token?client_secret=super-secret",
            )
        self.assertNotIn("super-secret", str(caught.exception))
        self.assertIn("live.ctraderapi.com", str(caught.exception))

    def test_token_endpoint_constant(self):
        self.assertEqual(TOKEN_ENDPOINT, "https://openapi.ctrader.com/apps/token")
        self.assertIsInstance(urllib.request.Request, type)
