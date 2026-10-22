"""Streamlit UI.  Run:  streamlit run insightcopilot/ui.py"""
import pandas as pd
import streamlit as st

from insightcopilot.adapters import AdapterError, publish_result
from insightcopilot.service import Service

st.set_page_config(page_title="InsightCopilot", layout="wide")


@st.cache_resource
def svc() -> Service:
    return Service.build()


st.title("InsightCopilot")
question = st.text_input("Ask your data")
target = st.sidebar.selectbox("Send result to", ["(none)", "metabase", "superset", "csv"])

if st.button("Run") and question:
    with st.spinner("Agent is working..."):
        result = svc().ask(question)
    st.session_state["result"] = result

result = st.session_state.get("result")
if result:
    if result.error and not result.rows:
        st.error(result.error)
    if result.summary:
        st.subheader("Answer")
        st.write(result.summary)
    for w in result.warnings:
        st.warning(w)
    if result.rows:
        df = pd.DataFrame(result.rows)
        chart = result.chart or {}
        if chart.get("type") in ("bar", "line"):
            data = df.set_index(chart["x"])[chart["y"]]
            (st.bar_chart if chart["type"] == "bar" else st.line_chart)(data)
        st.dataframe(df, use_container_width=True)
        st.code(result.sql, language="sql")
        if target != "(none)" and st.button(f"Publish to {target}"):
            try:
                st.success(publish_result(result, target))
            except AdapterError as e:
                st.error(str(e))
    with st.expander(f"Agent trace ({len(result.trace)} steps)"):
        st.json(result.trace)
