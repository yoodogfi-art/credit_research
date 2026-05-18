"""Page: Credit Flow — manual data entry, session_state backed."""

from datetime import datetime

import streamlit as st


def _load() -> dict:
    return st.session_state.get("credit_flow", {
        "issuance": "", "demand": "", "ratings": "", "news": "", "memo": "",
        "saved_at": "",
    })


def _save(data: dict) -> None:
    data["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    st.session_state["credit_flow"] = data


def render(_=None) -> None:
    st.header("Credit Flow")
    st.caption("발행, 수요예측, 신용등급 변경 등 수동 입력")

    saved = _load()
    if saved["saved_at"]:
        st.caption(f"마지막 저장: {saved['saved_at']}")

    tab1, tab2, tab3, tab4 = st.tabs(["발행 현황", "수요예측", "신용등급 변경", "뉴스 / 메모"])

    with tab1:
        st.markdown("#### 월간 발행 현황")
        c1, c2 = st.columns([3, 1])
        with c1:
            issuance = st.text_area(
                "발행 데이터",
                value=saved["issuance"],
                height=400,
                placeholder="2026-04 | 회사채 AA- | LG에너지솔루션 | 3년 | 5,000억 | 3.85%",
                key="cf_issuance",
                label_visibility="collapsed",
            )
        with c2:
            st.markdown("##### 입력 형식")
            st.markdown("날짜 | 섹터 등급 | 발행사 | 만기 | 금액 | 금리")
            st.markdown("엑셀 복붙 가능")
            if issuance:
                n = len([l for l in issuance.splitlines() if l.strip()])
                st.metric("건수", f"{n}건")

    with tab2:
        st.markdown("#### 수요예측 현황")
        c1, c2 = st.columns([3, 1])
        with c1:
            demand = st.text_area(
                "수요예측 데이터",
                value=saved["demand"],
                height=400,
                placeholder="발행사 | 등급 | 만기 | 발행액 | 모집액 | 경쟁률 | 금리 | 비고",
                key="cf_demand",
                label_visibility="collapsed",
            )
        with c2:
            st.markdown("##### 입력 형식")
            st.markdown("발행사 | 등급 | 만기 | 발행액 | 모집액 | 경쟁률 | 금리")
            if demand:
                n = len([l for l in demand.splitlines() if l.strip()])
                st.metric("건수", f"{n}건")

    with tab3:
        st.markdown("#### 신용등급 변경 내역")
        c1, c2 = st.columns([3, 1])
        with c1:
            ratings = st.text_area(
                "등급 변경",
                value=saved["ratings"],
                height=400,
                placeholder="날짜 | 발행사 | 변경 전 | 변경 후 | 방향 | 평가사 | 사유",
                key="cf_ratings",
                label_visibility="collapsed",
            )
        with c2:
            st.markdown("##### 입력 형식")
            st.markdown("날짜 | 발행사 | 이전 | 변경 | 방향 | 평가사")
            if ratings:
                n = len([l for l in ratings.splitlines() if l.strip()])
                st.metric("건수", f"{n}건")

    with tab4:
        st.markdown("#### 뉴스 / 시장 메모")
        news = st.text_area(
            "뉴스",
            value=saved["news"],
            height=200,
            placeholder="시장 주요 뉴스, 이슈 등 자유 입력",
            key="cf_news",
            label_visibility="collapsed",
        )
        st.markdown("#### 추가 메모")
        memo = st.text_area(
            "메모",
            value=saved["memo"],
            height=150,
            placeholder="기타 참고사항",
            key="cf_memo",
            label_visibility="collapsed",
        )

    st.markdown("---")
    col1, col2, _ = st.columns([1, 1, 5])
    with col1:
        if st.button("저장", type="primary", use_container_width=True):
            _save({
                "issuance": st.session_state.get("cf_issuance", ""),
                "demand":   st.session_state.get("cf_demand", ""),
                "ratings":  st.session_state.get("cf_ratings", ""),
                "news":     st.session_state.get("cf_news", ""),
                "memo":     st.session_state.get("cf_memo", ""),
            })
            st.success("저장 완료")
            st.rerun()
    with col2:
        if st.button("초기화", use_container_width=True):
            st.session_state.pop("credit_flow", None)
            st.rerun()