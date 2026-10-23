# Disciplina Studio API

All endpoints start with `/api`, take and return JSON, and use one response shape.

```json
{ "data": { "user": { "id": 1, "email": "asha@example.com" } } }
{ "error": { "code": "validation_error", "message": "Please check the highlighted fields.",
             "fields": { "password": "String should have at least 10 characters" } } }
```

`code` is stable (for programs), `message` is for people, `fields` names the form fields that need
fixing. A server error (`500`) also carries `request_id`, which matches the `X-Request-ID` response
header and the server log line.

**Signing in** sets httpOnly cookies. Every `POST`, `PATCH` and `DELETE` that needs a session must
send the `X-CSRF-TOKEN` header, copied from the `csrf_access_token` cookie (for `/api/auth/refresh`:
the `csrf_refresh_token` cookie). Request bodies are limited to 64 KB.

## System

| Method | URL | Auth | Success | Errors |
| --- | --- | --- | --- | --- |
| GET | `/api/health` | none | `200` `{status: "ok", database: "ok", version, environment, training_enabled}` | `503` with `status: "degraded"` if the database is unreachable |

## Accounts

| Method | URL | Auth | Body | Success | Errors (`code`) |
| --- | --- | --- | --- | --- | --- |
| POST | `/api/auth/register` | none | `name` (1–80), `email`, `password` (10–128) | `201` `{user}` + cookies | `400` validation_error, `409` email_taken, `429` rate_limited (3 per hour per IP) |
| POST | `/api/auth/login` | none | `email`, `password` | `200` `{user}` + cookies | `400`, `401` invalid_credentials (same for unknown email and wrong password), `403` account_disabled, `429` (5 per minute, 20 per hour per IP) |
| POST | `/api/auth/refresh` | refresh cookie + `X-CSRF-TOKEN` (refresh) | none | `200` `{user}` + new access cookie | `401` |
| POST | `/api/auth/logout` | cookies + `X-CSRF-TOKEN` | none | `200` `{signed_out: true}`, cookies cleared, both tokens revoked (works with an expired access token) | `401` csrf_failed |
| GET | `/api/auth/me` | signed in | none | `200` `{user}` | `401` |
| PATCH | `/api/users/me` | signed in + CSRF | any of `name`, `theme` (system, light, dark), `default_model` (base, full, lora), `default_temperature` (0–2) | `200` `{user}` | `400` |
| POST | `/api/users/me/password` | signed in + CSRF | `current_password`, `new_password` (10–128, different) | `200` `{user}` + new cookies; every other device is signed out | `400` (field `current_password` if it is wrong) |
| DELETE | `/api/users/me` | signed in + CSRF | `password` | `204`, cookies cleared, all your data deleted | `400` |

A user object: `id, email, name, role, theme, default_model, default_temperature, created_at, last_login_at`.
It never includes the password hash. Fields not listed for a request are refused (`400`), so a request
cannot set `role` or `email` by adding them to the body.

### `401` codes, and what the frontend does

| `code` | Meaning | Frontend |
| --- | --- | --- |
| `not_signed_in` | no login cookie | go to the sign-in page |
| `token_expired` | the 30-minute access token ran out | call `/api/auth/refresh` once, then retry the request |
| `token_revoked` | signed out, or the password was changed on another device | go to the sign-in page |
| `invalid_token` | damaged or forged cookie | go to the sign-in page |
| `account_unavailable` | the account was disabled or deleted | go to the sign-in page |
| `csrf_failed` | missing or wrong `X-CSRF-TOKEN` header | reload, then retry |

Endpoints for chat, the dataset, experiments and the dashboard are added in stage 5.
