# Instagram Business Login API — Complete Implementation Guide
### Multi-Tenant SaaS Omnichannel Platform

> **Architecture constraint applied:** One organization ↔ one Instagram account (1:1 mapping).  
> **API variant used throughout:** Instagram API with Instagram Login (Business Login for Instagram) — users authenticate with Instagram credentials, no Facebook Page required.

---

## Table of Contents

1. [Authentication & Authorization](#1-authentication--authorization)
2. [Multi-Tenant Connector Architecture](#2-multi-tenant-connector-architecture)
3. [Webhook Subscription Management](#3-webhook-subscription-management)
4. [Multi-Tenant Webhook Processing](#4-multi-tenant-webhook-processing)
5. [Instagram Messaging Integration](#5-instagram-messaging-integration)
6. [Scalable System Design](#6-scalable-system-design)
7. [Data Model Recommendations](#7-data-model-recommendations)
8. [End-to-End Flow Diagrams](#8-end-to-end-flow-diagrams)
9. [Common Pitfalls & Platform Limitations](#9-common-pitfalls--platform-limitations)

---

## 1. Authentication & Authorization

### 1.1 API Variant Selection

Use **Instagram API with Instagram Login** (Business Login for Instagram).

| Property | Value |
|----------|-------|
| Token type | Instagram User access token |
| Base URL | `graph.instagram.com` |
| Auth endpoint | `www.instagram.com/oauth/authorize` |
| Facebook Page required | ❌ No |
| Permissions namespace | `instagram_business_*` |

### 1.2 Required Scopes

For the messaging use-case you need:

```
instagram_business_basic
instagram_business_manage_messages
```

For a full omnichannel workspace (comments + publishing), also request:

```
instagram_business_manage_comments
instagram_business_content_publish
```

> ⚠️ **Old scope names deprecated January 27, 2025.** Always use the `instagram_business_*` names above. The old `business_manage_messages` etc. will stop working.

### 1.3 Complete OAuth Flow

```
Step 1 → User clicks "Connect Instagram" in your platform
Step 2 → Your backend generates an Authorization URL with state param
Step 3 → User authenticates on instagram.com and grants permissions
Step 4 → Instagram redirects to your redirect_uri with ?code=...
Step 5 → Your backend exchanges the code for a short-lived token (1 hr)
Step 6 → Immediately exchange for a long-lived token (60 days)
Step 7 → Store encrypted token, trigger webhook subscription
```

### 1.4 Authorization URL Structure

```
https://www.instagram.com/oauth/authorize
  ?client_id=<INSTAGRAM_APP_ID>
  &redirect_uri=https://app.yourplatform.com/oauth/instagram/callback
  &response_type=code
  &scope=instagram_business_basic,instagram_business_manage_messages
  &state=<CSRF_STATE_TOKEN>
```

**Query Parameters:**

| Parameter | Required | Notes |
|-----------|----------|-------|
| `client_id` | ✅ | Instagram App ID from App Dashboard (different from Meta App ID) |
| `redirect_uri` | ✅ | Must exactly match a registered OAuth redirect URI |
| `response_type` | ✅ | Always `code` |
| `scope` | ✅ | Comma-separated list of `instagram_business_*` scopes |
| `state` | Recommended | Opaque CSRF-protection value; bind to session |
| `force_reauth` | Optional | `true` forces credential re-entry |
| `enable_fb_login` | Optional | `false` hides the Facebook Login option |

**State token best practice:** Encode `{ orgId, userId, nonce }` as a signed JWT and validate it on callback. This prevents CSRF and carries the tenant context into the callback without a database round-trip.

### 1.5 Step 1: Get Authorization Code

```typescript
// services/oauth/instagram.ts
import { SignJWT } from 'jose';

export async function buildAuthorizationUrl(orgId: string, userId: string): Promise<string> {
  const state = await new SignJWT({ orgId, userId, nonce: crypto.randomUUID() })
    .setProtectedHeader({ alg: 'HS256' })
    .setExpirationTime('15m')
    .sign(new TextEncoder().encode(process.env.OAUTH_STATE_SECRET!));

  const params = new URLSearchParams({
    client_id: process.env.INSTAGRAM_APP_ID!,
    redirect_uri: process.env.INSTAGRAM_REDIRECT_URI!,
    response_type: 'code',
    scope: 'instagram_business_basic,instagram_business_manage_messages',
    state,
  });

  return `https://www.instagram.com/oauth/authorize?${params}`;
}
```

On callback, Instagram appends `?code=<AUTH_CODE>#_` — strip the `#_` suffix before using the code.

**Authorization code is valid for 1 hour and single-use.**

### 1.6 Step 2: Exchange Code for Short-Lived Token

```
POST https://api.instagram.com/oauth/access_token
Content-Type: multipart/form-data

client_id=<INSTAGRAM_APP_ID>
client_secret=<INSTAGRAM_APP_SECRET>
grant_type=authorization_code
redirect_uri=<YOUR_REDIRECT_URI>
code=<AUTH_CODE>
```

**Response:**
```json
{
  "data": [{
    "access_token": "EAACEdEose0...",
    "user_id": "1020...",
    "permissions": "instagram_business_basic,instagram_business_manage_messages"
  }]
}
```

- `user_id` is the **Instagram App-scoped User ID** — this is NOT the Instagram account ID (`IG_ID`). You will resolve the actual `IG_ID` in the next step.

### 1.7 Step 3: Exchange for Long-Lived Token

**Must be done server-side** — never expose `client_secret` to the browser.

```
GET https://graph.instagram.com/access_token
  ?grant_type=ig_exchange_token
  &client_secret=<INSTAGRAM_APP_SECRET>
  &access_token=<SHORT_LIVED_TOKEN>
```

**Response:**
```json
{
  "access_token": "EAACEdEose0...",
  "token_type": "bearer",
  "expires_in": 5183944
}
```

`expires_in` is seconds (~60 days).

### 1.8 Step 4: Resolve the Instagram Account ID (IG_ID)

After getting the long-lived token, fetch the actual Instagram professional account ID:

```
GET https://graph.instagram.com/v25.0/me
  ?fields=user_id,username,account_type,profile_picture_url
  &access_token=<LONG_LIVED_TOKEN>
```

**Response:**
```json
{
  "data": [{
    "user_id": "17841400008460056",
    "username": "yourbusiness",
    "account_type": "Business"
  }]
}
```

The `user_id` from this call is the **IG_ID** — used for:
- All API calls: `/<IG_ID>/messages`
- Webhook routing: `recipient.id` in webhook payloads equals this value

### 1.9 Token Lifecycle & Refresh

| Token | Valid For | Refresh |
|-------|-----------|---------|
| Authorization code | 1 hour, single-use | N/A |
| Short-lived access token | 1 hour | Exchange for long-lived |
| Long-lived access token | 60 days | Call `/refresh_access_token` |

**Refresh endpoint:**
```
GET https://graph.instagram.com/refresh_access_token
  ?grant_type=ig_refresh_token
  &access_token=<LONG_LIVED_TOKEN>
```

**Refresh conditions:**
- Token must be at least 24 hours old
- Token must not yet be expired
- User must still have `instagram_business_basic` granted

**Recommended refresh strategy:** Run a background worker daily. Refresh all tokens where `expires_at < NOW() + 15 days`. A 15-day buffer gives you plenty of runway to handle failures before expiry.

### 1.10 Token Security: Encryption at Rest

Never store access tokens as plaintext. Use AES-256-GCM:

```typescript
// lib/crypto/tokenEncryption.ts
import { createCipheriv, createDecipheriv, randomBytes } from 'crypto';

const ALGORITHM = 'aes-256-gcm';
const KEY = Buffer.from(process.env.TOKEN_ENCRYPTION_KEY!, 'hex'); // 32-byte key

export function encryptToken(plaintext: string): { iv: string; ciphertext: string; tag: string } {
  const iv = randomBytes(12);
  const cipher = createCipheriv(ALGORITHM, KEY, iv);
  const ciphertext = Buffer.concat([cipher.update(plaintext, 'utf8'), cipher.final()]);
  return {
    iv: iv.toString('hex'),
    ciphertext: ciphertext.toString('hex'),
    tag: cipher.getAuthTag().toString('hex'),
  };
}

export function decryptToken(iv: string, ciphertext: string, tag: string): string {
  const decipher = createDecipheriv(ALGORITHM, KEY, Buffer.from(iv, 'hex'));
  decipher.setAuthTag(Buffer.from(tag, 'hex'));
  return Buffer.concat([
    decipher.update(Buffer.from(ciphertext, 'hex')),
    decipher.final(),
  ]).toString('utf8');
}
```

---

## 2. Multi-Tenant Connector Architecture

### 2.1 Architecture Overview (1:1 constraint)

One organization can connect exactly one Instagram account. This simplifies the connector model significantly:

```
Organization
    │ 1
    │
    │ 0..1 (unique, non-null once connected)
    ▼
InstagramConnector
    │
    ├── ig_account_id (IG_ID — the platform identity)
    ├── ig_user_id (app-scoped user ID from token response)
    ├── encrypted access token
    └── webhook subscription status
```

### 2.2 Connector Entity Design

```typescript
// types/connector.ts
export type ConnectorStatus = 'pending' | 'active' | 'token_expired' | 'disconnected' | 'error';

export interface InstagramConnector {
  id: string;                    // UUID
  org_id: string;                // FK → organizations.id (UNIQUE)
  ig_account_id: string;         // IG_ID — used for routing & API calls (UNIQUE)
  ig_user_id: string;            // App-scoped user ID from token exchange
  ig_username: string;           // For display
  ig_account_type: 'Business' | 'Media_Creator';
  profile_picture_url: string | null;
  status: ConnectorStatus;
  permissions_granted: string[]; // e.g. ['instagram_business_basic', 'instagram_business_manage_messages']
  webhook_subscribed: boolean;
  token_id: string;              // FK → access_tokens.id
  connected_by_user_id: string;  // FK → users.id
  connected_at: Date;
  last_token_refresh_at: Date;
  disconnected_at: Date | null;
  created_at: Date;
  updated_at: Date;
}
```

### 2.3 Tenant Isolation Strategy

The single most important constraint: **`org_id` is unique in `instagram_connectors`**. Enforced at both DB and application level.

```typescript
// services/connector/createConnector.ts
export async function createOrUpdateConnector(
  orgId: string,
  igAccountId: string,
  igUserId: string,
  igUsername: string,
  tokenData: TokenData,
): Promise<InstagramConnector> {
  // Check if this IG account is already connected to ANOTHER org — block it
  const existingOtherOrg = await db.query(
    `SELECT org_id FROM instagram_connectors
     WHERE ig_account_id = $1 AND org_id != $2 AND status != 'disconnected'`,
    [igAccountId, orgId],
  );
  if (existingOtherOrg.rows.length > 0) {
    throw new ConflictError('This Instagram account is already connected to another organization.');
  }

  // Check if THIS org already has a connector — if so, update it (reconnect)
  const existing = await db.query(
    `SELECT id FROM instagram_connectors WHERE org_id = $1`,
    [orgId],
  );
  if (existing.rows.length > 0) {
    // Reconnect flow: update token, reset status
    return await updateConnector(existing.rows[0].id, igAccountId, tokenData);
  }

  // New connection
  return await insertConnector(orgId, igAccountId, igUserId, igUsername, tokenData);
}
```

### 2.4 Recommended Indexing Strategy

```sql
-- Primary lookup: webhook routing (hot path — must be sub-millisecond)
CREATE UNIQUE INDEX idx_connectors_ig_account_id
  ON instagram_connectors (ig_account_id)
  WHERE status = 'active';

-- Org lookup (settings page, re-auth checks)
CREATE UNIQUE INDEX idx_connectors_org_id
  ON instagram_connectors (org_id)
  WHERE status != 'disconnected';

-- Token refresh worker (scans expiring tokens)
CREATE INDEX idx_tokens_connector_expires
  ON access_tokens (connector_id, expires_at)
  WHERE revoked_at IS NULL;

-- Status monitoring
CREATE INDEX idx_connectors_status
  ON instagram_connectors (status);
```

### 2.5 Redis Caching Layer for Connector Lookups

The webhook processing hot path calls `ig_account_id → org_id` many thousands of times per second at scale. Cache it:

```typescript
// services/connector/connectorCache.ts
const CACHE_TTL_SECONDS = 3600; // 1 hour

export async function getOrgIdForIgAccount(igAccountId: string): Promise<string | null> {
  const cacheKey = `connector:ig:${igAccountId}`;

  const cached = await redis.get(cacheKey);
  if (cached) return cached;

  const result = await db.query(
    `SELECT org_id FROM instagram_connectors WHERE ig_account_id = $1 AND status = 'active'`,
    [igAccountId],
  );

  if (result.rows.length === 0) return null;

  const orgId = result.rows[0].org_id;
  await redis.setex(cacheKey, CACHE_TTL_SECONDS, orgId);
  return orgId;
}

export async function invalidateConnectorCache(igAccountId: string): Promise<void> {
  await redis.del(`connector:ig:${igAccountId}`);
}
```

---

## 3. Webhook Subscription Management

### 3.1 Two-Level Subscription Model

Instagram webhooks require two separate steps:

```
Level 1: App-level field subscription (done once in App Dashboard or via API)
          Subscribe your Meta App to Instagram webhook fields (e.g. "messages")

Level 2: Account-level subscription (done per-user via API after OAuth)
          Call POST /me/subscribed_apps for each connected Instagram account
```

Level 1 is configured once. Level 2 must be called every time a new account connects.

### 3.2 App-Level Webhook Configuration (One-Time)

In **App Dashboard → Webhooks → Instagram**, subscribe to:
- `messages`
- `messaging_seen`
- `message_reactions`
- `messaging_postbacks`
- `messaging_referral`
- `comments` (if comment moderation is in scope)

Set your **Callback URL** (e.g. `https://api.yourplatform.com/webhooks/instagram`) and a **Verify Token** of your choice.

### 3.3 Account-Level Subscription (Per-Tenant, After OAuth)

Immediately after successfully completing OAuth and storing the token, call:

```
POST https://graph.instagram.com/v25.0/<IG_ID>/subscribed_apps
  ?subscribed_fields=messages,messaging_seen,message_reactions,messaging_postbacks
  &access_token=<INSTAGRAM_USER_ACCESS_TOKEN>
```

**Response:**
```json
{ "success": true }
```

**This API call is NOT automatic** — it must be triggered explicitly after each successful OAuth connection.

```typescript
// services/connector/webhookSubscription.ts
export async function subscribeToWebhooks(
  igAccountId: string,
  accessToken: string,
): Promise<void> {
  const fields = [
    'messages',
    'messaging_seen',
    'message_reactions',
    'messaging_postbacks',
    'messaging_referral',
    'message_echoes',
  ].join(',');

  const url = `https://graph.instagram.com/v25.0/${igAccountId}/subscribed_apps`;
  const resp = await fetch(`${url}?subscribed_fields=${fields}&access_token=${accessToken}`, {
    method: 'POST',
  });

  if (!resp.ok) {
    const err = await resp.json();
    throw new Error(`Webhook subscription failed: ${JSON.stringify(err)}`);
  }

  // Update connector record
  await db.query(
    `UPDATE instagram_connectors SET webhook_subscribed = true WHERE ig_account_id = $1`,
    [igAccountId],
  );
}
```

### 3.4 Unsubscribe on Disconnect

When an organization disconnects their Instagram account:

```
DELETE https://graph.instagram.com/v25.0/<IG_ID>/subscribed_apps
  ?access_token=<ACCESS_TOKEN>
```

If the token is already expired, skip the API call (Meta will stop delivering webhooks for expired/revoked tokens automatically) and mark the connector as `disconnected` in your DB.

### 3.5 Webhook Endpoint Verification

Meta sends a `GET` request to your webhook URL when you register it:

```
GET /webhooks/instagram
  ?hub.mode=subscribe
  &hub.challenge=1158201444
  &hub.verify_token=your_verify_token
```

Your handler must:
1. Verify `hub.verify_token` matches your configured secret
2. Return `200` with the **plain-text** value of `hub.challenge`

```typescript
// routes/webhooks/instagram.ts (Next.js App Router example)
export async function GET(req: Request): Promise<Response> {
  const { searchParams } = new URL(req.url);
  const mode = searchParams.get('hub.mode');
  const token = searchParams.get('hub.verify_token');
  const challenge = searchParams.get('hub.challenge');

  if (mode === 'subscribe' && token === process.env.INSTAGRAM_WEBHOOK_VERIFY_TOKEN) {
    return new Response(challenge, { status: 200 });
  }

  return new Response('Forbidden', { status: 403 });
}
```

### 3.6 Payload Signature Verification

Every `POST` from Meta includes `X-Hub-Signature-256: sha256=<SIGNATURE>`. Validate before processing:

```typescript
import { createHmac } from 'crypto';

export function verifyWebhookSignature(rawBody: Buffer, signature: string): boolean {
  const expected = createHmac('sha256', process.env.INSTAGRAM_APP_SECRET!)
    .update(rawBody)
    .digest('hex');
  const received = signature.replace('sha256=', '');
  // Use timingSafeEqual to prevent timing attacks
  return timingSafeEqual(Buffer.from(expected, 'hex'), Buffer.from(received, 'hex'));
}
```

**Critical:** Read the raw body buffer before any JSON parsing. Most frameworks (Express, FastAPI) need explicit raw body middleware for this.

---

## 4. Multi-Tenant Webhook Processing

### 4.1 Webhook Payload Structure

All Instagram webhook events follow this envelope:

```json
{
  "object": "instagram",
  "entry": [
    {
      "id": "<IG_ACCOUNT_ID>",
      "time": 1741043123,
      "messaging": [
        {
          "sender": { "id": "<IGSID_of_customer>" },
          "recipient": { "id": "<IG_ACCOUNT_ID>" },
          "timestamp": 1741043111,
          "message": {
            "mid": "m_abc123...",
            "text": "Hello, is this product available?"
          }
        }
      ]
    }
  ]
}
```

**Tenant routing identifiers:**

| Field | Value | Usage |
|-------|-------|-------|
| `entry[].id` | IG account ID (`IG_ID`) | Primary routing key to find the org |
| `recipient.id` | Same as `entry[].id` | Confirms the receiving account |
| `sender.id` | Instagram-scoped user ID (`IGSID`) | Identifies the customer |
| `message.mid` | Message ID | Idempotency key |

### 4.2 Tenant Routing Logic

```typescript
// services/webhook/router.ts
export async function routeWebhookEvent(payload: InstagramWebhookPayload): Promise<void> {
  for (const entry of payload.entry) {
    const igAccountId = entry.id; // This IS the IG_ID

    // O(1) lookup via Redis cache, falls back to DB
    const orgId = await getOrgIdForIgAccount(igAccountId);
    if (!orgId) {
      logger.warn({ igAccountId }, 'Received webhook for unknown/disconnected account — ignoring');
      return;
    }

    const events = entry.messaging ?? entry.changes ?? [];
    for (const event of events) {
      await publishToKafka('instagram.events.raw', {
        orgId,           // Tenant context injected here
        igAccountId,
        eventType: classifyEvent(event),
        payload: event,
        receivedAt: new Date().toISOString(),
        messageId: event.message?.mid ?? event.changes?.[0]?.value?.id,
      });
    }
  }
}
```

### 4.3 Idempotency Strategy

Instagram may deliver the same event multiple times (retries on 5xx, network issues). Use the `message.mid` as an idempotency key:

```typescript
// services/webhook/idempotency.ts
const IDEMPOTENCY_TTL = 60 * 60 * 24; // 24 hours in Redis

export async function isAlreadyProcessed(messageId: string): Promise<boolean> {
  const key = `webhook:processed:${messageId}`;
  const result = await redis.set(key, '1', 'EX', IDEMPOTENCY_TTL, 'NX');
  return result === null; // null means key already existed
}
```

In your Kafka consumer:

```typescript
if (await isAlreadyProcessed(event.messageId)) {
  logger.info({ messageId: event.messageId }, 'Duplicate webhook — skipping');
  return;
}
// ... process event
```

### 4.4 Event Types and Classification

```typescript
type InstagramEventType =
  | 'message.received'
  | 'message.echo'       // Sent by the business themselves
  | 'message.reaction'
  | 'message.seen'
  | 'message.postback'
  | 'message.referral'
  | 'comment.received'
  | 'story.mention';

function classifyEvent(event: any): InstagramEventType {
  if (event.message?.is_echo) return 'message.echo';
  if (event.message) return 'message.received';
  if (event.reaction) return 'message.reaction';
  if (event.read) return 'message.seen';
  if (event.postback) return 'message.postback';
  if (event.referral) return 'message.referral';
  if (event.changes?.[0]?.field === 'comments') return 'comment.received';
  if (event.changes?.[0]?.field === 'mentions') return 'story.mention';
  throw new Error(`Unknown event type: ${JSON.stringify(event)}`);
}
```

### 4.5 Message Payload Examples

**Text message received:**
```json
{
  "sender": { "id": "5678901234" },
  "recipient": { "id": "17841400008460056" },
  "timestamp": 1741043111,
  "message": {
    "mid": "m_abc123def456",
    "text": "Do you ship to Nepal?"
  }
}
```

**Image attachment:**
```json
{
  "sender": { "id": "5678901234" },
  "recipient": { "id": "17841400008460056" },
  "timestamp": 1741043200,
  "message": {
    "mid": "m_xyz789",
    "attachments": [
      {
        "type": "image",
        "payload": { "url": "https://cdn.instagram.com/..." }
      }
    ]
  }
}
```

**Message seen (read receipt):**
```json
{
  "sender": { "id": "5678901234" },
  "recipient": { "id": "17841400008460056" },
  "timestamp": 1741043300,
  "read": { "watermark": 1741043111 }
}
```

### 4.6 Event Ordering & Dead-Letter Queue

Instagram webhooks are not guaranteed to arrive in order. Handle ordering at the consumer layer:

```typescript
// Kafka consumer group: one consumer group per org for ordering guarantees
// Partition key: orgId (ensures all events for one org go to same partition)
await kafka.publish('instagram.events.raw', {
  key: orgId,         // Partition key for ordering
  value: JSON.stringify(event),
});
```

For failed processing, use a dead-letter topic:

```
instagram.events.raw        → main processing
instagram.events.retry      → retry with exponential backoff (3 attempts)
instagram.events.dlq        → dead-letter (manual inspection)
```

Retry delays: 30s → 5m → 30m. After 3 failures, move to DLQ and alert on-call.

---

## 5. Instagram Messaging Integration

### 5.1 Receiving Messages

Messages arrive via webhook (section 4). No polling required.

**Conversation sync after downtime:** Fetch historical conversations via:

```
GET https://graph.instagram.com/v25.0/<IG_ID>/conversations
  ?fields=id,participants,messages{id,message,from,created_time,attachments}
  &access_token=<ACCESS_TOKEN>
```

Use the `since` parameter to get messages after a specific UNIX timestamp.

### 5.2 Sending Text Reply

```typescript
// services/messaging/send.ts
export async function sendTextMessage(
  igAccountId: string,
  recipientIgsid: string,
  text: string,
  accessToken: string,
): Promise<{ message_id: string }> {
  const resp = await fetch(`https://graph.instagram.com/v25.0/${igAccountId}/messages`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      recipient: { id: recipientIgsid },
      message: { text },
    }),
  });

  if (!resp.ok) {
    const err = await resp.json();
    throw new InstagramApiError(err);
  }

  return resp.json();
}
```

**Messaging window: 24 hours from the customer's last message.** Attempting to send outside the window returns error code 10 (PermissionError). Use `human_agent` tag for up to 7 days.

### 5.3 Sending Media Attachments

```typescript
export async function sendImageMessage(
  igAccountId: string,
  recipientIgsid: string,
  imageUrl: string,
  accessToken: string,
): Promise<void> {
  await fetch(`https://graph.instagram.com/v25.0/${igAccountId}/messages`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${accessToken}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      recipient: { id: recipientIgsid },
      message: {
        attachments: {
          type: 'image',
          payload: { url: imageUrl },
        },
      },
    }),
  });
}
```

**Media size limits:**

| Type | Formats | Max Size |
|------|---------|----------|
| Audio | aac, m4a, wav, mp4 | 25 MB |
| Image | png, jpeg | 8 MB |
| Video | mp4, ogg, avi, mov, webm | 25 MB |
| File | pdf | 25 MB |

### 5.4 Send With Human Agent Tag (Extended Window)

```typescript
await fetch(`https://graph.instagram.com/v25.0/${igAccountId}/messages`, {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    recipient: { id: recipientIgsid },
    message: { text: "We're looking into your order and will update you shortly." },
    messaging_type: 'MESSAGE_TAG',
    tag: 'human_agent',
  }),
});
```

The Human Agent feature must be approved in App Review before use.

### 5.5 Message Reactions (Send)

```typescript
await fetch(`https://graph.instagram.com/v25.0/${igAccountId}/messages`, {
  method: 'POST',
  headers: {
    Authorization: `Bearer ${accessToken}`,
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    recipient: { id: recipientIgsid },
    sender_action: 'react',
    payload: {
      message_id: '<TARGET_MESSAGE_ID>',
      reaction: '❤️',
    },
  }),
});
```

### 5.6 Fetch Conversation History

```typescript
// GET conversation thread for a specific customer
async function getConversation(igAccountId: string, igsid: string, accessToken: string) {
  const url = new URL(`https://graph.instagram.com/v25.0/${igAccountId}/conversations`);
  url.searchParams.set('user_id', igsid);
  url.searchParams.set('fields', 'id,messages{id,message,from,created_time,attachments}');
  url.searchParams.set('access_token', accessToken);

  const resp = await fetch(url.toString());
  return resp.json();
}
```

---

## 6. Scalable System Design

### 6.1 Service Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                         Client (Next.js)                      │
└──────────────────────────┬───────────────────────────────────┘
                           │ HTTPS
┌──────────────────────────▼───────────────────────────────────┐
│                      API Gateway / Load Balancer              │
└──────┬───────────────────┬──────────────────────┬────────────┘
       │                   │                      │
┌──────▼──────┐   ┌────────▼────────┐   ┌─────────▼──────────┐
│  OAuth      │   │  Connector      │   │  Webhook           │
│  Service    │   │  Service        │   │  Service           │
│             │   │                 │   │  (public HTTPS)    │
│ - Auth URL  │   │ - CRUD orgs     │   │  - Verify endpoint │
│ - Callback  │   │ - Token mgmt    │   │  - Sig validation  │
│ - Token exch│   │ - Status        │   │  - Publish Kafka   │
└──────┬──────┘   └────────┬────────┘   └─────────┬──────────┘
       │                   │                       │
       └───────────────────┴───────────────────────┘
                           │
                    ┌──────▼──────┐
                    │   Kafka     │
                    │             │
                    │ instagram.  │
                    │ events.raw  │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
┌───────▼──────┐  ┌────────▼────────┐  ┌─────▼────────────┐
│  Message     │  │  Conversation   │  │  Token Refresh   │
│  Ingestion   │  │  Sync Worker    │  │  Worker          │
│  Worker      │  │                 │  │                  │
│              │  │ - History sync  │  │ - Refresh 15d    │
│ - Dedup      │  │ - Missed msg    │  │   before expiry  │
│ - Store msg  │  │   backfill      │  │ - Alert on fail  │
│ - Notify UI  │  └─────────────────┘  └──────────────────┘
└──────┬───────┘
       │
       ├── PostgreSQL (messages, conversations)
       ├── Redis (cache, idempotency, pub/sub for real-time)
       └── S3 (media attachments)
```

### 6.2 OAuth Service

Responsibilities:
- Build authorization URLs with signed `state` JWTs
- Handle OAuth callback: validate state, exchange code, fetch IG_ID, store connector
- Trigger webhook subscription post-connect
- Handle reconnect (org already has connector — update token)

Scale: Stateless, horizontally scalable. No shared state needed.

### 6.3 Webhook Service

This is the most critical public-facing service. It receives all traffic from Meta.

**Requirements:**
- Must respond `200 OK` within **5 seconds** or Meta considers it a failure
- Must handle **1000 events per batch** (Meta may batch)
- Must **immediately acknowledge** and process asynchronously

```typescript
// routes/webhooks/instagram.ts
export async function POST(req: Request): Promise<Response> {
  const rawBody = Buffer.from(await req.arrayBuffer());
  const signature = req.headers.get('x-hub-signature-256') ?? '';

  // 1. Validate signature — reject early if invalid
  if (!verifyWebhookSignature(rawBody, signature)) {
    return new Response('Unauthorized', { status: 403 });
  }

  // 2. Parse and publish to Kafka — do NOT process inline
  const payload: InstagramWebhookPayload = JSON.parse(rawBody.toString());
  await routeWebhookEvent(payload); // publishes to Kafka, sub-millisecond

  // 3. Acknowledge immediately
  return new Response('OK', { status: 200 });
}
```

Scale: 3+ replicas minimum. Use connection pooling for Redis/Kafka. No DB calls in the hot path.

### 6.4 Token Refresh Worker

```typescript
// workers/tokenRefresh.ts
export async function runTokenRefreshCycle(): Promise<void> {
  // Find tokens expiring in next 15 days
  const expiringConnectors = await db.query(`
    SELECT c.id, c.ig_account_id, c.org_id, t.iv, t.ciphertext, t.auth_tag, t.expires_at
    FROM instagram_connectors c
    JOIN access_tokens t ON t.connector_id = c.id
    WHERE c.status = 'active'
      AND t.revoked_at IS NULL
      AND t.expires_at < NOW() + INTERVAL '15 days'
    ORDER BY t.expires_at ASC
  `);

  for (const connector of expiringConnectors.rows) {
    try {
      const currentToken = decryptToken(connector.iv, connector.ciphertext, connector.auth_tag);
      const refreshed = await refreshInstagramToken(currentToken);
      await rotateToken(connector.id, refreshed.access_token, refreshed.expires_in);
      await invalidateConnectorCache(connector.ig_account_id);
    } catch (err) {
      await markConnectorStatus(connector.id, 'token_expired');
      await notifyOrgTokenExpired(connector.org_id);
      logger.error({ connectorId: connector.id, err }, 'Token refresh failed');
    }
  }
}
```

Run on a cron: every 6 hours.

### 6.5 Rate Limiting

Instagram API rate limits are per-token (not global). Key limits:
- **Messaging API:** ~250 messages/second per token (undocumented, observe 429s)
- **Graph API calls:** 200 calls/hour per token for most endpoints

**Handling 429s:**

```typescript
async function instagramApiCall<T>(
  fn: () => Promise<T>,
  retries = 3,
): Promise<T> {
  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      return await fn();
    } catch (err: any) {
      if (err.status === 429) {
        const retryAfter = parseInt(err.headers?.['retry-after'] ?? '60', 10);
        const backoff = Math.min(retryAfter * 1000, 60_000) * Math.pow(2, attempt);
        await sleep(backoff + Math.random() * 1000); // jitter
        continue;
      }
      throw err;
    }
  }
  throw new Error('Rate limit retries exhausted');
}
```

### 6.6 Horizontal Scaling Considerations

| Service | Scaling Strategy |
|---------|-----------------|
| Webhook Service | Stateless; scale by CPU/RPS; minimum 3 replicas |
| OAuth Service | Stateless; scale by request volume |
| Kafka Consumers | Scale consumers up to partition count |
| Token Refresh Worker | Single instance (or distributed lock via Redis) |
| PostgreSQL | Read replicas for reporting; primary for writes |
| Redis | Cluster mode; separate cache vs. pub/sub |

---

## 7. Data Model Recommendations

### 7.1 Organizations

```sql
CREATE TABLE organizations (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name        TEXT NOT NULL,
  slug        TEXT UNIQUE NOT NULL,
  plan        TEXT NOT NULL DEFAULT 'free',
  status      TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'suspended', 'deleted')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 7.2 Users

```sql
CREATE TABLE users (
  id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id      UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  email       TEXT UNIQUE NOT NULL,
  role        TEXT NOT NULL DEFAULT 'member' CHECK (role IN ('owner', 'admin', 'member', 'agent')),
  created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_org_id ON users(org_id);
```

### 7.3 Instagram Connectors

```sql
CREATE TABLE instagram_connectors (
  id                      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id                  UUID NOT NULL UNIQUE REFERENCES organizations(id),  -- 1:1 enforced
  ig_account_id           TEXT NOT NULL,       -- IG_ID (platform identity, used for routing & API)
  ig_user_id              TEXT NOT NULL,       -- App-scoped user ID from token
  ig_username             TEXT NOT NULL,
  ig_account_type         TEXT NOT NULL CHECK (ig_account_type IN ('Business', 'Media_Creator')),
  profile_picture_url     TEXT,
  status                  TEXT NOT NULL DEFAULT 'pending'
                            CHECK (status IN ('pending', 'active', 'token_expired', 'disconnected', 'error')),
  permissions_granted     TEXT[] NOT NULL DEFAULT '{}',
  webhook_subscribed      BOOLEAN NOT NULL DEFAULT FALSE,
  connected_by_user_id    UUID REFERENCES users(id),
  connected_at            TIMESTAMPTZ,
  last_token_refresh_at   TIMESTAMPTZ,
  disconnected_at         TIMESTAMPTZ,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Active account routing (hot-path index)
CREATE UNIQUE INDEX idx_connectors_ig_account_active
  ON instagram_connectors(ig_account_id)
  WHERE status = 'active';

-- Status monitoring
CREATE INDEX idx_connectors_status ON instagram_connectors(status);
```

### 7.4 Access Tokens

```sql
CREATE TABLE access_tokens (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  connector_id    UUID NOT NULL REFERENCES instagram_connectors(id) ON DELETE CASCADE,
  token_iv        TEXT NOT NULL,         -- AES-GCM IV (hex)
  token_ciphertext TEXT NOT NULL,        -- Encrypted token (hex)
  token_auth_tag  TEXT NOT NULL,         -- AES-GCM auth tag (hex)
  token_type      TEXT NOT NULL DEFAULT 'long_lived',
  permissions     TEXT[] NOT NULL DEFAULT '{}',
  expires_at      TIMESTAMPTZ NOT NULL,
  issued_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  revoked_at      TIMESTAMPTZ,           -- Set when token is replaced or org disconnects
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- One active token per connector
CREATE UNIQUE INDEX idx_tokens_connector_active
  ON access_tokens(connector_id)
  WHERE revoked_at IS NULL;

-- Token refresh worker scan
CREATE INDEX idx_tokens_expires_at ON access_tokens(expires_at)
  WHERE revoked_at IS NULL;
```

### 7.5 Webhook Subscriptions (Audit Log)

```sql
CREATE TABLE webhook_subscriptions (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  connector_id    UUID NOT NULL REFERENCES instagram_connectors(id),
  subscribed_fields TEXT[] NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('active', 'unsubscribed', 'failed')),
  subscribed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  unsubscribed_at TIMESTAMPTZ,
  failure_reason  TEXT
);
```

### 7.6 Conversations

```sql
CREATE TABLE conversations (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES organizations(id),
  connector_id    UUID NOT NULL REFERENCES instagram_connectors(id),
  ig_thread_id    TEXT,                  -- Meta-assigned conversation ID (if available)
  customer_igsid  TEXT NOT NULL,         -- Instagram-scoped ID of the customer
  customer_name   TEXT,
  status          TEXT NOT NULL DEFAULT 'open'
                    CHECK (status IN ('open', 'resolved', 'snoozed', 'spam')),
  assigned_user_id UUID REFERENCES users(id),
  last_message_at TIMESTAMPTZ,
  last_customer_message_at TIMESTAMPTZ, -- For 24-hour window tracking
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX idx_conversations_org_customer
  ON conversations(org_id, customer_igsid, connector_id);

CREATE INDEX idx_conversations_org_status ON conversations(org_id, status);
CREATE INDEX idx_conversations_last_message ON conversations(org_id, last_message_at DESC);
```

### 7.7 Messages

```sql
CREATE TABLE messages (
  id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id          UUID NOT NULL REFERENCES organizations(id),
  conversation_id UUID NOT NULL REFERENCES conversations(id),
  ig_message_id   TEXT UNIQUE NOT NULL,  -- Meta's message.mid — idempotency key
  direction       TEXT NOT NULL CHECK (direction IN ('inbound', 'outbound')),
  sender_type     TEXT NOT NULL CHECK (sender_type IN ('customer', 'agent', 'bot')),
  sender_id       TEXT,                  -- IGSID for customer, user UUID for agent
  content_type    TEXT NOT NULL CHECK (content_type IN ('text', 'image', 'video', 'audio', 'file', 'sticker', 'reaction', 'story_mention', 'share', 'deleted')),
  text            TEXT,
  attachments     JSONB DEFAULT '[]',    -- [{ type, url, mime_type, size }]
  metadata        JSONB DEFAULT '{}',    -- Raw Instagram payload for debugging
  status          TEXT NOT NULL DEFAULT 'delivered'
                    CHECK (status IN ('sending', 'delivered', 'seen', 'failed')),
  sent_at         TIMESTAMPTZ,
  seen_at         TIMESTAMPTZ,
  created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Conversation thread view
CREATE INDEX idx_messages_conversation ON messages(conversation_id, created_at DESC);

-- Deduplication check
CREATE UNIQUE INDEX idx_messages_ig_id ON messages(ig_message_id);

-- Org-level message search
CREATE INDEX idx_messages_org_created ON messages(org_id, created_at DESC);
```

### 7.8 Example Records

**instagram_connectors:**
```json
{
  "id": "c1d2e3f4-...",
  "org_id": "a1b2c3d4-...",
  "ig_account_id": "17841400008460056",
  "ig_username": "mystore_nepal",
  "ig_account_type": "Business",
  "status": "active",
  "webhook_subscribed": true,
  "permissions_granted": ["instagram_business_basic", "instagram_business_manage_messages"],
  "connected_at": "2025-01-15T10:30:00Z",
  "last_token_refresh_at": "2025-03-01T06:00:00Z"
}
```

---

## 8. End-to-End Flow Diagrams

### 8.1 Flow 1: User Connects Instagram Account

```
Organization User        Your Platform (OAuth Service)       Instagram / Meta
      │                           │                                  │
      │── Click "Connect" ──────► │                                  │
      │                           │── Generate signed state JWT      │
      │                           │── Build Authorization URL ──────►│
      │◄── Redirect to IG ────────│                                  │
      │                           │                                  │
      │──────────────── Authenticate on Instagram ─────────────────► │
      │◄─── Redirect with ?code=AUTH_CODE ──────────────────────────│
      │                           │                                  │
      │── GET /oauth/callback ──► │                                  │
      │     ?code=AUTH_CODE       │── Validate state JWT             │
      │     &state=...            │── POST /oauth/access_token ─────►│
      │                           │◄── { access_token, user_id } ───│
      │                           │── GET /access_token (long) ─────►│
      │                           │◄── { access_token, expires } ───│
      │                           │── GET /me?fields=user_id,username►│
      │                           │◄── { user_id, username } ───────│
      │                           │── Encrypt & store token          │
      │                           │── Upsert instagram_connectors    │
      │                           │── POST /<IG_ID>/subscribed_apps►│
      │                           │◄── { success: true } ───────────│
      │                           │── Mark webhook_subscribed=true   │
      │◄── "Connected!" ──────────│                                  │
```

### 8.2 Flow 2: Receiving an Instagram DM

```
Instagram Customer      Meta Platform          Webhook Service        Kafka          Message Worker        DB / Cache
      │                      │                       │                   │                  │                   │
      │── Send DM ──────────►│                       │                   │                  │                   │
      │                      │── POST /webhooks ─────►│                  │                  │                   │
      │                      │   { entry[].id=IG_ID   │                  │                  │                   │
      │                      │     message.mid=...    │                  │                  │                   │
      │                      │     sender.id=IGSID }  │                  │                  │                   │
      │                      │                        │── Verify sig     │                  │                   │
      │                      │                        │── Redis lookup   │                  │                   │
      │                      │                        │   IG_ID → org_id │                  │                   │
      │                      │                        │── Publish event ►│                  │                   │
      │                      │◄── 200 OK ─────────────│                  │                  │                   │
      │                      │                        │                  │── Consume ───────►│                  │
      │                      │                        │                  │                  │── Dedup check ───►│
      │                      │                        │                  │                  │   (Redis SETNX)   │
      │                      │                        │                  │                  │── Upsert convo ──►│
      │                      │                        │                  │                  │── Insert message ►│
      │                      │                        │                  │                  │── Notify via SSE  │
```

### 8.3 Flow 3: Sending a Reply

```
Agent (Browser)          API Server           DB / Cache          Instagram API
      │                      │                    │                     │
      │── POST /messages ───►│                    │                     │
      │   { text, convId }   │── Load connector ─►│                     │
      │                      │◄── igAccountId     │                     │
      │                      │── Load token ─────►│                     │
      │                      │◄── encrypted token │                     │
      │                      │── Decrypt token    │                     │
      │                      │── Check 24h window │                     │
      │                      │── POST /<IG_ID>/messages ───────────────►│
      │                      │◄── { message_id } ──────────────────────│
      │                      │── Insert message record ─────────────── ►│
      │◄── { messageId } ────│                    │                     │
```

### 8.4 Flow 4: Token Refresh Worker

```
Token Refresh Worker           DB                    Instagram API           Cache
      │                         │                          │                    │
      │── SELECT expiring ─────►│                          │                    │
      │◄── [connectors list] ───│                          │                    │
      │                         │                          │                    │
      │ FOR EACH connector:     │                          │                    │
      │── Decrypt token         │                          │                    │
      │── GET /refresh_token ──────────────────────────────►│                  │
      │◄── { new_access_token } ───────────────────────────│                  │
      │── Encrypt new token     │                          │                    │
      │── UPDATE access_tokens ►│                          │                    │
      │── Revoke old token ────►│                          │                    │
      │── DEL cache key ───────────────────────────────────────────────────────►│
      │                         │                          │                    │
      │ ON FAILURE:             │                          │                    │
      │── Mark status=token_expired ────────────────────── ►│                  │
      │── Notify org ──────────►│                          │                    │
```

---

## 9. Common Pitfalls & Platform Limitations

### 9.1 Meta Platform Limitations (Documented)

| Limitation | Detail |
|-----------|--------|
| **24-hour messaging window** | Can only send proactive messages within 24h of last customer message. After that, only `human_agent` tag works (7 days), requiring App Review. |
| **No group messaging** | One customer per conversation. No multi-participant threads. |
| **Requests folder 30-day limit** | Messages in Requests that are inactive for 30 days are not returned by API calls. |
| **No inbox folder data in API** | Folder info (Primary/General/Requests) is not included in webhook payloads or API responses. |
| **Read status not reflected** | Webhook deliveries do not mark messages as Read in the Instagram app — only sending a reply does. |
| **Story media expires** | Story attachment URLs are CDN links that expire. Download and re-host if you need to persist them. |
| **Account must be public** | To receive comment/mention webhooks, the Instagram professional account must be public. |
| **No hashtag search** | Instagram API with Instagram Login does NOT support hashtag search (that's Facebook Login only). |
| **Advanced Access required** | Your app must complete Business Verification and App Review to serve accounts you don't own. |
| **App must be Live** | Meta does NOT send webhook notifications to apps in Development mode. |

### 9.2 Implementation Pitfalls

**1. `#_` suffix on auth code redirect**  
Instagram appends `#_` to the redirect URI after the auth code. Always strip it:
```typescript
const code = searchParams.get('code')?.replace(/#_$/, '');
```

**2. Instagram App ID ≠ Meta App ID**  
Business Login for Instagram uses a separate **Instagram App ID** found under `App Dashboard → Instagram → API setup with Instagram login`. Do not confuse with the Meta App ID shown at the top.

**3. Token exchange must be server-side**  
The `/oauth/access_token` and `/access_token` (long-lived) calls include your `client_secret`. Never expose this to the browser.

**4. Webhook subscription is not automatic**  
Completing OAuth does NOT auto-subscribe the account to webhooks. You MUST explicitly call `POST /<IG_ID>/subscribed_apps` after every connect/reconnect.

**5. `entry[].id` is the IG_ID, not the IGSID**  
The `entry[].id` in webhook payloads is the Instagram professional account ID (`IG_ID`). The `sender.id` is the customer's Instagram-scoped ID (`IGSID`). These are different entities.

**6. Cache invalidation on token rotation**  
After rotating a token (refresh or reconnect), invalidate the Redis cache immediately. Stale cached tokens cause 400/401 errors.

**7. Batched webhook entries**  
A single webhook POST can contain multiple `entry` objects, and each entry can have multiple `messaging` events. Always loop over both arrays.

**8. Do not store tokens in environment variables**  
Each tenant has their own token. They go in an encrypted DB column, not `.env`.

**9. Scope deprecation (already happened)**  
Old scopes `business_basic`, `business_manage_messages` etc. were deprecated January 27, 2025. Use `instagram_business_*` variants only.

**10. mTLS for production webhooks**  
For production hardening, configure mTLS using Meta's outbound CA certificate (`meta-outbound-api-ca-2025-12.pem`) to verify webhook requests are genuinely from Meta — not just any party that knows your endpoint URL.

---

## Appendix: TypeScript Types Reference

```typescript
// Complete webhook payload types
export interface InstagramWebhookPayload {
  object: 'instagram';
  entry: InstagramWebhookEntry[];
}

export interface InstagramWebhookEntry {
  id: string;          // IG_ID of the recipient (professional account)
  time: number;        // UNIX timestamp
  messaging?: InstagramMessagingEvent[];
  changes?: InstagramChangeEvent[];
}

export interface InstagramMessagingEvent {
  sender: { id: string };     // IGSID of customer
  recipient: { id: string };  // IG_ID of professional account
  timestamp: number;
  message?: {
    mid: string;
    text?: string;
    is_echo?: boolean;
    is_self?: boolean;
    attachments?: Array<{
      type: 'image' | 'video' | 'audio' | 'file' | 'sticker' | 'share';
      payload: { url?: string; sticker_id?: number };
    }>;
  };
  reaction?: {
    mid: string;
    action: 'react' | 'unreact';
    emoji?: string;
  };
  read?: { watermark: number };
  postback?: { mid: string; title: string; payload: string };
  referral?: { ref: string; source: string; type: string };
}
```

---

*Guide based on official Meta documentation as of June 2026. Always cross-reference with the [Instagram Platform Reference](https://developers.facebook.com/docs/instagram-platform/reference) for the latest endpoint details.*
