import json
import time
import uuid
from datetime import datetime, timedelta
from typing import Any

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials
from gspread.exceptions import APIError, WorksheetNotFound

from config import (
    DEFAULT_CACHE_TTL_SECONDS,
    GOOGLE_SERVICE_ACCOUNT_JSON,
    GOOGLE_SPREADSHEET_ID,
    REQUIRED_SHEETS,
    SHEET_BABY_LOGS,
    SHEET_CONSULTATION_LOGS,
    SHEET_DAILY_SUMMARY,
    SHEET_MASTER_SETTINGS,
    SHEET_MOTHER_LOGS,
    SHEET_PREGNANCY_LOGS,
    SHEET_TASKS,
    FAMILY_CONTEXT_KEYS,
    SHEET_FAMILY_CONTEXT,
)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def _parse_service_account_info(raw_value: str) -> dict[str, Any]:
    raw = str(raw_value or "").strip()
    if not raw:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON が未設定です。Streamlit Cloud の Secrets を確認してください。")

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        preview = raw[:160].replace("\n", "\\n")
        raise ValueError(
            "サービスアカウントJSONの解析に失敗しました。"
            f" Secrets の形式が壊れています。先頭確認: {preview} / error: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError("サービスアカウント情報がJSONオブジェクトではありません。")

    required_keys = [
        "type",
        "project_id",
        "private_key",
        "client_email",
        "token_uri",
    ]
    missing = [key for key in required_keys if not str(parsed.get(key, "")).strip()]
    if missing:
        raise ValueError(f"サービスアカウント情報に必須項目が足りません: {', '.join(missing)}")

    return parsed


@st.cache_resource
def _get_gspread_client():
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON が未設定です。secrets を確認してください。")

    if not GOOGLE_SPREADSHEET_ID:
        raise ValueError("GOOGLE_SPREADSHEET_ID が未設定です。secrets を確認してください。")

    service_account_info = _parse_service_account_info(GOOGLE_SERVICE_ACCOUNT_JSON)
    credentials = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    return gspread.authorize(credentials))


def _safe_api_call(func, *args, retries: int = 4, wait_seconds: float = 1.2, **kwargs):
    last_error = None
    for attempt in range(retries):
        try:
            return func(*args, **kwargs)
        except APIError as exc:
            last_error = exc
            status_code = None
            try:
                status_code = exc.response.status_code
            except Exception:
                pass

            if status_code == 429 and attempt < retries - 1:
                time.sleep(wait_seconds * (attempt + 1))
                continue
            raise
    raise last_error


@st.cache_data(ttl=DEFAULT_CACHE_TTL_SECONDS)
def read_sheet(sheet_name: str) -> pd.DataFrame:
    spreadsheet = get_spreadsheet()
    worksheet = spreadsheet.worksheet(sheet_name)

    values = _safe_api_call(worksheet.get_all_values)
    if not values:
        return pd.DataFrame()

    headers = [str(col).strip() for col in values[0]]
    if not headers or not any(headers):
        return pd.DataFrame()

    data_rows = values[1:]
    normalized_rows: list[list[str]] = []

    for row in data_rows:
        if len(row) < len(headers):
            row = row + [""] * (len(headers) - len(row))
        elif len(row) > len(headers):
            row = row[: len(headers)]
        normalized_rows.append(row)

    if not normalized_rows:
        return pd.DataFrame(columns=headers)

    return pd.DataFrame(normalized_rows, columns=headers)


@st.cache_data(ttl=DEFAULT_CACHE_TTL_SECONDS)
def get_sheet_headers(sheet_name: str) -> list[str]:
    df = read_sheet(sheet_name)
    return [str(col).strip() for col in df.columns.tolist()]


def clear_sheet_cache():
    read_sheet.clear()
    get_sheet_headers.clear()


def _ensure_headers(sheet_name: str):
    spreadsheet = get_spreadsheet()
    required_headers = REQUIRED_SHEETS[sheet_name]

    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except WorksheetNotFound:
        worksheet = _safe_api_call(
            spreadsheet.add_worksheet,
            title=sheet_name,
            rows=1000,
            cols=max(len(required_headers), 10),
        )
        _safe_api_call(worksheet.update, "A1", [required_headers])
        return

    current_headers = _safe_api_call(worksheet.row_values, 1)
    if not current_headers:
        _safe_api_call(worksheet.update, "A1", [required_headers])
        return

    changed = False
    merged_headers = current_headers[:]
    for header in required_headers:
        if header not in merged_headers:
            merged_headers.append(header)
            changed = True

    if changed:
        _safe_api_call(worksheet.update, "A1", [merged_headers])


def ensure_required_sheets():
    for sheet_name in REQUIRED_SHEETS:
        _ensure_headers(sheet_name)
    clear_sheet_cache()


def append_row(sheet_name: str, row: dict[str, Any]):
    headers = get_sheet_headers(sheet_name)
    if not headers:
        raise ValueError(f"{sheet_name} のヘッダー取得に失敗しました。")

    spreadsheet = get_spreadsheet()
    worksheet = spreadsheet.worksheet(sheet_name)
    values = [row.get(col, "") for col in headers]
    _safe_api_call(worksheet.append_row, values, value_input_option="USER_ENTERED")
    clear_sheet_cache()


def normalize_datetime_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df.copy()
    normalized = df.copy()
    normalized[column] = pd.to_datetime(normalized[column], errors="coerce")
    return normalized


def get_recent_rows(sheet_name: str, hours: int = 6) -> pd.DataFrame:
    df = read_sheet(sheet_name)
    if df.empty or "timestamp" not in df.columns:
        return df.copy()

    df = normalize_datetime_column(df, "timestamp")
    df = df.dropna(subset=["timestamp"])
    cutoff = datetime.now() - timedelta(hours=hours)
    return df[df["timestamp"] >= cutoff].sort_values("timestamp", ascending=False).reset_index(drop=True)


def get_today_rows(sheet_name: str) -> pd.DataFrame:
    df = read_sheet(sheet_name)
    if df.empty:
        return df.copy()

    target_col = None
    if "timestamp" in df.columns:
        target_col = "timestamp"
    elif "date" in df.columns:
        target_col = "date"

    if not target_col:
        return df.copy()

    df = normalize_datetime_column(df, target_col)
    df = df.dropna(subset=[target_col])
    today = datetime.now().date()
    return df[df[target_col].dt.date == today].sort_values(target_col, ascending=False).reset_index(drop=True)


def get_last_record(sheet_name: str, category: str | None = None) -> dict[str, Any]:
    df = read_sheet(sheet_name)
    if df.empty or "timestamp" not in df.columns:
        return {}

    df = normalize_datetime_column(df, "timestamp")
    df = df.dropna(subset=["timestamp"])

    if category and "category" in df.columns:
        df = df[df["category"].astype(str) == category]

    if df.empty:
        return {}

    return df.sort_values("timestamp", ascending=False).iloc[0].to_dict()


def generate_record_id(prefix: str = "rec") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:10]}"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def update_row_by_id(sheet_name: str, id_column: str, record_id: str, updates: dict[str, Any]) -> bool:
    if not record_id:
        return False

    spreadsheet = get_spreadsheet()
    worksheet = spreadsheet.worksheet(sheet_name)
    headers = get_sheet_headers(sheet_name)
    if not headers or id_column not in headers:
        return False

    df = read_sheet(sheet_name)
    if df.empty or id_column not in df.columns:
        return False

    matches = df.index[df[id_column].astype(str) == str(record_id)].tolist()
    if not matches:
        return False

    row_number = matches[0] + 2
    row_values = []
    for header in headers:
        if header in updates:
            row_values.append(updates.get(header, ""))
        else:
            current_val = ""
            try:
                current_val = df.iloc[matches[0]][header]
            except Exception:
                current_val = ""
            row_values.append("" if pd.isna(current_val) else current_val)

    _safe_api_call(
        worksheet.update,
        f"{gspread.utils.rowcol_to_a1(row_number, 1)}:{gspread.utils.rowcol_to_a1(row_number, len(headers))}",
        [row_values],
        value_input_option="USER_ENTERED",
    )
    clear_sheet_cache()
    return True


def delete_row_by_id(sheet_name: str, id_column: str, record_id: str) -> bool:
    if not record_id:
        return False

    spreadsheet = get_spreadsheet()
    worksheet = spreadsheet.worksheet(sheet_name)
    headers = get_sheet_headers(sheet_name)
    if not headers or id_column not in headers:
        return False

    df = read_sheet(sheet_name)
    if df.empty or id_column not in df.columns:
        return False

    matches = df.index[df[id_column].astype(str) == str(record_id)].tolist()
    if not matches:
        return False

    row_number = matches[0] + 2
    _safe_api_call(worksheet.delete_rows, row_number)
    clear_sheet_cache()
    return True


def fill_missing_ids_in_sheet(sheet_name: str, id_column: str, prefix: str) -> dict[str, Any]:
    headers = get_sheet_headers(sheet_name)
    if not headers:
        raise ValueError(f"{sheet_name} のヘッダー取得に失敗しました。")

    if id_column not in headers:
        raise ValueError(f"{sheet_name} に {id_column} 列がありません。")

    df = read_sheet(sheet_name)
    if df.empty:
        return {
            "sheet_name": sheet_name,
            "id_column": id_column,
            "prefix": prefix,
            "updated_count": 0,
            "target_rows": [],
        }

    work = df.copy()
    work[id_column] = work[id_column].astype(str).fillna("").str.strip()
    missing_indexes = work.index[work[id_column] == ""].tolist()

    if not missing_indexes:
        return {
            "sheet_name": sheet_name,
            "id_column": id_column,
            "prefix": prefix,
            "updated_count": 0,
            "target_rows": [],
        }

    spreadsheet = get_spreadsheet()
    worksheet = spreadsheet.worksheet(sheet_name)
    col_index = headers.index(id_column) + 1

    requests = []
    target_rows = []
    for idx in missing_indexes:
        row_number = idx + 2
        new_id = generate_record_id(prefix)
        a1 = gspread.utils.rowcol_to_a1(row_number, col_index)
        requests.append({"range": a1, "values": [[new_id]]})
        target_rows.append({"row_number": row_number, "new_id": new_id})

    _safe_api_call(worksheet.batch_update, requests, value_input_option="USER_ENTERED")
    clear_sheet_cache()

    return {
        "sheet_name": sheet_name,
        "id_column": id_column,
        "prefix": prefix,
        "updated_count": len(requests),
        "target_rows": target_rows,
    }


def backfill_record_ids() -> dict[str, Any]:
    targets = [
        {"sheet_name": SHEET_PREGNANCY_LOGS, "id_column": "record_id", "prefix": "preg"},
        {"sheet_name": SHEET_BABY_LOGS, "id_column": "record_id", "prefix": "baby"},
        {"sheet_name": SHEET_MOTHER_LOGS, "id_column": "record_id", "prefix": "mth"},
    ]

    results = []
    total_updated = 0

    for target in targets:
        result = fill_missing_ids_in_sheet(
            sheet_name=target["sheet_name"],
            id_column=target["id_column"],
            prefix=target["prefix"],
        )
        results.append(result)
        total_updated += int(result.get("updated_count", 0))

    return {"total_updated": total_updated, "results": results}


def get_master_settings_dict() -> dict[str, str]:
    df = read_sheet(SHEET_MASTER_SETTINGS)
    if df.empty or "key" not in df.columns:
        return {}

    result: dict[str, str] = {}
    for _, row in df.iterrows():
        key = str(row.get("key", "")).strip()
        if not key:
            continue
        result[key] = str(row.get("value", "")).strip()
    return result


def get_master_setting(key: str, default: str = "") -> str:
    settings = get_master_settings_dict()
    return settings.get(key, default)


def upsert_master_setting(key: str, value: str, description: str = ""):
    df = read_sheet(SHEET_MASTER_SETTINGS)
    spreadsheet = get_spreadsheet()
    worksheet = spreadsheet.worksheet(SHEET_MASTER_SETTINGS)
    headers = get_sheet_headers(SHEET_MASTER_SETTINGS)

    if df.empty or "key" not in df.columns:
        append_row(
            SHEET_MASTER_SETTINGS,
            {
                "key": key,
                "value": value,
                "description": description,
            },
        )
        return

    matches = df.index[df["key"].astype(str) == str(key)].tolist()
    if matches:
        row_number = matches[0] + 2
        row_values = []
        for header in headers:
            if header == "key":
                row_values.append(key)
            elif header == "value":
                row_values.append(value)
            elif header == "description":
                row_values.append(description)
            else:
                current_val = df.iloc[matches[0]].get(header, "")
                row_values.append("" if pd.isna(current_val) else current_val)

        _safe_api_call(
            worksheet.update,
            f"A{row_number}:{gspread.utils.rowcol_to_a1(row_number, len(headers))}",
            [row_values],
            value_input_option="USER_ENTERED",
        )
        clear_sheet_cache()
        return

    append_row(
        SHEET_MASTER_SETTINGS,
        {
            "key": key,
            "value": value,
            "description": description,
        },
    )


def add_pregnancy_log(category: str, status: str, detail: str, memo: str, recorded_by: str):
    append_row(
        SHEET_PREGNANCY_LOGS,
        {
            "record_id": generate_record_id("preg"),
            "timestamp": now_iso(),
            "category": category,
            "status": status,
            "detail": detail,
            "memo": memo,
            "recorded_by": recorded_by,
        },
    )


def add_baby_log(category: str, subtype: str, value: Any, unit: str, memo: str, recorded_by: str):
    append_row(
        SHEET_BABY_LOGS,
        {
            "record_id": generate_record_id("baby"),
            "timestamp": now_iso(),
            "category": category,
            "subtype": subtype,
            "value": value,
            "unit": unit,
            "memo": memo,
            "recorded_by": recorded_by,
        },
    )


def add_mother_log(category: str, status: str, value: Any, unit: str, memo: str, recorded_by: str):
    append_row(
        SHEET_MOTHER_LOGS,
        {
            "record_id": generate_record_id("mth"),
            "timestamp": now_iso(),
            "category": category,
            "status": status,
            "value": value,
            "unit": unit,
            "memo": memo,
            "recorded_by": recorded_by,
        },
    )


def add_task(
    task_id: str,
    task_type: str,
    title: str,
    detail: str,
    due_date: str,
    status: str,
    priority: str,
    owner: str,
    memo: str,
):
    now_value = now_iso()
    completed_at = now_value if str(status) == "完了" else ""

    append_row(
        SHEET_TASKS,
        {
            "task_id": task_id,
            "task_type": task_type,
            "title": title,
            "detail": detail,
            "due_date": due_date,
            "status": status,
            "priority": priority,
            "owner": owner,
            "memo": memo,
            "added_at": now_value,
            "completed_at": completed_at,
        },
    )


def update_task(
    task_id: str,
    task_type: str,
    title: str,
    detail: str,
    due_date: str,
    status: str,
    priority: str,
    owner: str,
    memo: str,
) -> bool:
    df = read_sheet(SHEET_TASKS)
    if df.empty or "task_id" not in df.columns:
        return False

    target = df[df["task_id"].astype(str) == str(task_id)]
    if target.empty:
        return False

    row = target.iloc[0]
    existing_completed_at = str(row.get("completed_at", "")).strip()
    if status == "完了":
        completed_at = existing_completed_at or now_iso()
    else:
        completed_at = ""

    return update_row_by_id(
        SHEET_TASKS,
        "task_id",
        task_id,
        {
            "task_type": task_type,
            "title": title,
            "detail": detail,
            "due_date": due_date,
            "status": status,
            "priority": priority,
            "owner": owner,
            "memo": memo,
            "completed_at": completed_at,
        },
    )


def complete_task(task_id: str) -> bool:
    return update_row_by_id(
        SHEET_TASKS,
        "task_id",
        task_id,
        {
            "status": "完了",
            "completed_at": now_iso(),
        },
    )


def reopen_task(task_id: str) -> bool:
    return update_row_by_id(
        SHEET_TASKS,
        "task_id",
        task_id,
        {
            "status": "未着手",
            "completed_at": "",
        },
    )


def generate_consultation_id() -> str:
    return f"consult_{uuid.uuid4().hex[:10]}"


def add_consultation_log(
    user_input: str,
    ai_response: str,
    context_summary: str,
    tag: str,
    recorded_by: str,
) -> str:
    consultation_id = generate_consultation_id()
    append_row(
        SHEET_CONSULTATION_LOGS,
        {
            "consultation_id": consultation_id,
            "timestamp": now_iso(),
            "user_input": user_input,
            "ai_response": ai_response,
            "context_summary": context_summary,
            "tag": tag,
            "recorded_by": recorded_by,
        },
    )
    return consultation_id


def get_consultation_by_id(consultation_id: str) -> dict[str, Any]:
    if not consultation_id:
        return {}

    df = read_sheet(SHEET_CONSULTATION_LOGS)
    if df.empty or "consultation_id" not in df.columns:
        return {}

    target = df[df["consultation_id"].astype(str) == str(consultation_id)]
    if target.empty:
        return {}

    return target.iloc[0].to_dict()


def fill_missing_consultation_ids() -> dict[str, Any]:
    headers = get_sheet_headers(SHEET_CONSULTATION_LOGS)
    if not headers:
        raise ValueError(f"{SHEET_CONSULTATION_LOGS} のヘッダー取得に失敗しました。")

    if "consultation_id" not in headers:
        raise ValueError(f"{SHEET_CONSULTATION_LOGS} に consultation_id 列がありません。")

    df = read_sheet(SHEET_CONSULTATION_LOGS)
    if df.empty:
        return {
            "sheet_name": SHEET_CONSULTATION_LOGS,
            "updated_count": 0,
            "target_rows": [],
        }

    work = df.copy()
    work["consultation_id"] = work["consultation_id"].astype(str).fillna("").str.strip()
    missing_indexes = work.index[work["consultation_id"] == ""].tolist()

    if not missing_indexes:
        return {
            "sheet_name": SHEET_CONSULTATION_LOGS,
            "updated_count": 0,
            "target_rows": [],
        }

    spreadsheet = get_spreadsheet()
    worksheet = spreadsheet.worksheet(SHEET_CONSULTATION_LOGS)
    col_index = headers.index("consultation_id") + 1

    updated_rows = []
    for idx in missing_indexes:
        row_number = idx + 2
        consultation_id = generate_consultation_id()
        cell_a1 = gspread.utils.rowcol_to_a1(row_number, col_index)
        _safe_api_call(
            worksheet.update,
            cell_a1,
            [[consultation_id]],
            value_input_option="USER_ENTERED",
        )
        updated_rows.append(row_number)

    clear_sheet_cache()

    return {
        "sheet_name": SHEET_CONSULTATION_LOGS,
        "updated_count": len(updated_rows),
        "target_rows": updated_rows,
    }


def add_daily_summary(date_value: str, summary_type: str, summary_text: str, generated_by: str = "manual"):
    append_row(
        SHEET_DAILY_SUMMARY,
        {
            "date": date_value,
            "summary_type": summary_type,
            "summary_text": summary_text,
            "generated_by": generated_by,
            "created_at": now_iso(),
        },
    )

def get_family_context_dict() -> dict[str, str]:
    df = read_sheet(SHEET_FAMILY_CONTEXT)
    if df.empty or "key" not in df.columns:
        return {}

    result: dict[str, str] = {}
    for _, row in df.iterrows():
        key = str(row.get("key", "")).strip()
        value = str(row.get("value", "")).strip()
        if not key:
            continue
        result[key] = value
    return result


def upsert_family_context(key: str, value: str, source: str = "manual"):
    key = str(key).strip()
    value = str(value).strip()
    source = str(source).strip() or "manual"

    if not key:
        return

    df = read_sheet(SHEET_FAMILY_CONTEXT)
    spreadsheet = get_spreadsheet()
    worksheet = spreadsheet.worksheet(SHEET_FAMILY_CONTEXT)
    headers = get_sheet_headers(SHEET_FAMILY_CONTEXT)

    if not headers:
        raise ValueError(f"{SHEET_FAMILY_CONTEXT} のヘッダー取得に失敗しました。")

    payload = {
        "key": key,
        "value": value,
        "updated_at": now_iso(),
        "source": source,
    }

    if df.empty or "key" not in df.columns:
        append_row(SHEET_FAMILY_CONTEXT, payload)
        return

    matches = df.index[df["key"].astype(str) == key].tolist()
    if matches:
        row_number = matches[0] + 2
        row_values = []
        for header in headers:
            if header in payload:
                row_values.append(payload[header])
            else:
                current_val = df.iloc[matches[0]].get(header, "")
                row_values.append("" if pd.isna(current_val) else current_val)

        _safe_api_call(
            worksheet.update,
            f"A{row_number}:{gspread.utils.rowcol_to_a1(row_number, len(headers))}",
            [row_values],
            value_input_option="USER_ENTERED",
        )
        clear_sheet_cache()
        return

    append_row(SHEET_FAMILY_CONTEXT, payload)


def get_family_context_rows() -> pd.DataFrame:
    df = read_sheet(SHEET_FAMILY_CONTEXT)
    if df.empty:
        return pd.DataFrame(columns=["項目", "内容", "更新日時", "更新元"])

    work = df.copy()
    if "key" not in work.columns:
        work["key"] = ""
    if "value" not in work.columns:
        work["value"] = ""
    if "updated_at" not in work.columns:
        work["updated_at"] = ""
    if "source" not in work.columns:
        work["source"] = ""

    work["項目"] = work["key"].astype(str).map(lambda x: FAMILY_CONTEXT_KEYS.get(x, x))
    work["内容"] = work["value"].astype(str)
    work["更新日時"] = work["updated_at"].astype(str)
    work["更新元"] = work["source"].astype(str)

    order_map = {key: idx for idx, key in enumerate(FAMILY_CONTEXT_KEYS.keys())}
    work["sort_order"] = work["key"].astype(str).map(lambda x: order_map.get(x, 999))
    work = work.sort_values(["sort_order", "項目"], ascending=[True, True])

    return work[["項目", "内容", "更新日時", "更新元"]].reset_index(drop=True)
