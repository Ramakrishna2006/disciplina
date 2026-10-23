# Changelog

## 0.5.0: Disciplina Studio features

- **Playground**: chat with the base, full fine-tuned and LoRA models (temperature, top-k), saved
  and renamable conversations.
- **Tokenizer** and **Embeddings** pages: see tokens and ids, a 2-D map of the learned word vectors,
  nearest neighbours.
- **Dataset** page: search, filter, sort and page through the 40 people.
- **Experiments**: train the whole recipe in the background (one at a time), live progress and loss
  curves, cancel, run again, delete, export CSV, compare 2 to 4. Interrupted runs are detected at
  start-up.
- **Dashboard**, **Activity** with a notification bell, **Settings** (profile, theme, default model,
  password, delete account) and **Help**.
- Pages load on demand (code-splitting); charts are dependency-free SVG with a checked
  colour-blind-safe palette, a legend and a table view.
- Quality: ruff lint in CI, tests run once per change (push to main and pull requests), a real
  training run through the web runner in CI.

## 0.4.0: website shell

React + TypeScript + Tailwind + shadcn/ui frontend: landing page, sign in, sign up, dashboard,
light and dark themes, route guards.

## 0.3.0: accounts

Register, sign in, refresh, sign out with httpOnly cookies, CSRF protection, rate limits, profile,
password change, account deletion, `flask create-admin`.

## 0.2.0: database

Flask app factory, nine tables with SQLAlchemy and migrations, `flask seed`, security headers,
request ids, health check.

## 0.1.0: engine

`llm/experiment.py`: the training pipeline as one function with presets, progress and cancel, shared
by the command line and the web app.
