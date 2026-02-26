# persona/personas.py
from __future__ import annotations
from dataclasses import dataclass

# -----------------------------
# 스타일 인덱스 규칙 (1~4)
# 1=충동(impulse)  2=감성(emotional)  3=안정(stable)  4=전략(strategic)
# 레벨 인덱스 규칙 (1~4)
# L1~L4 -> 1~4
# -----------------------------

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
    subtitle: str
    animal: str
    level: str      # "L1"~"L4"
    style: str      # "impulse"/"emotional"/"stable"/"strategic"
    tone_hint: str

    @property
    def image_path(self) -> str:
        """data/textures/img_{levelIndex}_{styleIndex}.png"""
        li = LEVEL_INDEX[self.level]
        si = STYLE_INDEX[self.style]
        return f"data/textures/img_{li}_{si}.png"


# 16개 페르소나(레벨×스타일) 정의
PERSONA_16: dict[str, Persona] = {
    # L1
    "L1_impulse": Persona("L1_impulse", "🔥 오늘만 사는 불나방형", "지금의 기분이 예산보다 먼저예요.", "여우", "L1", "impulse", "공감+아주 작은 규칙부터"),
    "L1_emotional": Persona("L1_emotional", "🎀 감정 따라 지갑여는 요정형", "기분 전환이 소비로 연결돼요.", "토끼", "L1", "emotional", "감정 트리거→대체 행동 제안"),
    "L1_stable": Persona("L1_stable", "🏠 현실은 알지만 약한 마음형", "알지만 흔들리는 순간이 있어요.", "곰", "L1", "stable", "현실적 상한+경보 규칙 강조"),
    "L1_strategic": Persona("L1_strategic", "📉 계획은 세우는 즉흥러형", "플랜은 있는데 실행이 흔들려요.", "강아지", "L1", "strategic", "루틴을 초간단으로"),

    # L2
    "L2_impulse": Persona("L2_impulse", "🛍 기분파 쇼핑러형", "필요보다 '예쁨'이 먼저예요.", "고양이", "L2", "impulse", "주간 상한/보류 규칙"),
    "L2_emotional": Persona("L2_emotional", "☕ 소확행 수집가형", "작은 행복이 자주 쌓여요.", "햄스터", "L2", "emotional", "카페/소확행 예산을 주간으로"),
    "L2_stable": Persona("L2_stable", "🍱 월급 지키는 생활러형", "생활비를 안정적으로 관리해요.", "거북이", "L2", "stable", "고정비 최적화/자동화"),
    "L2_strategic": Persona("L2_strategic", "📒 기록은 하지만 흔들리는 플래너형", "기록은 성실한데 가끔 삐끗해요.", "판다", "L2", "strategic", "기록→규칙 자동화로 연결"),

    # L3
    "L3_impulse": Persona("L3_impulse", "🎯 가끔 폭주하는 실속러형", "대체로 실속, 가끔 큰 한 방.", "아기호랑이", "L3", "impulse", "폭주만 차단(단건/주간 경보)"),
    "L3_emotional": Persona("L3_emotional", "✈️ 경험을 사랑하는 여행가형", "경험에 투자하는 타입이에요.", "펭귄", "L3", "emotional", "경험 예산은 살리고 최적화"),
    "L3_stable": Persona("L3_stable", "🧱 철벽 예산러형", "흔들리지 않는 한도 관리.", "고슴도치", "L3", "stable", "유지 전략 + 미세 조정"),
    "L3_strategic": Persona("L3_strategic", "📈 자산 키우는 준비생형", "지출을 자산으로 바꾸는 중.", "다람쥐", "L3", "strategic", "저축/목표 트래킹"),

    # L4
    "L4_impulse": Persona("L4_impulse", "🎲 계산된 일탈러형", "일탈도 예산 안에서 즐겨요.", "늑대", "L4", "impulse", "일탈 예산 슬롯 분리"),
    "L4_emotional": Persona("L4_emotional", "💎 가치소비 큐레이터형", "비싸도 납득되면 OK.", "백조", "L4", "emotional", "가치 소비 체크리스트"),
    "L4_stable": Persona("L4_stable", "🏦 현금흐름 지배자형", "흐름을 통제하는 안정감.", "코끼리", "L4", "stable", "현금흐름/비상금 최적화"),
    "L4_strategic": Persona("L4_strategic", "👑 재무 마스터형", "전체 구조를 설계하는 타입.", "사자", "L4", "strategic", "목표 기반 예산/리밸런싱"),
}