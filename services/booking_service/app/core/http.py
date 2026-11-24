"""What every call to another service shares."""

import httpx

# Building this reads the certificate bundle (about 12 ms of CPU), so it is done once, not per call.
TLS = httpx.create_ssl_context()
