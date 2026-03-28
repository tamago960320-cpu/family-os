import json
import os

import streamlit as st

APP_NAME = "家族OS / 育児AIアシスタント"
APP_ICON = "🍼"


def _get_secret_value(key: str, default: str = "") -> str:
    try:
        if key in st.secrets:
            value = st.secrets[key]
            if isinstance(value, dict):
                return json.dumps(dict(value), ensure_ascii=False)
            return str(value)
    except Exception:
        pass
    return str(os.getenv(key, default))


def _get_service_account_json() -> str:
    raw = _get_secret_value("GOOGLE_SERVICE_ACCOUNT_JSON", "")
    if raw:
        return raw

    try:
        if "GOOGLE_SERVICE_ACCOUNT" in st.secrets:
            value = st.secrets["GOOGLE_SERVICE_ACCOUNT"]
            if isinstance(value, dict):
                return json.dumps(dict(value), ensure_ascii=False)
            return str(value)
    except Exception:
        pass

    return ""


GOOGLE_SERVICE_ACCOUNT_JSON = _get_service_account_json()
GOOGLE_SPREADSHEET_ID = _get_secret_value("GOOGLE_SPREADSHEET_ID", "")
OPENAI_API_KEY = _get_secret_value("OPENAI_API_KEY", "")
OPENAI_MODEL = _get_secret_value("OPENAI_MODEL", "gpt-4.1-mini")


SHEET_FAMILY_PROFILE = "family_profile"
SHEET_PREGNANCY_LOGS = "pregnancy_logs"
SHEET_BABY_LOGS = "baby_logs"
SHEET_MOTHER_LOGS = "mother_logs"
SHEET_TASKS = "tasks"
SHEET_CONSULTATION_LOGS = "consultation_logs"
SHEET_DAILY_SUMMARY = "daily_summary"
SHEET_MASTER_SETTINGS = "master_settings"
SHEET_FAMILY_CONTEXT = "family_context"
SHEET_NOTIFICATION_LOGS = "notification_logs"


REQUIRED_SHEETS = {
    SHEET_FAMILY_PROFILE: [
        "family_id",
        "father_name",
        "mother_name",
        "baby_name",
        "baby_birthday",
        "notes",
    ],
    SHEET_PREGNANCY_LOGS: [
        "record_id",
        "timestamp",
        "category",
        "status",
        "detail",
        "memo",
        "recorded_by",
    ],
    SHEET_BABY_LOGS: [
        "record_id",
        "timestamp",
        "category",
        "subtype",
        "value",
        "unit",
        "memo",
        "recorded_by",
    ],
    SHEET_MOTHER_LOGS: [
        "record_id",
        "timestamp",
        "category",
        "status",
        "value",
        "unit",
        "memo",
        "recorded_by",
    ],
    SHEET_TASKS: [
        "task_id",
        "task_type",
        "title",
        "detail",
        "due_date",
        "status",
        "priority",
        "owner",
        "memo",
        "added_at",
        "completed_at",
    ],
    SHEET_CONSULTATION_LOGS: [
        "consultation_id",
        "timestamp",
        "user_input",
        "ai_response",
        "context_summary",
        "tag",
        "recorded_by",
    ],
    SHEET_DAILY_SUMMARY: [
        "date",
        "summary_type",
        "summary_text",
        "generated_by",
        "created_at",
    ],
    SHEET_MASTER_SETTINGS: [
        "key",
        "value",
        "description",
    ],
    SHEET_FAMILY_CONTEXT: [
        "key",
        "value",
        "updated_at",
        "source",
    ],
    SHEET_NOTIFICATION_LOGS: [
        "notification_id",
        "notification_type",
        "target",
        "message_text",
        "dedupe_key",
        "status",
        "sent_at",
    ],
}


PREGNANCY_CATEGORY_LABELS = {
    "pregnancy": "妊娠",
    "mother_health": "母体の体調",
    "hospital": "通院・受診",
    "preparation": "出産準備",
    "symptom": "症状",
}

BABY_CATEGORY_LABELS = {
    "feeding": "授乳",
    "milk": "ミルク",
    "pee": "おしっこ",
    "poop": "うんち",
    "sleep": "睡眠",
    "temperature": "体温",
    "symptom": "症状",
}

MOTHER_CATEGORY_LABELS = {
    "sleep": "睡眠",
    "meal": "食事",
    "pain": "痛み",
    "bleeding": "出血",
    "mood": "気分",
    "medicine": "服薬",
    "hospital": "通院・受診",
}

TASK_TYPE_LABELS = {
    "birth_preparation": "出産準備",
    "paperwork": "手続き",
    "hospital": "病院・受診",
    "vaccination": "予防接種",
    "family": "家族タスク",
    "shopping": "買い物",
    "general": "その他",
}

TASK_TYPE_OPTIONS_JA = list(TASK_TYPE_LABELS.values())

TASK_STATUS_OPTIONS = ["未着手", "進行中", "完了"]
TASK_PRIORITY_OPTIONS = ["高", "中", "低"]
RECORDED_BY_OPTIONS = ["いっせい", "りょうか"]

HOME_LOOKBACK_HOURS = 6
MAX_HOME_TASKS = 5

DEFAULT_CACHE_TTL_SECONDS = 180

RECENT_LOG_LIMIT = 10

PREGNANCY_STATUS_OPTIONS = [
    "変化なし",
    "少し気になる",
    "気になる",
    "要確認",
    "メモのみ",
]

MOTHER_PAIN_STATUS_OPTIONS = [
    "なし",
    "軽い",
    "中くらい",
    "強い",
]

MOTHER_BLEEDING_STATUS_OPTIONS = [
    "なし",
    "少量",
    "中量",
    "多い",
]

BABY_FEEDING_SUBTYPE_OPTIONS = ["母乳", "搾乳", "混合"]
BABY_SLEEP_SUBTYPE_OPTIONS = ["入眠", "起床", "昼寝開始", "昼寝終了"]
BABY_POOP_SUBTYPE_OPTIONS = ["少量", "普通", "多め", "ゆるい", "硬め"]
BABY_TEMPERATURE_UNIT = "℃"
BABY_MILK_UNIT = "ml"
BABY_SLEEP_UNIT = "分"

PRIORITY_ORDER = {"高": 0, "中": 1, "低": 2}
STATUS_ORDER = {"未着手": 0, "進行中": 1, "完了": 2}

PAGE_HOME = "ホーム"
PAGE_PREGNANCY = "妊娠後期"
PAGE_BABY = "新生児記録"
PAGE_MOTHER = "母体ケア"
PAGE_SUMMARY = "日次サマリー"
PAGE_TASKS = "タスク"
PAGE_CONSULT = "相談AI"

PAGES = [
    PAGE_HOME,
    PAGE_PREGNANCY,
    PAGE_BABY,
    PAGE_MOTHER,
    PAGE_SUMMARY,
    PAGE_TASKS,
    PAGE_CONSULT,
]

PAGE_ICONS = {
    PAGE_HOME: "🏠",
    PAGE_PREGNANCY: "🤰",
    PAGE_BABY: "👶",
    PAGE_MOTHER: "🩺",
    PAGE_SUMMARY: "📊",
    PAGE_TASKS: "✅",
    PAGE_CONSULT: "💬",
}

MASTER_SETTING_KEYS = {
    "hospital_main_phone": "産院代表番号",
    "hospital_night_phone": "夜間連絡先",
    "taxi_phone": "タクシー番号",
    "emergency_contact_1": "緊急連絡先1",
    "emergency_contact_2": "緊急連絡先2",
    "hospital_address": "産院住所",
    "memo_emergency_rule": "受診判断メモ",
    "line_channel_access_token": "LINEチャネルアクセストークン",
    "line_channel_secret": "LINEチャネルシークレット",
    "line_group_id": "LINEグループID",
    "line_notifications_enabled": "LINE通知有効",
    "notify_morning_hour": "朝通知の時刻",
    "notify_gap_hours": "抜け漏れ通知間隔(時間)",
    "notify_summary_daily_hour": "サマリー通知の時刻",
    "notify_task_due_morning_enabled": "期限当日朝通知",
    "notify_high_priority_advance_enabled": "高優先度2週間前通知",
    "notify_gap_check_enabled": "記録抜け漏れ通知",
    "notify_daily_attention_enabled": "今日の注意メモ通知",
    "notify_summary_on_update_enabled": "日次サマリー通知",
}

FAMILY_CONTEXT_KEYS = {
    "current_concerns": "現在の主な悩み",
    "ongoing_symptoms": "継続中の症状",
    "recent_purchase_topics": "最近の購入相談",
    "purchase_status": "購入状況",
    "mother_recent_meals": "母体の最近の食事",
    "mother_condition_summary": "母体の状態要約",
    "pending_preparations": "未完了の準備",
    "important_notes": "重要メモ",
}