"""Export schema artifacts without starting a server. Run from backend/."""
import json
from pathlib import Path
from app.main import app
from app.schemas import CityState
from app.city_service import generate_city

target = Path(__file__).resolve().parents[1] / "frontend" / "src" / "api"
target.mkdir(parents=True, exist_ok=True)
(target / "openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n", encoding="utf-8")
(target / "city.schema.json").write_text(json.dumps(CityState.model_json_schema(), indent=2) + "\n", encoding="utf-8")
fixtures = target.parent / "test" / "fixtures"
fixtures.mkdir(parents=True, exist_ok=True)
(fixtures / "city.json").write_text(json.dumps(generate_city().model_dump(), indent=2) + "\n", encoding="utf-8")
