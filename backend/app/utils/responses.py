"""Every successful API response has the same shape: {"data": ..., "meta": {...}}."""
from flask import jsonify


def ok(data=None, status=200, meta=None):
    body = {"data": data}
    if meta is not None:
        body["meta"] = meta
    return jsonify(body), status
