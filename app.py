"""Web server: serves the dashboard and refreshes data in the background."""
import json
import os
import threading
import time

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse

import scanner

HERE = os.path.dirname(os.path.abspath(__file__))
app = FastAPI()


def refresh_loop():
    while True:
        try:
            scanner.run()
        except Exception as e:  # keep the loop alive on network/data errors
            print("refresh failed:", e)
        time.sleep(scanner.load_config()["refresh_minutes"] * 60)


@app.on_event("startup")
def start_refresher():
    threading.Thread(target=refresh_loop, daemon=True).start()


@app.get("/api/data")
def data():
    if not os.path.exists(scanner.DATA_PATH):
        return JSONResponse({"updated": None, "gauges": [], "stocks": [], "errors": [], "rules": {}})
    with open(scanner.DATA_PATH) as f:
        return JSONResponse(json.load(f))


@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"))
