from __future__ import annotations

from datetime import date
import uuid

import pandas as pd
import streamlit as st

from ai_service import parse_quick_input_text
from config import (
    BABY_CATEGORY_LABELS,
    BABY_FEEDING_SUBTYPE_OPTIONS,
    BABY_MILK_UNIT,
    BABY_POOP_SUBTYPE_OPTIONS,
    BABY_SLEEP_SUBTYPE_OPTIONS,
    BABY_SLEEP_UNIT,
    BABY_TEMPERATURE_UNIT,
    MASTER_SETTING_KEYS,
    MOTHER_BLEEDING_STATUS_OPTIONS,
    MOTHER_CATEGORY_LABELS,
    MOTHER_PAIN_STATUS_OPTIONS,
    PREGNANCY_CATEGORY_LABELS,
    PREGNANCY_STATUS_OPTIONS,
    RECORDED_BY_OPTIONS,
    SHEET_BABY_LOGS,
    SHEET_MOTHER_LOGS,
    SHEET_PREGNANCY_LOGS,
    SHEET_TASKS,
    TASK_PRIORITY_OPTIONS,
)
from repository import (
    add_baby_log,
    add_mother_log,
    add_pregnancy_log,
    add_task,
    delete_row_by_id,
    get_master_settings_dict,
    get_recent_rows,
    read_sheet,
    update_row_by_id,
    upsert_master_setting,
)
from services import (
    build_edit_target_options,
    build_recent_display_rows,
    build_task_display_rows,
    get_emergency_settings_rows,
    get_open_tasks,
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


def render_voice_quick_input_section(
    recorded_by: str,
    key_prefix: str,
    allowed_targets: list[str],
    title: str = "🎙️ 音声クイック入力",
    desc: str = "スマホの音声入力で話した内容をAIが記録候補に変換します。",
):
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
        f"""
        <div class='section-card'>
            <div class='section-title'>{title}</div>
            <div class='section-desc'>{desc}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.text_area(
        "音声クイック入力",
        key=text_key,
        height=110,
        placeholder="例: 母乳10分、少し眠そう / りょうかが腰痛で中くらい / 張りが少し気になる",
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
                allowed_targets=allowed_targets,
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


def render_delete_record_box(
    sheet_name: str,
    id_column: str,
    record_id: str,
    item_label: str,
    key_prefix: str,
):
    st.markdown("---")
    st.markdown(
        f"""
        <div class='section-card'>
            <div class='section-title'>🗑️ {item_label}記録の削除</div>
            <div class='section-desc'>削除すると元に戻せません。実行前に確認してください。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    confirm = st.checkbox(
        f"{item_label}のこの記録を削除する",
        key=f"{key_prefix}_delete_confirm",
    )

    if st.button(
        f"{item_label}記録を削除",
        key=f"{key_prefix}_delete_button",
        use_container_width=True,
        type="secondary",
    ):
        if not confirm:
            st.error("削除する場合は確認チェックを入れてください。")
        else:
            ok = delete_row_by_id(sheet_name, id_column, record_id)
            if ok:
                save_success(f"{item_label}記録を削除したよ。")
            else:
                st.error("削除に失敗しました。")


def render_edit_pregnancy():
    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>✏️ 直近の妊娠後期記録を修正</div>
            <div class='section-desc'>最近の記録内容を選んで、状態やメモを更新できます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    options_df = build_edit_target_options(SHEET_PREGNANCY_LOGS, "妊娠後期", PREGNANCY_CATEGORY_LABELS)
    if options_df.empty:
        st.caption("編集できる妊娠後期記録はまだありません。")
        return

    option_map = dict(zip(options_df["表示"], options_df["record_id"]))
    selected_label = st.selectbox("修正する記録", list(option_map.keys()), key="edit_pregnancy_select")
    selected_id = option_map[selected_label]

    source_df = read_sheet(SHEET_PREGNANCY_LOGS)
    row = source_df[source_df["record_id"].astype(str) == str(selected_id)].iloc[0]

    with st.form("edit_pregnancy_form"):
        st.markdown("<div class='edit-box'>妊娠後期ログの内容を更新します。</div>", unsafe_allow_html=True)
        category_keys = list(PREGNANCY_CATEGORY_LABELS.keys())
        current_category = str(row.get("category", "symptom"))
        category = st.selectbox(
            "カテゴリ",
            options=category_keys,
            format_func=lambda x: PREGNANCY_CATEGORY_LABELS[x],
            index=category_keys.index(current_category) if current_category in category_keys else 0,
        )
        status = st.text_input("状態", value=str(row.get("status", "")))
        detail = st.text_input("詳細", value=str(row.get("detail", "")))
        memo = st.text_area("メモ", value=str(row.get("memo", "")))
        current_recorded_by = str(row.get("recorded_by", RECORDED_BY_OPTIONS[0]))
        recorded_by = st.selectbox(
            "記録者",
            RECORDED_BY_OPTIONS,
            index=RECORDED_BY_OPTIONS.index(current_recorded_by)
            if current_recorded_by in RECORDED_BY_OPTIONS
            else 0,
        )
        submit = st.form_submit_button("妊娠後期記録を更新", use_container_width=True)
        if submit:
            ok = update_row_by_id(
                SHEET_PREGNANCY_LOGS,
                "record_id",
                selected_id,
                {
                    "category": category,
                    "status": status,
                    "detail": detail,
                    "memo": memo,
                    "recorded_by": recorded_by,
                },
            )
            if ok:
                save_success("妊娠後期記録を更新したよ。")
            else:
                st.error("更新に失敗しました。")

    render_delete_record_box(
        sheet_name=SHEET_PREGNANCY_LOGS,
        id_column="record_id",
        record_id=selected_id,
        item_label="妊娠後期",
        key_prefix="pregnancy",
    )


def render_pregnancy(recorded_by: str):
    render_page_head(
        title="妊娠後期モード",
        emoji="🤰",
        kicker="PREGNANCY MODE",
        desc="張り・痛み・出血/破水メモ・受診判断・入院準備・緊急連絡先をひとつに集約した画面です。",
    )

    open_tasks = get_open_tasks(read_sheet(SHEET_TASKS))
    pregnancy_tasks = open_tasks[
        open_tasks.get("task_type", pd.Series(dtype=str)).astype(str).isin(
            ["birth_preparation", "hospital", "shopping", "family"]
        )
    ].copy()

    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>🌷 出産前モード</div>
            <div class='section-desc'>必要な記録と準備をひとつの画面群に集約しています。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    render_voice_quick_input_section(
        recorded_by=recorded_by,
        key_prefix="pregnancy_voice",
        allowed_targets=["pregnancy_logs", "mother_logs"],
        title="🎙️ 音声クイック入力",
        desc="張り・痛み・出血・受診メモなどを話した内容から記録候補を作ります。",
    )

    tab_hari, tab_pain, tab_fluid, tab_hospital, tab_bag, tab_emergency, tab_edit = st.tabs(
        ["張り", "痛み", "出血/破水", "通院・受診", "入院準備", "緊急連絡先", "記録修正"]
    )

    with tab_hari:
        with st.form("pregnancy_contraction_form"):
            status = st.selectbox("張りの状態", PREGNANCY_STATUS_OPTIONS, index=1)
            detail = st.text_input("詳細", placeholder="頻度、時間帯、何分くらい続いたか")
            memo = st.text_area("メモ", placeholder="気になることを自由に")
            submit = st.form_submit_button("張りを保存", use_container_width=True)
            if submit:
                add_pregnancy_log("symptom", status, f"張り / {detail}".strip(" /"), memo, recorded_by)
                save_success("張りの記録を保存したよ。")

    with tab_pain:
        with st.form("pregnancy_pain_form"):
            status = st.selectbox("痛みの強さ", MOTHER_PAIN_STATUS_OPTIONS, index=1)
            value = st.text_input("場所・内容", placeholder="腰、下腹部、恥骨など")
            memo = st.text_area("メモ", placeholder="いつからか、休むと変わるか")
            submit = st.form_submit_button("痛みを保存", use_container_width=True)
            if submit:
                add_mother_log("pain", status, value, "", memo, recorded_by)
                save_success("痛みの記録を保存したよ。")

    with tab_fluid:
        with st.form("pregnancy_fluid_form"):
            status = st.selectbox("状態", ["なし", "少量", "気になる", "要確認"], index=0)
            detail = st.selectbox("内容", ["出血", "破水っぽい", "おりもの", "その他"])
            memo = st.text_area("メモ", placeholder="色、量、におい、時間など")
            submit = st.form_submit_button("出血/破水メモを保存", use_container_width=True)
            if submit:
                add_pregnancy_log("symptom", status, detail, memo, recorded_by)
                save_success("出血/破水メモを保存したよ。")

    with tab_hospital:
        with st.form("pregnancy_hospital_form"):
            status = st.selectbox("通院・受診", ["予定確認", "受診した", "相談した", "要連絡"], index=0)
            detail = st.text_input("詳細", placeholder="病院名、受診内容、指示内容")
            memo = st.text_area("受診判断メモ", placeholder="次に何をするか、注意点など")
            submit = st.form_submit_button("通院・受診を保存", use_container_width=True)
            if submit:
                add_pregnancy_log("hospital", status, detail, memo, recorded_by)
                save_success("通院・受診記録を保存したよ。")

    with tab_bag:
        st.markdown(
            """
            <div class='section-card'>
                <div class='section-title'>🎒 入院準備チェック</div>
                <div class='section-desc'>入院バッグや出産前準備タスクをここでまとめて確認・追加できます。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        bag_task_table = build_task_display_rows(pregnancy_tasks, limit=10)
        if bag_task_table.empty:
            st.caption("入院準備系の未完了タスクはまだありません。下から追加できるよ。")
        else:
            st.dataframe(bag_task_table, use_container_width=True, hide_index=True)

        with st.form("pregnancy_bag_form"):
            title = st.text_input("準備するもの", placeholder="母子手帳、入院書類、飲み物、充電器など")
            detail = st.text_area("詳細", placeholder="入れる場所や確認メモ")
            due_date = st.date_input("期限", value=date.today())
            priority = st.selectbox("優先度", TASK_PRIORITY_OPTIONS, index=0)
            submit = st.form_submit_button("入院準備タスクを追加", use_container_width=True)
            if submit:
                if not title.strip():
                    st.error("準備するものを入れてください。")
                else:
                    add_task(
                        task_id=str(uuid.uuid4())[:8],
                        task_type="birth_preparation",
                        title=title.strip(),
                        detail=detail.strip(),
                        due_date=str(due_date),
                        status="未着手",
                        priority=priority,
                        owner=recorded_by,
                        memo="妊娠後期モードから追加",
                    )
                    save_success("入院準備タスクを追加したよ。")

    with tab_emergency:
        st.markdown(
            """
            <div class='section-card'>
                <div class='section-title'>☎️ 緊急連絡先</div>
                <div class='section-desc'>産院・夜間・タクシー・家族連絡先をまとめて確認できます。</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        settings_table = get_emergency_settings_rows()
        if settings_table.empty:
            st.caption("まだ設定されていません。")
        else:
            st.dataframe(settings_table, use_container_width=True, hide_index=True)

        current_settings = get_master_settings_dict()
        with st.form("pregnancy_emergency_settings_form"):
            hospital_main_phone = st.text_input(
                "産院代表番号",
                value=current_settings.get("hospital_main_phone", ""),
                placeholder="例: 052-000-0000",
            )
            hospital_night_phone = st.text_input(
                "夜間連絡先",
                value=current_settings.get("hospital_night_phone", ""),
                placeholder="例: 052-111-1111",
            )
            taxi_phone = st.text_input(
                "タクシー番号",
                value=current_settings.get("taxi_phone", ""),
                placeholder="例: 0120-000-000",
            )
            emergency_contact_1 = st.text_input(
                "緊急連絡先1",
                value=current_settings.get("emergency_contact_1", ""),
                placeholder="例: 実家・夫など",
            )
            emergency_contact_2 = st.text_input(
                "緊急連絡先2",
                value=current_settings.get("emergency_contact_2", ""),
                placeholder="予備の連絡先",
            )
            hospital_address = st.text_input(
                "産院住所",
                value=current_settings.get("hospital_address", ""),
                placeholder="住所を保存",
            )
            memo_emergency_rule = st.text_area(
                "受診判断メモ",
                value=current_settings.get("memo_emergency_rule", ""),
                placeholder="この症状ならまず連絡、などの家族ルール",
            )
            submit = st.form_submit_button("緊急連絡先を保存", use_container_width=True)
            if submit:
                payload = {
                    "hospital_main_phone": hospital_main_phone.strip(),
                    "hospital_night_phone": hospital_night_phone.strip(),
                    "taxi_phone": taxi_phone.strip(),
                    "emergency_contact_1": emergency_contact_1.strip(),
                    "emergency_contact_2": emergency_contact_2.strip(),
                    "hospital_address": hospital_address.strip(),
                    "memo_emergency_rule": memo_emergency_rule.strip(),
                }
                for key, value in payload.items():
                    upsert_master_setting(key, value, MASTER_SETTING_KEYS[key])
                save_success("緊急連絡先を保存したよ。")

    with tab_edit:
        render_edit_pregnancy()


def render_edit_baby():
    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>✏️ 直近の赤ちゃん記録を修正</div>
            <div class='section-desc'>最近の赤ちゃん記録を選んで、種別・数値・メモなどを直せます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    options_df = build_edit_target_options(SHEET_BABY_LOGS, "赤ちゃん", BABY_CATEGORY_LABELS)
    if options_df.empty:
        st.caption("編集できる赤ちゃん記録はまだありません。")
        return

    option_map = dict(zip(options_df["表示"], options_df["record_id"]))
    selected_label = st.selectbox("修正する記録", list(option_map.keys()), key="edit_baby_select")
    selected_id = option_map[selected_label]

    source_df = read_sheet(SHEET_BABY_LOGS)
    row = source_df[source_df["record_id"].astype(str) == str(selected_id)].iloc[0]

    with st.form("edit_baby_form"):
        st.markdown("<div class='edit-box'>赤ちゃんログの内容を更新します。</div>", unsafe_allow_html=True)
        category_keys = list(BABY_CATEGORY_LABELS.keys())
        current_category = str(row.get("category", "feeding"))
        category = st.selectbox(
            "カテゴリ",
            options=category_keys,
            format_func=lambda x: BABY_CATEGORY_LABELS[x],
            index=category_keys.index(current_category) if current_category in category_keys else 0,
        )
        subtype = st.text_input("種別", value=str(row.get("subtype", "")))
        value = st.text_input("値", value=str(row.get("value", "")))
        unit = st.text_input("単位", value=str(row.get("unit", "")))
        memo = st.text_area("メモ", value=str(row.get("memo", "")))
        current_recorded_by = str(row.get("recorded_by", RECORDED_BY_OPTIONS[0]))
        recorded_by = st.selectbox(
            "記録者",
            RECORDED_BY_OPTIONS,
            index=RECORDED_BY_OPTIONS.index(current_recorded_by)
            if current_recorded_by in RECORDED_BY_OPTIONS
            else 0,
        )
        submit = st.form_submit_button("赤ちゃん記録を更新", use_container_width=True)
        if submit:
            ok = update_row_by_id(
                SHEET_BABY_LOGS,
                "record_id",
                selected_id,
                {
                    "category": category,
                    "subtype": subtype,
                    "value": value,
                    "unit": unit,
                    "memo": memo,
                    "recorded_by": recorded_by,
                },
            )
            if ok:
                save_success("赤ちゃん記録を更新したよ。")
            else:
                st.error("更新に失敗しました。")

    render_delete_record_box(
        sheet_name=SHEET_BABY_LOGS,
        id_column="record_id",
        record_id=selected_id,
        item_label="赤ちゃん",
        key_prefix="baby",
    )


def render_baby(recorded_by: str):
    render_page_head(
        title="新生児記録",
        emoji="👶",
        kicker="NEWBORN LOG",
        desc="主要記録を片手で素早く入れるための画面です。授乳・排泄・睡眠・体温をすぐ残せます。",
    )

    recent_table = build_recent_display_rows(get_recent_rows(SHEET_BABY_LOGS, hours=24), BABY_CATEGORY_LABELS, limit=8)
    if recent_table.empty:
        st.caption("直近24時間の赤ちゃん記録はまだありません。")
    else:
        st.dataframe(recent_table, use_container_width=True, hide_index=True)

    render_voice_quick_input_section(
        recorded_by=recorded_by,
        key_prefix="baby_voice",
        allowed_targets=["baby_logs"],
        title="🎙️ 音声クイック入力",
        desc="授乳・ミルク・排泄・睡眠・体温を、話した内容から記録候補に変換します。",
    )

    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>🍼 クイック記録</div>
            <div class='section-desc'>授乳・排泄・睡眠・体温を、スマホでも押しやすく入力できます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_feed, tab_milk, tab_pee, tab_poop, tab_sleep, tab_temp, tab_symptom, tab_edit = st.tabs(
        ["授乳", "ミルク", "おしっこ", "うんち", "睡眠", "体温", "症状", "記録修正"]
    )

    with tab_feed:
        with st.form("baby_feeding_form"):
            subtype = st.selectbox("授乳種別", BABY_FEEDING_SUBTYPE_OPTIONS)
            value = st.number_input("時間（分）", min_value=0, max_value=180, value=10, step=1)
            memo = st.text_area("メモ", placeholder="左右、飲み方、気になる様子など")
            submit = st.form_submit_button("授乳を保存", use_container_width=True)
            if submit:
                add_baby_log("feeding", subtype, value, BABY_SLEEP_UNIT, memo, recorded_by)
                save_success("授乳記録を保存したよ。")

    with tab_milk:
        with st.form("baby_milk_form"):
            value = st.number_input("量（ml）", min_value=0, max_value=500, value=80, step=5)
            memo = st.text_area("メモ", placeholder="飲み切ったか、残したかなど")
            submit = st.form_submit_button("ミルクを保存", use_container_width=True)
            if submit:
                add_baby_log("milk", "ミルク", value, BABY_MILK_UNIT, memo, recorded_by)
                save_success("ミルク記録を保存したよ。")

    with tab_pee:
        with st.form("baby_pee_form"):
            subtype = st.selectbox("状態", ["普通", "少なめ", "多め"])
            memo = st.text_area("メモ", placeholder="色や気になる点があれば")
            submit = st.form_submit_button("おしっこを保存", use_container_width=True)
            if submit:
                add_baby_log("pee", subtype, 1, "回", memo, recorded_by)
                save_success("おしっこ記録を保存したよ。")

    with tab_poop:
        with st.form("baby_poop_form"):
            subtype = st.selectbox("状態", BABY_POOP_SUBTYPE_OPTIONS)
            memo = st.text_area("メモ", placeholder="色や量など")
            submit = st.form_submit_button("うんちを保存", use_container_width=True)
            if submit:
                add_baby_log("poop", subtype, 1, "回", memo, recorded_by)
                save_success("うんち記録を保存したよ。")

    with tab_sleep:
        with st.form("baby_sleep_form"):
            subtype = st.selectbox("睡眠イベント", BABY_SLEEP_SUBTYPE_OPTIONS)
            value = st.number_input("時間（分）", min_value=0, max_value=1440, value=30, step=5)
            memo = st.text_area("メモ", placeholder="寝つきや起き方など")
            submit = st.form_submit_button("睡眠を保存", use_container_width=True)
            if submit:
                add_baby_log("sleep", subtype, value, BABY_SLEEP_UNIT, memo, recorded_by)
                save_success("睡眠記録を保存したよ。")

    with tab_temp:
        with st.form("baby_temp_form"):
            value = st.number_input("体温", min_value=34.0, max_value=42.0, value=36.8, step=0.1, format="%.1f")
            memo = st.text_area("メモ", placeholder="機嫌、測った部位など")
            submit = st.form_submit_button("体温を保存", use_container_width=True)
            if submit:
                add_baby_log("temperature", "体温", value, BABY_TEMPERATURE_UNIT, memo, recorded_by)
                save_success("体温記録を保存したよ。")

    with tab_symptom:
        with st.form("baby_symptom_form"):
            subtype = st.text_input("症状", placeholder="咳、鼻水、吐き戻しなど")
            memo = st.text_area("メモ", placeholder="いつからか、どんな様子か")
            submit = st.form_submit_button("症状メモを保存", use_container_width=True)
            if submit:
                if not subtype.strip():
                    st.error("症状を入力してください。")
                else:
                    add_baby_log("symptom", subtype.strip(), "", "", memo, recorded_by)
                    save_success("症状メモを保存したよ。")

    with tab_edit:
        render_edit_baby()


def render_edit_mother():
    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>✏️ 直近の母体記録を修正</div>
            <div class='section-desc'>最近の母体記録を選んで、状態・数値・メモを更新できます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    options_df = build_edit_target_options(SHEET_MOTHER_LOGS, "母体", MOTHER_CATEGORY_LABELS)
    if options_df.empty:
        st.caption("編集できる母体記録はまだありません。")
        return

    option_map = dict(zip(options_df["表示"], options_df["record_id"]))
    selected_label = st.selectbox("修正する記録", list(option_map.keys()), key="edit_mother_select")
    selected_id = option_map[selected_label]

    source_df = read_sheet(SHEET_MOTHER_LOGS)
    row = source_df[source_df["record_id"].astype(str) == str(selected_id)].iloc[0]

    with st.form("edit_mother_form"):
        st.markdown("<div class='edit-box'>母体ログの内容を更新します。</div>", unsafe_allow_html=True)
        category_keys = list(MOTHER_CATEGORY_LABELS.keys())
        current_category = str(row.get("category", "sleep"))
        category = st.selectbox(
            "カテゴリ",
            options=category_keys,
            format_func=lambda x: MOTHER_CATEGORY_LABELS[x],
            index=category_keys.index(current_category) if current_category in category_keys else 0,
        )
        status = st.text_input("状態", value=str(row.get("status", "")))
        value = st.text_input("値", value=str(row.get("value", "")))
        unit = st.text_input("単位", value=str(row.get("unit", "")))
        memo = st.text_area("メモ", value=str(row.get("memo", "")))
        current_recorded_by = str(row.get("recorded_by", RECORDED_BY_OPTIONS[0]))
        recorded_by = st.selectbox(
            "記録者",
            RECORDED_BY_OPTIONS,
            index=RECORDED_BY_OPTIONS.index(current_recorded_by)
            if current_recorded_by in RECORDED_BY_OPTIONS
            else 0,
        )
        submit = st.form_submit_button("母体記録を更新", use_container_width=True)
        if submit:
            ok = update_row_by_id(
                SHEET_MOTHER_LOGS,
                "record_id",
                selected_id,
                {
                    "category": category,
                    "status": status,
                    "value": value,
                    "unit": unit,
                    "memo": memo,
                    "recorded_by": recorded_by,
                },
            )
            if ok:
                save_success("母体記録を更新したよ。")
            else:
                st.error("更新に失敗しました。")

    render_delete_record_box(
        sheet_name=SHEET_MOTHER_LOGS,
        id_column="record_id",
        record_id=selected_id,
        item_label="母体",
        key_prefix="mother",
    )


def render_mother(recorded_by: str):
    render_page_head(
        title="母体ケア",
        emoji="🩺",
        kicker="MOTHER CARE",
        desc="睡眠・食事・痛み・出血・気分・薬・通院をまとめて記録する画面です。",
    )

    recent_table = build_recent_display_rows(get_recent_rows(SHEET_MOTHER_LOGS, hours=24), MOTHER_CATEGORY_LABELS, limit=8)
    if recent_table.empty:
        st.caption("直近24時間の母体記録はまだありません。")
    else:
        st.dataframe(recent_table, use_container_width=True, hide_index=True)

    render_voice_quick_input_section(
        recorded_by=recorded_by,
        key_prefix="mother_voice",
        allowed_targets=["mother_logs"],
        title="🎙️ 音声クイック入力",
        desc="睡眠・食事・痛み・出血・気分・服薬・通院を、話した内容から記録候補に変換します。",
    )

    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>🌼 体調記録</div>
            <div class='section-desc'>母体の状態を、必要なカテゴリごとにやさしく記録できます。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    tab_sleep, tab_meal, tab_pain, tab_bleeding, tab_mood, tab_medicine, tab_hospital, tab_edit = st.tabs(
        ["睡眠", "食事", "痛み", "出血", "気分", "服薬", "通院", "記録修正"]
    )

    with tab_sleep:
        with st.form("mother_sleep_form"):
            status = st.selectbox("睡眠の状態", ["寝た", "起きた", "少し休めた", "眠れていない"])
            value = st.number_input("時間（分）", min_value=0, max_value=1440, value=60, step=10)
            memo = st.text_area("メモ")
            submit = st.form_submit_button("睡眠を保存", use_container_width=True)
            if submit:
                add_mother_log("sleep", status, value, "分", memo, recorded_by)
                save_success("母体の睡眠記録を保存したよ。")

    with tab_meal:
        with st.form("mother_meal_form"):
            status = st.selectbox("食事の状態", ["しっかり食べた", "少し食べた", "食欲なし", "水分のみ"])
            value = st.text_input("内容", placeholder="ごはん、パン、ゼリーなど")
            memo = st.text_area("メモ")
            submit = st.form_submit_button("食事を保存", use_container_width=True)
            if submit:
                add_mother_log("meal", status, value, "", memo, recorded_by)
                save_success("食事記録を保存したよ。")

    with tab_pain:
        with st.form("mother_pain_form"):
            status = st.selectbox("痛みの強さ", MOTHER_PAIN_STATUS_OPTIONS, index=1)
            value = st.text_input("場所", placeholder="腰、下腹部、会陰など")
            memo = st.text_area("メモ")
            submit = st.form_submit_button("痛みを保存", use_container_width=True)
            if submit:
                add_mother_log("pain", status, value, "", memo, recorded_by)
                save_success("痛み記録を保存したよ。")

    with tab_bleeding:
        with st.form("mother_bleeding_form"):
            status = st.selectbox("出血の量", MOTHER_BLEEDING_STATUS_OPTIONS)
            value = st.text_input("状態", placeholder="鮮血、茶色っぽいなど")
            memo = st.text_area("メモ")
            submit = st.form_submit_button("出血を保存", use_container_width=True)
            if submit:
                add_mother_log("bleeding", status, value, "", memo, recorded_by)
                save_success("出血記録を保存したよ。")

    with tab_mood:
        with st.form("mother_mood_form"):
            status = st.selectbox("気分", ["安定", "少し不安", "不安強め", "疲れ気味", "つらい"])
            value = st.text_input("ひとこと", placeholder="眠い、焦る、落ち着いてるなど")
            memo = st.text_area("メモ")
            submit = st.form_submit_button("気分を保存", use_container_width=True)
            if submit:
                add_mother_log("mood", status, value, "", memo, recorded_by)
                save_success("気分記録を保存したよ。")

    with tab_medicine:
        with st.form("mother_medicine_form"):
            status = st.selectbox("服薬", ["飲んだ", "飲んでいない", "必要時のみ"])
            value = st.text_input("薬名", placeholder="処方薬、サプリなど")
            memo = st.text_area("メモ")
            submit = st.form_submit_button("服薬を保存", use_container_width=True)
            if submit:
                add_mother_log("medicine", status, value, "", memo, recorded_by)
                save_success("服薬記録を保存したよ。")

    with tab_hospital:
        with st.form("mother_hospital_form"):
            status = st.selectbox("通院・受診", ["予定あり", "受診した", "相談した", "要確認"])
            value = st.text_input("内容", placeholder="病院名、診察内容など")
            memo = st.text_area("メモ")
            submit = st.form_submit_button("通院を保存", use_container_width=True)
            if submit:
                add_mother_log("hospital", status, value, "", memo, recorded_by)
                save_success("通院記録を保存したよ。")

    with tab_edit:
        render_edit_mother()