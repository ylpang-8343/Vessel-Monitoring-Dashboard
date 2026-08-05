""""Sign in with Microsoft" via the standard OAuth 2.0 authorization-code flow against the
Microsoft identity platform (Entra ID / "Azure AD").

Deliberately does *not* validate the ID token's JWT signature itself. Instead, after exchanging
the authorization code for an access token, it calls Microsoft Graph's `/v1.0/me` endpoint with
that token - Graph's response *is* the trust boundary here (the same pattern Microsoft's own
"simple web app" quickstarts use), which avoids needing to fetch and cache Microsoft's signing
keys (JWKS) just to verify a token we'd otherwise throw away. See routers/auth.py for how the
three calls below (authorize URL, token exchange, profile fetch) fit into the full login flow.
"""

import httpx

from app.config import settings

# Standard OAuth scopes for "read the signed-in user's basic profile and email" - no access to
# mail, calendar, files, etc. is requested.
SCOPES = "openid profile email User.Read"


def is_configured() -> bool:
    """Whether an admin/deployer has actually registered an Azure app and filled in its
    credentials - see config.py. The frontend hides the "Sign in with Microsoft" button
    entirely when this is false, rather than showing a button that would just 503."""
    return bool(settings.microsoft_client_id and settings.microsoft_client_secret)


def _authority() -> str:
    return f"{settings.microsoft_authority_base_url}/{settings.microsoft_tenant_id}"


def build_authorize_url(state: str) -> str:
    """The URL to send the browser to for the user to sign in/consent at Microsoft. `state` is
    an opaque CSRF token the caller generated - Microsoft echoes it back unchanged on the
    callback, where it's checked against the same value stored in a short-lived cookie."""
    params = httpx.QueryParams(
        {
            "client_id": settings.microsoft_client_id,
            "response_type": "code",
            "redirect_uri": settings.microsoft_redirect_uri,
            "scope": SCOPES,
            "state": state,
            "response_mode": "query",
        }
    )
    return f"{_authority()}/oauth2/v2.0/authorize?{params}"


def exchange_code_for_token(code: str) -> str:
    """Trade the one-time authorization code (from the callback's `code` query param) for an
    access token, via a server-to-server POST - the client secret never touches the browser.
    Returns the access token string; raises httpx.HTTPError on any failure (network, or
    Microsoft rejecting the request), which routers/auth.py catches and turns into a clean
    "sign-in failed" redirect rather than a 500."""
    response = httpx.post(
        f"{_authority()}/oauth2/v2.0/token",
        data={
            "client_id": settings.microsoft_client_id,
            "client_secret": settings.microsoft_client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": settings.microsoft_redirect_uri,
            "scope": SCOPES,
        },
        timeout=10,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def fetch_profile(access_token: str) -> dict:
    """Fetch the signed-in user's profile from Microsoft Graph using the access token just
    obtained. The fields this app actually uses are `mail` (falls back to `userPrincipalName`
    for accounts without a mailbox - e.g. some work/school accounts) and `id` (Microsoft's
    stable per-account identifier, stored as User.microsoft_id)."""
    response = httpx.get(
        f"{settings.microsoft_graph_base_url}/v1.0/me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )
    response.raise_for_status()
    return response.json()
