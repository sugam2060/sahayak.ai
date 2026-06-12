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
    Gateway -->|Publish Inbound Event| Kafka[Kafka Message Broker]
    Kafka -->|Consume Inbound Event| ChatService[ChatAI Service]
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
| **ChatAI Service** | Kafka Consumer Worker | Distributed | Consumes incoming platform events, handles conversation states, executes agentic reasoning via LangGraph, and maps DB actions. |
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

---

## 7. ChatAI Service & AI Agent Architecture (`services/chatai-service`)

The ChatAI Service runs an agentic workflow using **LangGraph** to automate support interactions on connected platforms (Telegram, Instagram) with human fallback controls.

### 7.1 State Graph Workflow (`ai/graph.py`)

The conversational logic is implemented as a StateGraph containing state transitions:

```mermaid
graph TD
    START --> Chat[chat Node]
    Chat -->|Conditional Edge: _should_continue| ToolDecision{Tool requested?}
    
    ToolDecision -->|Standard Tool Calls| ToolsNode[tools Node]
    ToolsNode --> Chat
    
    ToolDecision -->|generate_product_card| ProductCardNode[generate_product_card Node]
    ProductCardNode --> END
    
    ToolDecision -->|No Tool Calls| SynthNode[synthesizer Node]
    SynthNode --> END
```

#### Node Definitions:
* **`chat` Node**: Formulates the prompt and invokes the LLM. It dynamically rebuilds the system message on every execution turn to include active CRM context, system rules, and summaries.
* **Conditional Edge (`_should_continue`)**: Inspects the LLM's response. If the LLM generates a tool call, the edge routes the execution. If it requests `generate_product_card`, it routes to the specialized product rendering node. If it requests any other tool, it routes to `tools`. Otherwise, it proceeds to the `synthesizer` to conclude.
* **`tools` Node**: Invokes standard tool functions (RAG search, ticketing, order operations) and routes execution back to the `chat` node to evaluate the outcomes.
* **`generate_product_card` Node**: Pulls catalog metadata via the `Workers` gRPC client, parses the item details (including its secure encryption `share_url`), appends a structured card data payload to the state graph, and completes.
* **`synthesizer` Node**: Performs final string cleansing. It strips out markdown styles (such as bolding or header symbols) from the response text, ensuring compatibility with plain-text messaging platforms (Telegram/Instagram).

### 7.2 Conversation State & Memory Checkpointing (`ai/state.py` / `ai/agent.py`)

The conversation state is represented by `AgentState`, which records chat parameters:
* `messages`: Chronological list of message objects.
* `organization_id` & `organization_name`: Active tenant details.
* `platform`: Client messenger channel (`telegram`, `instagram`).
* `sender_id` & `chat_id`: External messaging identifiers.
* `bot_name` & `bot_token`: API metadata of the responding bot.
* `system_prompt` & `auto_order_enabled`: Active rules configured by the organization admin.
* `customer_name`: Target customer's display name.
* `image_urls` & `products`: Accumulators tracking assets returned to the customer.

#### State Storage:
* State graphs are compiled using **`MongoDBSaver`** checkpointing.
* The conversation thread is keyed using a dynamic `thread_id` formatted as: `[platform]+[chat_id]+[sender_id]`.

### 7.3 Hybrid Context Synchronization (Human-AI Merge)

To allow seamless transitions between AI automation and manual human intervention in the web dashboard, the agent implements a synchronization process:

```
                  MongoDB Message Log (Unified System of Record)
             +-------------------------------------------------------+
             | Msg 1 (Inbound) | Msg 2 (Outbound) | Msg 3 (Human DM) |
             +-----------------+------------------+------------------+
                                        |                   |
   Checkpointer State Graph             v Alignment         v Sync Range
+----------------------------+   +-----------------------------------+
| Msg 1 (Inbound)            |   | Extract and convert newer messages|
| Msg 2 (Outbound) [Aligned] | =>| and inject them into LangGraph    |
+----------------------------+   | before LLM execution              |
                                 +-----------------------------------+
```

1. **Query Unified Log**: `run_agent` queries the conversation's MongoDB document, which acts as the unified system of record, logging *all* incoming/outgoing messages (including manual replies sent by human agents from the dashboard inbox).
2. **Find Alignment Index**: It checks the checkpointer's message history and finds the last message that matches the MongoDB history (aligning by direction and text contents).
3. **Synchronize Newer Messages**: If a human agent intervened and sent messages manually, the checkpointer state would be out of sync. The merger detects this gap and appends all subsequent messages from MongoDB (converting them to `HumanMessage` or `AIMessage` wrappers) directly into the LangGraph state.
4. **Resubmit to LLM**: The state is updated with the full unified context before the LLM runs. This guarantees that the AI agent is fully aware of manual human replies and user responses.

### 7.4 Dynamic Prompt & CRM Assembly (`ai/memory.py`)

The `build_system_message` function dynamically generates the LLM's system instructions:
* **Instructions & Guidelines**: Inject the organization's custom system prompt and standard operational rules (truth enforcement, stock query requirements, visual card rules, plain-text limits, prompt injection guardrails).
* **CRM Details**: Queries the PostgreSQL `customers` table using the sender ID and platform. If a profile is found with `phone` or `delivery_address` on file, these details are dynamically injected into the system prompt. The LLM is instructed to use these details directly to place orders, bypassing redundant questions.
* **Context Summaries**: Merges the current message history with a running `previous_summary` (generated when history tokens exceed limits) to maintain context without overloading the LLM's token window.

### 7.5 RAG Search Pipeline (`ai/tools/rag/`)

Sahayak implements RAG using a vector database setup:
* **Vector Database**: **Pinecone** index (`PINECONE_API_KEY`, `PINECONE_INDEX_HOST`).
* **Embeddings**: Uses Pinecone's built-in inference embedding model **`multilingual-e5-large`**.
* **Chunking (`rag_indexer.py`)**: Split text documents into 500-character chunks with a 50-character overlap. Splits are prioritized on sentence boundaries. Deterministic chunk IDs are computed using MD5: `MD5(org_id + ":chunk:" + index)`.
* **Data Isolation**: Chunks are upserted into organizational namespaces (`namespace=organization_id`). Vector searches are executed against the specific organization's namespace with metadata filters (`organization_id == target_org_id`), providing strict data isolation between tenants.

### 7.6 Custom Tools Ecosystem (`ai/tools/`)

The agent has access to tools executing backend logic:
* **Catalog Exploration**:
  * `search_products(query)`: Queries PostgreSQL for products matching keyword/semantic constraints.
  * `check_stock(product_id)`: Verifies product inventory.
  * `generate_product_card(product_ids)`: Triggers detail generation (incorporating title, price, and secure `share_url`).
* **E-Commerce Transactions**:
  * `place_order(product_id, quantity, customer_phone, delivery_address)`: Creates orders in PostgreSQL via workers.
  * `get_order_details(order_id)`: Checks order status and details.
  * `initiate_refund(order_id, reason)`: Initiates return workflows.
* **Support Escalation**:
  * `create_support_ticket(title, description, priority)`: Creates support tickets.
  * `handoff_to_human(reason)`: Disables AI assignment (`ai_assigned = False` in MongoDB) and routes the thread back to the human agent inbox.
