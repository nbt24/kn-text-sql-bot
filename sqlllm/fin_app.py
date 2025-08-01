from dotenv import load_dotenv
import os
import sqlite3
import streamlit as st
import google.generativeai as genai
import pandas as pd
import logging
logging.getLogger("streamlit.runtime.scriptrunner.script_runner").setLevel(logging.ERROR)


# Load environment variables
load_dotenv()

# --- Configuration ---
DB_NAME = "finance.db"
TABLE_NAME = "FINANCE"
MODEL_NAME = "gemini-2.5-pro"
GENAI_API_KEY = os.getenv("GOOGLE_API_KEY")

# --- Set up Gemini ---
genai.configure(api_key=GENAI_API_KEY)
model = genai.GenerativeModel(MODEL_NAME)

# --- Path setup ---
db_path = os.path.join(os.path.dirname(__file__), DB_NAME)

# --- Streamlit UI Settings ---
st.set_page_config(page_title="📊 NBT Finance Chatbot", layout="centered")
st.markdown("<h2 style='text-align: center; color: #4b0081;'>Next Bigg Tech: Finance SQL Chatbot</h2>", unsafe_allow_html=True)
st.markdown("<p style='text-align: center; color: #555;'>Ask natural questions about student finance data!</p>", unsafe_allow_html=True)

# --- Chat History ---
if "history" not in st.session_state:
    st.session_state.history = []

# --- Gemini Prompt Template ---
system_prompt = f"""
You are an expert SQL assistant working on an SQLite3 database named {DB_NAME}.
The table is named {TABLE_NAME} and has the following schema:

CREATE TABLE {TABLE_NAME} (
    StudentID INTEGER PRIMARY KEY,
    Name TEXT NOT NULL,
    Age INTEGER,
    Gender TEXT,
    Department TEXT,
    TotalFees REAL,
    FeesPaid REAL,
    ScholarshipAmount REAL,
    MonthlyExpenses REAL
);

You will be given a question in English and should return only the appropriate SQLite query.

Examples:
1. "Who has received the highest scholarship?" → SELECT Name FROM {TABLE_NAME} ORDER BY ScholarshipAmount DESC LIMIT 1;
2. "List students who haven’t paid full fees" → SELECT Name FROM {TABLE_NAME} WHERE FeesPaid < TotalFees;

Only respond with the SQL query — no explanation, no ```sql blocks, no extra words.

If the user asks about unrelated topics (e.g., weather, movies), reply:
"I'm here to help with student finance-related questions like fees, scholarships, or expenses. Please ask accordingly."
"""

# --- Function to get Gemini SQL response ---
def get_gemini_sql(question: str) -> str:
    try:
        print("\n=== Gemini Prompt Sent ===")
        print("Prompt (system):", system_prompt)
        print("User Question:", question)

        response = model.generate_content([system_prompt, question])
        return response.text.strip()
    except Exception as e:
        print("\n=== Gemini API Error ===")
        print(type(e).__name__, ":", e)
        return None


# --- Function to execute SQL query ---
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

# --- Input Field ---
user_input = st.text_input("💬 Ask a question about student finance data:", key="input")

# if st.button("Submit") and user_input:
#     sql_query = get_gemini_sql(user_input)

#     # Handle irrelevant questions
#     if not sql_query or "I'm here to help" in sql_query:
#         st.session_state.history.append(("user", user_input))
#         st.session_state.history.append(("bot", "I'm here to help with student finance-related questions like fees, scholarships, or expenses. Please ask accordingly."))
#     else:
#         result, error = run_sql_query(sql_query)
#         st.session_state.history.append(("user", user_input))

#         if error:
#             st.session_state.history.append(("bot", error))
#         elif result:
#             columns, rows = result
#             if rows:
#                 # Format table
#                 table_md = "| " + " | ".join(columns) + " |\n"
#                 table_md += "| " + " | ".join(["---"] * len(columns)) + " |\n"
#                 for row in rows:
#                     table_md += "| " + " | ".join(str(cell) for cell in row) + " |\n"
#                 st.session_state.history.append(("bot", table_md))
#             else:
#                 st.session_state.history.append(("bot", "No matching records found."))
#         else:
#             st.session_state.history.append(("bot", "An unknown error occurred."))

# # --- Display Chat History ---
# for sender, msg in st.session_state.history:
#     if sender == "user":
#         st.markdown(f"<div style='background-color:#fdb727;padding:8px;border-radius:10px;margin-bottom:5px;text-align:right;color:#000'><b>You:</b> {msg}</div>", unsafe_allow_html=True)
#     else:
#         st.markdown(f"<div style='background-color:#eee;padding:10px;border-radius:10px;margin-bottom:5px;color:#333'><b>Bot:</b><br>{msg}</div>", unsafe_allow_html=True)


# ... [Keep your existing imports, setup, functions] ...

if st.button("Submit") and user_input:
    sql_query = get_gemini_sql(user_input)

    # Handle irrelevant questions
    if not sql_query or "I'm here to help" in sql_query:
        st.session_state.history.append(("user", user_input))
        st.session_state.history.append(("bot", "I'm here to help with student finance-related questions like fees, scholarships, or expenses. Please ask accordingly."))
    else:
        result, error = run_sql_query(sql_query)
        st.session_state.history.append(("user", user_input))

        if error:
            st.session_state.history.append(("bot", error))
        elif result:
            columns, rows = result
            if rows:
                # Instead of markdown, show nice table for the bot reply
                st.session_state.history.append(("bot_table", (columns, rows)))
            else:
                st.session_state.history.append(("bot", "No matching records found."))
        else:
            st.session_state.history.append(("bot", "An unknown error occurred."))

# --- Display Chat History ---
for sender, msg in st.session_state.history:
    if sender == "user":
        st.markdown(
            f"<div style='background-color:#fdb727;padding:8px;border-radius:10px;margin-bottom:5px;text-align:right;color:#000'><b>You:</b> {msg}</div>",
            unsafe_allow_html=True
        )
    elif sender == "bot":
        # Plain text bot message
        st.markdown(
            f"<div style='background-color:#eee;padding:10px;border-radius:10px;margin-bottom:5px;color:#333'><b>Bot:</b><br>{msg}</div>",
            unsafe_allow_html=True
        )
    elif sender == "bot_table":
        # Display table nicely
        columns, rows = msg
        st.markdown(
            f"<div style='background-color:#eee;padding:10px;border-radius:10px;margin-bottom:5px;color:#333'><b>Bot:</b></div>",
            unsafe_allow_html=True
        )
        df = pd.DataFrame(
            data=[list(row) for row in rows],
            columns=columns
        )
        st.dataframe(df, use_container_width=True,hide_index=True)

