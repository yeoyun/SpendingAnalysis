from __future__ import annotations

from typing import Dict, Any, List
import json
import os
import requests
from dotenv import load_dotenv

# .env 로드
load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def call_llm_json(
    messages: List[Dict[str, str]],
    model: str = "gemini-2.5-flash",
    temperature: float = 0.4,
    timeout: int = 60,
) -> Dict[str, Any]:

    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 .env 파일에 설정되지 않았습니다.")

    # OpenAI messages → Gemini 형식 변환
    contents = []
    for m in messages:
        role = m["role"]
        if role == "system":
            role = "user"  # Gemini는 system role 없음
        contents.append({
            "role": role,
            "parts": [{"text": m["content"]}]
        })

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "responseMimeType": "application/json"
        }
    }

    resp = requests.post(url, json=payload, timeout=timeout)

    if resp.status_code != 200:
        raise ValueError(f"Gemini API 호출 실패: {resp.text}")

    data = resp.json()

    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
        return json.loads(text)
    except Exception as e:
        raise ValueError(f"Gemini 응답 JSON 파싱 실패: {e}\n원문:\n{data}")