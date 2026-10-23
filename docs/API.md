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

## Lists and pages

Lists answer `{"data": [...], "meta": {"page": 1, "per_page": 20, "total": 57, "pages": 3}}`.
Use `?page=` and `?per_page=` (1–100). Unknown query parameters are refused (`400`), like unknown
body fields. A page after the last one is an empty list.

Everything below needs you to be signed in (`401` otherwise). Ids of things that are not yours
answer `404`, exactly like ids that do not exist.

## App settings

| Method | URL | Auth | Success |
| --- | --- | --- | --- |
| GET | `/api/config` | none | `{app, version, training_enabled, presets: [{name, pretrain_steps, finetune_steps, minutes}], limits, models: [{id, label, description}]}` |

`/api/health` also reports `models`: `loaded` (in memory), `available` (files present, loaded on first
use) or `missing` (run `python main.py train`).

## Playground

| Method | URL | Body / query | Success | Errors (`code`) |
| --- | --- | --- | --- | --- |
| POST | `/api/chat` | `message` (1–500), `model` (base, full, lora; default lora), `temperature` (0–2), `top_k` (1–100 or null), `session_id` (optional: continue a conversation) | `200` `{session_id, reply, latency_ms, tokens, messages: [question, answer]}` | `400`, `404` (session not yours), `429` (30 per minute per user), `503` models_unavailable |
| GET | `/api/chat/sessions` | `page`, `per_page` | `200` list of `{id, title, model, created_at, updated_at, message_count, last_message}`, newest first | |
| GET | `/api/chat/sessions/<id>` | | `200` `{session, messages}` | `404` |
| PATCH | `/api/chat/sessions/<id>` | `title` (1–80) | `200` `{session}` | `400`, `404` |
| DELETE | `/api/chat/sessions/<id>` | | `204` (its messages too) | `404` |
| POST | `/api/tokenize` | `text` (0–1000) | `200` `{tokens: [{id, text}], count, characters, chars_per_token}` | `400` |
| GET | `/api/embeddings` | `model` (default base) | `200` `{model, points: [{word, category, x, y}]}`; x and y from 0 to 1 | |
| GET | `/api/embeddings/neighbors` | `word` (1–40), `k` (1–10, default 5), `model` | `200` `{word, model, neighbors: [{word, similarity}]}` | `404` not_a_token (the word is not one token) |

A new conversation gets the first 60 characters of its first message as its title. The base model
continues the text you send; the fine-tuned models get it as a question (`Q: ...\nA:`).

## Dataset

| Method | URL | Query | Success |
| --- | --- | --- | --- |
| GET | `/api/people` | `search` (name, city, job or food contains), `city`, `job`, `food`, `split` (fine-tuning, held-out), `sort` (name, city, job, food, split), `order` (asc, desc), `page`, `per_page` (default 40) | `200` list of `{id, name, city, job, food, split}` |
| GET | `/api/people/facets` | | `200` `{city: [{value, count}], job, food, split, total}` |

## Experiments

| Method | URL | Body / query | Success | Errors (`code`) |
| --- | --- | --- | --- | --- |
| GET | `/api/experiments` | `scope` (mine, public), `status`, `replay` (true, false), `search`, `sort` (created_at, name, status, qa_heldout), `order`, `page`, `per_page` | `200` list of experiments | `400` |
| POST | `/api/experiments` | `name` (1–80), `description` (0–500), `pretrain_steps` (50–5000), `finetune_steps` (20–2000), `lora_rank` (1–32, default 8), `replay` (default true), `seed` (0–9999) | `202` `{experiment}` with status `queued`; `meta.queue_position` | `400`, `403` training_disabled, `409` experiment_active (you already have one queued or training), `429` (10 per hour per user) |
| GET | `/api/experiments/<id>` | | `200` `{experiment, queue_position?}` | `404` |
| PATCH | `/api/experiments/<id>` | any of `name`, `description`, `is_public` (admins only; completed experiments only) | `200` `{experiment}` | `400`, `403` (not the owner, or admin_only), `404`, `409` not_completed |
| DELETE | `/api/experiments/<id>` | | `204` (metrics, results and model files too) | `403`, `404`, `409` experiment_running (cancel it first) |
| POST | `/api/experiments/<id>/cancel` | | `200` `{experiment}`: a queued one is cancelled at once, a running one within a second | `403`, `404`, `409` not_active |
| GET | `/api/experiments/<id>/metrics` | `after_id` (only points newer than this id) | `200` list of `{id, phase (pretrain, full, lora), step, train_loss, val_loss}`; `meta: {last_id, status, progress, phase, complete}` | `404` |
| GET | `/api/experiments/<id>/log` | | `200` `{lines}` (the last 200 lines of the training log) | `404` |
| GET | `/api/experiments/<id>/export.csv` | | `200` a CSV file: the loss curves, then the scores | `404` |
| GET | `/api/experiments/compare` | `ids` (2–4, comma-separated) | `200` `{experiments, metrics: {"<id>": [...]}}` | `400`, `404` |

An experiment: `id, name, description, status, is_public, owner_id, owner_name, pretrain_steps,
finetune_steps, lora_rank, replay, seed, phase, progress (0–1), error, cancel_requested, created_at,
started_at, finished_at, is_owner, results: [{model, qa_seen, qa_heldout, completion, perplexity,
trainable_params}]`.

**Lifecycle:** `queued` → `running` → `completed`, `failed` or `cancelled`. If the server stops during
training the experiment becomes `interrupted` at the next start (it cannot be resumed; start it again).
One experiment trains at a time, oldest first. While it runs, the page polls `metrics?after_id=` every
2 seconds. When `meta.complete` turns true, it loads the metrics once more from 0, because the finished
run adds validation losses to earlier pre-training points.

## Dashboard and activity

| Method | URL | Body / query | Success |
| --- | --- | --- | --- |
| GET | `/api/dashboard` | | `200` `{kpis: {experiments, completed, active, chats, questions, best_heldout}, latest: {experiment, metrics} or null, active_experiment, activity (5 newest), unread}` |
| GET | `/api/activity` | `unread` (true: unread only), `page`, `per_page` | `200` list of `{id, type, message, experiment_id, created_at, read_at}`; `meta.unread` |
| POST | `/api/activity/read` | `ids` (optional list; without it: everything) | `200` `{marked, unread}` (other users' events are never touched) |

Event types: `experiment.completed`, `experiment.failed`, `experiment.cancelled`, `experiment.interrupted`.
