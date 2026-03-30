from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from config import (
    PAGE_SCHEDULE,
    RECORDED_BY_OPTIONS,
    SCHEDULE_PRIORITY_OPTIONS,
    SCHEDULE_SHARED_TO_LABELS,
    SCHEDULE_SHARED_TO_OPTIONS,
    SCHEDULE_STATUS_OPTIONS,
    SCHEDULE_TYPE_LABELS,
    SCHEDULE_TYPE_OPTIONS_JA,
    SHEET_FAMILY_SCHEDULE,
)
from repository import (
    add_family_schedule,
    complete_family_schedule,
    delete_row_by_id,
    get_family_schedule_by_id,
    read_sheet,
    reopen_family_schedule,
    update_family_schedule,
)
from services import (
    build_schedule_display_rows,
    build_schedule_edit_options,
    build_schedule_history_rows,
    get_completed_schedules,
    get_open_schedules,
)


def save_success(message: str):
    st.success(message)
    st.rerun()


def render_page_head(title: str, emoji: str, kicker: str, desc: str):
    st.markdown(
        f"""
        <div class='page-head'>
            <div class='page-kicker'>{kicker}</div>
            <div class='page-title'>{emoji} {title}</div>
            <div class='page-desc'>{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def get_schedule_type_code_from_label(label_ja: str) -> str:
    for code, label in SCHEDULE_TYPE_LABELS.items():
        if label == label_ja:
            return code
    return "family_event"


def parse_date_value(value, fallback: date | None = None) -> date:
    fallback = fallback or date.today()
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return fallback
        return parsed.date()
    except Exception:
        return fallback


def _build_type_filtered_table(open_schedules: pd.DataFrame, schedule_type: str) -> pd.DataFrame:
    if open_schedules.empty:
        return pd.DataFrame()

    work = open_schedules.copy()
    if "schedule_type" not in work.columns:
        return pd.DataFrame()

    work = work[work["schedule_type"].astype(str) == schedule_type].copy()
    return build_schedule_display_rows(work, limit=50)


def render_schedule_update_section(recorded_by: str, schedule_df: pd.DataFrame):
    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>✏️ 予定更新</div>
            <div class='section-desc'>既存の予定を編集、完了、未完了へ戻すことができます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if schedule_df.empty or "schedule_id" not in schedule_df.columns:
        st.caption("更新できる予定はまだありません。")
        return

    options_df = build_schedule_edit_options(schedule_df)
    if options_df.empty:
        st.caption("更新できる予定はまだありません。")
        return

    option_labels = list(options_df["表示"])
    option_schedule_ids = list(options_df["schedule_id"])
    selected_schedule_id = str(st.session_state.get("selected_schedule_id", "")).strip()

    selected_index = 0
    if selected_schedule_id and selected_schedule_id in option_schedule_ids:
        selected_index = option_schedule_ids.index(selected_schedule_id)

    selected_label = st.selectbox(
        "更新する予定",
        option_labels,
        index=selected_index,
        key="schedule_edit_select",
    )

    selected_id = option_schedule_ids[option_labels.index(selected_label)]
    st.session_state["selected_schedule_id"] = selected_id

    row = get_family_schedule_by_id(selected_id)
    if not row:
        st.error("対象予定が見つかりませんでした。")
        return

    current_schedule_type = str(row.get("schedule_type", "family_event"))
    current_schedule_type_label = SCHEDULE_TYPE_LABELS.get(current_schedule_type, SCHEDULE_TYPE_OPTIONS_JA[0])
    type_index = SCHEDULE_TYPE_OPTIONS_JA.index(current_schedule_type_label) if current_schedule_type_label in SCHEDULE_TYPE_OPTIONS_JA else 0

    current_status = str(row.get("status", SCHEDULE_STATUS_OPTIONS[0]))
    status_index = SCHEDULE_STATUS_OPTIONS.index(current_status) if current_status in SCHEDULE_STATUS_OPTIONS else 0

    current_priority = str(row.get("priority", SCHEDULE_PRIORITY_OPTIONS[0]))
    priority_index = SCHEDULE_PRIORITY_OPTIONS.index(current_priority) if current_priority in SCHEDULE_PRIORITY_OPTIONS else 0

    current_owner = str(row.get("owner", recorded_by))
    owner_index = RECORDED_BY_OPTIONS.index(current_owner) if current_owner in RECORDED_BY_OPTIONS else 0

    current_shared_to = str(row.get("shared_to", "both"))
    shared_index = SCHEDULE_SHARED_TO_OPTIONS.index(current_shared_to) if current_shared_to in SCHEDULE_SHARED_TO_OPTIONS else 0

    with st.form("schedule_update_form"):
        st.markdown("<div class='edit-box'>予定内容を更新します。</div>", unsafe_allow_html=True)

        schedule_type_label = st.selectbox("種別", SCHEDULE_TYPE_OPTIONS_JA, index=type_index)
        title = st.text_input("タイトル", value=str(row.get("title", "")))
        subcategory = st.text_input("補足分類", value=str(row.get("subcategory", "")), placeholder="例: ヒブ1回目 / 園見学 / 書類提出")
        target_name = st.text_input("対象", value=str(row.get("target_name", "")), placeholder="例: 赤ちゃん / りょうか / 家族")
        start_date = st.date_input("開始日", value=parse_date_value(row.get("start_date", ""), date.today()))
        due_date = st.date_input("期限", value=parse_date_value(row.get("due_date", ""), date.today()))
        status = st.selectbox("状態", SCHEDULE_STATUS_OPTIONS, index=status_index)
        priority = st.selectbox("優先度", SCHEDULE_PRIORITY_OPTIONS, index=priority_index)
        owner = st.selectbox("担当", RECORDED_BY_OPTIONS, index=owner_index)
        shared_to = st.selectbox(
            "共有範囲",
            SCHEDULE_SHARED_TO_OPTIONS,
            index=shared_index,
            format_func=lambda x: SCHEDULE_SHARED_TO_LABELS.get(x, x),
        )
        reminder_days_before = st.text_input(
            "通知日数",
            value=str(row.get("reminder_days_before", "")),
            placeholder="例: 14,7,3,0",
        )
        memo = st.text_area("メモ", value=str(row.get("memo", "")))

        col1, col2, col3 = st.columns(3)
        with col1:
            update_submit = st.form_submit_button("予定を更新", use_container_width=True)
        with col2:
            complete_submit = st.form_submit_button("この予定を完了", use_container_width=True)
        with col3:
            reopen_submit = st.form_submit_button("完了を解除", use_container_width=True)

        if update_submit:
            if not title.strip():
                st.error("タイトルを入力してください。")
            else:
                ok = update_family_schedule(
                    schedule_id=selected_id,
                    schedule_type=get_schedule_type_code_from_label(schedule_type_label),
                    title=title.strip(),
                    subcategory=subcategory.strip(),
                    target_name=target_name.strip(),
                    start_date=str(start_date),
                    due_date=str(due_date),
                    status=status,
                    priority=priority,
                    owner=owner,
                    shared_to=shared_to,
                    reminder_days_before=reminder_days_before.strip(),
                    memo=memo.strip(),
                    source="manual",
                )
                if ok:
                    save_success("予定を更新したよ。")
                else:
                    st.error("予定更新に失敗しました。")

        if complete_submit:
            ok = complete_family_schedule(selected_id)
            if ok:
                save_success("予定を完了にしたよ。")
            else:
                st.error("予定完了更新に失敗しました。")

        if reopen_submit:
            ok = reopen_family_schedule(selected_id)
            if ok:
                save_success("完了を解除したよ。")
            else:
                st.error("完了解除に失敗しました。")

    st.markdown("---")
    delete_confirm = st.checkbox("この予定を削除する", key="schedule_delete_confirm")
    if st.button("予定を削除", key="schedule_delete_button", use_container_width=True, type="secondary"):
        if not delete_confirm:
            st.error("削除する場合は確認チェックを入れてください。")
        else:
            ok = delete_row_by_id(SHEET_FAMILY_SCHEDULE, "schedule_id", selected_id)
            if ok:
                save_success("予定を削除したよ。")
            else:
                st.error("削除に失敗しました。")


def render_schedule_templates(recorded_by: str):
    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>📦 テンプレ追加</div>
            <div class='section-desc'>よく使う予防接種・保活の予定をまとめて追加できます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    template_type = st.selectbox("テンプレ種類", ["予防接種のたたき台", "保活のたたき台"], key="schedule_template_select")

    if st.button("テンプレを追加", use_container_width=True, key="schedule_template_add"):
        if template_type == "予防接種のたたき台":
            rows = [
                {"schedule_type": "vaccination", "title": "2か月ごろ 予防接種開始の確認", "subcategory": "開始時期確認", "target_name": "赤ちゃん"},
                {"schedule_type": "vaccination", "title": "ヒブワクチンの予定確認", "subcategory": "定期接種", "target_name": "赤ちゃん"},
                {"schedule_type": "vaccination", "title": "小児肺炎球菌の予定確認", "subcategory": "定期接種", "target_name": "赤ちゃん"},
                {"schedule_type": "vaccination", "title": "B型肝炎の予定確認", "subcategory": "定期接種", "target_name": "赤ちゃん"},
                {"schedule_type": "vaccination", "title": "ロタワクチンの予定確認", "subcategory": "定期接種", "target_name": "赤ちゃん"},
            ]
        else:
            rows = [
                {"schedule_type": "nursery", "title": "保活の情報収集開始", "subcategory": "情報収集", "target_name": "家族"},
                {"schedule_type": "nursery", "title": "候補園リストを作る", "subcategory": "園選定", "target_name": "家族"},
                {"schedule_type": "nursery", "title": "園見学予約を入れる", "subcategory": "見学", "target_name": "家族"},
                {"schedule_type": "nursery", "title": "必要書類を確認する", "subcategory": "書類確認", "target_name": "家族"},
                {"schedule_type": "nursery", "title": "申込締切を確認する", "subcategory": "締切確認", "target_name": "家族"},
            ]

        for row in rows:
            add_family_schedule(
                schedule_type=row["schedule_type"],
                title=row["title"],
                subcategory=row["subcategory"],
                target_name=row["target_name"],
                start_date="",
                due_date="",
                status="未着手",
                priority="中",
                owner=recorded_by,
                shared_to="both",
                reminder_days_before="14,7,3,0",
                memo="テンプレから追加",
                source="template",
            )

        save_success(f"{template_type}を追加したよ。")


def render_schedule(recorded_by: str):
    render_page_head(
        title="予定共有",
        emoji="🗓️",
        kicker="FAMILY SCHEDULE",
        desc="予防接種・保活・健診・手続きを、夫婦で同じ一覧として共有する画面です。",
    )

    st.session_state["current_page"] = PAGE_SCHEDULE
    try:
        st.query_params["page"] = PAGE_SCHEDULE
    except Exception:
        pass

    schedule_df = read_sheet(SHEET_FAMILY_SCHEDULE)
    open_schedules = get_open_schedules(schedule_df)
    completed_schedules = get_completed_schedules(schedule_df)

    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>📌 近い予定</div>
            <div class='section-desc'>未完了の予定を、期限が近い順に見られます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    open_table = build_schedule_display_rows(open_schedules, limit=50)
    if open_table.empty:
        st.caption("未完了の予定はありません。")
    else:
        st.dataframe(open_table, use_container_width=True, hide_index=True)

    tab_near, tab_vaccination, tab_nursery, tab_done = st.tabs(
        ["近い予定", "予防接種", "保活", "完了履歴"]
    )

    with tab_near:
        if open_table.empty:
            st.caption("未完了の予定はありません。")
        else:
            st.dataframe(open_table.head(20), use_container_width=True, hide_index=True)

    with tab_vaccination:
        vaccination_table = _build_type_filtered_table(open_schedules, "vaccination")
        if vaccination_table.empty:
            st.caption("予防接種予定はまだありません。")
        else:
            st.dataframe(vaccination_table, use_container_width=True, hide_index=True)

    with tab_nursery:
        nursery_table = _build_type_filtered_table(open_schedules, "nursery")
        if nursery_table.empty:
            st.caption("保活予定はまだありません。")
        else:
            st.dataframe(nursery_table, use_container_width=True, hide_index=True)

    with tab_done:
        history_table = build_schedule_history_rows(completed_schedules, limit=30)
        if history_table.empty:
            st.caption("完了履歴はまだありません。")
        else:
            st.dataframe(history_table, use_container_width=True, hide_index=True)

    render_schedule_update_section(recorded_by, schedule_df)

    owner_index = RECORDED_BY_OPTIONS.index(recorded_by) if recorded_by in RECORDED_BY_OPTIONS else 0

    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>➕ 予定追加</div>
            <div class='section-desc'>夫婦共有したい予定を新しく追加できます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("schedule_add_form"):
        schedule_type_label = st.selectbox("種別", SCHEDULE_TYPE_OPTIONS_JA)
        title = st.text_input("タイトル", placeholder="例: ヒブ1回目の予約 / 園見学予約 / 出生届提出")
        subcategory = st.text_input("補足分類", placeholder="例: 1回目 / 見学 / 締切")
        target_name = st.text_input("対象", placeholder="例: 赤ちゃん / 家族 / りょうか")
        start_date = st.date_input("開始日", value=date.today())
        due_date = st.date_input("期限", value=date.today())
        status = st.selectbox("状態", SCHEDULE_STATUS_OPTIONS, index=0)
        priority = st.selectbox("優先度", SCHEDULE_PRIORITY_OPTIONS, index=1)
        owner = st.selectbox("担当", RECORDED_BY_OPTIONS, index=owner_index)
        shared_to = st.selectbox(
            "共有範囲",
            SCHEDULE_SHARED_TO_OPTIONS,
            index=0,
            format_func=lambda x: SCHEDULE_SHARED_TO_LABELS.get(x, x),
        )
        reminder_days_before = st.text_input("通知日数", value="14,7,3,0")
        memo = st.text_area("メモ", placeholder="補足、持ち物、確認事項など")
        submit = st.form_submit_button("予定を追加", use_container_width=True)

        if submit:
            if not title.strip():
                st.error("タイトルを入力してください。")
            else:
                add_family_schedule(
                    schedule_type=get_schedule_type_code_from_label(schedule_type_label),
                    title=title.strip(),
                    subcategory=subcategory.strip(),
                    target_name=target_name.strip(),
                    start_date=str(start_date),
                    due_date=str(due_date),
                    status=status,
                    priority=priority,
                    owner=owner,
                    shared_to=shared_to,
                    reminder_days_before=reminder_days_before.strip(),
                    memo=memo.strip(),
                    source="manual",
                )
                save_success("予定を追加したよ。")

    render_schedule_templates(recorded_by)