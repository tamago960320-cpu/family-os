from __future__ import annotations

from datetime import datetime
from typing import Any

import pandas as pd

from config import (
    BABY_CATEGORY_LABELS,
    FAMILY_CONTEXT_KEYS,
    HOME_LOOKBACK_HOURS,
    MAX_HOME_TASKS,
    MOTHER_CATEGORY_LABELS,
    PAGE_SCHEDULE,
    PREGNANCY_CATEGORY_LABELS,
    PRIORITY_ORDER,
    RECENT_LOG_LIMIT,
    SCHEDULE_SHARED_TO_LABELS,
    SCHEDULE_TYPE_LABELS,
    SHEET_BABY_LOGS,
    SHEET_FAMILY_CONTEXT,
    SHEET_FAMILY_SCHEDULE,
    SHEET_MASTER_SETTINGS,
    SHEET_MOTHER_LOGS,
    SHEET_PREGNANCY_LOGS,
    SHEET_TASKS,
    STATUS_ORDER,
    TASK_TYPE_LABELS,
)
from repository import get_family_context_dict, get_master_settings_dict, read_sheet


def hours_since(ts_value) -> float | None:
    if ts_value in (None, ""):
        return None
    try:
        ts = pd.to_datetime(ts_value, errors="coerce")
        if pd.isna(ts):
            return None
        diff = datetime.now() - ts.to_pydatetime()
        return round(diff.total_seconds() / 3600, 1)
    except Exception:
        return None


def format_hours_label(ts_value, empty_label: str = "記録なし") -> str:
    hours = hours_since(ts_value)
    if hours is None:
        return empty_label
    if hours < 1:
        minutes = max(1, int(hours * 60))
        return f"{minutes}分前"
    return f"{hours}時間前"


def format_datetime_label(ts_value, empty_label: str = "") -> str:
    if ts_value in (None, ""):
        return empty_label
    ts = pd.to_datetime(ts_value, errors="coerce")
    if pd.isna(ts):
        return empty_label
    return ts.strftime("%Y-%m-%d %H:%M")


def get_label(category: str, mapping: dict[str, str]) -> str:
    return mapping.get(str(category), str(category))


def normalize_datetime_column(df: pd.DataFrame, column: str) -> pd.DataFrame:
    if df.empty or column not in df.columns:
        return df.copy()
    work = df.copy()
    work[column] = pd.to_datetime(work[column], errors="coerce")
    return work


def get_today_from_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()

    target_col = None
    if "timestamp" in df.columns:
        target_col = "timestamp"
    elif "date" in df.columns:
        target_col = "date"

    if not target_col:
        return df.copy()

    work = normalize_datetime_column(df, target_col)
    work = work.dropna(subset=[target_col])
    today = datetime.now().date()
    return work[work[target_col].dt.date == today].sort_values(target_col, ascending=False).reset_index(drop=True)


def get_recent_from_df(df: pd.DataFrame, hours: int = 6) -> pd.DataFrame:
    if df.empty or "timestamp" not in df.columns:
        return df.copy()

    work = normalize_datetime_column(df, "timestamp")
    work = work.dropna(subset=["timestamp"])
    cutoff = datetime.now() - pd.Timedelta(hours=hours)
    return work[work["timestamp"] >= cutoff].sort_values("timestamp", ascending=False).reset_index(drop=True)


def get_last_record_from_df(df: pd.DataFrame, category: str | None = None) -> dict[str, Any]:
    if df.empty or "timestamp" not in df.columns:
        return {}

    work = normalize_datetime_column(df, "timestamp")
    work = work.dropna(subset=["timestamp"])

    if category and "category" in work.columns:
        work = work[work["category"].astype(str) == category]

    if work.empty:
        return {}

    return work.sort_values("timestamp", ascending=False).iloc[0].to_dict()


def get_open_tasks(tasks_df: pd.DataFrame) -> pd.DataFrame:
    if tasks_df.empty:
        return pd.DataFrame(
            columns=[
                "task_id",
                "task_type",
                "title",
                "due_date",
                "status",
                "priority",
                "owner",
                "detail",
                "memo",
                "added_at",
                "completed_at",
            ]
        )

    df = tasks_df.copy()
    for col in [
        "status",
        "priority",
        "due_date",
        "task_type",
        "title",
        "owner",
        "detail",
        "memo",
        "added_at",
        "completed_at",
    ]:
        if col not in df.columns:
            df[col] = ""

    df = df[df["status"].astype(str) != "完了"].copy()
    if df.empty:
        return df

    df["priority_order"] = df["priority"].astype(str).map(PRIORITY_ORDER).fillna(99)
    df["status_order"] = df["status"].astype(str).map(STATUS_ORDER).fillna(99)
    df["due_dt"] = pd.to_datetime(df["due_date"], errors="coerce")
    df["added_dt"] = pd.to_datetime(df["added_at"], errors="coerce")
    df = df.sort_values(
        ["priority_order", "status_order", "due_dt", "added_dt", "title"],
        ascending=[True, True, True, True, True],
    )
    return df.reset_index(drop=True)


def get_completed_tasks(tasks_df: pd.DataFrame) -> pd.DataFrame:
    if tasks_df.empty:
        return pd.DataFrame(
            columns=[
                "task_id",
                "task_type",
                "title",
                "due_date",
                "status",
                "priority",
                "owner",
                "detail",
                "memo",
                "added_at",
                "completed_at",
            ]
        )

    df = tasks_df.copy()
    for col in [
        "status",
        "priority",
        "due_date",
        "task_type",
        "title",
        "owner",
        "detail",
        "memo",
        "added_at",
        "completed_at",
    ]:
        if col not in df.columns:
            df[col] = ""

    df = df[df["status"].astype(str) == "完了"].copy()
    if df.empty:
        return df

    df["completed_dt"] = pd.to_datetime(df["completed_at"], errors="coerce")
    df["added_dt"] = pd.to_datetime(df["added_at"], errors="coerce")
    df = df.sort_values(["completed_dt", "added_dt", "title"], ascending=[False, False, True])
    return df.reset_index(drop=True)


def get_open_schedules(schedule_df: pd.DataFrame) -> pd.DataFrame:
    if schedule_df.empty:
        return pd.DataFrame(
            columns=[
                "schedule_id",
                "schedule_type",
                "title",
                "subcategory",
                "target_name",
                "start_date",
                "due_date",
                "status",
                "priority",
                "owner",
                "shared_to",
                "reminder_days_before",
                "memo",
                "source",
                "created_at",
                "updated_at",
                "completed_at",
            ]
        )

    df = schedule_df.copy()
    for col in [
        "schedule_type",
        "title",
        "subcategory",
        "target_name",
        "start_date",
        "due_date",
        "status",
        "priority",
        "owner",
        "shared_to",
        "reminder_days_before",
        "memo",
        "source",
        "created_at",
        "updated_at",
        "completed_at",
    ]:
        if col not in df.columns:
            df[col] = ""

    df = df[df["status"].astype(str) != "完了"].copy()
    if df.empty:
        return df

    df["priority_order"] = df["priority"].astype(str).map(PRIORITY_ORDER).fillna(99)
    df["status_order"] = df["status"].astype(str).map(STATUS_ORDER).fillna(99)
    df["due_dt"] = pd.to_datetime(df["due_date"], errors="coerce")
    df["start_dt"] = pd.to_datetime(df["start_date"], errors="coerce")
    df["created_dt"] = pd.to_datetime(df["created_at"], errors="coerce")
    df = df.sort_values(
        ["priority_order", "status_order", "due_dt", "start_dt", "created_dt", "title"],
        ascending=[True, True, True, True, True, True],
    )
    return df.reset_index(drop=True)


def get_completed_schedules(schedule_df: pd.DataFrame) -> pd.DataFrame:
    if schedule_df.empty:
        return pd.DataFrame(
            columns=[
                "schedule_id",
                "schedule_type",
                "title",
                "subcategory",
                "target_name",
                "start_date",
                "due_date",
                "status",
                "priority",
                "owner",
                "shared_to",
                "reminder_days_before",
                "memo",
                "source",
                "created_at",
                "updated_at",
                "completed_at",
            ]
        )

    df = schedule_df.copy()
    for col in [
        "schedule_type",
        "title",
        "subcategory",
        "target_name",
        "start_date",
        "due_date",
        "status",
        "priority",
        "owner",
        "shared_to",
        "reminder_days_before",
        "memo",
        "source",
        "created_at",
        "updated_at",
        "completed_at",
    ]:
        if col not in df.columns:
            df[col] = ""

    df = df[df["status"].astype(str) == "完了"].copy()
    if df.empty:
        return df

    df["completed_dt"] = pd.to_datetime(df["completed_at"], errors="coerce")
    df["due_dt"] = pd.to_datetime(df["due_date"], errors="coerce")
    df = df.sort_values(["completed_dt", "due_dt", "title"], ascending=[False, True, True])
    return df.reset_index(drop=True)


def build_home_dashboard_snapshot(limit_tasks: int = MAX_HOME_TASKS) -> dict[str, Any]:
    baby_df = read_sheet(SHEET_BABY_LOGS)
    mother_df = read_sheet(SHEET_MOTHER_LOGS)
    pregnancy_df = read_sheet(SHEET_PREGNANCY_LOGS)
    tasks_df = read_sheet(SHEET_TASKS)
    schedule_df = read_sheet(SHEET_FAMILY_SCHEDULE)

    recent_baby = get_recent_from_df(baby_df, HOME_LOOKBACK_HOURS)
    recent_mother = get_recent_from_df(mother_df, HOME_LOOKBACK_HOURS)
    recent_pregnancy = get_recent_from_df(pregnancy_df, HOME_LOOKBACK_HOURS)

    baby_today = get_today_from_df(baby_df)
    mother_today = get_today_from_df(mother_df)
    pregnancy_today = get_today_from_df(pregnancy_df)

    open_tasks = get_open_tasks(tasks_df).head(limit_tasks).copy()
    open_schedules = get_open_schedules(schedule_df).head(5).copy()

    return {
        "baby_last_feeding": get_last_record_from_df(baby_df, "feeding"),
        "baby_last_sleep": get_last_record_from_df(baby_df, "sleep"),
        "baby_last_temperature": get_last_record_from_df(baby_df, "temperature"),
        "mother_last_pain": get_last_record_from_df(mother_df, "pain"),
        "mother_last_bleeding": get_last_record_from_df(mother_df, "bleeding"),
        "recent_baby": recent_baby,
        "recent_mother": recent_mother,
        "recent_pregnancy": recent_pregnancy,
        "baby_today": baby_today,
        "mother_today": mother_today,
        "pregnancy_today": pregnancy_today,
        "today_counts": {
            "baby": len(baby_today),
            "mother": len(mother_today),
            "pregnancy": len(pregnancy_today),
        },
        "tasks_df": tasks_df,
        "open_tasks": open_tasks,
        "schedule_df": schedule_df,
        "open_schedules": open_schedules,
    }


def build_gap_checks(
    recent_baby_df: pd.DataFrame,
    recent_mother_df: pd.DataFrame,
    recent_pregnancy_df: pd.DataFrame,
) -> list[str]:
    checks: list[str] = []

    if recent_baby_df.empty:
        checks.append("赤ちゃんの記録がまだありません。最初の1件を入れておくと安心です。")
    else:
        baby_categories = set(recent_baby_df.get("category", pd.Series(dtype=str)).astype(str).tolist())
        if "feeding" not in baby_categories and "milk" not in baby_categories:
            checks.append(f"授乳またはミルクの記録が直近{HOME_LOOKBACK_HOURS}時間にありません。")
        if "pee" not in baby_categories:
            checks.append(f"おしっこの記録が直近{HOME_LOOKBACK_HOURS}時間にありません。")

    if recent_mother_df.empty:
        checks.append(f"母体の記録が直近{HOME_LOOKBACK_HOURS}時間にありません。")

    if recent_pregnancy_df.empty:
        checks.append(f"妊娠後期メモが直近{HOME_LOOKBACK_HOURS}時間にありません。必要なら張りや体調を残しておこう。")

    return checks


def get_home_open_tasks(limit: int = MAX_HOME_TASKS) -> pd.DataFrame:
    tasks_df = read_sheet(SHEET_TASKS)
    open_tasks = get_open_tasks(tasks_df)
    if open_tasks.empty:
        return open_tasks
    return open_tasks.head(limit).copy()


def get_today_summary_data() -> dict[str, Any]:
    baby_df = read_sheet(SHEET_BABY_LOGS)
    mother_df = read_sheet(SHEET_MOTHER_LOGS)
    pregnancy_df = read_sheet(SHEET_PREGNANCY_LOGS)
    tasks_today = read_sheet(SHEET_TASKS)

    return {
        "baby_today": get_today_from_df(baby_df),
        "mother_today": get_today_from_df(mother_df),
        "pregnancy_today": get_today_from_df(pregnancy_df),
        "tasks_today": tasks_today,
    }


def count_by_category(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "category" not in df.columns:
        return pd.DataFrame(columns=["category", "count"])

    counted = df["category"].astype(str).value_counts().rename_axis("category").reset_index(name="count")
    return counted


def count_today_records() -> dict[str, int]:
    data = get_today_summary_data()
    return {
        "baby": len(data["baby_today"]),
        "mother": len(data["mother_today"]),
        "pregnancy": len(data["pregnancy_today"]),
    }


def _safe_count(df: pd.DataFrame, category: str) -> int:
    if df.empty or "category" not in df.columns:
        return 0
    return int((df["category"].astype(str) == category).sum())


def _task_progress_text(tasks_df: pd.DataFrame) -> str:
    if tasks_df.empty or "status" not in tasks_df.columns:
        return "タスクはまだありません。"

    total = len(tasks_df)
    done = int((tasks_df["status"].astype(str) == "完了").sum())
    open_count = total - done
    return f"タスクは全{total}件で、未完了{open_count}件、完了{done}件。"


def generate_daily_summary_text() -> str:
    data = get_today_summary_data()
    baby_today = data["baby_today"]
    mother_today = data["mother_today"]
    pregnancy_today = data["pregnancy_today"]
    tasks_today = data["tasks_today"]

    feeding_count = _safe_count(baby_today, "feeding")
    milk_count = _safe_count(baby_today, "milk")
    pee_count = _safe_count(baby_today, "pee")
    poop_count = _safe_count(baby_today, "poop")
    sleep_count = _safe_count(baby_today, "sleep")
    temp_count = _safe_count(baby_today, "temperature")

    lines = [
        f"今日の赤ちゃん記録は合計{len(baby_today)}件です。",
        f"授乳{feeding_count}件、ミルク{milk_count}件、おしっこ{pee_count}件、うんち{poop_count}件、睡眠{sleep_count}件、体温{temp_count}件。",
        f"母体記録は{len(mother_today)}件、妊娠後期記録は{len(pregnancy_today)}件です。",
        _task_progress_text(tasks_today),
    ]

    if len(baby_today) == 0 and len(mother_today) == 0 and len(pregnancy_today) == 0:
        lines.append("今日はまだ主要記録が入っていません。まずは体調かタスクを1件入れておくと見通しが立ちます。")

    return "\n".join(lines)


def build_recent_display_rows(df: pd.DataFrame, mapping: dict[str, str], limit: int = 5) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["時刻", "カテゴリ", "内容", "メモ", "記録者"])

    work = df.copy()
    if "timestamp" in work.columns:
        work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
        work = work.sort_values("timestamp", ascending=False)
        work["時刻"] = work["timestamp"].dt.strftime("%m/%d %H:%M")
    else:
        work["時刻"] = ""

    if "category" not in work.columns:
        work["category"] = ""

    work["カテゴリ"] = work["category"].astype(str).map(lambda x: get_label(x, mapping))

    if "detail" in work.columns:
        status = work["status"].astype(str) if "status" in work.columns else ""
        detail = work["detail"].astype(str)
        work["内容"] = (status + " " + detail).str.strip()
    else:
        subtype = work["subtype"].astype(str) if "subtype" in work.columns else ""
        value = work["value"].astype(str) if "value" in work.columns else ""
        unit = work["unit"].astype(str) if "unit" in work.columns else ""
        work["内容"] = (subtype + " " + value + unit).str.strip()

    work["メモ"] = work.get("memo", "").astype(str)
    work["記録者"] = work.get("recorded_by", "").astype(str)
    return work[["時刻", "カテゴリ", "内容", "メモ", "記録者"]].head(limit).reset_index(drop=True)


def build_task_display_rows(df: pd.DataFrame, limit: int = MAX_HOME_TASKS) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["期限", "種別", "タイトル", "優先度", "状態", "担当"])

    work = df.copy().head(limit)
    work["期限"] = work.get("due_date", "").astype(str)
    work["種別"] = work.get("task_type", "").astype(str).map(lambda x: TASK_TYPE_LABELS.get(x, x))
    work["タイトル"] = work.get("title", "").astype(str)
    work["優先度"] = work.get("priority", "").astype(str)
    work["状態"] = work.get("status", "").astype(str)
    work["担当"] = work.get("owner", "").astype(str)
    return work[["期限", "種別", "タイトル", "優先度", "状態", "担当"]].reset_index(drop=True)


def build_task_history_rows(df: pd.DataFrame, limit: int = 20) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["完了日時", "作成日時", "期限", "種別", "タイトル", "優先度", "担当"])

    work = df.copy().head(limit)
    work["完了日時"] = work.get("completed_at", "").astype(str).map(lambda x: format_datetime_label(x, ""))
    work["作成日時"] = work.get("added_at", "").astype(str).map(lambda x: format_datetime_label(x, ""))
    work["期限"] = work.get("due_date", "").astype(str)
    work["種別"] = work.get("task_type", "").astype(str).map(lambda x: TASK_TYPE_LABELS.get(x, x))
    work["タイトル"] = work.get("title", "").astype(str)
    work["優先度"] = work.get("priority", "").astype(str)
    work["担当"] = work.get("owner", "").astype(str)
    return work[["完了日時", "作成日時", "期限", "種別", "タイトル", "優先度", "担当"]].reset_index(drop=True)


def build_schedule_display_rows(df: pd.DataFrame, limit: int = 50) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["期限", "種別", "タイトル", "対象", "共有", "優先度", "状態", "担当"])

    work = df.copy().head(limit)
    work["期限"] = work.get("due_date", "").astype(str)
    work["種別"] = work.get("schedule_type", "").astype(str).map(lambda x: SCHEDULE_TYPE_LABELS.get(x, x))
    work["タイトル"] = work.get("title", "").astype(str)
    work["対象"] = work.get("target_name", "").astype(str)
    work["共有"] = work.get("shared_to", "").astype(str).map(lambda x: SCHEDULE_SHARED_TO_LABELS.get(x, x))
    work["優先度"] = work.get("priority", "").astype(str)
    work["状態"] = work.get("status", "").astype(str)
    work["担当"] = work.get("owner", "").astype(str)
    return work[["期限", "種別", "タイトル", "対象", "共有", "優先度", "状態", "担当"]].reset_index(drop=True)


def build_schedule_history_rows(df: pd.DataFrame, limit: int = 30) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["完了日時", "期限", "種別", "タイトル", "対象", "共有", "担当"])

    work = df.copy().head(limit)
    work["完了日時"] = work.get("completed_at", "").astype(str).map(lambda x: format_datetime_label(x, ""))
    work["期限"] = work.get("due_date", "").astype(str)
    work["種別"] = work.get("schedule_type", "").astype(str).map(lambda x: SCHEDULE_TYPE_LABELS.get(x, x))
    work["タイトル"] = work.get("title", "").astype(str)
    work["対象"] = work.get("target_name", "").astype(str)
    work["共有"] = work.get("shared_to", "").astype(str).map(lambda x: SCHEDULE_SHARED_TO_LABELS.get(x, x))
    work["担当"] = work.get("owner", "").astype(str)
    return work[["完了日時", "期限", "種別", "タイトル", "対象", "共有", "担当"]].reset_index(drop=True)


def build_schedule_edit_options(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty or "schedule_id" not in df.columns:
        return pd.DataFrame(columns=["schedule_id", "表示"])

    work = df.copy()
    for col in [
        "due_date",
        "schedule_type",
        "title",
        "priority",
        "owner",
        "status",
        "target_name",
        "completed_at",
    ]:
        if col not in work.columns:
            work[col] = ""

    work["種別表示"] = work["schedule_type"].astype(str).map(lambda x: SCHEDULE_TYPE_LABELS.get(x, x))
    work["表示"] = (
        work["due_date"].astype(str).fillna("")
        + " | "
        + work["種別表示"].astype(str).fillna("")
        + " | "
        + work["title"].astype(str).fillna("")
        + " | "
        + work["priority"].astype(str).fillna("")
        + " | "
        + work["owner"].astype(str).fillna("")
        + " | "
        + work["status"].astype(str).fillna("")
    )

    work["priority_order"] = work["priority"].astype(str).map(PRIORITY_ORDER).fillna(99)
    work["status_order"] = work["status"].astype(str).map(STATUS_ORDER).fillna(99)
    work["completed_dt"] = pd.to_datetime(work["completed_at"], errors="coerce")
    work["due_dt"] = pd.to_datetime(work["due_date"], errors="coerce")
    work = work.sort_values(
        ["status_order", "priority_order", "due_dt", "completed_dt", "title"],
        ascending=[True, True, True, False, True],
    )

    return work[["schedule_id", "表示"]].reset_index(drop=True)


def build_category_count_rows(df: pd.DataFrame, mapping: dict[str, str]) -> pd.DataFrame:
    counted = count_by_category(df)
    if counted.empty:
        return pd.DataFrame(columns=["カテゴリ", "件数"])

    counted["カテゴリ"] = counted["category"].astype(str).map(lambda x: get_label(x, mapping))
    counted["件数"] = counted["count"]
    return counted[["カテゴリ", "件数"]].reset_index(drop=True)


def build_edit_target_options(sheet_name: str, label_name: str, mapping: dict[str, str]) -> pd.DataFrame:
    df = read_sheet(sheet_name)
    if df.empty or "record_id" not in df.columns:
        return pd.DataFrame(columns=["record_id", "表示"])

    work = df.copy()
    if "timestamp" in work.columns:
        work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
        work = work.sort_values("timestamp", ascending=False)
        work["時刻"] = work["timestamp"].dt.strftime("%m/%d %H:%M")
    else:
        work["時刻"] = ""

    if "category" not in work.columns:
        work["category"] = ""

    work["カテゴリ"] = work["category"].astype(str).map(lambda x: get_label(x, mapping))

    if "detail" in work.columns:
        status = work["status"].astype(str) if "status" in work.columns else ""
        detail = work["detail"].astype(str)
        work["内容"] = (status + " " + detail).str.strip()
    else:
        subtype = work["subtype"].astype(str) if "subtype" in work.columns else ""
        value = work["value"].astype(str) if "value" in work.columns else ""
        unit = work["unit"].astype(str) if "unit" in work.columns else ""
        work["内容"] = (subtype + " " + value + unit).str.strip()

    work["表示"] = (
        work["時刻"].astype(str)
        + " | "
        + work["カテゴリ"].astype(str)
        + " | "
        + work["内容"].astype(str)
    )

    return work[["record_id", "表示"]].head(RECENT_LOG_LIMIT).reset_index(drop=True)


def get_emergency_settings_rows() -> pd.DataFrame:
    settings = get_master_settings_dict()
    if not settings:
        return pd.DataFrame(columns=["項目", "値"])

    rows = [
        {"項目": "産院代表番号", "値": settings.get("hospital_main_phone", "")},
        {"項目": "夜間連絡先", "値": settings.get("hospital_night_phone", "")},
        {"項目": "タクシー番号", "値": settings.get("taxi_phone", "")},
        {"項目": "緊急連絡先1", "値": settings.get("emergency_contact_1", "")},
        {"項目": "緊急連絡先2", "値": settings.get("emergency_contact_2", "")},
        {"項目": "産院住所", "値": settings.get("hospital_address", "")},
        {"項目": "受診判断メモ", "値": settings.get("memo_emergency_rule", "")},
    ]
    return pd.DataFrame(rows)


def build_consultation_context_text() -> str:
    snapshot = build_home_dashboard_snapshot(limit_tasks=10)
    lines: list[str] = []

    lines.append(build_family_context_text())
    lines.append("")
    lines.append("【ホーム要約】")
    lines.append(f"前回授乳: {format_datetime_label(snapshot['baby_last_feeding'].get('timestamp'), '記録なし')}")
    lines.append(f"前回睡眠: {format_datetime_label(snapshot['baby_last_sleep'].get('timestamp'), '記録なし')}")
    lines.append(f"母体の最後の痛み記録: {format_datetime_label(snapshot['mother_last_pain'].get('timestamp'), '記録なし')}")
    lines.append(f"母体の最後の出血記録: {format_datetime_label(snapshot['mother_last_bleeding'].get('timestamp'), '記録なし')}")
    lines.append(
        f"今日の記録件数: 赤ちゃん {snapshot['today_counts']['baby']} / 母体 {snapshot['today_counts']['mother']} / 妊娠後期 {snapshot['today_counts']['pregnancy']}"
    )

    open_tasks = build_task_display_rows(snapshot["open_tasks"], limit=5)
    if open_tasks.empty:
        lines.append("未完了タスク: なし")
    else:
        lines.append("未完了タスク:")
        for _, row in open_tasks.iterrows():
            lines.append(f"- {row['期限']} / {row['種別']} / {row['タイトル']} / {row['優先度']} / {row['担当']}")

    open_schedules = build_schedule_display_rows(snapshot["open_schedules"], limit=5)
    if open_schedules.empty:
        lines.append("近い予定: なし")
    else:
        lines.append("近い予定:")
        for _, row in open_schedules.iterrows():
            lines.append(f"- {row['期限']} / {row['種別']} / {row['タイトル']} / {row['対象']} / {row['担当']}")

    recent_sections = [
        ("赤ちゃん直近", build_recent_display_rows(snapshot["recent_baby"], BABY_CATEGORY_LABELS, limit=5)),
        ("母体直近", build_recent_display_rows(snapshot["recent_mother"], MOTHER_CATEGORY_LABELS, limit=5)),
        ("妊娠後期直近", build_recent_display_rows(snapshot["recent_pregnancy"], PREGNANCY_CATEGORY_LABELS, limit=5)),
    ]

    for section_name, table in recent_sections:
        lines.append(f"【{section_name}】")
        if table.empty:
            lines.append("- 記録なし")
        else:
            for _, row in table.iterrows():
                lines.append(
                    f"- {row['時刻']} / {row['カテゴリ']} / {row['内容']} / メモ: {row['メモ']} / 記録者: {row['記録者']}"
                )

    settings_df = get_emergency_settings_rows()
    if not settings_df.empty:
        lines.append("【緊急連絡先】")
        for _, row in settings_df.iterrows():
            if str(row["値"]).strip():
                lines.append(f"- {row['項目']}: {row['値']}")

    return "\n".join(lines)


def build_family_context_text() -> str:
    context = get_family_context_dict()
    if not context:
        return "家族コンテキスト: まだ未登録"

    lines = ["【家族の現在地】"]
    for key, label in FAMILY_CONTEXT_KEYS.items():
        value = str(context.get(key, "")).strip()
        if value:
            lines.append(f"- {label}: {value}")

    if len(lines) == 1:
        return "家族コンテキスト: まだ未登録"

    return "\n".join(lines)
