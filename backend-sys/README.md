# Sahayak Backend Service Documentation

This document provides a comprehensive technical guide and reference for the **Sahayak** microservices backend platform. Sahayak is designed as a high-performance, agentic e-commerce automation platform using a modern, secure, and asynchronous Python architecture.

---

## 1. Architectural Overview

Sahayak is built using a microservices-based architecture structured around high-speed internal gRPC communication and a unified external FastAPI gateway.

```mermaid
graph TD
    Client[Client Browser / Next.js] -->|HTTPS Requests| Gateway[FastAPI API Gateway]
    Gateway -->|Sliding Window Rate Limiting| RedisPool[(Redis Cache & Session)]
    Gateway -->|Async gRPC| AuthService[gRPC Auth Service]
    Gateway -->|Async gRPC| ChatService[gRPC ChatAI Service]
    AuthService -->|SQLAlchemy AsyncPG| DB[(PostgreSQL Database)]
    AuthService -->|Read/Write Session/Auth Cache| RedisPool
    AuthService -->|Celery Tasks| RedisBroker[(Redis Message Broker)]
    CeleryWorker[Celery Mail Worker] -->|Fetch Tasks| RedisBroker
    CeleryWorker -->|SMTP Protocol| MailServer[External SMTP Server]
```

### Components Summary

| Component Name | Technology | Address (Default) | Role / Purpose |
| :--- | :--- | :--- | :--- |
| **API Gateway** | FastAPI | `localhost:8000` | Exposes unified REST endpoints, enforces CORS, validates client headers, manages rate-limiting, and translates requests into gRPC stubs. |
| **Auth Service** | gRPC (Async) | `localhost:50051` | Manages registration, logins, token issuance/refresh, brute-force lockouts, and database audit logs. |
| **ChatAI Service** | gRPC (Async) | `localhost:50052` | Stubs AI prompt parsing and hooks up database storage for conversation logs. |
| **Mail Worker** | Celery / `smtplib` | Distributed | Executes background asynchronous operations such as sending verification e-mails. |
| **Cache & Sessions** | Redis | `localhost:6379/0` | Key-value store facilitating rate limits, cache-aside identity checks, and short-term verification tokens. |
| **Relational Database** | PostgreSQL | `localhost:5432` | Stores schemas for users, organizations, orders, products, and system configurations. |

---

## 2. API Gateway (`services/api_gateway`)

The FastAPI API Gateway acts as the gateway entry-point. It maintains persistent async gRPC channels connecting to internal services.

### Core Modules

* **`main.py`**:
  * Initializes the `FastAPI` instance.
  * Employs an `asynccontextmanager` (`lifespan`) to handle startup and shutdown routines for async gRPC channels (`insecure_channel`).
  * Attaches gRPC stubs directly to the FastAPI `app.state` to enable fast path routing.
  * Adds CORS middleware supporting local and wildcard hosts.
  * Incorporates global sliding-window rate-limiting.
* **Rate Limiting Middleware (`middlewares/rate_limiter.py`)**:
  * Implements `SlidingWindowRateLimiter` inheriting from `BaseHTTPMiddleware`.
  * Protects `/auth`, `/chat`, and `/health` paths while excluding performance-critical endpoints like `/auth/me`.
  * **Mechanism**:
    1. Divides time into segments of `window_size` (60 seconds).
    2. Performs atomic updates inside a Redis pipeline (`transaction=True`) fetching count variables for both current and preceding time windows:
       `rate_limit:{client_ip}:{current_window_start}`
       `rate_limit:{client_ip}:{prev_window_start}`
    3. Calculates a weighted request count using the current time offset:
       $$\text{Weighted Count} = \text{Prev Count} \times \left(1 - \frac{\text{Time elapsed in current window}}{\text{Window Size}}\right) + \text{Current Count}$$
    4. If the weighted count exceeds the limits (default: 10 requests per minute), returns a `429 Too Many Requests` JSON response.
    5. Otherwise, increments the count and sets a Time-To-Live (TTL) equivalent to $2 \times \text{window\_size}$.

### Routing Map (`services/api_gateway/routers/auth_routers`)

Each router converts incoming client payloads (schemas modeled via `pydantic`) into protobuf request structures, invokes internal gRPC stubs, handles errors, and returns JSON responses.

* **`/auth/register`** (`registration.py`):
  * **Payload**: `org_name`, `org_slug`, `user_full_name`, `user_email`, `user_password`.
  * **Action**: Invokes `AuthService.Register` gRPC handler. On success, responds with created IDs.
* **`/auth/verify/{token}`** (`verification.py`):
  * **Action**: Invokes `AuthService.VerifyEmail` with token string. Returns verification outcome.
* **`/auth/login`** (`login.py`):
  * **Payload**: `email`, `password`.
  * **Action**: Invokes `AuthService.Login`.
  * **Security Handling**: Parses source client IP (`request.client.host`) and `user-agent` to pass to the authentication service.
  * **Session Initialization**: On successful authentication, sets two secure, client-side HTTP-Only cookies:
    * `access_token` (Expiry: 1 hour, `httponly=True`, `samesite="lax"`, `path="/"`)
    * `refresh_token` (Expiry: 30 days, `httponly=True`, `samesite="lax"`, `path="/"`)
* **`/auth/me`** (`me.py`):
  * **Action**: Extracts `access_token` from incoming cookies. Calls `AuthService.VerifyAccessToken` to retrieve current session parameters (User ID, full name, role, organization details).
* **`/auth/refresh`** (`refresh.py`):
  * **Action**: Retrieves `refresh_token` from cookies. Invokes `AuthService.RefreshToken` to execute single-use refresh token rotation. Updates cookies with a new set of access/refresh tokens.
* **`/auth/logout`** (`logout.py`):
  * **Action**: Extracts cookies, triggers `AuthService.Logout` to invalidate databases/caches, and deletes the `access_token` and `refresh_token` cookies by setting their values to empty strings with an expiration of zero.

---

## 3. Auth Service (`services/auth_service`)

The Authentication Service handles cryptographic functions, token verification, brute-force protections, caching, and audit logging.

### Internal Security Operations

1. **Password Encryption**:
   * Utilizes `passlib` with `bcrypt` algorithms to compute secure salt hashes (`hash_password`) and verify inputs (`verify_password`).
2. **Brute-Force Account Locking**:
   * Tracks failed login attempts in the database.
   * If a user fails to authenticate $5$ consecutive times, sets a database field `locked_until` to current time + 15 minutes.
   * Fast-lock check is performed inside the login route, preventing database password verification from firing if the lockout timestamp has not expired.
3. **Session Caching (Cache-Aside pattern)**:
   * During token validation, looks up the session in Redis under the key `user_session:{user_id}`.
   * If missing (cache miss), queries the PostgreSQL database via SQLAlchemy, validates user statuses (`is_active` and `is_verified`), and caches the parsed session schema back into Redis with an expiration offset equivalent to token validity.
4. **Single-Use Refresh Token Rotation**:
   * Refresh tokens are cryptographically generated and their hashes are recorded in the database `refresh_tokens` table.
   * When `/auth/refresh` is triggered, the submitted refresh token is decoded.
   * The database is queried for a record matching the `user_id` and the `token_hash`.
   * **Replay Attack Protection**: If a client attempts to submit a refresh token that has already been rotated (or flagged as revoked), the system immediately invokes `force_user_logout(user_id)`—clearing the session cache in Redis and deleting all refresh tokens associated with that user from PostgreSQL, forcing a full re-authentication flow.
   * On normal validation, a new access token is generated, a new refresh token is issued, and the database record is updated (rotated) to reference the new token hash.
5. **Auditing**:
   * Login successes, failures, lockout occurrences, email verifications, and token rotations are written asynchronously to the database.
   * These write operations are decoupled from client threads using `asyncio.create_task(log_audit_event(...))`.

---

## 4. Shared Modules (`shared/`)

Shared packages establish connection states, configuration defaults, compilation wrappers, and schemas across services.

### Configuration (`config.py`)

Employs `starlette.config.Config` to load parameters from a unified root `.env` file with sensible fallbacks:

```python
DATABASE_URL = config("DATABASE_URL", default="postgresql+asyncpg://user:pass@localhost:5432/dbname")
AUTH_SERVICE_ADDR = config("AUTH_SERVICE_ADDR", default="localhost:50051")
CHATAI_SERVICE_ADDR = config("CHATAI_SERVICE_ADDR", default="localhost:50052")
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")
JWT_SECRET = config("JWT_SECRET", default="your-secret-key")
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 30
```

### Relational Schema (`shared/database/schema`)

The project uses SQLAlchemy 2.0 with static type-mapping (`Mapped`, `mapped_column`) to manage relational configurations:

```mermaid
erDiagram
    organizations ||--o| users : "owner / member"
    organizations ||--o| refresh_tokens : "has"
    organizations ||--o| organization_config_ai : "has"
    organizations ||--o| teams : "has"
    organizations ||--o| products : "has"
    organizations ||--o| orders : "has"
    organizations ||--o| platform_connectors : "has"
    
    users ||--o| refresh_tokens : "holds"
    users ||--o| team_members : "belongs"
    users ||--o| orders : "assigned_to"
    users ||--o| audit_logs : "creates"
    
    teams ||--o| team_members : "groups"
    orders ||--|{ order_items : "contains"
    products ||--o| order_items : "referenced_in"
```

#### Class Definitions

* **`Organization`** (`organizations.py`):
  * **Fields**: `id` (UUID), `name`, `slug` (unique), `plan` (Enum: `FREE`, `PREMIUM`), `is_active` (Boolean), `owner_id` (ForeignKey to `users.id`, nullable).
* **`User`** (`users.py`):
  * **Fields**: `id` (UUID), `organization_id` (ForeignKey to `organizations.id`), `is_verified` (Boolean), `email` (unique index), `password_hash`, `full_name`, `role` (Enum: `OWNER`, `ADMIN`, `AGENT`), `is_active` (Boolean), `last_login_at`, `failed_login_attempts`, `locked_until`.
* **`RefreshToken`** (`refresh_tokens.py`):
  * **Composite Primary Key**: `user_id` (unique index), `organization_id`.
  * **Fields**: `token_hash`, `expire_at`, `revoked` (Boolean).
* **`AuditLog`** (`audit_logs.py`):
  * **Fields**: `id` (UUID), `user_id`, `organization_id`, `event_type` (Enum: `LOGIN_SUCCESS`, `LOGIN_FAILED`, `ACCOUNT_LOCKED`, `TOKEN_REFRESH`, `PASSWORD_CHANGE`, `EMAIL_VERIFICATION`), `ip_address`, `user_agent`, `details` (JSONB).
* **`Team` & `TeamMember`** (`teams.py`):
  * Teams group agents inside an organization. `TeamMember` maps relationships with roles.
* **`Product`** (`products.py`):
  * E-commerce item schemas including `price` (stored as integer representing subunit cents), `currency` (default: "NPR"), `stock`, `sku`, and `metadata_json`.
* **`Order` & `OrderItem`** (`orders.py`):
  * Tracks user sales. Fields include `platform` (Enum: `INSTAGRAM`, `TIKTOK`, `FACEBOOK_MESSENGER`, `CHATBOX`), `delivery_address`, `status` (Enum: `PENDING`, `DISPATCH`, `DELIVERED`), and price sub-totals.
* **`PlatformConnector`** (`platform_connectors.py`):
  * Manages credentials linking external channels (Tiktok API, Instagram OAuth) to the organization system.
* **`OrganizationConfigAI`** (`organization_config_ai.py`):
  * Configuration variables governing agent actions, detailing custom `system_prompt` configurations and `auto_order_enabled` settings.

---

## 5. gRPC Protobuf Contracts (`shared/proto/service.proto`)

Internal operations are declared in `service.proto`.

### AuthService Interface

* `Register(RegisterRequest) returns (RegisterResponse)`
* `VerifyEmail(VerifyEmailRequest) returns (VerifyEmailResponse)`
* `Login(LoginRequest) returns (LoginResponse)`
* `VerifyAccessToken(VerifyAccessTokenRequest) returns (VerifyAccessTokenResponse)`
* `RefreshToken(RefreshTokenRequest) returns (RefreshTokenResponse)`
* `Logout(LogoutRequest) returns (LogoutResponse)`

### ChatService Interface

* `GetAIResponse(ChatRequest) returns (ChatResponse)`

---

## 6. Celery Background Workers (`services/workers`)

Asynchronous background operations leverage a Celery app configuration.

### Worker Execution Structure

* **Celery Instance (`shared/celery_app.py`)**:
  * Configured using Redis as the message broker (`REDIS_URL`).
  * Runs single-threaded on Windows environments under development using `--pool=solo`.
* **Mail Task (`services/workers/mail_service.py`)**:
  * `send_verification_email(email, subject, html_content)`:
    * Dispatched from the registration service thread with `.delay()`.
    * Utilizes `smtplib` to authenticate against SMTP endpoints defined in configurations.
    * Initiates secure communication protocols via `.starttls()`, logs credentials, and fires emails containing dynamic verification tokens formatted within templates (`services/auth_service/templates/verification_email.html`).
