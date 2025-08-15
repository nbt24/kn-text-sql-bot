import sqlite3
import os
import pandas as pd

# Define database and table name
db_name = "badjate.db"
table_name = "Recommendations"

# Define realistic stock names along with their data as per given columns
data = [
    (1, "TCS", "2025-07-01", 3800, "2025-07-10", 3950, 4000, 3750, "IT"),
    (2, "Reliance", "2025-07-03", 2600, "2025-07-15", 2550, 2700, 2550, "Energy"),
    (3, "HDFC Bank", "2025-07-05", 1700, "2025-07-20", 1750, 1800, 1680, "Banking"),
    (4, "Infosys", "2025-07-07", 1500, "2025-07-18", 1525, 1550, 1480, "IT"),
    (5, "Maruti Suzuki", "2025-07-09", 9800, "2025-07-25", 10000, 10200, 9700, "Auto"),
    (6, "Bharti Airtel", "2025-07-11", 950, "2025-07-22", 970, 1000, 940, "Telecom"),
    (7, "Asian Paints", "2025-07-13", 3200, "2025-07-28", 3150, 3300, 3180, "FMCG"),
    (8, "ICICI Bank", "2025-07-15", 1200, "2025-07-30", 1225, 1250, 1190, "Banking"),
    (9, "Titan", "2025-07-17", 3500, "2025-08-01", 3600, 3700, 3480, "Retail"),
    (10, "ONGC", "2025-07-19", 180, "2025-08-05", 175, 200, 178, "Aditya"),
]

# Define columns
columns = [
    "OrderID INTEGER PRIMARY KEY",
    "StockName TEXT",
    "BuyDate TEXT",
    "BuyPrice INTEGER",
    "SellDate TEXT",
    "SellPrice INTEGER",
    "Target INTEGER",
    "StopLoss INTEGER",
    "Category TEXT"
]

# Create database and insert data
conn = sqlite3.connect(db_name)
cursor = conn.cursor()

cursor.execute(f"DROP TABLE IF EXISTS {table_name};")
cursor.execute(f"CREATE TABLE {table_name} ({', '.join(columns)});")

cursor.executemany(f"""
    INSERT INTO {table_name} (OrderID, StockName, BuyDate, BuyPrice, SellDate, SellPrice, Target, StopLoss, Category)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
""", data)

conn.commit()
conn.close()

# Confirm the DB file exists
os.path.exists(db_name)
