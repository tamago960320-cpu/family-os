from __future__ import annotations

import streamlit as st

from config import (
    APP_ICON,
    APP_NAME,
    MASTER_SETTING_KEYS,
    PAGE_BABY,
    PAGE_CONSULT,
    PAGE_HOME,
    PAGE_ICONS,
    PAGE_MOTHER,
    PAGE_PREGNANCY,
    PAGE_SUMMARY,
    PAGE_TASKS,
    PAGES,
    RECORDED_BY_OPTIONS,
)
from repository import (
    backfill_record_ids,
    ensure_required_sheets,
    get_master_settings_dict,
    upsert_master_setting,
)
from pages.home_page import render_home
from pages.record_pages import render_baby, render_mother, render_pregnancy
from pages.assist_pages import render_consult, render_summary, render_tasks

st.set_page_config(page_title=APP_NAME, page_icon=APP_ICON, layout="centered")

CARD_STYLE = """
<style>
:root {
    --bg-main:
        radial-gradient(circle at top right, rgba(255, 223, 238, 0.52) 0%, rgba(255,255,255,0) 28%),
        radial-gradient(circle at top left, rgba(226, 239, 255, 0.40) 0%, rgba(255,255,255,0) 24%),
        linear-gradient(180deg, #fff9fc 0%, #fffefe 34%, #f8fbff 100%);
    --card-bg: rgba(255, 255, 255, 0.94);
    --card-border: rgba(255, 186, 214, 0.26);
    --card-border-soft: rgba(194, 198, 234, 0.20);
    --card-shadow: 0 10px 24px rgba(233, 157, 191, 0.08);
    --card-shadow-soft: 0 6px 14px rgba(190, 188, 223, 0.06);

    --text-main: #5c4d58;
    --text-sub: #8b7a86;
    --text-soft: #a3929d;

    --accent: #f38bb2;
    --accent-strong: #ea6d9e;
    --accent-soft: #fff3f8;

    --radius-xxl: 24px;
    --radius-xl: 20px;
    --radius-lg: 16px;
    --radius-md: 12px;
}

html, body, [data-testid="stAppViewContainer"] {
    background: var(--bg-main);
    color: var(--text-main);
}

[data-testid="stAppViewContainer"] {
    background-attachment: fixed;
}

[data-testid="stHeader"] {
    background: rgba(255,255,255,0);
}

.block-container {
    max-width: 760px;
    padding-top: 0.35rem;
    padding-bottom: 6.4rem;
}

h1, h2, h3 {
    color: #5d4b62;
    letter-spacing: 0.01em;
}

p, li, label, div, span {
    color: var(--text-main);
}

.page-head {
    border: 1px solid rgba(255, 187, 214, 0.28);
    border-radius: var(--radius-xxl);
    padding: 15px 15px 12px 15px;
    margin-bottom: 12px;
    background:
        radial-gradient(circle at top right, rgba(255, 230, 240, 0.72) 0%, rgba(255,255,255,0) 30%),
        linear-gradient(135deg, rgba(255,255,255,0.98) 0%, rgba(252,246,255,0.96) 100%);
    box-shadow: 0 10px 22px rgba(235, 150, 186, 0.09);
}

.page-kicker {
    font-size: 0.78rem;
    font-weight: 800;
    letter-spacing: 0.06em;
    color: #c17396;
    margin-bottom: 4px;
}

.page-title {
    font-size: 1.18rem;
    font-weight: 800;
    color: #5e4a61;
    margin-bottom: 4px;
}

.page-desc {
    color: var(--text-sub);
    font-size: 0.92rem;
    line-height: 1.55;
}

.section-card {
    border: 1px solid var(--card-border);
    border-radius: var(--radius-xl);
    padding: 13px 14px 11px 14px;
    margin-bottom: 12px;
    background: linear-gradient(135deg, rgba(255,255,255,0.96) 0%, rgba(255,247,251,0.94) 100%);
    box-shadow: var(--card-shadow);
    backdrop-filter: blur(8px);
}

.hero-card {
    border: 1px solid rgba(255, 186, 214, 0.30);
    border-radius: 24px;
    padding: 14px 15px 12px 15px;
    margin-bottom: 10px;
    background:
        radial-gradient(circle at top right, rgba(255, 225, 239, 0.78) 0%, rgba(255,255,255,0) 28%),
        linear-gradient(135deg, rgba(255,255,255,0.98) 0%, rgba(251,246,255,0.97) 100%);
    box-shadow: 0 10px 22px rgba(235, 150, 186, 0.10);
}

.section-title {
    font-size: 1rem;
    font-weight: 800;
    margin-bottom: 4px;
    color: #604b63;
}

.section-desc {
    color: var(--text-sub);
    font-size: 0.90rem;
    line-height: 1.5;
}

.mini-chip-row {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;
    margin-top: 9px;
}

.mini-chip {
    display: inline-block;
    border-radius: 999px;
    padding: 5px 10px;
    font-size: 0.78rem;
    font-weight: 700;
    color: #7a6070;
    background: linear-gradient(135deg, #fff2f7 0%, #f8f3ff 100%);
    border: 1px solid rgba(243, 139, 178, 0.16);
}

.compact-top-card {
    border: 1px solid rgba(255, 186, 214, 0.24);
    border-radius: 18px;
    padding: 11px 12px 10px 12px;
    margin-bottom: 10px;
    background: rgba(255,255,255,0.92);
    box-shadow: var(--card-shadow-soft);
}

.compact-top-title {
    font-size: 0.82rem;
    font-weight: 800;
    color: #b06b8e;
    margin-bottom: 4px;
}

.compact-top-text {
    font-size: 0.88rem;
    color: var(--text-sub);
    line-height: 1.45;
}

.home-stat-grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-bottom: 10px;
}

.home-stat-grid-3 {
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 10px;
    margin-bottom: 10px;
}

.home-stat-card {
    border: 1px solid rgba(255, 186, 214, 0.22);
    border-radius: 18px;
    padding: 12px 12px 10px 12px;
    background: rgba(255,255,255,0.92);
    box-shadow: var(--card-shadow-soft);
}

.home-stat-label {
    font-size: 0.84rem;
    color: var(--text-sub);
    margin-bottom: 6px;
    line-height: 1.35;
}

.home-stat-value {
    font-size: 1.55rem;
    font-weight: 800;
    color: #5d4b62;
    line-height: 1.1;
}

.home-stat-value.small {
    font-size: 1.2rem;
}

.timeline-card {
    border: 1px solid rgba(255, 186, 214, 0.18);
    border-radius: 16px;
    padding: 11px 12px 10px 12px;
    background: rgba(255,255,255,0.92);
    box-shadow: var(--card-shadow-soft);
    margin-bottom: 8px;
}

.timeline-top {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 8px;
    margin-bottom: 6px;
}

.timeline-time {
    font-size: 0.78rem;
    font-weight: 700;
    color: var(--text-sub);
}

.timeline-category {
    font-size: 0.76rem;
    font-weight: 700;
    color: #b06b8e;
    background: #fff2f7;
    border: 1px solid rgba(243, 139, 178, 0.14);
    border-radius: 999px;
    padding: 3px 8px;
    white-space: nowrap;
}

.timeline-body {
    font-size: 0.90rem;
    color: var(--text-main);
    line-height: 1.45;
}

.task-mini-card {
    border: 1px solid rgba(255, 186, 214, 0.18);
    border-radius: 16px;
    padding: 11px 12px 10px 12px;
    background: rgba(255,255,255,0.92);
    box-shadow: var(--card-shadow-soft);
    margin-bottom: 8px;
}

.task-mini-title {
    font-size: 0.95rem;
    font-weight: 800;
    color: #5d4b62;
    margin-bottom: 4px;
}

.task-mini-meta {
    font-size: 0.80rem;
    color: var(--text-sub);
    line-height: 1.4;
}

.quick-grid-2 {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
}

.bottom-nav-wrap {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 999;
    background: rgba(255, 252, 253, 0.96);
    border-top: 1px solid rgba(255, 190, 216, 0.26);
    padding: 8px 10px calc(8px + env(safe-area-inset-bottom));
    backdrop-filter: blur(12px);
    box-shadow: 0 -8px 18px rgba(233, 187, 208, 0.10);
}

.bottom-nav-title {
    text-align: center;
    font-size: 0.76rem;
    color: var(--text-sub);
    margin-bottom: 6px;
    font-weight: 700;
}

.bottom-nav-wrap div[role="radiogroup"] {
    display: flex !important;
    gap: 8px;
    overflow-x: auto;
    flex-wrap: nowrap !important;
    padding-bottom: 2px;
    scrollbar-width: none;
}

.bottom-nav-wrap div[role="radiogroup"]::-webkit-scrollbar {
    display: none;
}

.bottom-nav-wrap div[role="radiogroup"] > label {
    min-width: fit-content;
    margin: 0 !important;
}

.bottom-nav-wrap div[role="radiogroup"] label[data-baseweb="radio"] {
    background: rgba(255,255,255,0.92);
    border: 1px solid rgba(236, 107, 159, 0.14);
    border-radius: 999px;
    padding: 9px 14px;
    box-shadow: 0 6px 14px rgba(240, 170, 196, 0.08);
    transition: all 0.18s ease;
}

.bottom-nav-wrap div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) {
    background: linear-gradient(135deg, #ffeaf3 0%, #f6efff 100%);
    border: 1px solid rgba(236, 107, 159, 0.24);
    box-shadow: 0 8px 16px rgba(235, 150, 186, 0.14);
}

.bottom-nav-wrap div[role="radiogroup"] label[data-baseweb="radio"] > div:last-child {
    font-size: 0.88rem;
    font-weight: 800;
    color: #6a5163;
    white-space: nowrap;
}

.bottom-nav-wrap div[role="radiogroup"] input[type="radio"] {
    display: none !important;
}

@media (max-width: 640px) {
    .timeline-top {
        align-items: flex-start;
        flex-direction: column;
        gap: 4px;
    }

    .timeline-category {
        white-space: normal;
    }
}

div[data-baseweb="select"] > div,
div[data-baseweb="input"] > div,
textarea,
input {
    border-radius: 14px !important;
}

textarea, input {
    background: rgba(255,255,255,0.97) !important;
}

button[kind],
.stButton > button,
.stDownloadButton > button,
.stFormSubmitButton > button {
    border-radius: 999px !important;
    border: 1px solid rgba(236, 107, 159, 0.16) !important;
    min-height: 2.85rem !important;
    font-weight: 700 !important;
    box-shadow: 0 6px 14px rgba(240, 170, 196, 0.08);
    transition: all 0.18s ease;
}

.stButton > button[kind="primary"],
.stFormSubmitButton > button[kind="primary"] {
    background: linear-gradient(135deg, #f6a3c4 0%, #f38bb2 55%, #eb78a4 100%) !important;
    color: white !important;
    border: none !important;
}

.stButton > button[kind="secondary"],
.stFormSubmitButton > button[kind="secondary"] {
    background: rgba(255,255,255,0.94) !important;
    color: #6f5a69 !important;
}

div[role="tablist"] {
    gap: 0.35rem;
    margin-bottom: 0.45rem;
}

button[role="tab"] {
    border-radius: 999px !important;
    padding: 0.42rem 0.88rem !important;
    background: rgba(255,255,255,0.76) !important;
    border: 1px solid rgba(236, 107, 159, 0.12) !important;
    min-height: auto !important;
}

button[role="tab"][aria-selected="true"] {
    background: linear-gradient(135deg, #ffeaf3 0%, #f6efff 100%) !important;
    color: #6a5163 !important;
    font-weight: 800 !important;
}

[data-testid="stAlert"] {
    border-radius: 16px;
    border: none;
    box-shadow: 0 6px 14px rgba(0, 0, 0, 0.03);
}

.bottom-nav-wrap {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 999;
    background: rgba(255, 252, 253, 0.96);
    border-top: 1px solid rgba(255, 190, 216, 0.26);
    padding: 8px 10px calc(8px + env(safe-area-inset-bottom));
    backdrop-filter: blur(12px);
    box-shadow: 0 -8px 18px rgba(233, 187, 208, 0.10);
}

.bottom-nav-scroll {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding-bottom: 2px;
    scrollbar-width: none;
}

.bottom-nav-scroll::-webkit-scrollbar {
    display: none;
}

.bottom-nav-title {
    text-align: center;
    font-size: 0.76rem;
    color: var(--text-sub);
    margin-bottom: 6px;
    font-weight: 700;
}

.bottom-nav-wrap .stButton {
    min-width: 108px;
    flex: 0 0 auto;
}

.bottom-nav-wrap .stButton > button {
    min-height: 2.45rem !important;
    padding: 0.45rem 0.82rem !important;
    white-space: nowrap !important;
}

.footer-safe-space {
    height: 2px;
}

hr {
    border: none;
    border-top: 1px solid rgba(236, 107, 159, 0.10);
    margin: 0.8rem 0;
}

@media (max-width: 640px) {
    .block-container {
        padding-top: 0.24rem;
        padding-left: 0.72rem;
        padding-right: 0.72rem;
        padding-bottom: 6.5rem;
    }

    .hero-card,
    .page-head,
    .section-card {
        border-radius: 20px;
    }

    .hero-card {
        padding: 13px 13px 11px 13px;
        margin-bottom: 9px;
    }

    .page-head {
        padding: 13px 13px 11px 13px;
        margin-bottom: 10px;
    }

    .section-card {
        padding: 12px 12px 10px 12px;
        margin-bottom: 10px;
    }

    .page-title {
        font-size: 1.08rem;
    }

    .page-desc,
    .section-desc {
        font-size: 0.88rem;
        line-height: 1.48;
    }

    .home-stat-grid-3,
    .quick-grid-2 {
        grid-template-columns: 1fr;
    }

    .home-stat-value {
        font-size: 1.35rem;
    }
}
</style>
"""


def _get_page_from_query() -> str:
    try:
        page = st.query_params.get("page", PAGE_HOME)
        if page in PAGES:
            return page
    except Exception:
        pass
    return PAGE_HOME


def set_current_page(page: str):
    if page not in PAGES:
        page = PAGE_HOME
    st.session_state["current_page"] = page
    try:
        st.query_params["page"] = page
    except Exception:
        pass


def init_app():
    if "default_recorded_by" not in st.session_state:
        st.session_state["default_recorded_by"] = RECORDED_BY_OPTIONS[0]

    if "schema_checked" not in st.session_state:
        st.session_state["schema_checked"] = False

    query_page = _get_page_from_query()
    current_page = st.session_state.get("current_page", query_page)

    if current_page not in PAGES:
        current_page = PAGE_HOME

    set_current_page(current_page)


def render_header():
    st.markdown(CARD_STYLE, unsafe_allow_html=True)
    st.markdown(
        f"""
        <div class='hero-card'>
            <div class='section-title'>{APP_ICON} {APP_NAME}</div>
            <div class='section-desc'>今やることがすぐ分かる、スマホ前提の家族OS。</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_global_controls() -> str:
    current_default = st.session_state.get("default_recorded_by", RECORDED_BY_OPTIONS[0])
    default_index = RECORDED_BY_OPTIONS.index(current_default) if current_default in RECORDED_BY_OPTIONS else 0

    st.markdown(
        """
        <div class='compact-top-card'>
            <div class='compact-top-title'>👤 記録者</div>
            <div class='compact-top-text'>
                 だれが記録したかが残ります（家族で共有できます）
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    recorded_by = st.selectbox(
        "記録者",
        RECORDED_BY_OPTIONS,
        index=default_index,
        label_visibility="collapsed",
    )
    st.session_state["default_recorded_by"] = recorded_by
    return recorded_by


def render_bottom_nav():
    current_page = st.session_state.get("current_page", PAGE_HOME)

    labels = [f"{PAGE_ICONS.get(page, '')} {page}" for page in PAGES]
    label_to_page = {f"{PAGE_ICONS.get(page, '')} {page}": page for page in PAGES}

    current_label = f"{PAGE_ICONS.get(current_page, '')} {current_page}"
    if current_label not in labels:
        current_label = labels[0]

    st.markdown("<div class='bottom-nav-wrap'>", unsafe_allow_html=True)
    st.markdown("<div class='bottom-nav-title'>画面切替</div>", unsafe_allow_html=True)

    selected_label = st.radio(
        "画面切替",
        options=labels,
        index=labels.index(current_label),
        horizontal=True,
        label_visibility="collapsed",
        key="bottom_nav_radio",
    )

    selected_page = label_to_page[selected_label]
    if selected_page != current_page:
        set_current_page(selected_page)
        st.markdown(
            """
            <script>
                window.scrollTo(0, 0);
            </script>
            """,
            unsafe_allow_html=True,
        )
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)
    st.markdown("<div class='footer-safe-space'></div>", unsafe_allow_html=True)


def _bool_from_setting(value: str, default: bool = False) -> bool:
    text = str(value).strip().lower()
    if not text:
        return default
    return text in {"1", "true", "on", "yes", "y"}


def _int_from_setting(value: str, default: int) -> int:
    try:
        return int(str(value).strip())
    except Exception:
        return default


def render_line_settings():
    st.markdown(
        """
        <div class='section-card'>
            <div class='section-title'>💬 LINE通知設定</div>
            <div class='section-desc'>
                LINEグループ通知のON/OFF、トークン、グループID、通知時刻をここから編集できます。
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    settings = get_master_settings_dict()

    enabled_default = _bool_from_setting(settings.get("line_notifications_enabled", ""), False)
    task_due_default = _bool_from_setting(settings.get("notify_task_due_morning_enabled", ""), True)
    high_priority_default = _bool_from_setting(settings.get("notify_high_priority_advance_enabled", ""), True)
    gap_default = _bool_from_setting(settings.get("notify_gap_check_enabled", ""), True)
    daily_attention_default = _bool_from_setting(settings.get("notify_daily_attention_enabled", ""), True)
    summary_default = _bool_from_setting(settings.get("notify_summary_on_update_enabled", ""), True)

    morning_hour_default = _int_from_setting(settings.get("notify_morning_hour", ""), 8)
    if morning_hour_default < 0 or morning_hour_default > 23:
        morning_hour_default = 8

    gap_hours_default = _int_from_setting(settings.get("notify_gap_hours", ""), 6)
    if gap_hours_default not in [1, 2, 3, 4, 6, 8, 12, 24]:
        gap_hours_default = 6

    summary_hour_default = _int_from_setting(settings.get("notify_summary_daily_hour", ""), 20)
    if summary_hour_default < 0 or summary_hour_default > 23:
        summary_hour_default = 20

    with st.form("line_settings_form"):
        st.caption("LINE Developers の値と、Webhookで取得した group_id をここに保存します。")

        line_notifications_enabled = st.checkbox("LINE通知を有効にする", value=enabled_default)

        line_channel_access_token = st.text_area(
            "LINEチャネルアクセストークン",
            value=settings.get("line_channel_access_token", ""),
            height=120,
            placeholder="LINE Messaging API のチャネルアクセストークン",
        )

        line_channel_secret = st.text_input(
            "LINEチャネルシークレット",
            value=settings.get("line_channel_secret", ""),
            type="password",
            placeholder="Webhook署名検証に使うシークレット",
        )

        line_group_id = st.text_input(
            "LINEグループID",
            value=settings.get("line_group_id", ""),
            placeholder="Webhookで自動取得された groupId",
        )

        col1, col2 = st.columns(2)
        with col1:
            notify_morning_hour = st.selectbox(
                "朝通知の時刻",
                options=list(range(0, 24)),
                index=morning_hour_default,
                format_func=lambda x: f"{x:02d}:00",
            )
        with col2:
            notify_gap_hours = st.selectbox(
                "抜け漏れ通知間隔",
                options=[1, 2, 3, 4, 6, 8, 12, 24],
                index=[1, 2, 3, 4, 6, 8, 12, 24].index(gap_hours_default),
                format_func=lambda x: f"{x}時間ごと",
            )

        notify_summary_daily_hour = st.selectbox(
            "日次サマリー通知の時刻",
            options=list(range(0, 24)),
            index=summary_hour_default,
            format_func=lambda x: f"{x:02d}:00",
        )

        st.markdown("---")
        st.caption("通知種別ごとにON/OFFできます。")

        notify_task_due_morning_enabled = st.checkbox(
            "タスク期限当日通知を有効にする",
            value=task_due_default,
        )
        notify_high_priority_advance_enabled = st.checkbox(
            "高優先度未完了通知を有効にする",
            value=high_priority_default,
        )
        notify_gap_check_enabled = st.checkbox(
            "記録抜け漏れ通知を有効にする",
            value=gap_default,
        )
        notify_daily_attention_enabled = st.checkbox(
            "今日の注意メモ通知を有効にする",
            value=daily_attention_default,
        )
        notify_summary_on_update_enabled = st.checkbox(
            "日次サマリー通知を有効にする",
            value=summary_default,
        )

        submit = st.form_submit_button("LINE設定を保存", use_container_width=True)

        if submit:
            payload = {
                "line_notifications_enabled": "TRUE" if line_notifications_enabled else "FALSE",
                "line_channel_access_token": line_channel_access_token.strip(),
                "line_channel_secret": line_channel_secret.strip(),
                "line_group_id": line_group_id.strip(),
                "notify_morning_hour": str(notify_morning_hour),
                "notify_gap_hours": str(notify_gap_hours),
                "notify_summary_daily_hour": str(notify_summary_daily_hour),
                "notify_task_due_morning_enabled": "TRUE" if notify_task_due_morning_enabled else "FALSE",
                "notify_high_priority_advance_enabled": "TRUE" if notify_high_priority_advance_enabled else "FALSE",
                "notify_gap_check_enabled": "TRUE" if notify_gap_check_enabled else "FALSE",
                "notify_daily_attention_enabled": "TRUE" if notify_daily_attention_enabled else "FALSE",
                "notify_summary_on_update_enabled": "TRUE" if notify_summary_on_update_enabled else "FALSE",
            }

            for key, value in payload.items():
                upsert_master_setting(key, value, MASTER_SETTING_KEYS.get(key, key))

            st.success("LINE設定を保存したよ。GAS側の再初期化が必要なら initializeLineNotificationSetup() をもう一度実行してね。")


def render_schema_maintenance():
    with st.expander("⚙️ 初期設定・シート整備", expanded=False):
        st.caption("普段は押さなくてOK。シート列を追加した直後や初期設定時だけ使う。")

        if st.button("必須シートとヘッダーを確認", use_container_width=True, key="run_schema_check"):
            ensure_required_sheets()
            st.session_state["schema_checked"] = True
            st.success("必須シートとヘッダーを確認したよ。")

        st.markdown("---")
        st.caption("旧データ補完が必要なときだけ使う。")

        confirm = st.checkbox("旧データの record_id を一括補完する", key="confirm_backfill_record_ids")

        if st.button("record_id を一括補完", use_container_width=True, key="run_backfill_record_ids"):
            if not confirm:
                st.error("実行する場合は確認チェックを入れてください。")
            else:
                try:
                    result = backfill_record_ids()
                    total_updated = int(result.get("total_updated", 0))
                    detail_rows = []
                    for item in result.get("results", []):
                        detail_rows.append(
                            {
                                "シート": item.get("sheet_name", ""),
                                "補完件数": item.get("updated_count", 0),
                            }
                        )

                    if total_updated > 0:
                        st.success(f"record_id を {total_updated} 件補完したよ。")
                    else:
                        st.info("補完対象の旧データはありませんでした。")

                    if detail_rows:
                        st.dataframe(detail_rows, use_container_width=True, hide_index=True)
                except Exception as exc:
                    st.error(f"record_id 補完に失敗しました: {exc}")

        st.markdown("---")
        render_line_settings()


def main():
    init_app()
    render_header()
    recorded_by = render_global_controls()
    render_schema_maintenance()

    page = st.session_state["current_page"]

    if page == PAGE_HOME:
        render_home(recorded_by)
    elif page == PAGE_PREGNANCY:
        render_pregnancy(recorded_by)
    elif page == PAGE_BABY:
        render_baby(recorded_by)
    elif page == PAGE_MOTHER:
        render_mother(recorded_by)
    elif page == PAGE_SUMMARY:
        render_summary()
    elif page == PAGE_TASKS:
        render_tasks(recorded_by)
    elif page == PAGE_CONSULT:
        render_consult(recorded_by)

    render_bottom_nav()


if __name__ == "__main__":
    main()