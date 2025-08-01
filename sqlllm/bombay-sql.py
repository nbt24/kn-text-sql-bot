import sqlite3
import os
import pandas as pd

# Define database and table name
db_name = "bombay_wala.db"
table_name = "SALES"

# Define realistic sweet and namkeen sales data
data = [
    (1, "Kaju Katli", "Sweet", "2025-07-25", 0.5, 800, "Cash"),
    (2, "Bhakarwadi", "Namkeen", "2025-07-26", 1.0, 300, "UPI"),
    (3, "Rasgulla", "Sweet", "2025-07-27", 1.0, 450, "Card"),
    (4, "Chivda", "Namkeen", "2025-07-27", 0.25, 100, "Cash"),
    (5, "Ladoo", "Sweet", "2025-07-28", 0.75, 600, "UPI"),
    (6, "Sev", "Namkeen", "2025-07-29", 0.5, 200, "Cash"),
    (7, "Barfi", "Sweet", "2025-07-29", 1.5, 1200, "Card"),
]

# Define columns
columns = [
    "OrderID INTEGER PRIMARY KEY",
    "ItemName TEXT",
    "Category TEXT",
    "SaleDate TEXT",
    "QuantityInKg REAL",
    "TotalPrice INTEGER",
    "PaymentMode TEXT"
]

# Create database and insert data
conn = sqlite3.connect(db_name)
cursor = conn.cursor()

cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
cursor.execute(f"CREATE TABLE {table_name} ({', '.join(columns)});")

cursor.executemany(f"""
    INSERT INTO {table_name} (OrderID, ItemName, Category, SaleDate, QuantityInKg, TotalPrice, PaymentMode)
    VALUES (?, ?, ?, ?, ?, ?, ?);
""", data)

conn.commit()
conn.close()

# Confirm the DB file exists
os.path.exists(db_name)
