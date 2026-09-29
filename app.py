import matplotlib

# Must run before any "import matplotlib.pyplot" anywhere in the app (portfolio.py,
# functions.py): headless servers like Streamlit Community Cloud have no display, and
# matplotlib's default backend selection can otherwise misbehave or warn.
matplotlib.use("Agg")

import streamlit as st

from command_parser import ParseError, parse_command
from functions import FUNCTIONS
from learn_panel import render_learn_panel

st.set_page_config(page_title="Analytics Terminal", layout="wide")

st.title("Analytics Terminal")

with st.form("command_bar", clear_on_submit=False):
    raw_command = st.text_input(
        "Command",
        value=st.session_state.get("raw_command", ""),
        placeholder="e.g. AAPL US GP",
        label_visibility="collapsed",
    )
    submitted = st.form_submit_button("Go")

if submitted:
    st.session_state["raw_command"] = raw_command
    st.session_state["result"] = parse_command(raw_command)

# Rendered on every run (not only after a valid command) so Streamlit keeps its state.
show_learn = st.toggle("Show Learn panel", value=True, key="show_learn")

result = st.session_state.get("result")

if result is None:
    st.caption(
        "Enter a command above: TICKER MARKET FUNCTION (e.g. AAPL US GP, AZN LN DES). "
        "The Bloomberg form with the security type also works: AAPL US Equity GP."
    )
elif isinstance(result, ParseError):
    st.error(result.message)
elif show_learn:
    output_column, learn_column = st.columns([3, 2])
    with output_column:
        FUNCTIONS[result.function](result)
    with learn_column:
        render_learn_panel(result.function)
else:
    FUNCTIONS[result.function](result)
