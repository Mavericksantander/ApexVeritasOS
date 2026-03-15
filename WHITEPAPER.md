# Apex Protocol (ApexVeritasOS) — Whitepaper (MVP v0.x)

Fecha: 2026-03-15  
Repositorio: Apex-Protocol  
Estado: MVP funcional para desarrollo local y demos (no “production-grade” todavía; ver Limitaciones y Roadmap)

## Resumen (Abstract)

Los agentes autónomos hoy operan con credenciales débiles (API keys / tokens) y sin una capa común de gobernanza. Esto dificulta atribución, auditoría, reputación y seguridad al ejecutar acciones reales (shell, archivos, dinero, APIs externas) y al colaborar entre múltiples agentes.

**Apex Protocol** es una infraestructura mínima de confianza y coordinación para agentes autónomos. El MVP implementa:

- Identidad verificable (AVID) ligada a claves + metadatos + constitución.
- Gobernanza: autorización de acciones, reglas/policies y “constitution-as-code”.
- Auditoría trazable: logs con hash-chain por agente.
- Reputación explicable: métricas derivadas y score con decay temporal.
- A2A: mensajería y handshake (AHP) para colaboración agent-to-agent.
- Registry + Observatory: directorio y observabilidad del ecosistema (MVP).

## Problema

Los sistemas agentic modernos enfrentan 4 fallas recurrentes:

1. **Identidad débil**: una API key prueba “acceso” pero no “identidad” ni binding a gobernanza.
2. **Acción sin control**: herramientas ejecutan comandos o modifican sistemas sin política uniforme.
3. **Reputación opaca**: scores simples sin explicación generan incentivos incorrectos y son fáciles de manipular.
4. **Colaboración sin verificación**: en A2A (agent-to-agent), sin handshake ni prueba mínima, la coordinación se vuelve insegura.

## Objetivo

Crear una capa de gobernanza y coordinación que permita:

- atribuir y auditar acciones a un agente específico (durable identity),
- aplicar reglas de seguridad antes de ejecutar acciones peligrosas,
- registrar eventos con integridad verificable,
- permitir discovery y cooperación entre agentes por reputación y verificación.

## Arquitectura: “Apex Stack”

El MVP se organiza como tres módulos, que juntos se comportan como infraestructura:

1. **ApexVeritasOS** (governance runtime)
   - Identidad, auth, task logging, authorize_action, constitution engine, A2A, reputación y auditoría.
2. **Apex Registry** (identity + discovery)
   - Directorio público de agentes, capacidades, reputación y (MVP) attestations emitidas por “issuers”.
3. **Apex Observatory** (ops + analytics)
   - Activity feed, graph de interacciones A2A, trust analytics básicos.

## Principios de diseño

- **Verificable por defecto**: identidad y logs con integridad verificable.
- **Governance-by-construction**: acciones pasan por autorización antes de ejecución.
- **Explainability**: reputación debe ser descomponible en señales entendibles.
- **Compatibilidad**: fácil de integrar con frameworks (OpenClaw, LangChain, CrewAI) con wrappers simples.
- **Free-first**: demo y adopción inicial sin infraestructura paga (CI, dashboards, SQLite/Postgres).

## Identidad: AVID (ApexVeritas Identity)

### Definición

**AVID** es el identificador externo principal de un agente en el ecosistema Apex.

Propósito:

- Atribución: “qué agente hizo esto”.
- Binding: identidad ligada a constitución y metadatos en registro.
- Trazabilidad: logs y eventos referencian AVID.

### Derivación criptográfica

El MVP genera AVID como hash determinístico de un payload estable:

- `public_key` del agente (registro)
- `metadata` del agente (nombre, developer_id/owner, capabilities, etc.)
- `constitution_hash` (hash de la constitución activa o su versión)
- `created_at` (timestamp de registro)

Formato:

`AVID-<sha256_hex>`

Propiedades:

- **No forjable** sin conocer el payload exacto.
- **Durable**: AVID se persiste en DB y es **inmutable** tras creación.

### Endpoints de identidad

- `GET /agents/{agent_id}/identity` (protegido con JWT)
- `GET /agents/identity/{avid}` (lookup público “safe” sin secretos)

## Autenticación y sesiones

El MVP usa un modelo de dos etapas:

1. **Registro** (bootstrap): el agente obtiene `agent_id`, `avid` y `public_key` (clave/secret de bootstrap).
2. **Sesión**: el agente obtiene un JWT temporal (access token) para llamar endpoints protegidos.

Esto permite rotar/restringir sesiones sin exponer la clave bootstrap en cada request.

## Gobernanza de acciones

### authorize_action (policy decision point)

`POST /authorize_action` decide si una acción se permite, se niega o requiere verificación/aprobación adicional.

Acciones típicas:

- `execute_shell_command`
- `modify_file`
- `call_external_api`
- `spend_money`

La decisión se toma con:

1. **Constitution Engine** (hard guardrails)
2. **Policies configurables** (reglas dinámicas)
3. **Contexto del agente** (reputación, capabilities, señales)

El resultado siempre se registra (allow/deny/require_approval) con razón y severidad.

### Constitution-as-code (MVP)

El motor constitucional opera como un filtro normativo por encima de la política.

Outputs típicos:

- `COMPLIANT`
- `VIOLATION`
- `UNCERTAIN`

En caso de violación, se genera un “witness record” estructurado (sin exponer secretos) y se publica un evento (SSE).

Nota: el MVP prioriza registros auditables; no implementa “formal verification” todavía.

## Auditoría con integridad: hash-chain (append-only)

Para mitigar manipulación de logs, el MVP mantiene una **hash chain por agente** en:

- `authorization_logs`
- `a2a_messages`

Campos:

- `prev_hash`
- `entry_hash`

Esto permite verificar integridad secuencial (si se borra/reordena un evento, la cadena no valida).

Limitación: no es WORM storage; para no repudio fuerte en producción se recomienda almacenamiento append-only externo.

## Reputación: señal explicable

El MVP evita “un número mágico” como única medida. Se guardan señales derivadas:

- `tasks_success`, `tasks_failure`
- `blocked_action_count`
- `invalid_signature_count`
- `last_task_at`
- métricas de ventana: `last_30d_delta` (derivado)
- `success_rate` (derivado)

### Score efectivo con decay temporal

Se expone `reputation_effective` como una versión con decay:

`reputation_effective = base * exp(-days/30)`

Objetivo: reducir inercia, penalizar inactividad y limitar gaming del score histórico.

## A2A (Agent-to-Agent) y AHP (Apex Handshake Protocol)

### Motivación

Para que un “agent principal” delegue tareas a un “colaborador” se requieren:

- discovery (encontrar candidatos),
- verificación (identidad + reputación + compatibilidad),
- canal auditado (mensajes firmados + logs).

### A2A Messaging (MVP)

Endpoints:

- `POST /a2a/signing_key` (registrar key de firma de mensajes)
- `POST /a2a/send` (enviar mensaje firmado)
- `GET /a2a/inbox` (recibir)

Los mensajes se guardan con hash-chain (ver Auditoría).

### AHP Handshake (MVP)

Protocolo de sesión para acordar:

- identidades (AVID),
- constitución y compatibilidad,
- restricciones de la sesión,
- auditoría.

Endpoints:

- `POST /a2a/handshake/init`
- `GET /a2a/handshake/{session_id}`
- `POST /a2a/handshake/confirm`

### “Pool” de agentes verificados

Para permitir que agentes no-nativos “entren al pool”:

- `GET /agents/verified` (público)
  - filtra por `capability`, `min_reputation`, `active_only`
  - expone AVID, reputación y señales mínimas (sin secretos)

Esto habilita:

- discovery por capacidades,
- selección por reputación,
- coordinación con handshake + mensajes firmados.

## Registry (directorio global) — MVP

El Registry es un endpoint público de descubrimiento:

- `GET /registry/agents`

Incluye:

- AVID, capabilities, reputación, estado activo (si aplica)
- (opcional) **attestations** emitidas por “issuers”

### Attestations (MVP)

En el MVP, las attestations se firman con HMAC usando secretos de issuer (`REGISTRY_ISSUER_KEYS`).

Endpoint:

- `POST /registry/attestations`

Esto es suficiente para demos y early adoption, pero en producción se migra a PKI/DID/VC.

## Observatory (operación) — MVP

Endpoints:

- `GET /observatory/activity` (feed: tasks, auth decisions, a2a)
- `GET /observatory/graph` (nodos/edges desde mensajes y sesiones)
- `GET /observatory/trust_analytics` (analítica simple)

Propósito:

- visibilidad operacional,
- debugging de coordinación,
- señales de riesgo (spikes de denies, firmas inválidas, etc.).

## SDK y adaptadores a frameworks

SDK Python soporta:

- registro, token JWT, log_task, heartbeat
- authorize_action
- A2A (keys, send, inbox)
- AHP (handshake init/confirm)

Adaptadores “gratis” (un archivo por framework) traducen:

- “tool calls” → `authorize_action`
- “task completion” → `log_task`

Objetivo: integración rápida sin forzar dependencias pesadas.

## Dashboard (web) — MVP

Sin framework, pero orientado a “ops”:

- polling a `/dashboard/summary`
- timeline SSE desde `/events` (cuando disponible)
- tabla de agentes verificados + filtros
- top blocked reasons
- enlaces a `/docs` y lookup de identidad por AVID

## Estado actual: qué está implementado vs qué falta

### Implementado (MVP)

- AVID generado y persistido, inmutable.
- Endpoints públicos de discovery: `/agents/public`, `/agents/search`, `/agents/verified`, `/registry/agents`.
- Auth: bootstrap + JWT para rutas protegidas.
- authorize_action con logging y reglas de riesgo.
- A2A messaging + signing key registry + inbox.
- AHP handshake (sesión).
- Audit hash-chain para logs y mensajes.
- Reputation métricas derivadas + score efectivo con decay.
- Observatory endpoints básicos + dashboard web.
- CI (GitHub Actions) con tests y coverage mínimo.

### Limitaciones actuales (honestas)

- **SSE in-memory single-process**: eventos no se comparten entre múltiples instancias; al reiniciar se pierde el stream.
- **Issuer attestations (HMAC)**: suficiente para demo; no es PKI/DID.
- **JWT**: sin refresh tokens avanzados, rotación automática, revocación y key management profesional.
- **Observabilidad**: sin Prometheus/OpenTelemetry/alerts.
- **Anti-sybil avanzado**: no hay stake, proof-of-personhood, ni redes de confianza maduras.

## Roadmap propuesto (free-first)

1. Redis pub/sub para eventos SSE distribuidos (barato, común, fácil).
2. Prometheus metrics + OpenTelemetry tracing (gratis; requiere setup).
3. JWT refresh tokens + revocación + rotación de claves.
4. Attestations con PKI (ECDSA) y/o DID/VC.
5. Reputation graph (peer ratings ponderados + anti-sybil).
6. Contracts + dispute resolution (v3 institucional).

## Apéndice: Superficie de API (resumen)

- Onboarding:
  - `POST /register_agent`
  - `POST /external/register_agent`
  - `POST /auth/token`
- Identity:
  - `GET /agents/{agent_id}/identity` (JWT)
  - `GET /agents/identity/{avid}` (public)
- Ops:
  - `GET /dashboard/summary`
  - `GET /events` (SSE)
  - `GET /observatory/*`
- Directory:
  - `GET /agents/public`, `GET /agents/search`, `GET /agents/verified`
  - `GET /registry/agents`
- Safety:
  - `POST /authorize_action`
- Tasks:
  - `POST /agent/{agent_id}/log_task`
- Heartbeat:
  - `POST /agents/{agent_id}/heartbeat`
- A2A:
  - `POST /a2a/signing_key`
  - `POST /a2a/send`
  - `GET /a2a/inbox`
  - `POST /a2a/handshake/init`
  - `GET /a2a/handshake/{session_id}`
  - `POST /a2a/handshake/confirm`

