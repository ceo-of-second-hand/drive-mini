"""Save the API description (OpenAPI) as common/openapi.json: the shared contract with the web client.

FastAPI builds the description from the routes and common/schemas.py. The web client can't import
Python, so its TypeScript types are generated from this file instead (cd web && npm run gen:api).
tests/test_openapi.py fails when the file is out of date.

Run after changing common/schemas.py or a route:  python -m server.export_openapi
"""
import json
from pathlib import Path

from server.main import app

CONTRACT = Path(__file__).resolve().parent.parent / "common" / "openapi.json"


def contract_text() -> str:
    # Sorted keys and fixed indentation, so a change shows up as a small, readable diff.
    return json.dumps(app.openapi(), indent=2, sort_keys=True, ensure_ascii=False) + "\n"


if __name__ == "__main__":
    CONTRACT.write_text(contract_text(), encoding="utf-8", newline="\n")
    print(f"Wrote {CONTRACT}. Now regenerate the web types: cd web && npm run gen:api")
