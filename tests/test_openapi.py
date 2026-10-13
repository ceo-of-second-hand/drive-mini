"""The shared contract (common/openapi.json) must describe the API exactly as the server runs it."""
import json

from server.export_openapi import CONTRACT
from server.main import app

REGENERATE = ("common/openapi.json is out of date. Run `python -m server.export_openapi`, "
              "then `cd web && npm run gen:api`, and commit both files.")


def test_contract_matches_the_running_api():
    saved = json.loads(CONTRACT.read_text(encoding="utf-8"))
    assert saved == app.openapi(), REGENERATE


def test_contract_has_the_shapes_the_web_client_uses():
    schemas = json.loads(CONTRACT.read_text(encoding="utf-8"))["components"]["schemas"]
    assert {"FileOut", "UserOut", "TokenOut", "ErrorOut", "RegisterIn"} <= set(schemas)
    assert set(schemas["FileOut"]["required"]) >= {"id", "name", "size", "created_at", "modified_at"}
