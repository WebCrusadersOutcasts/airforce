import csv
from flask import Flask, render_template, request
import psycopg2
from psycopg2 import sql
from io import TextIOWrapper
from flask_cors import CORS

app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Database connection credentials
DB_NAME = "datathon"
DB_USER = "datathon_user"
DB_PASSWORD = "EeTXudLXaOtmBqLX0tKUhJ8kGWarqHTO"
DB_HOST = "dpg-coc79mol6cac73er920g-a.singapore-postgres.render.com"
DB_PORT = "5432"

# Establish database connection
conn = psycopg2.connect(
    dbname=DB_NAME,
    user=DB_USER,
    password=DB_PASSWORD,
    host=DB_HOST,
    port=DB_PORT
)
cur = conn.cursor()

# Function to create table if not exists
def create_table(table_name):
    cur.execute(sql.SQL('''
        CREATE TABLE IF NOT EXISTS {}
        (
            id SERIAL PRIMARY KEY,
            "Time(sec)" VARCHAR,
            "Time(hh)" VARCHAR,
            "TGT (C)" VARCHAR,
            "NH(%)" VARCHAR,
            "NL(%)" VARCHAR,
            "ALT" VARCHAR,
            "LAS" VARCHAR,
            "OAT c" VARCHAR,
            "Validity" VARCHAR,
            "WonW" VARCHAR
        )
    ''').format(sql.Identifier(table_name)))
    conn.commit()

# Function to handle custom CSV upload and insertion into the database
def handle_custom_csv_upload(file, table_name):
    create_table(table_name)

    # Read the CSV file
    error_rows = []
    for row_number, line in enumerate(file, start=1):
        try:
            # Split the line into fields based on commas
            fields = line.strip().split(',')

            # Validate the number of fields
            if len(fields) != 10:
                error_rows.append(row_number)
                continue  # Skip inserting this row

            # Extract values from the fields
            columns = [
                fields[0],  # "Time(sec)"
                fields[1],  # "Time(hh)"
                fields[2],  # "TGT (C)"
                fields[3],  # "NH(%)"
                fields[4],  # "NL(%)"
                fields[5],  # "ALT"
                fields[6],  # "LAS"
                fields[7],  # "OAT c"
                fields[8],  # "Validity"
                fields[9]   # "WonW"
            ]

            # Insert data into the database table
            cur.execute(sql.SQL('''
                INSERT INTO {}
                ("Time(sec)", "Time(hh)", "TGT (C)", "NH(%)", "NL(%)", "ALT", "LAS", "OAT c", "Validity", "WonW")
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ''').format(sql.Identifier(table_name)), columns)

        except IndexError:
            error_rows.append(row_number)
            continue  # Skip this row due to an index error

        except Exception as e:
            conn.rollback()  # Rollback the transaction on error
            return f'Error: An error occurred while processing row {row_number}: {str(e)}'

    # Commit the transaction after all valid rows are processed
    conn.commit()

    if error_rows:
        return f'Error: Invalid number of fields in rows: {", ".join(map(str, error_rows))}'
    else:
        return 'Custom CSV file uploaded successfully!'

# Route for file upload
@app.route('/', methods=['GET', 'POST'])
def upload_custom_csv():
    if request.method == 'POST':
        table_name = request.form['table_name']
        file = request.files['file']
        
        if file.filename == '':
            return 'No file selected!'
        
        if file and file.filename.endswith('.csv'):
            result_message = handle_custom_csv_upload(file, table_name)
            return result_message
        else:
            return 'Please upload a valid CSV file!'
    
    return render_template('upload.html')

if __name__ == '__main__':
    app.run(debug=True)``