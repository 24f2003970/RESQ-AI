import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    city_seed: int = int(os.getenv("RESQ_CITY_SEED", "2026"))
    allowed_origins: tuple[str, ...] = (
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:4173", "http://127.0.0.1:4173",
    )


settings = Settings()
