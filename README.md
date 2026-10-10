## ONEID account linking

An existing FAKEPRESS user can sign in locally, then open the login screen's ONEID section and authenticate their ONEID account to link the two identities. The ONEID nickname becomes the FAKEPRESS nickname when it is available. The site stores the ONEID user ID in `oneid_links`; it never stores the ONEID password or access token.

FAKEPRESS now sends sign-in to the ONEID login page. Existing users connect their old FAKEPRESS nickname and password once after ONEID login, preserving their articles; new users can create a FAKEPRESS profile from their ONEID account.

For local integration, serve the frontend at `http://localhost:5500/`, run the FAKEPRESS API on port 8002, and point `api-config.js` at `http://127.0.0.1:8002`. Set backend `ONEID_API_URL` and frontend `oneid-config.js` to the ONEID API on port 8000. Production URLs must use HTTPS. Add the deployed FAKEPRESS frontend origin and callback URL to ONEID's `ONEID_ALLOWED_ORIGINS` and `ONEID_CLIENT_REDIRECT_URIS`. Linked-account admin routes verify the ONEID bearer token live; the admin page receives it from the site's SSO session.

Run the API from `backend` with `python -m uvicorn main:app --reload --port 8002`.
