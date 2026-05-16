# Sahayak Monorepo

Sahayak is a high-performance, agentic e-commerce automation platform built with a microservices architecture. It leverages gRPC for high-speed internal communication and FastAPI for a modern, secure API Gateway.

## 🚀 Tech Stack
- **Core**: Python (managed by `uv`)
- **API Gateway**: FastAPI
- **Internal Services**: gRPC (Async)
- **Database**: PostgreSQL with SQLAlchemy (Async)
- **Caching & Sessions**: Redis
- **Background Tasks**: Celery with Redis broker
- **Migrations**: Alembic

## 🛡️ Security Features
- **Secure Sessions**: Cookie-based authentication using `HttpOnly`, `SameSite=Lax` cookies.
- **Refresh Token Rotation**: Automatic issuance of single-use refresh tokens on every renewal to prevent replay attacks.
- **Account Locking**: Brute-force protection that temporarily locks accounts (15 mins) after 5 failed attempts.
- **Audit Logging**: Comprehensive security logs tracking successful/failed logins, lockouts, and refreshes, including **IP Address** and **User-Agent** tracking.
- **Cache-Aside Sessions**: High-frequency session verification via Redis with automatic database fallback.

## 🏗️ Project Structure
```text
my-monorepo/
├── services/
│   ├── api_gateway/      # Entry point, route handling, rate limiting
│   ├── auth_service/     # Identity management, JWT, Auditing, DB logic
│   └── ...               # Future services (ChatAI, etc.)
├── shared/
│   ├── database/         # SQLAlchemy schemas and engine configuration
│   ├── proto/            # gRPC service definitions (.proto files)
│   ├── mail_service/     # Shared email tasks
│   └── config.py         # Centralized environment configuration
└── migrations/           # Alembic migration history
```

## 🛠️ Setup & Installation

### 1. Prerequisites
Ensure you have `uv` installed:
```powershell
pip install uv
```

### 2. Environment Configuration
Create a `.env` file in the root directory:
```env
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/sahayak
REDIS_URL=redis://localhost:6379/0
JWT_SECRET=your_super_secret_key
FRONTEND_URL=http://localhost:3000
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
```

### 3. Database Migrations
To bring your database schema up to date using Alembic:
```powershell
# Set PYTHONPATH so Alembic can find the shared modules
$env:PYTHONPATH="."

# Apply migrations
uv run alembic upgrade head
```

## 🏃 Running the Services

Open 3 separate terminals in the project root:

### Terminal 1: Auth Service (gRPC)
```powershell
uv run -m services.auth_service.main
```

### Terminal 2: API Gateway (FastAPI)
```powershell
uv run -m services.api_gateway.main
```

### Terminal 3: Celery Worker
```powershell
uv run python -m celery -A shared.celery_app worker --loglevel=info --pool=solo

```

## 🧪 Testing Scenarios
- **Login**: `POST /auth/login` (Returns secure cookies).
- **Session Info**: `GET /auth/me` (Uses cookies to verify session).
- **Token Refresh**: `POST /auth/refresh_token` (Rotates your session tokens).
- **Audit Logs**: Check the `audit_logs` table in your DB to see your IP and browser metadata in action.
