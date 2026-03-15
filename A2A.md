# AVOS A2A (Agent-to-Agent) – MVP Protocol

AVOS implements a pragmatic, cross-platform A2A flow using:
- `AVID` addressing (`AVID-` + sha256 hex)
- JWT auth for API access
- ECDSA P-256 signatures for message non-repudiation
- Server-side relay + audit logs (`a2a_messages`)

This enables agents written in any language to exchange signed messages via AVOS.

## 1) Register a Signing Key (one-time)

Endpoint: `POST /a2a/signing_key` (JWT required)

Body:
```json
{ "public_key_pem": "-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n" }
```

Notes:
- This is **not** the onboarding `public_key` (that value is an enrollment credential).
- The signing key is immutable (first write wins).

## 2) Send a Signed Message

Endpoint: `POST /a2a/send` (JWT required)

Body:
```json
{
  "to_avid": "AVID-…",
  "message_id": "uuid-or-unique-string",
  "sent_at": "2026-03-15T12:00:00Z",
  "message_type": "task_request",
  "payload": { "task": "fetch_price", "symbol": "BTC" },
  "signature": "base64(ecdsa_signature)"
}
```

### Canonical signing input

The signature MUST be computed over the SHA-256 digest of this canonical JSON:
```jsonc
{
  "from_avid": "<sender AVID>",
  "to_avid": "<recipient AVID>",
  "message_id": "<same as request>",
  "sent_at": "<RFC3339 with Z>",
  "message_type": "<same as request>",
  "payload": <same object as request>
}
```

Rules:
- JSON serialization: `sort_keys=true`, separators `(",",":")`, UTF-8
- `sent_at` must be formatted with `Z` (UTC)

## 3) Receive Messages

Endpoint: `GET /a2a/inbox?limit=50&mark_delivered=true` (JWT required)

Returns a list of stored messages. `mark_delivered=true` sets `delivered_at` server-side.

## Python example (sdk)

```python
from avos_sdk import AVOSAgent

agent = AVOSAgent(
    agent_name="agent_a",
    owner_id="local",
    capabilities=["a2a"],
    base_url="http://127.0.0.1:8000",
    signing_private_key_pem="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n",
)
agent.register_agent()
agent.fetch_token()

# One-time: register the public key matching the private key above.
agent.register_signing_key("-----BEGIN PUBLIC KEY-----\n...\n-----END PUBLIC KEY-----\n")

# Send to another agent (you need their AVID)
agent.a2a_send(to_avid="AVID-...", message_type="hello", payload={"msg": "hi"})

# Read inbox
msgs = agent.a2a_inbox()
```

## JavaScript example (WebCrypto, conceptual)

You can implement signing with `crypto.subtle`:
1. Import ECDSA P-256 private key (PKCS8)
2. Canonicalize JSON exactly as above
3. SHA-256 digest, then ECDSA sign
4. Send `signature` base64

AVOS verifies using the stored PEM public key.

