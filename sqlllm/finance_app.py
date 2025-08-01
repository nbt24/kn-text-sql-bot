from dotenv import load_dotenv
load_dotenv() ## load all the environemnt variables

import streamlit as st
import os
import sqlite3

import os
import sqlite3

db_path = os.path.join(os.path.dirname(__file__), "finance.db")
print("DB PATH:", db_path)
print("File exists:", os.path.exists(db_path))

conn = sqlite3.connect(db_path)
cursor = conn.cursor()
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables in DB:", tables)

import google.generativeai as genai
## Configure Genai Key

genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

## Function To Load Google Gemini Model and provide queries as response

def get_gemini_response(question,prompt):
    model=genai.GenerativeModel('gemini-2.5-pro')
    response=model.generate_content([prompt[0],question])
    return response.text

## Fucntion To retrieve query from the database

def read_sql_query(sql,db):
    cursor.execute(sql)
    rows=cursor.fetchall()
    conn.commit()
    conn.close()
    for row in rows:
        print(row)
    return rows

## Define Your Prompt
prompt=[
    """
    You are an expert in converting English questions to SQL query using sqlite3!
    The SQL database has the name FINANCE and has the following columns - TE TABLE IF NOT EXISTS STUDENT (
    StudentID INTEGER PRIMARY KEY,
    Name TEXT NOT NULL,
    Age INTEGER,
    Gender TEXT,
    Department TEXT,
    TotalFees REAL,
    FeesPaid REAL,
    ScholarshipAmount REAL,
    MonthlyExpenses REAL \n\nFor example,\nExample 1 -  Who has received the highest scholarship?, 
    the SQL command will be something like this SELECT Name FROM STUDENT ORDER BY ScholarshipAmount DESC LIMIT 1;
    \nExample 2 -  List names of students who haven’t paid full fees?, 
    the SQL command will be something like this SELECT Name FROM STUDENT WHERE FeesPaid < TotalFees; 
    also the sql code should not have ``` in beginning or end and sql word in output

    """


]

## Streamlit App

st.set_page_config(page_title="I can Retrieve Any SQL query")
st.header("Gemini App To Retrieve SQL Data")

question=st.text_input("Input: ",key="input")

submit=st.button("Ask the question")

# if submit is clicked
if submit:
    
    response=get_gemini_response(question,prompt)
    print(response)
    sql = response.strip()
    print("Generated SQL:", sql)
    try:
        result = read_sql_query(sql, "finance.db")
    except sqlite3.OperationalError as e:
        print("Invalid SQL:", sql)
        print("Error:", e)
    st.subheader("The REsponse is")
    for row in result:
        print(row)
        st.header(row)









