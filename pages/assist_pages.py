from __future__ import annotations

from datetime import date
import uuid

import pandas as pd
import streamlit as st

from ai_service import generate_consultation_answer, generate_family_context_updates
from config import (
    PAGE_CONSULT,
    RECORDED_BY_OPTIONS,
    SHEET_CONSULTATION_LOGS,
    SHEET_TASKS,
    TASK_PRIORITY_OPTIONS,
    TASK_STATUS_OPTIONS,
    TASK_TYPE_LABELS,
    TASK_TYPE_OPTIONS_JA,
)
from repository import (
    add_consultation_log,
    add_task,
    complete_task,
    get_consultation_by_id,
    read_sheet,
    reopen_task,
    update_task,
    get_family_context_dict,
    upsert_family_context,
)
from services import (
    build_category_count_rows,
    build_consultation_context_text,
    build_task_display_rows,
    build_task_history_rows,
    generate_daily_summary_text,
    get_completed_tasks,
    get_open_tasks,
    get_today_summary_data,
    build_family_context_text,
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


def get_task_type_code_from_label(label_ja: str) -> str:
    for code, label in TASK_TYPE_LABELS.items():
        if label == label_ja:
            return code
    return "general"


def build_task_edit_options(tasks_df: pd.DataFrame) -> pd.DataFrame:
    if tasks_df.empty or "task_id" not in tasks_df.columns:
        return pd.DataFrame(columns=["task_id", "表示"])

    work = tasks_df.copy()

    if "due_date" not in work.columns:
        work["due_date"] = ""
    if "task_type" not in work.columns:
        work["task_type"] = ""
    if "title" not in work.columns:
        work["title"] = ""
    if "priority" not in work.columns:
        work["priority"] = ""
    if "owner" not in work.columns:
        work["owner"] = ""
    if "status" not in work.columns:
        work["status"] = ""
    if "completed_at" not in work.columns:
        work["completed_at"] = ""

    work["種別表示"] = work["task_type"].astype(str).map(lambda x: TASK_TYPE_LABELS.get(x, x))
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

    work["status_order"] = work["status"].astype(str).map({"未着手": 0, "進行中": 1, "完了": 2}).fillna(99)
    work["completed_dt"] = pd.to_datetime(work["completed_at"], errors="coerce")
    work["due_dt"] = pd.to_datetime(work["due_date"], errors="coerce")
    work = work.sort_values(["status_order", "due_dt", "completed_dt", "title"], ascending=[True, True, False, True])

    return work[["task_id", "表示"]].reset_index(drop=True)


def parse_due_date(value) -> date:
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return date.today()
        return parsed.date()
    except Exception:
        return date.today()


def render_task_update_section(recorded_by: str, tasks_df: pd.DataFrame):
    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>✏️ タスク更新</div>
            <div class='section-desc'>既存タスクの内容更新、完了、完了解除をここから行えます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if tasks_df.empty or "task_id" not in tasks_df.columns:
        st.caption("更新できるタスクはまだありません。")
        return

    options_df = build_task_edit_options(tasks_df)
    if options_df.empty:
        st.caption("更新できるタスクはまだありません。")
        return

    option_labels = list(options_df["表示"])
    option_task_ids = list(options_df["task_id"])
    selected_task_id = str(st.session_state.get("selected_task_id", "")).strip()

    selected_index = 0
    if selected_task_id and selected_task_id in option_task_ids:
        selected_index = option_task_ids.index(selected_task_id)

    selected_label = st.selectbox(
        "更新するタスク",
        option_labels,
        index=selected_index,
        key="task_edit_select",
    )

    selected_id = option_task_ids[option_labels.index(selected_label)]
    st.session_state["selected_task_id"] = selected_id

    source_df = read_sheet(SHEET_TASKS)
    target = source_df[source_df["task_id"].astype(str) == str(selected_id)]
    if target.empty:
        st.error("対象タスクが見つかりませんでした。")
        return

    row = target.iloc[0]

    current_task_type = str(row.get("task_type", "general"))
    current_task_type_label = TASK_TYPE_LABELS.get(current_task_type, TASK_TYPE_OPTIONS_JA[0])
    task_type_index = TASK_TYPE_OPTIONS_JA.index(current_task_type_label) if current_task_type_label in TASK_TYPE_OPTIONS_JA else 0

    current_status = str(row.get("status", TASK_STATUS_OPTIONS[0]))
    status_index = TASK_STATUS_OPTIONS.index(current_status) if current_status in TASK_STATUS_OPTIONS else 0

    current_priority = str(row.get("priority", TASK_PRIORITY_OPTIONS[0]))
    priority_index = TASK_PRIORITY_OPTIONS.index(current_priority) if current_priority in TASK_PRIORITY_OPTIONS else 0

    current_owner = str(row.get("owner", recorded_by))
    owner_index = RECORDED_BY_OPTIONS.index(current_owner) if current_owner in RECORDED_BY_OPTIONS else 0

    added_at_label = str(row.get("added_at", "")).strip()
    completed_at_label = str(row.get("completed_at", "")).strip()

    with st.form("task_update_form"):
        st.markdown("<div class='edit-box'>タスク内容を更新します。</div>", unsafe_allow_html=True)

        if added_at_label:
            st.caption(f"作成日時: {added_at_label}")
        else:
            st.caption("作成日時: 未記録")

        if completed_at_label:
            st.caption(f"完了日時: {completed_at_label}")
        else:
            st.caption("完了日時: 未完了")

        task_type_label = st.selectbox("種別", TASK_TYPE_OPTIONS_JA, index=task_type_index)
        title = st.text_input("タイトル", value=str(row.get("title", "")))
        detail = st.text_area("詳細", value=str(row.get("detail", "")))
        due_date = st.date_input("期限", value=parse_due_date(row.get("due_date", "")))
        status = st.selectbox("状態", TASK_STATUS_OPTIONS, index=status_index)
        priority = st.selectbox("優先度", TASK_PRIORITY_OPTIONS, index=priority_index)
        owner = st.selectbox("担当", RECORDED_BY_OPTIONS, index=owner_index)
        memo = st.text_area("メモ", value=str(row.get("memo", "")))

        col1, col2, col3 = st.columns(3)
        with col1:
            update_submit = st.form_submit_button("タスクを更新", use_container_width=True)
        with col2:
            complete_submit = st.form_submit_button("このタスクを完了", use_container_width=True)
        with col3:
            reopen_submit = st.form_submit_button("完了を解除", use_container_width=True)

        if update_submit:
            if not title.strip():
                st.error("タイトルを入力してください。")
            else:
                ok = update_task(
                    task_id=selected_id,
                    task_type=get_task_type_code_from_label(task_type_label),
                    title=title.strip(),
                    detail=detail.strip(),
                    due_date=str(due_date),
                    status=status,
                    priority=priority,
                    owner=owner,
                    memo=memo.strip(),
                )
                if ok:
                    if status == "完了":
                        save_success("タスクを更新して完了履歴も保存したよ。")
                    else:
                        save_success("タスクを更新したよ。")
                else:
                    st.error("タスク更新に失敗しました。")

        if complete_submit:
            ok = complete_task(selected_id)
            if ok:
                save_success("タスクを完了にして、完了日時も保存したよ。")
            else:
                st.error("タスク完了更新に失敗しました。")

        if reopen_submit:
            ok = reopen_task(selected_id)
            if ok:
                save_success("完了を解除したよ。完了日時はクリアしたよ。")
            else:
                st.error("完了解除に失敗しました。")


def render_summary():
    from config import BABY_CATEGORY_LABELS, MOTHER_CATEGORY_LABELS, PREGNANCY_CATEGORY_LABELS

    render_page_head(
        title="日次サマリー",
        emoji="📊",
        kicker="DAILY SUMMARY",
        desc="今日の記録件数と内訳を見て、赤ちゃん・母体・妊娠後期の全体感を確認する画面です。",
    )

    data = get_today_summary_data()

    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>🌼 今日の件数</div>
            <div class='section-desc'>まずは今日どれくらい記録できているかを確認します。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("赤ちゃん", len(data["baby_today"]))
    with col2:
        st.metric("母体", len(data["mother_today"]))
    with col3:
        st.metric("妊娠後期", len(data["pregnancy_today"]))

    baby_counts = build_category_count_rows(data["baby_today"], BABY_CATEGORY_LABELS)
    mother_counts = build_category_count_rows(data["mother_today"], MOTHER_CATEGORY_LABELS)
    preg_counts = build_category_count_rows(data["pregnancy_today"], PREGNANCY_CATEGORY_LABELS)

    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>🧾 内訳</div>
            <div class='section-desc'>カテゴリごとの件数を分けて確認できます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab1, tab2, tab3 = st.tabs(["赤ちゃん内訳", "母体内訳", "妊娠後期内訳"])
    with tab1:
        if baby_counts.empty:
            st.caption("赤ちゃんの記録はまだありません。")
        else:
            st.dataframe(baby_counts, use_container_width=True, hide_index=True)
    with tab2:
        if mother_counts.empty:
            st.caption("母体の記録はまだありません。")
        else:
            st.dataframe(mother_counts, use_container_width=True, hide_index=True)
    with tab3:
        if preg_counts.empty:
            st.caption("妊娠後期の記録はまだありません。")
        else:
            st.dataframe(preg_counts, use_container_width=True, hide_index=True)

    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>📝 今日のまとめ</div>
            <div class='section-desc'>数字だけでなく、今日の流れを文章でも確認できます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.text(generate_daily_summary_text())


def render_tasks(recorded_by: str):
    render_page_head(
        title="タスク",
        emoji="✅",
        kicker="TASK BOARD",
        desc="出産準備、病院、家族タスクをまとめて管理する画面です。未完了と完了履歴を分けて確認できます。",
    )

    tasks_df = read_sheet(SHEET_TASKS)
    open_tasks = get_open_tasks(tasks_df)
    completed_tasks = get_completed_tasks(tasks_df)

    open_table = build_task_display_rows(open_tasks, limit=50)

    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>📋 未完了タスク</div>
            <div class='section-desc'>今やるべきものを先に確認できます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if open_table.empty:
        st.caption("未完了タスクはありません。")
    else:
        st.dataframe(open_table, use_container_width=True, hide_index=True)

    render_task_update_section(recorded_by, tasks_df)

    owner_index = RECORDED_BY_OPTIONS.index(recorded_by) if recorded_by in RECORDED_BY_OPTIONS else 0

    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>➕ タスク追加</div>
            <div class='section-desc'>新しい準備や手続きを追加できます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    with st.form("task_form"):
        task_type_label = st.selectbox("種別", TASK_TYPE_OPTIONS_JA)
        title = st.text_input("タイトル", placeholder="例: 入院バッグ最終確認")
        detail = st.text_area("詳細")
        due_date = st.date_input("期限", value=date.today())
        status = st.selectbox("状態", TASK_STATUS_OPTIONS)
        priority = st.selectbox("優先度", TASK_PRIORITY_OPTIONS, index=1)
        owner = st.selectbox("担当", RECORDED_BY_OPTIONS, index=owner_index)
        memo = st.text_area("メモ")
        submit = st.form_submit_button("タスクを追加", use_container_width=True)

        if submit:
            if not title.strip():
                st.error("タイトルを入力してください。")
            else:
                add_task(
                    task_id=str(uuid.uuid4())[:8],
                    task_type=get_task_type_code_from_label(task_type_label),
                    title=title.strip(),
                    detail=detail.strip(),
                    due_date=str(due_date),
                    status=status,
                    priority=priority,
                    owner=owner,
                    memo=memo.strip(),
                )
                if status == "完了":
                    save_success("完了済みタスクとして追加し、完了日時も保存したよ。")
                else:
                    save_success("タスクを追加したよ。")

    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>🕘 完了履歴</div>
            <div class='section-desc'>完了したタスクを履歴として確認できます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    history_table = build_task_history_rows(completed_tasks, limit=30)
    if history_table.empty:
        st.caption("完了履歴はまだありません。")
    else:
        st.dataframe(history_table, use_container_width=True, hide_index=True)


def _get_latest_saved_consult_answer() -> tuple[str, str, str, str]:
    df = read_sheet(SHEET_CONSULTATION_LOGS)
    if df.empty:
        return "", "", "", ""

    work = df.copy()

    if "timestamp" in work.columns:
        work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
        work = work.sort_values("timestamp", ascending=False)

    row = work.iloc[0]
    consultation_id = str(row.get("consultation_id", "")).strip()
    answer = str(row.get("ai_response", "")).strip()
    user_input = str(row.get("user_input", "")).strip()
    tag = str(row.get("tag", "")).strip()

    return consultation_id, answer, user_input, tag


def _build_consult_select_options(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["consultation_id", "label"])

    work = df.copy()

    if "consultation_id" not in work.columns:
        work["consultation_id"] = ""
    if "timestamp" not in work.columns:
        work["timestamp"] = ""
    if "tag" not in work.columns:
        work["tag"] = ""
    if "user_input" not in work.columns:
        work["user_input"] = ""

    work["ts"] = pd.to_datetime(work["timestamp"], errors="coerce")
    work = work.sort_values("ts", ascending=False)

    work["時刻"] = work["ts"].dt.strftime("%m/%d %H:%M")
    work["時刻"] = work["時刻"].fillna("日時不明")
    work["相談要約"] = work["user_input"].astype(str).str.slice(0, 40)
    work["label"] = (
        work["時刻"].astype(str)
        + " | "
        + work["tag"].astype(str)
        + " | "
        + work["相談要約"].astype(str)
    )

    return work[["consultation_id", "label"]].reset_index(drop=True)


def render_consult(recorded_by: str):
    render_page_head(
        title="相談AI",
        emoji="💬",
        kicker="CONSULT SUPPORT",
        desc="直近の記録を踏まえて、今やることを整理する相談画面です。医療判断は断定せず、安全側で案内します。",
    )

    st.session_state["current_page"] = PAGE_CONSULT
    try:
        st.query_params["page"] = PAGE_CONSULT
    except Exception:
        pass

    context_text = build_consultation_context_text()

    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>🧠 相談する前に</div>
            <div class='section-desc'>直近の記録を参考にしながら、いま何を優先するかを整理します。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    family_context_rows = get_family_context_dict()
    if family_context_rows:
        st.markdown(
            """
            <div class='section-card'>
                <div class='section-title'>🧾 家族の現在地</div>
                <div class='section-desc'>相談で蓄積した、家族の悩み・準備状況・継続メモを参照します。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.text(build_family_context_text())
    with st.expander("参考に渡す直近コンテキストを見る"):
        st.text(context_text)

    with st.form("consult_form"):
        tag = st.selectbox("相談カテゴリ", ["妊娠後期", "母体", "赤ちゃん", "手続き", "家族運営", "その他"])
        user_input = st.text_area(
            "相談内容",
            placeholder="例: 張りが増えてきた気がする。今すぐ病院に連絡した方がいいか、それとももう少し様子見でいいか整理したい。",
            height=140,
        )
        submit = st.form_submit_button("相談する", use_container_width=True)

        if submit:
            if not user_input.strip():
                st.error("相談内容を入力してください。")
            else:
                with st.spinner("相談内容を整理しています..."):
                    try:
                        current_family_context_text = build_family_context_text()
                        answer = generate_consultation_answer(user_input.strip(), context_text)

                        consultation_id = add_consultation_log(
                            user_input=user_input.strip(),
                            ai_response=answer,
                            context_summary=context_text[:5000],
                            tag=tag,
                            recorded_by=recorded_by,
                        )

                        updates = generate_family_context_updates(
                            user_input=user_input.strip(),
                            answer_text=answer,
                            current_context_text=current_family_context_text,
                        )

                        for key, value in updates.items():
                            if str(value).strip():
                                upsert_family_context(key, value, source="consult_ai")

                        st.session_state["latest_consultation_id"] = consultation_id
                        st.session_state["latest_consult_answer"] = answer
                        st.session_state["latest_consult_input"] = user_input.strip()
                        st.session_state["latest_consult_tag"] = tag
                        st.session_state["selected_consultation_id"] = consultation_id
                        st.session_state["current_page"] = PAGE_CONSULT

                        st.rerun()

                    except Exception as exc:
                        st.error(f"相談AIの実行に失敗しました: {exc}")

    answer = str(st.session_state.get("latest_consult_answer", "")).strip()
    consult_input = str(st.session_state.get("latest_consult_input", "")).strip()
    consult_tag = str(st.session_state.get("latest_consult_tag", "")).strip()
    selected_consultation_id = str(st.session_state.get("selected_consultation_id", "")).strip()

    if not answer:
        latest_id, latest_answer, latest_input, latest_tag = _get_latest_saved_consult_answer()
        answer = latest_answer
        consult_input = latest_input
        consult_tag = latest_tag
        if latest_id:
            selected_consultation_id = latest_id
            st.session_state["selected_consultation_id"] = latest_id

    recent_consults = read_sheet(SHEET_CONSULTATION_LOGS)

    if not recent_consults.empty:
        st.markdown(
            """
            <div class='section-card'>
                <div class='section-title'>🗂️ 履歴から見る</div>
                <div class='section-desc'>過去の相談を選んで、回答内容を再表示できます。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        options_df = _build_consult_select_options(recent_consults)
        if not options_df.empty:
            label_map = dict(zip(options_df["label"], options_df["consultation_id"]))

            labels = list(label_map.keys())
            selected_index = 0
            if selected_consultation_id:
                for idx, label in enumerate(labels):
                    if str(label_map[label]) == selected_consultation_id:
                        selected_index = idx
                        break

            selected_label = st.selectbox(
                "履歴を選択",
                labels,
                index=selected_index,
                key="consult_history_select",
            )
            selected_consultation_id = str(label_map[selected_label])
            st.session_state["selected_consultation_id"] = selected_consultation_id

            selected_row = get_consultation_by_id(selected_consultation_id)
            if selected_row:
                answer = str(selected_row.get("ai_response", "")).strip()
                consult_input = str(selected_row.get("user_input", "")).strip()
                consult_tag = str(selected_row.get("tag", "")).strip()

    if answer:
        st.markdown(
            """
            <div class='section-card'>
                <div class='section-title'>🌸 相談結果</div>
                <div class='section-desc'>行動の優先順位が分かる形で表示します。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if consult_tag:
            st.caption(f"カテゴリ: {consult_tag}")
        if consult_input:
            st.caption(f"相談内容: {consult_input}")

        st.markdown(answer)

    if not recent_consults.empty:
        st.markdown(
            """
            <div class='section-card'>
                <div class='section-title'>🕘 最近の相談一覧</div>
                <div class='section-desc'>直近の相談履歴を確認できます。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        work = recent_consults.copy()
        if "timestamp" in work.columns:
            work["timestamp"] = pd.to_datetime(work["timestamp"], errors="coerce")
            work = work.sort_values("timestamp", ascending=False)
            work["時刻"] = work["timestamp"].dt.strftime("%m/%d %H:%M")
        else:
            work["時刻"] = ""

        if "tag" not in work.columns:
            work["tag"] = ""
        if "user_input" not in work.columns:
            work["user_input"] = ""
        if "recorded_by" not in work.columns:
            work["recorded_by"] = ""

        work["カテゴリ"] = work["tag"].astype(str)
        work["相談"] = work["user_input"].astype(str)
        work["記録者"] = work["recorded_by"].astype(str)

        st.dataframe(
            work[["時刻", "カテゴリ", "相談", "記録者"]].head(10),
            use_container_width=True,
            hide_index=True,
        )