import json
import traceback
import pandas as pd
import streamlit as st

from src.mcqgenerator.utils import read_file
from langchain.callbacks import get_openai_callback
from src.mcqgenerator.MCQGenerator import generate_evaluate_chain

# Load template/schema (use your path)
SCHEMA_PATH = r'C:\Users\modgi\mcqgen\response.json'
with open(SCHEMA_PATH, 'r', encoding='utf-8') as f:
    RESPONSE_JSON = json.load(f)

st.set_page_config(page_title="MCQs Creator", layout="wide")
st.title("MCQs Creator Application")


def _loose_json_load(s: str):
    """Try a couple of ways to decode JSON-like strings."""
    s = s.strip()
    try:
        return json.loads(s)
    except Exception:
        try:
            return json.loads(s.replace("'", '"'))
        except Exception:
            try:
                s2 = s.strip('`')
                return json.loads(s2)
            except Exception:
                return None


def parse_quiz_payload(quiz_payload):
    """
    Normalize quiz_payload into a list of dict rows:
      - If string: try to json.loads it (loose)
      - If dict-of-dicts with numeric keys ("1","2",...) => return ordered list of values
      - If single dict with question fields => return [dict]
      - If list of dicts => return as-is
    Returns: list[dict] or [] if cannot parse
    """
    if quiz_payload is None:
        return []

    if isinstance(quiz_payload, str):
        parsed = _loose_json_load(quiz_payload)
        if parsed is None:
            return []
        quiz_payload = parsed

    if isinstance(quiz_payload, dict):
        values = list(quiz_payload.values())
        if all(isinstance(v, dict) for v in values) and any(('mcq' in v or 'question' in v) for v in values):
            try:
                items = sorted(quiz_payload.items(), key=lambda kv: int(str(kv[0])))
            except Exception:
                items = list(quiz_payload.items())
            rows = [v for _, v in items if isinstance(v, dict)]
            return rows
        if 'mcq' in quiz_payload or 'question' in quiz_payload:
            return [quiz_payload]
        return []

    if isinstance(quiz_payload, list) and all(isinstance(x, dict) for x in quiz_payload):
        return quiz_payload

    return []


def normalize_rows_to_table(rows):
    """Given list[dict] rows (each question), produce display rows"""
    table_rows = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        no = r.get('no') or r.get('index') or r.get('id') or ""
        question = r.get('mcq') or r.get('question') or ""
        options = r.get('options', {}) or {}
        opt_a = opt_b = opt_c = opt_d = ""
        options_combined = ""

        if isinstance(options, dict):
            opt_a = options.get('a', "")
            opt_b = options.get('b', "")
            opt_c = options.get('c', "")
            opt_d = options.get('d', "")
            items = []
            for k in ['a', 'b', 'c', 'd']:
                v = options.get(k)
                if v:
                    items.append(f"{k}) {v}")
            options_combined = " | ".join(items)
        elif isinstance(options, list):
            items = [str(x) for x in options]
            options_combined = " | ".join(items)
            if len(items) > 0: opt_a = items[0]
            if len(items) > 1: opt_b = items[1]
            if len(items) > 2: opt_c = items[2]
            if len(items) > 3: opt_d = items[3]
        else:
            options_combined = str(options)

        correct = r.get('correct') or r.get('answer') or r.get('correct_answer') or ""

        table_rows.append({
            "No": no,
            "Question": question,
            "Option A": opt_a,
            "Option B": opt_b,
            "Option C": opt_c,
            "Option D": opt_d,
            "Options (combined)": options_combined,
            "Correct": correct
        })
    return table_rows


# ---------- UI form ----------
with st.form("user_inputs"):
    uploaded_file = st.file_uploader("Upload a PDF or txt file")
    mcq_count = st.number_input("No. of MCQs", min_value=1, max_value=50, value=3)
    subject = st.text_input("Insert Subject", max_chars=50)
    tone = st.text_input("Complexity Level of Questions", max_chars=30, placeholder="Simple")
    submit = st.form_submit_button("Create MCQs")

# ---------- On submit ----------
if submit:
    if uploaded_file is None:
        st.error("Please upload a file.")
        st.stop()
    if not subject.strip():
        st.error("Please enter a subject.")
        st.stop()

    try:
        text = read_file(uploaded_file)
    except Exception as e:
        st.error("Failed to read uploaded file.")
        st.exception(e)
        st.stop()

    with st.spinner("Generating MCQs..."):
        try:
            with get_openai_callback() as cb:
                # Pass RESPONSE_JSON as dict
                response = generate_evaluate_chain({
                    "text": text,
                    "number": int(mcq_count),
                    "subject": subject,
                    "tone": tone,
                    "response_json": RESPONSE_JSON
                })
        except Exception as e:
            st.error("Error while calling generator.")
            st.exception(e)
            st.stop()

    # Optional: show token usage if available
    try:
        st.caption(f"Tokens — total: {cb.total_tokens}, prompt: {cb.prompt_tokens}, completion: {cb.completion_tokens}, cost: {cb.total_cost}")
    except Exception:
        pass

    # Ensure response is a dict (or parse it)
    if isinstance(response, str):
        parsed = _loose_json_load(response)
        response = parsed if isinstance(parsed, dict) else response

    if not isinstance(response, dict):
        st.error("Generator returned an unexpected response format.")
        st.stop()

    quiz_payload = response.get("quiz") or response.get("Quiz") or response.get("QUIZ")
    rows = parse_quiz_payload(quiz_payload)
    if not rows:
        st.error("Could not parse 'quiz' from response.")
        st.stop()

    table_rows = normalize_rows_to_table(rows)
    if not table_rows:
        st.error("Parsed quiz rows are empty after normalization.")
        st.stop()

    df = pd.DataFrame(table_rows)
    df.index = range(1, len(df) + 1)

    st.subheader("Generated MCQs")
    st.dataframe(df, use_container_width=True)
