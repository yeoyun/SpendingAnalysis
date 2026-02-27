from __future__ import annotations

from typing import Dict, Any, List
import json
import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


def call_llm_json(
    messages: List[Dict[str, str]],
    model: str = "gemini-2.5-flash",
    temperature: float = 0.4,
    timeout_connect: int = 10,
    timeout_read: int = 60,
    max_retries: int = 2,
) -> Dict[str, Any]:
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY가 .env 파일에 설정되지 않았습니다.")

    contents = []
    for m in messages:
        role = m["role"]
        if role == "system":
            role = "user"
        contents.append({"role": role, "parts": [{"text": m["content"]}]})

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={GEMINI_API_KEY}"
    )

    payload = {
        "contents": contents,
        "generationConfig": {
            "temperature": temperature,
            "responseMimeType": "application/json",
        },
    }

    last_err = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(
                url,
                json=payload,
                timeout=(timeout_connect, timeout_read),  # ✅ 핵심
            )
            if resp.status_code != 200:
                raise ValueError(f"Gemini API 호출 실패: {resp.text}")

            data = resp.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            return json.loads(text)

        except Exception as e:
            last_err = e
            if attempt < max_retries:
                time.sleep(0.8 * (attempt + 1))
                continue
            raise ValueError(f"Gemini 호출/파싱 실패 (retries={max_retries}): {last_err}")