"""Serving the built React app from the API process, for single-container deploys.

Unknown non-API paths fall back to ``index.html`` so client-side routes such as
``/marketplace`` survive a page refresh.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse


def mount_frontend(app: FastAPI, dist_dir: str) -> None:
    root = Path(dist_dir).resolve()
    index = root / "index.html"
    if not index.is_file():
        raise RuntimeError(f"FRONTEND_DIST_DIR={dist_dir} has no index.html; run `npm run build` first.")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        file = (root / path).resolve()
        if path and file.is_file() and file.is_relative_to(root):
            return FileResponse(file)
        return FileResponse(index)
