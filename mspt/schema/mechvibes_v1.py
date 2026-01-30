from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MechvibesV1Schema(BaseModel):
    """Mechvibes config.json schema (version 1) per wiki.

    Notes:
    - `defines` values depend on `key_define_type`.
    - The app may allow undocumented properties; we allow extras.
    """

    model_config = ConfigDict(extra="allow")

    id: str
    name: str

    key_define_type: Literal["single", "multi"]
    includes_numpad: bool
    sound: str

    # For `single`: clip definition [startMs, lengthMs]
    # For `multi`: filename string
    defines: dict[str, list[int] | str]

    version: Literal[1, "1"] = 1

    # Common optional fields seen in packs
    author: str | None = None
    icon: str | None = None
    tags: list[str] = Field(default_factory=list)
