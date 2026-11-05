"""OAuth helpers.

Token exchange uses the fixed Open API token URL. It is not a trading socket
and the URL cannot be overridden. Redirects are refused.
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request

from ctrader_demo.constants import ALLOWED_REDIRECT_URI, AUTHORIZE_ENDPOINT, OPEN_API_APP_NAME, TOKEN_ENDPOINT
from ctrader_demo.errors import ApiError, ConfigError, DemoGuardError
from ctrader_demo.guards import assert_not_forbidden_host


def build_authorize_url(*, client_id: str, redirect_uri: str, scope: str = "trading") -> str:
    if scope not in {"trading", "accounts"}:
        raise ConfigError("scope must be trading or accounts")
    assert_public_redirect(redirect_uri)
    query = urllib.parse.urlencode(
        {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "product": "web",
        }
    )
    return AUTHORIZE_ENDPOINT + "?" + query


def assert_public_redirect(redirect_uri: str) -> str:
    """Only the redirect URI registered for poteto-demo-sltp is accepted."""

    parsed = urllib.parse.urlparse(redirect_uri.strip())
    path = parsed.path or ""
    if path == "/":
        path = ""
    registered = urllib.parse.urlparse(ALLOWED_REDIRECT_URI)
    if (
        parsed.scheme != registered.scheme
        or parsed.hostname != registered.hostname
        or parsed.port is not None
        or path != ""
        or parsed.query
        or parsed.fragment
        or parsed.username
        or parsed.password
    ):
        raise DemoGuardError(
            "DEMO GUARD: CTRADER_REDIRECT_URI must be https://localhost. "
            f"That is the redirect URI registered for Open API app {OPEN_API_APP_NAME}."
        )
    assert_not_forbidden_host(parsed.hostname or "")
    return ALLOWED_REDIRECT_URI


def build_token_request(
    *,
    grant_type: str,
    client_id: str,
    client_secret: str,
    code: str | None = None,
    redirect_uri: str | None = None,
    refresh_token: str | None = None,
) -> urllib.request.Request:
    if urllib.parse.urlparse(TOKEN_ENDPOINT).hostname != "openapi.ctrader.com":
        raise DemoGuardError("DEMO GUARD: token endpoint constant is not openapi.ctrader.com.")
    query: dict[str, str] = {
        "grant_type": grant_type,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    if grant_type == "authorization_code":
        if not code or not redirect_uri:
            raise ConfigError("authorization_code exchange requires code and redirect_uri")
        assert_public_redirect(redirect_uri)
        query["code"] = code
        query["redirect_uri"] = redirect_uri
        method = "GET"
    elif grant_type == "refresh_token":
        if not refresh_token:
            raise ConfigError(
                "refresh_token grant requires CTRADER_REFRESH_TOKEN. "
                f"Open API app {OPEN_API_APP_NAME} is still Submitted, so this token "
                "does not exist until Spotware activates the app and OAuth completes."
            )
        query["refresh_token"] = refresh_token
        method = "POST"
    else:
        raise ConfigError("grant_type must be authorization_code or refresh_token")
    url = TOKEN_ENDPOINT + "?" + urllib.parse.urlencode(query)
    return urllib.request.Request(
        url,
        method=method,
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )


class RefuseRedirectHandler(urllib.request.HTTPRedirectHandler):
    """The token host must stay openapi.ctrader.com."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: A002 - urllib signature
        parts = urllib.parse.urlsplit(newurl)
        clean = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
        raise DemoGuardError(
            f"DEMO GUARD: token endpoint attempted to redirect to {clean!r}. Refusing."
        )


def secure_urlopen(request: urllib.request.Request, timeout: float = 30):
    opener = urllib.request.build_opener(RefuseRedirectHandler)
    return opener.open(request, timeout=timeout)


def parse_token_response(body: bytes) -> dict:
    try:
        data = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ApiError("BAD_JSON", "Token endpoint returned non-JSON.", 0) from exc
    if not isinstance(data, dict):
        raise ApiError("BAD_JSON", "Token endpoint returned a non-object.", 0)
    error_code = data.get("errorCode")
    if error_code:
        raise ApiError(str(error_code), str(data.get("description") or ""), 0)
    access = data.get("accessToken")
    refresh = data.get("refreshToken")
    if not access or not refresh:
        raise ApiError(
            "MISSING_TOKEN",
            "Token response did not include accessToken and refreshToken.",
            0,
        )
    return {
        "accessToken": access,
        "refreshToken": refresh,
        "expiresIn": data.get("expiresIn"),
        "tokenType": data.get("tokenType"),
    }


def fetch_token(request: urllib.request.Request, *, urlopen=secure_urlopen, timeout: float = 30) -> dict:
    parsed = urllib.parse.urlparse(request.full_url)
    if parsed.hostname != "openapi.ctrader.com" or not request.full_url.startswith(TOKEN_ENDPOINT + "?"):
        raise DemoGuardError(
            "DEMO GUARD: refusing token request. Tokens are exchanged only at "
            "https://openapi.ctrader.com/apps/token."
        )
    with urlopen(request, timeout=timeout) as response:
        final = response.geturl() if hasattr(response, "geturl") else request.full_url
        final_host = urllib.parse.urlparse(final).hostname
        if final_host != "openapi.ctrader.com":
            raise DemoGuardError(
                "DEMO GUARD: token response URL was not openapi.ctrader.com. Refusing."
            )
        body = response.read()
    return parse_token_response(body)
