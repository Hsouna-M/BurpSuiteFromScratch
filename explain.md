# Project Codebase Explanation

This document explains the structure and functionality of the MITM (Man-In-The-Middle) Proxy project. It provides a breakdown of each file, the classes it contains, and its role in the system.

## Architectural Overview

The project is built as a modular MITM proxy with the following components:
1.  **Proxy Server**: Intercepts HTTP/HTTPS traffic between the client (browser) and the internet.
2.  **Redis Storage**: Acts as a centralized data store and message broker between the Proxy Server and the GUI.
3.  **Proxy API**: A Flask-based REST API that exposes the data in Redis to the frontend.
4.  **GUI**: A Flask web application that provides the user interface for inspecting and controlling traffic.
5.  **Certificate Authority**: Manages dynamic SSL certificate generation to enable HTTPS interception.

## File Breakdown

### 1. `proxyserver.py`
**Description**: This is the core engine of the project. It runs the TCP server that listens for incoming connections from the browser. It handles SSL/TLS termination, request interception, and forwarding.

**Classes**:
*   `MITMProxyServer`: The main server class.
    *   `__init__`: Initializes the server, Redis connection, and CA.
    *   `start`: Binds to the socket and listens for connections. Starts the API server in a separate thread.
    *   `_handle_client`: entry point for a new connection. Distinguishes between HTTP and HTTPS (CONNECT) requests.
    *   `_handle_connect_request`: Handles the HTTPS handshake (CONNECT method). It generates a fake certificate for the target domain, establishes an SSL tunnel with the client, and then reads the encrypted request.
    *   `_read_and_store_request`: Reads the actual request inside the SSL tunnel, saves it to Redis, and waits for a decision (Allow/Block) from the user (via Redis status). If in Filter Mode, checks configuration first.
    *   `_handle_http_request`: Handles plain HTTP requests. Similar interception logic to HTTPS but without SSL wrapping.

**Key Functionalities**:
*   **TCP Listener**: Accepts browser connections.
*   **SSL Man-in-the-Middle**: Dynamically generates certificates to decrypt HTTPS traffic.
*   **Interception Loop**: Pauses execution while waiting for the user to Allow/Block a request in the GUI.
*   **Filter Mode Logic**: Automatically checks blocked domains/keywords to bypass manual review.

### 2. `redis_storage.py`
**Description**: Handles all interactions with the Redis database. Redis is used to store intercepted requests, responses, and configuration settings.

**Classes**:
*   `RedisStorage`: Wrapper class for `redis-py`.
    *   `save_request`: Stores a parsed request (headers, body, method, etc.) in a Redis Hash and adds its ID to a list of pending requests.
    *   `get_request` / `get_response`: Retrieves data for a specific ID.
    *   `update_request_status` / `update_response_status`: Updates the state (pending -> allowed/blocked).
    *   `set_proxy_mode` / `get_proxy_mode`: Stores the current operating mode (Intercept vs Filter).
    *   `add_blocked_domain` / `get_blocked_domains`: Manages the blocklist for domains.
    *   `add_blocked_keyword` / `get_blocked_keywords`: Manages the blocklist for keywords.

**Key Functionalities**:
*   **Persistence**: Keeps track of requests even if the server restarts (until expiration).
*   **State Management**: Acts as the "shared memory" for the Proxy Server and GUI to communicate asynchronously.

### 3. `proxy_api.py`
**Description**: A backend API built with Flask. It serves as the bridge between the Redis storage and the Frontend (GUI). The GUI makes HTTP calls to this API to get data or change settings.

**Classes**:
*   `ProxyAPI`: The Flask application class.
    *   `_setup_routes`: Defines the URL endpoints.
        *   `GET /api/requests`: List all pending requests.
        *   `GET /api/requests/<id>`: Get details of a request.
        *   `POST /api/requests/<id>/allow`: User allowed the request.
        *   `POST /api/requests/<id>/block`: User blocked the request.
        *   `GET/POST /api/config/mode`: Get or set the proxy mode.
        *   `GET/POST/DELETE /api/config/domains`: Manage blocked domains.
        *   `GET/POST/DELETE /api/config/keywords`: Manage blocked keywords.

**Key Functionalities**:
*   **REST Interface**: JSON-based API for all proxy operations.
*   **Decoupling**: Separates the database logic from the frontend presentation.

### 4. `gui.py`
**Description**: The user-facing web application server (also Flask). It serves the HTML/JS frontend and proxies API requests to the `ProxyAPI`.

**Classes**:
*   `ProxyGUI`: The Flask web server.
    *   `index`: Serves `index.html`.
    *   `get_requests`...: Pass-through routes that forward calls from the browser to the `ProxyAPI`.

**Key Functionalities**:
*   **Web Server**: Hosts the frontend assets.
*   **API Gateway**: Forwards frontend requests to the backend API (often running on a different port).

### 5. `request_interceptor.py`
**Description**: A utility module for parsing raw HTTP data strings into structured Python dictionaries.

**Classes**:
*   `RequestInterceptor`:
    *   `parse_request`: Takes a raw HTTP string (e.g., "GET / HTTP/1.1...") and splits it into Method, Path, Headers, and Body.
    *   `extract_hostname`: Extracts the target hostname from a CONNECT request line.

**Key Functionalities**:
*   **HTTP Parsing**: logic to decode raw bytes from the socket into usable data.

### 6. `certificate_authority.py`
**Description**: Manages valid SSL generation. It holds the root CA certificate and uses it to sign fake certificates for every website the user visits.

**Classes**:
*   `CertificateAuthority`:
    *   `generate_ca_certificate`: Creates a root CA certificate if one doesn't exist.
    *   `generate_certificate`: Generates a leaf certificate for a specific hostname (e.g., google.com) and signs it with the root CA.

**Key Functionalities**:
*   **PKI Management**: Handles cryptographic operations for SSL spoofing.

### 7. `templates/index.html`
**Description**: The single-page application (SPA) frontend. It contains the HTML structure, CSS styling, and JavaScript logic for the user interface.

**Key Functionalities**:
*   **Request Inspector**: Shows a list of intercepted requests.
*   **Details View**: Shows headers and body of the selected request/response.
*   **Editor**: Allows editing the JSON headers or raw body text.
*   **Control Panel**: Buttons to Forward or Drop requests.
*   **Mode Toggle**: Switches between Intercept Logic and Filter Logic.
*   **Filter Config**: Forms to add/remove blocked domains and keywords.
*   **Polling**: JavaScript automatically polls the API to update the request list.

### 8. `config.py`
**Description**: Contains constant variables and configuration settings used across the project (ports, hosts, file paths).

**Key Functionalities**:
*   **Centralized Configuration**: easy place to change ports or timeout settings.
