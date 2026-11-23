"""SRG web page: the team status table (spec SRG-R3, R11, R12, R14; plan S9).

Run with real Jira data (needs .env and config.yaml):
    streamlit run app.py
Run with the made-up sample data (no Jira account, no token):
    streamlit run app.py -- --demo      (or: streamlit run demo_app.py)
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime

import streamlit as st

from status_report.config import ConfigError
from status_report.jira_client import JiraError
from status_report.page import (
    SAMPLE_BANNER,
    PageState,
    detail_lines,
    detail_rows,
    headline,
    refresh,
    table_rows,
)
from status_report.report import marked, report_name, to_markdown
from status_report.run import load_settings, make_client, read_portfolio


def demo_mode() -> bool:
    return "--demo" in sys.argv[1:] or os.environ.get("SRG_DEMO", "").strip() == "1"


def start(demo: bool) -> dict:
    """Settings, client and the first read. A start-up error stops the page (R13.2, R13.3)."""
    try:
        config = load_settings(demo=demo)
        client = make_client(demo)
        first = read_portfolio(client, config, demo=demo, at_start=True)
    except (ConfigError, JiraError) as error:
        st.error(str(error))
        st.stop()
    return {"config": config, "client": client, "state": PageState(first)}


def show_details(row) -> None:
    st.subheader(f"{row.name} – {marked(row.colour)}")
    for line in detail_lines(row):
        st.write(line)
    rows = detail_rows(row)
    if row.error:
        return
    if not rows:
        st.write("No Black, Red or Amber tickets.")
        return
    has_links = any(r["Link"] for r in rows)
    for r in rows:
        link = r.pop("Link")
        if has_links:
            r["Key"] = link  # Shown as the key; a click opens the ticket in Jira (R11.3)
    config = {"Key": st.column_config.LinkColumn("Key", display_text=r".*/browse/(.*)")} if has_links else None
    st.dataframe(rows, hide_index=True, column_config=config, width="stretch")


def main(demo: bool | None = None) -> None:
    demo = demo_mode() if demo is None else demo
    st.set_page_config(page_title="Team status – SRG", layout="wide")
    st.title("Team status")
    if demo:
        st.info(SAMPLE_BANNER)  # R14.2
    if "srg" not in st.session_state:
        st.session_state.srg = start(demo)  # R3.1: read Jira when the page opens
    session = st.session_state.srg

    if st.button("Refresh"):  # R3.1
        session["state"] = refresh(
            session["state"],
            lambda: read_portfolio(session["client"], session["config"], demo=demo),
            datetime.now(UTC),
        )
    state = session["state"]
    if state.error:
        st.error(headline(state))  # N4.2: the error and the last good read time
    else:
        st.subheader(headline(state))  # R3.2: "as of hh:mm"
    portfolio = state.last_good
    if portfolio is None:
        st.stop()
    if state.error:
        st.caption("The table below is the last good read. It is not new data.")

    event = st.dataframe(
        table_rows(portfolio), hide_index=True, width="stretch",
        on_select="rerun", selection_mode="single-row", key="teams",
    )
    st.download_button(  # R12: the Markdown report from the same data
        "Generate report", data=to_markdown(portfolio), file_name=report_name(portfolio),
        mime="text/markdown",
    )
    selected = event.selection.rows if event else []
    if selected:
        show_details(portfolio.rows[selected[0]])  # R11
    else:
        st.caption("Click a team row to see its Black, Red and Amber tickets.")
    if portfolio.warnings:
        with st.expander(f"Warnings ({len(portfolio.warnings)})"):
            for warning in portfolio.warnings:
                st.write(warning)


if __name__ == "__main__":  # Streamlit runs the page as __main__
    main()
