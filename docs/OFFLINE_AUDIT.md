# Offline Runtime Audit

The application runtime is local after dependencies and model files are installed. Vite proxies API traffic to the local FastAPI service. Fonts are packaged in npm dependencies; the Digital Twin uses generated geometry and local Three.js assets. ML inference loads a local joblib artifact. No hosted inference, AI API key, map tile provider, CDN script or analytics service is part of the documented runtime path.

The supported launcher binds Uvicorn, Vite and the production preview to `127.0.0.1`. FastAPI CORS is limited to the local development and preview origins configured in `backend/app/config.py`. There is no authentication layer; do not change the host binding to a public interface for a hackathon demo.

First-time `pip install` and `npm ci` need package registry access. A browser may independently contact its configured search, update or safe-browsing services; the app does not require those services for its own runtime. The local preflight and acceptance probes use loopback only. The acceptance report identifies itself as in-process `TestClient` execution and does not demonstrate browser network isolation.

The source audit for Part 10 searched app source, HTML and build configuration for external scripts, remote fonts, map tile URLs and analytics hooks. Repository documentation and local API URLs also contain `https://` strings, so matches were inspected by context instead of treating every URL as a runtime dependency. No system firewall or network configuration was changed.

Limits: no host-level packet capture or offline browser session was available for this verification. Therefore, the claim is **offline-capable local runtime after setup**, not a packet-level proof that every host browser installation makes zero background requests.
