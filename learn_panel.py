import streamlit as st

from command_parser import FUNCTION_CODES
from learn_loader import LearnFileError, load_learn


def render_learn_panel(code):
    try:
        learn = load_learn(code)
    except LearnFileError as e:
        st.error(str(e))
        return

    # Fixed-height container so a long panel scrolls instead of pushing the page down.
    with st.container(height=650, border=True):
        st.subheader(f"{learn['mnemonic']}: {learn['full_name']}")

        st.markdown("**What it does (real Bloomberg terminal)**")
        st.markdown(learn["what_it_does"])

        st.markdown("**Why analysts use it**")
        st.markdown(learn["why_analysts_use_it"])

        st.markdown("**Key concepts**")
        for concept in learn["key_concepts"]:
            st.markdown(f"- **{concept['term']}**: {concept['explanation']}")

        st.markdown("**How to read the output**")
        for item in learn["how_to_read_the_output"]:
            st.markdown(f"- {item}")

        st.markdown("**Common mistakes**")
        for item in learn["common_mistakes"]:
            st.markdown(f"- {item}")

        st.markdown("**Interview questions**")
        for entry in learn["interview_questions"]:
            with st.expander(entry["question"]):
                st.markdown(entry["model_answer"])

        st.markdown("**Try it on the terminal**")
        for position, item in enumerate(learn["terminal_checklist"]):
            st.checkbox(item, key=f"learn_{code}_check_{position}")

        st.markdown("**Related functions**")
        related = [
            f"`{name}` ({'in this terminal' if name in FUNCTION_CODES else 'real terminal only'})"
            for name in learn["related_functions"]
        ]
        st.markdown(", ".join(related) if related else "None listed.")
