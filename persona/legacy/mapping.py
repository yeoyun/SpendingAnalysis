# persona/mapping.py
from __future__ import annotations

# 사용자(category_lv1) -> COICOP-like category mapping

DEFAULT_CATEGORY_TO_COICOP = {
    # 식비 계열
    "식비": "food_non_alcoholic",
    "커피/디저트": "restaurants_hotels",
    "카페": "restaurants_hotels",
    "외식": "restaurants_hotels",
    "음식": "restaurants_hotels",

    # 주거/생활
    "주거/통신": "housing_utilities",
    "주거": "housing_utilities",
    "공과금": "housing_utilities",
    "관리비": "housing_utilities",
    "통신": "communication",
    "구독": "other_goods_services",

    # 교통
    "교통": "transport",
    "차량": "transport",

    # 쇼핑/패션
    "패션/쇼핑": "clothing_footwear",
    "쇼핑": "clothing_footwear",
    "패션": "clothing_footwear",

    # 건강
    "의료/건강": "health",
    "의료": "health",
    "건강": "health",

    # 문화/여가
    "문화/여가": "recreation_culture",
    "취미": "recreation_culture",
    "여행": "recreation_culture",
    "오락": "recreation_culture",

    # 교육
    "교육": "education",

    # 기타
    "생활": "household_goods_services",
    "생필품": "household_goods_services",
    "기타": "other_goods_services",
    "선물": "other_goods_services",

    # 주류/담배
    "주류/담배": "alcohol_tobacco",
    "술": "alcohol_tobacco",
    "담배": "alcohol_tobacco",
}

def map_to_coicop(category_lv1: str) -> str:
    """Map user's category_lv1 to coicop category key. Unknown -> other_goods_services."""
    if not category_lv1:
        return "other_goods_services"
    return DEFAULT_CATEGORY_TO_COICOP.get(category_lv1.strip(), "other_goods_services")