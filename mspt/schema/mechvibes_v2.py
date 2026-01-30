from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MechvibesV2Schema(BaseModel):
    """Mechvibes config.json schema (version 2) per wiki.

    V2 adds key-up support for `key_define_type=multi` via `"<keyCode>-up"`.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    name: str

    key_define_type: Literal["multi"] = "multi"

    # Fallback sounds
    sound: str
    soundup: str

    # Per-key definitions. Keys are keycodes or "<keyCode>-up".
    defines: dict[str, str]

    version: Literal[2, "2"] = 2

    author: str | None = None
    icon: str | None = None
    tags: list[str] = Field(default_factory=list)
