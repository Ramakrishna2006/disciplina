# Disciplina Studio: frontend

React 19 + TypeScript + Vite 8, styled with Tailwind CSS 4 and shadcn/ui components.
It talks to the Flask API in [`../backend`](../backend/README.md) through one file,
[`src/services/api.ts`](src/services/api.ts).

```powershell
cd frontend
npm install          # once (and after package.json changes)
npm run dev          # http://localhost:5173  (Flask must run on :5000; /api is forwarded to it)
npm test             # component, form and API-client tests (Vitest)
npm run build        # type-check, then build into frontend/dist (served by Flask)
```

| Path | What it is |
| --- | --- |
| `index.html`, `src/main.tsx` | The page and the code that starts React |
| `src/App.tsx` | Every page address and who may see it |
| `src/index.css` | Design tokens: every colour, radius and font, for light and dark |
| `src/services/api.ts` | The only code that calls the backend: CSRF header, refresh-and-retry, errors |
| `src/hooks/useAuth.tsx` | Who is signed in (asks the server; no token is ever stored in JavaScript) |
| `src/hooks/useTheme.tsx` | Light, dark or system theme |
| `src/lib/schemas.ts` | Form rules (Zod), the same as the backend's |
| `src/components/ui/` | shadcn/ui components, copied in so we can read and change them |
| `src/components/` | Our components: form field, theme switch, user menu, route guards |
| `src/layouts/` | The public layout and the app layout (sidebar + top bar) |
| `src/pages/` | One file per page |
| `public/theme-init.js` | Applies dark mode before the page is drawn (no white flash) |
| `components.json` | shadcn settings: `npx shadcn@latest add <component>` puts new components in `src/components/ui/` |

**Two servers in development, one in production.** `npm run dev` serves the React app on :5173
and forwards every `/api` request to Flask on :5000, so the browser sees a single address and the
login cookies just work. After `npm run build`, Flask serves `frontend/dist` itself on :5000.

**Settings:** nothing secret belongs in the frontend. Anything in a `VITE_` variable is visible
to every visitor, so API keys and passwords stay in `backend/.env`.
