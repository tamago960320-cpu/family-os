from __future__ import annotations

import pandas as pd
import streamlit as st

from ai_service import parse_quick_input_text
from config import (
    BABY_CATEGORY_LABELS,
    MAX_HOME_TASKS,
    MOTHER_CATEGORY_LABELS,
    PAGE_TASKS,
    PREGNANCY_CATEGORY_LABELS,
    TASK_TYPE_LABELS,
)
from repository import add_baby_log, add_mother_log, add_pregnancy_log
from services import (
    build_gap_checks,
    build_home_dashboard_snapshot,
    build_recent_display_rows,
    format_datetime_label,
    format_hours_label,
)


def save_success(message: str):
    st.success(message)
    st.rerun()


def render_page_head():
    st.markdown(
        """
        <div class='page-head'>
            <div class='page-kicker'>HOME DASHBOARD</div>
            <div class='page-title'>🏠 ホーム</div>
            <div class='page-desc'>
                今日の状態と、次にやることを見る画面です。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    with st.expander("この画面でできること"):
        st.caption("授乳・睡眠・注意点・やること・直近記録を確認できます。")


def render_home_stat_cards(snapshot: dict):
    feeding_label = format_hours_label(snapshot["baby_last_feeding"].get("timestamp"))
    sleep_label = format_hours_label(snapshot["baby_last_sleep"].get("timestamp"))

    st.markdown(
        f"""
        <div class='home-stat-grid-2'>
            <div class='home-stat-card'>
                <div class='home-stat-label'>前回授乳</div>
                <div class='home-stat-value'>{feeding_label}</div>
            </div>
            <div class='home-stat-card'>
                <div class='home-stat-label'>前回睡眠</div>
                <div class='home-stat-value'>{sleep_label}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class='home-stat-grid-3'>
            <div class='home-stat-card'>
                <div class='home-stat-label'>今日の赤ちゃん記録</div>
                <div class='home-stat-value small'>{snapshot["today_counts"]["baby"]}</div>
            </div>
            <div class='home-stat-card'>
                <div class='home-stat-label'>今日の母体記録</div>
                <div class='home-stat-value small'>{snapshot["today_counts"]["mother"]}</div>
            </div>
            <div class='home-stat-card'>
                <div class='home-stat-label'>今日の妊娠記録</div>
                <div class='home-stat-value small'>{snapshot["today_counts"]["pregnancy"]}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_checks_section(snapshot: dict, checks: list[str]):
    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>⚠️ 直近チェック</div>
            <div class='section-desc'>直近6時間の抜け漏れや、気にしておきたい点を確認します。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if checks:
        for item in checks:
            st.warning(item)
    else:
        st.success("直近6時間の主要記録は問題なし。")

    mother_note = []
    if snapshot["mother_last_pain"]:
        mother_note.append(
            f"最後の痛み記録: {format_datetime_label(snapshot['mother_last_pain'].get('timestamp'))} / {snapshot['mother_last_pain'].get('status', '')}"
        )
    if snapshot["mother_last_bleeding"]:
        mother_note.append(
            f"最後の出血記録: {format_datetime_label(snapshot['mother_last_bleeding'].get('timestamp'))} / {snapshot['mother_last_bleeding'].get('status', '')}"
        )

    if mother_note:
        st.info("\n".join(mother_note))


def _target_label(target: str) -> str:
    mapping = {
        "baby_logs": "赤ちゃん",
        "mother_logs": "母体",
        "pregnancy_logs": "妊娠後期",
    }
    return mapping.get(str(target), str(target))


def _category_label(target: str, category: str) -> str:
    target = str(target).strip()
    category = str(category).strip()

    if target == "baby_logs":
        return BABY_CATEGORY_LABELS.get(category, category)
    if target == "mother_logs":
        return MOTHER_CATEGORY_LABELS.get(category, category)
    if target == "pregnancy_logs":
        return PREGNANCY_CATEGORY_LABELS.get(category, category)
    return category


def _build_quick_input_preview_rows(records: list[dict]) -> pd.DataFrame:
    rows = []
    for idx, record in enumerate(records, start=1):
        rows.append(
            {
                "No": idx,
                "対象": _target_label(record.get("target", "")),
                "カテゴリ": _category_label(record.get("target", ""), record.get("category", "")),
                "種別/状態": record.get("subtype", "") or record.get("status", ""),
                "値": record.get("value", ""),
                "単位": record.get("unit", ""),
                "詳細": record.get("detail", ""),
                "メモ": record.get("memo", ""),
            }
        )
    return pd.DataFrame(rows)


def _save_parsed_quick_input(records: list[dict], recorded_by: str) -> int:
    saved_count = 0

    for record in records:
        target = str(record.get("target", "")).strip()
        category = str(record.get("category", "")).strip()

        if target == "baby_logs":
            add_baby_log(
                category=category,
                subtype=str(record.get("subtype", "")).strip(),
                value=record.get("value", ""),
                unit=str(record.get("unit", "")).strip(),
                memo=str(record.get("memo", "")).strip(),
                recorded_by=recorded_by,
            )
            saved_count += 1

        elif target == "mother_logs":
            add_mother_log(
                category=category,
                status=str(record.get("status", "")).strip(),
                value=record.get("value", ""),
                unit=str(record.get("unit", "")).strip(),
                memo=str(record.get("memo", "")).strip(),
                recorded_by=recorded_by,
            )
            saved_count += 1

        elif target == "pregnancy_logs":
            add_pregnancy_log(
                category=category,
                status=str(record.get("status", "")).strip(),
                detail=str(record.get("detail", "")).strip(),
                memo=str(record.get("memo", "")).strip(),
                recorded_by=recorded_by,
            )
            saved_count += 1

    return saved_count


def render_voice_quick_input_section(recorded_by: str, key_prefix: str = "home_voice"):
    text_key = f"{key_prefix}_text"
    allow_multi_key = f"{key_prefix}_allow_multi"
    parsed_key = f"{key_prefix}_parsed"

    if text_key not in st.session_state:
        st.session_state[text_key] = ""
    if allow_multi_key not in st.session_state:
        st.session_state[allow_multi_key] = False
    if parsed_key not in st.session_state:
        st.session_state[parsed_key] = {}

    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>🎙️ 音声クイック入力</div>
            <div class='section-desc'>
                スマホの音声入力でそのまま話してOK。内容をAIが記録候補に変換します。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.text_area(
        "音声クイック入力",
        key=text_key,
        height=110,
        placeholder="例: 母乳10分、少し眠そう / うんち多め、黄色 / 張りが少し気になる / りょうかが腰痛で中くらい",
    )
    st.checkbox(
        "複数記録を許可する",
        key=allow_multi_key,
        help="通常は1件だけ保存候補を作ります。1回の入力から複数件に分けたい時だけONにします。",
    )

    col1, col2 = st.columns(2)

    with col1:
        if st.button("解析する", use_container_width=True, key=f"{key_prefix}_analyze"):
            parsed = parse_quick_input_text(
                user_input=st.session_state[text_key],
                allow_multi=bool(st.session_state[allow_multi_key]),
                allowed_targets=["baby_logs", "mother_logs", "pregnancy_logs"],
            )
            st.session_state[parsed_key] = parsed

    parsed = st.session_state.get(parsed_key, {})
    if parsed:
        if parsed.get("ok"):
            records = parsed.get("records", [])
            preview_df = _build_quick_input_preview_rows(records)

            st.markdown(
                """
                <div class='section-card'>
                    <div class='section-title'>🧾 保存前プレビュー</div>
                    <div class='section-desc'>内容を確認してから保存できます。</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            if not preview_df.empty:
                st.dataframe(preview_df, use_container_width=True, hide_index=True)

            with col2:
                if st.button("この内容で保存", use_container_width=True, key=f"{key_prefix}_save"):
                    saved_count = _save_parsed_quick_input(records, recorded_by)
                    st.session_state[text_key] = ""
                    st.session_state[allow_multi_key] = False
                    st.session_state[parsed_key] = {}
                    if saved_count > 0:
                        save_success(f"{saved_count}件の記録を保存したよ。")
                    else:
                        st.error("保存できる記録がありませんでした。")
        else:
            st.error(str(parsed.get("error", "解析に失敗しました。")))


def render_tasks_section(snapshot: dict):
    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>✅ 今日やること</div>
            <div class='section-desc'>優先度の高い未完了タスクを上から確認できます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    open_tasks = snapshot.get("open_tasks")
    if open_tasks is None or open_tasks.empty:
        st.caption("未完了タスクはありません。")
        return

    work = open_tasks.head(MAX_HOME_TASKS).copy()

    for idx, row in work.iterrows():
        task_id = str(row.get("task_id", "")).strip()
        due_date = str(row.get("due_date", "")).strip()
        task_type = TASK_TYPE_LABELS.get(str(row.get("task_type", "")).strip(), str(row.get("task_type", "")).strip())
        title = str(row.get("title", "")).strip()
        priority = str(row.get("priority", "")).strip()
        owner = str(row.get("owner", "")).strip()
        detail = str(row.get("detail", "")).strip()
        memo = str(row.get("memo", "")).strip()

        meta_parts = [x for x in [due_date, task_type, priority, owner] if x]
        meta_text = " / ".join(meta_parts)

        if detail or memo:
            body_parts = [x for x in [detail, memo] if x]
            body_text = " / ".join(body_parts)
        else:
            body_text = "詳細未入力"

        st.markdown(
            f"""
            <div class='task-mini-card'>
                <div class='task-mini-title'>{title if title else "タイトルなし"}</div>
                <div class='task-mini-meta'>{meta_text}</div>
                <div class='task-mini-meta' style='margin-top:6px;'>{body_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("詳細を見る", key=f"home_task_detail_{task_id}_{idx}", use_container_width=True):
            st.session_state["selected_task_id"] = task_id
            st.session_state["current_page"] = PAGE_TASKS
            try:
                st.query_params["page"] = PAGE_TASKS
            except Exception:
                pass
            st.rerun()


def render_recent_timeline_group(title: str, emoji: str, rows, empty_message: str):
    st.markdown(
        f"""
        <div class='section-card'>
            <div class='section-title'>{emoji} {title}</div>
            <div class='section-desc'>直近の流れをカードで確認できます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if rows.empty:
        st.caption(empty_message)
        return

    for _, row in rows.iterrows():
        time_text = str(row.get("時刻", "")).strip()
        category_text = str(row.get("カテゴリ", "")).strip()
        content_text = str(row.get("内容", "")).strip()
        memo_text = str(row.get("メモ", "")).strip()
        recorder_text = str(row.get("記録者", "")).strip()

        body_parts = [x for x in [content_text, memo_text] if x]
        body_text = " / ".join(body_parts)

        footer_parts = [x for x in [recorder_text] if x]
        footer_text = " / ".join(footer_parts)

        st.markdown(
            f"""
            <div class='timeline-card'>
                <div class='timeline-top'>
                    <div class='timeline-time'>{time_text}</div>
                    <div class='timeline-category'>{category_text}</div>
                </div>
                <div class='timeline-body'>{body_text if body_text else "内容なし"}</div>
                {"<div class='task-mini-meta' style='margin-top:6px;'>" + footer_text + "</div>" if footer_text else ""}
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_quick_input_section(recorded_by: str):
    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>✨ クイック入力</div>
            <div class='section-desc'>よく使う記録はホームからすぐ追加できます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🍼 授乳を記録", use_container_width=True, key="quick_feed"):
            add_baby_log("feeding", "母乳", "", "", "ホームから追加", recorded_by)
            save_success("授乳記録を保存したよ。")

    with col2:
        if st.button("💧 おしっこを記録", use_container_width=True, key="quick_pee"):
            add_baby_log("pee", "", 1, "回", "ホームから追加", recorded_by)
            save_success("おしっこ記録を保存したよ。")

    col3, col4 = st.columns(2)
    with col3:
        if st.button("😴 睡眠を記録", use_container_width=True, key="quick_sleep"):
            add_baby_log("sleep", "睡眠", 1, "回", "ホームから追加", recorded_by)
            save_success("睡眠記録を保存したよ。")

    with col4:
        if st.button("🤰 張りをメモ", use_container_width=True, key="quick_preg"):
            add_pregnancy_log("symptom", "少し気になる", "張り", "ホームから追加", recorded_by)
            save_success("張りメモを保存したよ。")


def render_home(recorded_by: str):
    snapshot = build_home_dashboard_snapshot(limit_tasks=MAX_HOME_TASKS)
    checks = build_gap_checks(
        snapshot["recent_baby"],
        snapshot["recent_mother"],
        snapshot["recent_pregnancy"],
    )

    render_page_head()

    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>🌷 いまの様子</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    render_home_stat_cards(snapshot)

    render_checks_section(snapshot, checks)
    render_voice_quick_input_section(recorded_by, key_prefix="home_voice")
    render_quick_input_section(recorded_by)
    render_tasks_section(snapshot)

    with st.expander("🕘 直近記録を見る", expanded=False):
        baby_recent_table = build_recent_display_rows(snapshot["recent_baby"], BABY_CATEGORY_LABELS, limit=5)
        mother_recent_table = build_recent_display_rows(snapshot["recent_mother"], MOTHER_CATEGORY_LABELS, limit=5)
        preg_recent_table = build_recent_display_rows(snapshot["recent_pregnancy"], PREGNANCY_CATEGORY_LABELS, limit=5)

        render_recent_timeline_group(
            "赤ちゃんの直近記録",
            "🍼",
            baby_recent_table,
            "直近の赤ちゃん記録はありません。",
        )
        render_recent_timeline_group(
            "母体の直近記録",
            "🤱",
            mother_recent_table,
            "直近の母体記録はありません。",
        )
        render_recent_timeline_group(
            "妊娠後期の直近記録",
            "🌼",
            preg_recent_table,
            "直近の妊娠後期記録はありません。",
        )