import sqlite3

import os

db_path = os.path.join(os.path.dirname(__file__), "student.db")

## Connectt to SQlite
connection=sqlite3.connect(db_path)

# Create a cursor object to insert record,create table

cursor=connection.cursor()

## create the table
table_info="""
Create table if not exists STUDENT(NAME VARCHAR(25),CLASS VARCHAR(25),
SECTION VARCHAR(25),MARKS INT);

"""
cursor.execute(table_info)

## Insert Some more records

cursor.execute('''Insert Into STUDENT values('Aditya','Data Science','A',90)''')
cursor.execute('''Insert Into STUDENT values('Varun','Data Science','B',100)''')
cursor.execute('''Insert Into STUDENT values('Ansh','Data Science','A',86)''')
cursor.execute('''Insert Into STUDENT values('Karan','DEVOPS','A',50)''')
cursor.execute('''Insert Into STUDENT values('Kartik','DEVOPS','A',35)''')

## Display All the records

print("The isnerted records are")
data = cursor.execute('''Select * from STUDENT''')
for row in data:
    print(row)

## Commit your changes int he databse
connection.commit()
connection.close()
