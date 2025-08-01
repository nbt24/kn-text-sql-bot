from dotenv import load_dotenv
import os
import sqlite3
import streamlit as st
import google.generativeai as genai
import pandas as pd
import logging

logging.getLogger("streamlit.runtime.scriptrunner.script_runner").setLevel(logging.ERROR)

# --- Load environment variables ---
load_dotenv()

# --- Configuration ---
DB_NAME = "bombay_wala.db"
TABLE_NAME = "SALES"
MODEL_NAME = "gemini-2.5-pro"
GENAI_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- Set up Gemini ---
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

# --- Path setup ---
db_path = os.path.join(os.path.dirname(__file__), DB_NAME)

# --- Streamlit UI Settings ---
st.set_page_config(page_title="🍬 Bombay Wala Chatbot", layout="centered")
st.markdown("""
    <div style='text-align:center;'>
        <h2 style='color:#b3541e;'>🍥 Bombay Wala: Sweet & Namkeen Chatbot 🍥</h2>
        <p style='color:#555;'>Ask me anything about your sweet and namkeen orders, inventory, or sales!</p>
        <hr style='border-top: 1px dashed #e07b39; width: 60%;'>
    </div>
""", unsafe_allow_html=True)

# --- Chat History ---
if "history" not in st.session_state:
    st.session_state.history = []

# --- Gemini Prompt Template ---
system_prompt = f"""
You are a friendly chatbot for a sweet and namkeen store called Bombay Wala.
You work on an SQLite3 database named {DB_NAME} and the main table is {TABLE_NAME}.

Your job is to answer natural language questions about orders, products, customers, inventory, or payments. The query can have keywords that are alternatives to the column names. Map them to the corresponding column names properly, as the query will be in natural text.
Return only valid SQLite queries as responses — no explanations, no formatting, no comments.

If a question is unrelated to Bombay Wala's data, reply:
"I'm here to help with Bombay Wala's sweets & namkeen data. Please ask about orders, inventory, customers, or sales."
"""

# --- Gemini SQL Generator ---
def get_gemini_sql(question: str) -> str:
    try:
        response = model.generate_content([system_prompt, question])
        return response.text.strip()
    except Exception:
        return None

# --- Run SQL on DB ---
def run_sql_query(sql: str):
    try:
        if not os.path.exists(db_path):
            return None, "⚠️ Database not found."

        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute(sql)
        rows = cursor.fetchall()
        col_names = [desc[0] for desc in cursor.description]
        conn.close()
        return (col_names, rows), None
    except sqlite3.OperationalError as e:
        return None, f"⚠️ SQL Error: {str(e)}"
    except Exception as e:
        return None, f"⚠️ Unexpected Error: {str(e)}"

# --- Display Chat History ---
for sender, msg in st.session_state.history:
    if sender == "user":
        st.markdown(
            f"<div style='background-color:#ffe6cc;padding:10px 15px;border-radius:10px;margin-bottom:6px;text-align:right;color:#7b3f00;font-weight:bold;box-shadow:1px 1px 3px rgba(0,0,0,0.1);'>🧑‍🍳 You: {msg}</div>",
            unsafe_allow_html=True
        )
    elif sender == "bot":
        st.markdown(
            f"<div style='background-color:#fff5e6;padding:10px 15px;border-radius:10px;margin-bottom:6px;color:#5e2900;box-shadow:1px 1px 3px rgba(0,0,0,0.1);'><b>🍬 Bombay Wala Bot:</b><br>{msg}</div>",
            unsafe_allow_html=True
        )
    elif sender == "bot_table":
        columns, rows = msg
        st.markdown(
            f"<div style='background-color:#fff5e6;padding:10px 15px;border-radius:10px;margin-bottom:6px;color:#5e2900;'><b>🍬 Bombay Wala Bot:</b></div>",
            unsafe_allow_html=True
        )
        df = pd.DataFrame(data=rows, columns=columns)
        st.dataframe(df, use_container_width=True)

# --- User Input at the BOTTOM ---
with st.form(key="query_form", clear_on_submit=True):
    user_input = st.text_input("🧁 Type your query below (e.g. total sales of laddoos):", key="input")
    submitted = st.form_submit_button("Submit")

if submitted and user_input:
    sql_query = get_gemini_sql(user_input)

    # Handle irrelevant or failed queries
    if not sql_query or "I'm here to help" in sql_query:
        st.session_state.history.append(("user", user_input))
        st.session_state.history.append((
            "bot",
            "I'm here to help with Bombay Wala's sweets & namkeen data. Please ask about orders, inventory, customers, or sales."
        ))
    else:
        result, error = run_sql_query(sql_query)
        st.session_state.history.append(("user", user_input))

        if error:
            st.session_state.history.append(("bot", error))
        elif result:
            columns, rows = result
            if rows:
                st.session_state.history.append(("bot_table", (columns, rows)))
            else:
                st.session_state.history.append(("bot", "No matching records found."))
        else:
            st.session_state.history.append(("bot", "An unknown error occurred."))
    st.rerun()
