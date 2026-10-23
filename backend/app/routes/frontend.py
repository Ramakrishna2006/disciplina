"""
Serves the built React app (frontend/dist, made by `npm run build`) from the same address as
the API. One address means: no CORS, and the login cookies work without any extra settings.

    /assets/...           the JavaScript and CSS files (their names change with every build,
                          so browsers may cache them for a year)
    /favicon.svg etc.     other files in frontend/dist
    anything else         index.html; React decides which page to show (/app, /login, ...)
    /api/...              never handled here: unknown API addresses get the JSON 404

During development you do not need this: `npm run dev` serves the frontend on :5173 and
forwards /api to Flask.
"""
from flask import Blueprint, abort, current_app, send_from_directory

bp = Blueprint("frontend", __name__)


def _dist():
    dist = current_app.config["FRONTEND_DIST"]
    if not (dist / "index.html").is_file():
        abort(404, description="The frontend is not built yet. Run `npm run build` in frontend/, "
                               "or use `npm run dev` during development.")
    return dist


@bp.get("/", defaults={"path": ""})
@bp.get("/<path:path>")
def spa(path):
    if path == "api" or path.startswith("api/"):
        abort(404)                                   # keep API errors as JSON
    dist = _dist()
    if path and (dist / path).is_file():
        response = send_from_directory(dist, path)  # safe: refuses paths that leave dist/
        if path.startswith("assets/"):
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        return response
    response = send_from_directory(dist, "index.html")
    response.headers["Cache-Control"] = "no-cache"   # always check for a new build
    return response
