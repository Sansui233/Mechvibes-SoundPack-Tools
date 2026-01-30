from __future__ import annotations

from typing import Annotated, Literal, TypeAlias

from pydantic import BaseModel, Field

TimingPair: TypeAlias = tuple[float, float]
TimingList: TypeAlias = Annotated[list[TimingPair], Field(min_length=1, max_length=2)]


KeyName: TypeAlias = Literal[
    "AltLeft",
    "ArrowDown",
    "ArrowLeft",
    "ArrowRight",
    "ArrowUp",
    "Backquote",
    "Backslash",
    "Backspace",
    "BracketLeft",
    "BracketRight",
    "CapsLock",
    "Comma",
    "ControlLeft",
    "Delete",
    "Digit0",
    "Digit1",
    "Digit2",
    "Digit3",
    "Digit4",
    "Digit5",
    "Digit6",
    "Digit7",
    "Digit8",
    "Digit9",
    "End",
    "Enter",
    "Equal",
    "Escape",
    "F1",
    "F10",
    "F11",
    "F12",
    "F2",
    "F3",
    "F4",
    "F5",
    "F6",
    "F7",
    "F8",
    "F9",
    "Home",
    "Insert",
    "KeyA",
    "KeyB",
    "KeyC",
    "KeyD",
    "KeyE",
    "KeyF",
    "KeyG",
    "KeyH",
    "KeyI",
    "KeyJ",
    "KeyK",
    "KeyL",
    "KeyM",
    "KeyN",
    "KeyO",
    "KeyP",
    "KeyQ",
    "KeyR",
    "KeyS",
    "KeyT",
    "KeyU",
    "KeyV",
    "KeyW",
    "KeyX",
    "KeyY",
    "KeyZ",
    "Minus",
    "NumLock",
    "Numpad0",
    "Numpad1",
    "Numpad2",
    "Numpad3",
    "Numpad4",
    "Numpad5",
    "Numpad6",
    "Numpad7",
    "Numpad8",
    "Numpad9",
    "NumpadAdd",
    "NumpadDecimal",
    "NumpadDivide",
    "NumpadEnter",
    "NumpadMultiply",
    "NumpadSubtract",
    "PageDown",
    "PageUp",
    "Pause",
    "Period",
    "PrintScreen",
    "Quote",
    "ScrollLock",
    "Semicolon",
    "ShiftLeft",
    "ShiftRight",
    "Slash",
    "Space",
    "Tab",
]


class Options(BaseModel):
    random_pitch: bool = False
    recommended_volume: float = 1.0


class DefinitionKey(BaseModel):
    timing: TimingList


class MVDXSchema(BaseModel):
    audio_file: str
    config_version: str
    created_at: str
    definition_method: str = "single"
    author: str | None = None
    icon: str | None = None
    id: str
    name: str
    options: Options = Field(default_factory=Options)
    tags: list[str] = Field(default_factory=list)
    definitions: dict[KeyName, DefinitionKey]
