# persona/benchmarks_kostat_2024q3.py
"""
KOSTAT Household Income & Expenditure Trends (2024 Q3)
- Table 5: Income / Disposable income / Avg propensity to consume by income quintile
- Table 6: Consumption expenditure by COICOP-like categories and quintile

Source: KOSTAT press release PDF (2024년 3/4분기 가계동향조사 결과)
"""

from __future__ import annotations

# ---- COICOP-like categories used in Table 6 ----
COICOP_CATEGORIES = [
    "food_non_alcoholic",      # 식료품·비주류음료
    "alcohol_tobacco",         # 주류·담배
    "clothing_footwear",       # 의류·신발
    "housing_utilities",       # 주거·수도·광열
    "household_goods_services",# 가정용품·가사서비스
    "health",                  # 보건
    "transport",               # 교통
    "communication",           # 통신
    "recreation_culture",      # 오락·문화
    "education",               # 교육
    "restaurants_hotels",      # 음식·숙박
    "other_goods_services",    # 기타 상품·서비스
]

# ---- Quintile benchmark (values are in WON) ----
# Table 5 (thousand won → won):
# income: 1,182 / 2,823 / 4,362 / 6,360 / 11,543 (천원)
# disposable income: 962 / 2,367 / 3,524 / 5,100 / 8,981 (천원)
# avg propensity to consume (%): 134.7 / 78.2 / 76.3 / 71.6 / 56.2
#
# Table 6 (천원): consumption totals and category amounts.
BENCHMARK_2024Q3 = {
    "meta": {
        "name": "KOSTAT_HIET_2024Q3",
        "unit": "WON",
        "note": "Converted from thousand-won tables in KOSTAT PDF.",
    },
    "quintiles": {
        1: {
            "income": 1182_000,
            "disposable_income": 962_000,
            "avg_propensity_to_consume": 134.7,
            "consumption_total": 1296_000,
            "categories": {
                "food_non_alcoholic": 293_000,
                "alcohol_tobacco": 29_000,
                "clothing_footwear": 38_000,
                "housing_utilities": 235_000,
                "household_goods_services": 49_000,
                "health": 151_000,
                "transport": 91_000,
                "communication": 52_000,
                "recreation_culture": 77_000,
                "education": 26_000,
                "restaurants_hotels": 173_000,
                "other_goods_services": 83_000,
            },
        },
        2: {
            "income": 2823_000,
            "disposable_income": 2367_000,
            "avg_propensity_to_consume": 78.2,
            "consumption_total": 1852_000,
            "categories": {
                "food_non_alcoholic": 325_000,
                "alcohol_tobacco": 35_000,
                "clothing_footwear": 65_000,
                "housing_utilities": 289_000,
                "household_goods_services": 75_000,
                "health": 185_000,
                "transport": 168_000,
                "communication": 90_000,
                "recreation_culture": 123_000,
                "education": 63_000,
                "restaurants_hotels": 298_000,
                "other_goods_services": 136_000,
            },
        },
        3: {
            "income": 4362_000,
            "disposable_income": 3524_000,
            "avg_propensity_to_consume": 76.3,
            "consumption_total": 2689_000,
            "categories": {
                "food_non_alcoholic": 411_000,
                "alcohol_tobacco": 43_000,
                "clothing_footwear": 109_000,
                "housing_utilities": 334_000,
                "household_goods_services": 126_000,
                "health": 227_000,
                "transport": 272_000,
                "communication": 127_000,
                "recreation_culture": 193_000,
                "education": 194_000,
                "restaurants_hotels": 456_000,
                "other_goods_services": 196_000,
            },
        },
        4: {
            "income": 6360_000,
            "disposable_income": 5100_000,
            "avg_propensity_to_consume": 71.6,
            "consumption_total": 3653_000,
            "categories": {
                "food_non_alcoholic": 515_000,
                "alcohol_tobacco": 43_000,
                "clothing_footwear": 144_000,
                "housing_utilities": 357_000,
                "household_goods_services": 149_000,
                "health": 286_000,
                "transport": 493_000,
                "communication": 168_000,
                "recreation_culture": 243_000,
                "education": 379_000,
                "restaurants_hotels": 593_000,
                "other_goods_services": 283_000,
            },
        },
        5: {
            "income": 11543_000,
            "disposable_income": 8981_000,
            "avg_propensity_to_consume": 56.2,
            "consumption_total": 5045_000,
            "categories": {
                "food_non_alcoholic": 626_000,
                "alcohol_tobacco": 51_000,
                "clothing_footwear": 216_000,
                "housing_utilities": 417_000,
                "household_goods_services": 241_000,
                "health": 397_000,
                "transport": 536_000,
                "communication": 189_000,
                "recreation_culture": 492_000,
                "education": 602_000,
                "restaurants_hotels": 818_000,
                "other_goods_services": 460_000,
            },
        },
    },
}