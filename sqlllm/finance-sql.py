import sqlite3

# Connect to SQLite database (creates it if it doesn't exist)
conn = sqlite3.connect("finance.db")
cursor = conn.cursor()

# Create the FINANCE table
cursor.execute('''
CREATE TABLE IF NOT EXISTS FINANCE (
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
''')

# Sample data
students = [
    (1, 'Ananya Sharma', 20, 'Female', 'Finance', 200000, 150000, 20000, 12000),
    (2, 'Rohit Mehra', 21, 'Male', 'Economics', 180000, 180000, 0, 10000),
    (3, 'Kavita Rao', 22, 'Female', 'Finance', 200000, 120000, 50000, 8000),
    (4, 'Arjun Verma', 23, 'Male', 'Marketing', 190000, 190000, 0, 11000),
    (5, 'Sneha Patel', 21, 'Female', 'Finance', 200000, 100000, 80000, 7000)
]

# Insert data
cursor.executemany('''
INSERT OR REPLACE INTO FINANCE (StudentID, Name, Age, Gender, Department, TotalFees, FeesPaid, ScholarshipAmount, MonthlyExpenses)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
''', students)

# Commit and close
conn.commit()
conn.close()

print("Database 'finance.db' created and populated successfully.")
