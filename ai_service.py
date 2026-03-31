from __future__ import annotations

import json
import re
from typing import Any

from openai import OpenAI

from config import (
    BABY_CATEGORY_LABELS,
    FAMILY_CONTEXT_KEYS,
    MOTHER_CATEGORY_LABELS,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    PREGNANCY_CATEGORY_LABELS,
)

SYSTEM_PROMPT = """
あなたは家族向けの育児・出産準備アシスタントです。
目的は、今回の相談に対して、今やるべきこと・注意点・考え方を、実用的かつ詳しく整理することです。
医療判断を断定せず、安全側に配慮してください。
回答は日本語で返してください。

最重要ルール:
- 今回の相談内容を主役にして答える
- 過去の相談内容や過去の回答は、今回の判断の参考にしてよい
- ただし、過去の回答全文をそのまま再掲しない
- 「前回から継続している点」「これまでの傾向」は必要な場合のみ短く要約して触れる
- 浅い要約で終わらず、理由や背景も説明する
- 家族が読んで理解しやすい言葉で書く
- 危険そうな症状がある場合は、最初に産院・受診相談の優先度を明示する
- 不安を煽りすぎず、行動が明確になるようにする
- 医療・診断の断定はしない
- 記録・症状・生活状況・タスク状況が判断に影響するなら、それも踏まえて整理する

出力構成:
1. まず結論
2. そう考える理由
3. 今やること
4. 様子を見るポイント
5. 受診・産院連絡を検討する目安

回答方針:
- 必要なら各項目をしっかり詳しく書く
- 箇条書きだけで終わらず、要所では文章でも補足する
- 「なぜそうするのか」が分かるようにする
- 緊急性が低いときも、様子見の観察ポイントを具体化する
- 緊急性が高そうなときは、その根拠と優先行動を先に示す
""".strip()

FAMILY_CONTEXT_UPDATE_PROMPT = """
あなたは家族OSの状態更新アシスタントです。
相談内容とAI回答から、この家族の「現在地」として長めに保持したい情報だけを抽出してください。

出力は必ずJSONオブジェクトのみ。
キーは次の中から必要なものだけ使ってください。
不要なら空文字にしてください。

- current_concerns
- ongoing_symptoms
- recent_purchase_topics
- purchase_status
- mother_recent_meals
- mother_condition_summary
- pending_preparations
- important_notes

ルール:
- 今後の相談でも役立つ内容だけを残す
- 一時的で細かすぎる表現は避ける
- 同じ内容の言い換えを重複させない
- 1項目は短く要約する
- 医療断定はしない
- JSON以外は出力しない
""".strip()

QUICK_INPUT_PROMPT_TEMPLATE = """
あなたは家族OSの音声クイック入力解析アシスタントです。
ユーザーの自由入力文を、家族OSに保存しやすい構造化JSONへ変換してください。

出力は必ずJSONのみ。
説明文やコードブロックは不要です。

allowed_targets:
{allowed_targets_text}

allow_multi:
{allow_multi_text}

必ず次の形式で返してください。

{{
  "mode": "single または multi",
  "records": [
    {{
      "target": "baby_logs / mother_logs / pregnancy_logs",
      "category": "",
      "subtype": "",
      "status": "",
      "value": "",
      "unit": "",
      "detail": "",
      "memo": ""
    }}
  ]
}}

ルール:
- allow_multi が false の場合は records は最大1件
- allow_multi が true の場合のみ複数件にしてよい
- target は allowed_targets の中から選ぶ
- baby_logs の category は次のみ:
  feeding, milk, pee, poop, sleep, temperature, symptom
- mother_logs の category は次のみ:
  sleep, meal, pain, bleeding, mood, medicine, hospital
- pregnancy_logs の category は次のみ:
  pregnancy, mother_health, hospital, preparation, symptom
- baby_logs では主に subtype / value / unit / memo を使う
- mother_logs では主に status / value / unit / memo を使う
- pregnancy_logs では主に status / detail / memo を使う
- 不明な値は空文字にする
- 推測しすぎない
- 時刻の解釈はしない
- 体温は unit を ℃
- ミルクは unit を ml
- 回数は unit を 回
- 分数は unit を 分
- うんち/おしっこは value を 1、unit を 回 に寄せてよい
- 「張り」「破水っぽい」「出血」など妊娠後期の症状は pregnancy_logs を優先
- 「腰痛」「眠れていない」「食欲なし」など母体の体調は mother_logs を優先
- 「母乳10分」「ミルク80ml」「おしっこ」「うんち」「体温37.2」などは baby_logs を優先

解析対象:
{user_input}
""".strip()


def get_openai_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY が未設定です。secrets.toml を確認してください。")
    return OpenAI(api_key=OPENAI_API_KEY)


def extract_response_text(response) -> str:
    text_parts: list[str] = []

    try:
        output = getattr(response, "output", None)
        if output:
            for item in output:
                content = getattr(item, "content", None)
                if not content:
                    continue
                for c in content:
                    text_val = getattr(c, "text", None)
                    if text_val:
                        text_parts.append(str(text_val))
    except Exception:
        pass

    if text_parts:
        return "\n".join(text_parts).strip()

    try:
        output_text = getattr(response, "output_text", "")
        if output_text:
            return str(output_text).strip()
    except Exception:
        pass

    return "回答の取得に失敗しました。もう一度試してください。"


def build_consultation_prompt(user_input: str, context_text: str) -> str:
    return f"""
{SYSTEM_PROMPT}

相談内容:
{user_input}

参考コンテキスト:
{context_text}
""".strip()


def generate_consultation_answer(user_input: str, context_text: str) -> str:
    if not str(user_input).strip():
        return "相談内容が空です。内容を入れてからもう一度試してください。"

    if not OPENAI_API_KEY:
        return "OPENAI_API_KEY が未設定です。secrets.toml を確認してください。"

    client = get_openai_client()
    prompt = build_consultation_prompt(
        user_input=user_input.strip(),
        context_text=str(context_text).strip(),
    )

    response = client.responses.create(
        model=OPENAI_MODEL,
        input=prompt,
    )
    return extract_response_text(response)


def _normalize_family_context_updates(raw: dict) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key in FAMILY_CONTEXT_KEYS.keys():
        value = raw.get(key, "")
        normalized[key] = str(value).strip() if value is not None else ""
    return normalized


def _extract_json_object_text(text: str) -> str:
    raw = str(text).strip()
    if not raw:
        return ""

    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and start < end:
        return raw[start : end + 1].strip()

    return raw


def generate_family_context_updates(
    user_input: str,
    answer_text: str,
    current_context_text: str,
) -> dict[str, str]:
    if not OPENAI_API_KEY:
        return {}

    if not str(user_input).strip() or not str(answer_text).strip():
        return {}

    client = get_openai_client()

    prompt = f"""
{FAMILY_CONTEXT_UPDATE_PROMPT}

現在の家族コンテキスト:
{current_context_text}

今回の相談内容:
{user_input}

今回のAI回答:
{answer_text}
""".strip()

    try:
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=prompt,
        )
        text = extract_response_text(response)
        json_text = _extract_json_object_text(text)
        parsed = json.loads(json_text)

        if not isinstance(parsed, dict):
            return {}

        return _normalize_family_context_updates(parsed)

    except Exception as exc:
        return {
            "important_notes": f"family_context更新失敗: {str(exc)}"
        }


def _extract_json_any_text(text: str) -> str:
    raw = str(text).strip()
    if not raw:
        return ""

    fence_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw, flags=re.DOTALL)
    if fence_match:
        return fence_match.group(1).strip()

    obj_start = raw.find("{")
    obj_end = raw.rfind("}")
    arr_start = raw.find("[")
    arr_end = raw.rfind("]")

    if obj_start != -1 and obj_end != -1 and obj_start < obj_end:
        return raw[obj_start : obj_end + 1].strip()

    if arr_start != -1 and arr_end != -1 and arr_start < arr_end:
        return raw[arr_start : arr_end + 1].strip()

    return raw


def _coerce_value(value: Any) -> Any:
    if value is None:
        return ""

    if isinstance(value, (int, float)):
        return value

    text = str(value).strip()
    if not text:
        return ""

    normalized = text.replace("．", ".").replace("。", ".").replace(",", "")
    if re.fullmatch(r"-?\d+", normalized):
        try:
            return int(normalized)
        except Exception:
            return text

    if re.fullmatch(r"-?\d+\.\d+", normalized):
        try:
            return float(normalized)
        except Exception:
            return text

    return text


def _normalize_quick_input_record(
    raw: dict[str, Any],
    allowed_targets: list[str] | None = None,
) -> dict[str, Any]:
    baby_categories = set(BABY_CATEGORY_LABELS.keys())
    mother_categories = set(MOTHER_CATEGORY_LABELS.keys())
    pregnancy_categories = set(PREGNANCY_CATEGORY_LABELS.keys())

    target = str(raw.get("target", "")).strip()
    if allowed_targets:
        allowed_set = {str(x).strip() for x in allowed_targets}
        if target not in allowed_set:
            target = ""

    category = str(raw.get("category", "")).strip()
    subtype = str(raw.get("subtype", "")).strip()
    status = str(raw.get("status", "")).strip()
    unit = str(raw.get("unit", "")).strip()
    detail = str(raw.get("detail", "")).strip()
    memo = str(raw.get("memo", "")).strip()
    value = _coerce_value(raw.get("value", ""))

    if target == "baby_logs":
        if category not in baby_categories:
            category = ""
        status = ""
        detail = ""
    elif target == "mother_logs":
        if category not in mother_categories:
            category = ""
        subtype = ""
        detail = ""
    elif target == "pregnancy_logs":
        if category not in pregnancy_categories:
            category = ""
        subtype = ""
        value = ""
        unit = ""
    else:
        return {
            "target": "",
            "category": "",
            "subtype": "",
            "status": "",
            "value": "",
            "unit": "",
            "detail": "",
            "memo": "",
        }

    return {
        "target": target,
        "category": category,
        "subtype": subtype,
        "status": status,
        "value": value,
        "unit": unit,
        "detail": detail,
        "memo": memo,
    }


def _has_meaningful_record(record: dict[str, Any]) -> bool:
    target = str(record.get("target", "")).strip()
    category = str(record.get("category", "")).strip()
    subtype = str(record.get("subtype", "")).strip()
    status = str(record.get("status", "")).strip()
    value = record.get("value", "")
    unit = str(record.get("unit", "")).strip()
    detail = str(record.get("detail", "")).strip()
    memo = str(record.get("memo", "")).strip()

    if not target or not category:
        return False

    if target == "baby_logs":
        return any(
            [
                subtype,
                str(value).strip() if value != "" else "",
                unit,
                memo,
            ]
        ) or category in {"pee", "poop"}

    if target == "mother_logs":
        return any(
            [
                status,
                str(value).strip() if value != "" else "",
                unit,
                memo,
            ]
        )

    if target == "pregnancy_logs":
        return any(
            [
                status,
                detail,
                memo,
            ]
        )

    return False


def parse_quick_input_text(
    user_input: str,
    allow_multi: bool = False,
    allowed_targets: list[str] | None = None,
) -> dict[str, Any]:
    input_text = str(user_input).strip()
    if not input_text:
        return {
            "ok": False,
            "error": "入力が空です。",
            "mode": "single",
            "records": [],
        }

    if not OPENAI_API_KEY:
        return {
            "ok": False,
            "error": "OPENAI_API_KEY が未設定です。secrets.toml を確認してください。",
            "mode": "single",
            "records": [],
        }

    allowed = allowed_targets[:] if allowed_targets else ["baby_logs", "mother_logs", "pregnancy_logs"]
    allowed_targets_text = ", ".join(allowed)
    allow_multi_text = "true" if allow_multi else "false"

    prompt = QUICK_INPUT_PROMPT_TEMPLATE.format(
        allowed_targets_text=allowed_targets_text,
        allow_multi_text=allow_multi_text,
        user_input=input_text,
    )

    try:
        client = get_openai_client()
        response = client.responses.create(
            model=OPENAI_MODEL,
            input=prompt,
        )
        text = extract_response_text(response)
        json_text = _extract_json_any_text(text)
        parsed = json.loads(json_text)

        raw_records: list[dict[str, Any]] = []
        mode = "multi" if allow_multi else "single"

        if isinstance(parsed, dict):
            mode = str(parsed.get("mode", mode)).strip() or mode
            records = parsed.get("records", [])
            if isinstance(records, list):
                raw_records = [item for item in records if isinstance(item, dict)]
            elif isinstance(records, dict):
                raw_records = [records]
            else:
                if any(k in parsed for k in ["target", "category", "subtype", "status", "value", "unit", "detail", "memo"]):
                    raw_records = [parsed]
        elif isinstance(parsed, list):
            raw_records = [item for item in parsed if isinstance(item, dict)]

        normalized_records = [
            _normalize_quick_input_record(item, allowed_targets=allowed)
            for item in raw_records
        ]
        normalized_records = [item for item in normalized_records if _has_meaningful_record(item)]

        if not allow_multi and normalized_records:
            normalized_records = normalized_records[:1]
            mode = "single"
        elif allow_multi and len(normalized_records) > 1:
            mode = "multi"
        elif normalized_records:
            mode = "single"

        if not normalized_records:
            return {
                "ok": False,
                "error": "記録候補をうまく抽出できませんでした。内容を少し具体的にしてもう一度試してください。",
                "mode": "single",
                "records": [],
                "raw_text": text,
            }

        return {
            "ok": True,
            "error": "",
            "mode": mode,
            "records": normalized_records,
            "raw_text": text,
        }

    except Exception as exc:
        return {
            "ok": False,
            "error": f"音声クイック入力の解析に失敗しました: {exc}",
            "mode": "single",
            "records": [],
        }
