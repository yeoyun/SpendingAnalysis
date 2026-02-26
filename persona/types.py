from __future__ import annotations

from dataclasses import dataclass


STYLE_INDEX = {
    "impulse": 1,
    "emotional": 2,
    "stable": 3,
    "strategic": 4,
}

LEVEL_INDEX = {
    "L1": 1,
    "L2": 2,
    "L3": 3,
    "L4": 4,
}


@dataclass(frozen=True)
class Persona:
    key: str
    title: str
    one_liner: str
    animal: str
    level: str           # L1~L4
    style: str           # impulse/emotional/stable/strategic
    coach_hint: str

    @property
    def image_path(self) -> str:
        """
        이미지 경로 규칙:
        data/textures/img_{levelIndex}_{styleIndex}.png
        예) L2_emotional -> img_2_2.png
        """
        lv = LEVEL_INDEX.get(self.level, 1)
        st = STYLE_INDEX.get(self.style, 1)
        return f"data/textures/img_{lv}_{st}.png"


@dataclass(frozen=True)
class PersonaResult:
    persona_key: str
    estimated_income: int
    signals: dict