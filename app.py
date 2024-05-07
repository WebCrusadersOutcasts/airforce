import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import psycopg2
from psycopg2 import sql
from flask import Flask, request, jsonify
from flask_cors import CORS

# Function to establish connection to PostgreSQL database
def connect_to_db(db_credentials):
    conn = psycopg2.connect(
        dbname=db_credentials['dbname'],
        user=db_credentials['user'],
        password=db_credentials['password'],
        host=db_credentials['host'],
        port=db_credentials['port']
    )
    return conn

# Function to fetch unique values for a column from the database
def fetch_unique_values(conn, table_name, column_name):
    query = sql.SQL("SELECT DISTINCT {} FROM {}").format(
        sql.Identifier(column_name),
        sql.Identifier(table_name)
    )
    with conn.cursor() as cur:
        cur.execute(query)
        values = cur.fetchall()
    return [val[0] for val in values]

# Function to fetch data from the database based on user input
def fetch_data(conn, table_name, date, aircraft_no, sortie_numbers):
    query = sql.SQL("SELECT * FROM {} WHERE {} = %s AND {} = %s AND {} = %s").format(
        sql.Identifier(table_name),
        sql.Identifier("Date"),
        sql.Identifier("Aircraft No"),
        sql.Identifier("Sortie Numbers")
    )
    with conn.cursor() as cur:
        cur.execute(query, (date, aircraft_no, sortie_numbers))
        data = cur.fetchall()
    
    # Convert string values to integers or floats where possible
    converted_data = []
    for row in data:
        converted_row = []
        for val in row:
            if isinstance(val, str):
                # Try converting to integer
                try:
                    val = int(val)
                except ValueError:
                    # Try converting to float
                    try:
                        val = float(val)
                    except ValueError:
                        # If conversion fails, keep the value as is
                        pass
            converted_row.append(val)
        converted_data.append(converted_row)
    
    columns = [desc[0] for desc in cur.description]
    df = pd.DataFrame(converted_data, columns=columns)
    return df

def check_tgt_events(conn, table_name, date, aircraft_no, sortie_numbers):
    try:
        # Fetch data from database based on user input
        df = fetch_data(conn, table_name, date, aircraft_no, sortie_numbers)

        tgt_column_name = df.columns[2]
        tgt_values = df[tgt_column_name]

        event1 = False
        event2 = False
        event3 = False
        event2_start_row = 0
        consecutive_count = 0
        violation_prompts = []

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=df.index, y=tgt_values, mode='lines', name='TGT'))

        for idx, tgt_value in tgt_values.items():
            if tgt_value <= 610:
                event1 = True
            elif 610 < tgt_value <= 645:
                consecutive_count += 1
                if consecutive_count >= 160 and not event2:
                    event2 = True
                    event2_start_row = idx - consecutive_count + 1
                    fig.add_shape(
                        type="line",
                        x0=idx, y0=min(tgt_values), x1=idx, y1=max(tgt_values),
                        line=dict(color="orange", width=2, dash="dashdot")
                    )
            elif tgt_value > 645:
                event3 = True
                if not event2:
                    event2_start_row = idx
                    event2 = True
                consecutive_count += 1
                if consecutive_count >= 160:
                    fig.add_shape(
                        type="line",
                        x0=idx, y0=min(tgt_values), x1=idx, y1=max(tgt_values),
                        line=dict(color="red", width=2, dash="dashdot")
                    )
            else:
                consecutive_count = 0

        if event2 or event3:
            start_idx = event2_start_row
            end_idx = idx
            for i in range(event2_start_row, idx + 1):
                if tgt_values[i] <= 610:
                    if i > start_idx:
                        violation_prompts.append(
                            f"TGT Violation Detected: Inspection of engine required.\n"
                            f"Time Interval: {df.iloc[start_idx].iloc[0]} - {df.iloc[i-1].iloc[0]}\n"
                            f"TGT Range: {tgt_values[start_idx]} - {tgt_values[i-1]}"
                        )
                    start_idx = i + 1
            if start_idx <= idx:
                violation_prompts.append(
                    f"TGT Violation Detected: Inspection of engine required.\n"
                    f"Time Interval: {df.iloc[start_idx].iloc[0]} - {df.iloc[idx].iloc[0]}\n"
                    f"TGT Range: {tgt_values[start_idx]} - {tgt_values[idx]}"
                )

        if not (event2 or event3):
            violation_prompts.append("No TGT violation detected.")

        for prompt in violation_prompts:
            print(prompt)

        fig.update_layout(
            xaxis_title="Time",
            yaxis_title="TGT",
            title="TGT Violation Detection"
        )

        fig.show()

    except Exception as e:
        print("Error:", e)

def check_engine_cooling(conn, table_name, date, aircraft_no, sortie_numbers):
    try:
        # Fetch data from database based on user input
        df = fetch_data(conn, table_name, date, aircraft_no, sortie_numbers)

        engine_column = 'NH(%)'

        tolerance = 1
        row_count = 0
        engine_cooling = False

        last_row = df.shape[0] - 1

        if last_row - 640 > 0:
            engine_nh = df.loc[last_row - 640:last_row - 481, engine_column].mean()

            cooling_range = df.loc[last_row - 799:last_row, engine_column]

            for value in cooling_range:
                if engine_nh - tolerance <= value <= engine_nh + tolerance:
                    row_count += 1
                    if row_count >= 240:
                        engine_cooling = True
                        break
                else:
                    row_count = 0

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=df.index, y=df[engine_column], mode='lines', name='Engine Data'))
            fig.update_layout(title='Engine Data Over Time', xaxis_title='Time', yaxis_title='Engine Value')
            fig.show()

            if engine_cooling:
                print(f"No Violation Detected, engine cooled for 30 seconds at {engine_nh} NH before Shutdown")
            else:
                print("Violation detected, engine not cooled for 30 seconds before shutdown, possible emergency engine stop attempted")

        else:
            print("Not enough data rows to calculate EngineNH.")

    except Exception as e:
        print("Error:", e)

def check_nl_compressor_rpm(conn, table_name, date, aircraft_no, sortie_numbers):
    try:
        # Fetch data from database based on user input
        df = fetch_data(conn, table_name, date, aircraft_no, sortie_numbers)

        if df.shape[1] < 5:
            raise ValueError("The data must have at least five columns. Ensure the correct data source is used.")

        time_col = df.columns[0]
        nh_col = df.columns[4]
        tgt_col = df.columns[2]

        nh_event1 = True
        nh_event2 = False
        nh_event3 = False
        nh_start_row = 0
        nh_count = 0
        violation_prompt = ""
        violation_data = []

        for idx, nh_value in enumerate(df[nh_col]):
            if nh_value <= 108.5:
                nh_event1 = True
            elif 108.5 < nh_value <= 111.5:
                if nh_event1:
                    nh_start_row = idx
                    nh_count = 1
                    nh_event1 = False
                else:
                    nh_count += 1

                if nh_count >= 160:
                    nh_event2 = True
                    violation_data.append((df.loc[idx, time_col], 'Event 2'))
                    break
            elif nh_value > 111.5:
                nh_event3 = True
                violation_data.append((df.loc[idx, time_col], 'Event 3'))
                break

        if nh_event2:
            violation_prompt = (
                "Violation Detected: Inspection of engine required.\n"
                f"Start Row: {nh_start_row + 2}\n"
                f"Time: {df.loc[nh_start_row, time_col]}\n"
                f"NL: {df.loc[nh_start_row, nh_col]}\n"
                f"TGT: {df.loc[nh_start_row, tgt_col]}\n"
                "For post violation check, refer to VT 101B-44132-1A, Chap 6, Page 10"
            )
        elif nh_event3:
            violation_prompt = (
                "Violation Detected: Engine to be examined.\n"
                f"Row: {idx + 2}\n"
                f"Time: {df.loc[idx, time_col]}\n"
                f"NL: {df.loc[idx, nh_col]}\n"
                f"TGT: {df.loc[idx, tgt_col]}\n"
                "For post violation check, refer to VT 101B-44132-1A, Chap 6, Page 10"
            )
        else:
            violation_prompt = "No NL violation detected."

        print(violation_prompt)

        fig = px.line(df, x=time_col, y=nh_col, labels={"x": "Time", "y": "NH (Compressor RPM)"}, title="Compressor RPM over Time")
        fig.add_hline(y=108.5, line_dash="dash", line_color="orange", annotation_text="Lower Limit (108.5)", annotation_position="top left")
        fig.add_hline(y=111.5, line_dash="dash", line_color="red", annotation_text="Upper Limit (111.5)")
        
        for event_time, event_type in violation_data:
            fig.add_vline(x=event_time, line_dash="dash", line_color="red", annotation_text=event_type)

        fig.show()

    except Exception as e:
        print("Error:", e)

# Database credentials
db_credentials = {
    'dbname': 'datathon',
    'user': 'datathon_user',
    'password': 'EeTXudLXaOtmBqLX0tKUhJ8kGWarqHTO',
    'host': 'dpg-coc79mol6cac73er920g-a.singapore-postgres.render.com',
    'port': '5432'
}

# Create a Flask app
app = Flask(__name__)
CORS(app)

# Define API endpoints
@app.route('/check-tgt-events', methods=['POST', 'GET'])
def check_tgt_events_api():
    req_data = request.json
    date = req_data['date']
    aircraft_no = req_data['aircraft_no']
    sortie_numbers = req_data['sortie_numbers']
    conn = connect_to_db(db_credentials)
    if conn:
        result = check_tgt_events(conn, aircraft_no, date, aircraft_no, sortie_numbers)
        conn.close()
        return jsonify(result), 200
    else:
        return jsonify({"error": "Failed to connect to the database."}), 500

@app.route('/check-engine-cooling', methods=['POST', 'GET'])
def check_engine_cooling_api():
    req_data = request.json
    date = req_data['date']
    aircraft_no = req_data['aircraft_no']
    sortie_numbers = req_data['sortie_numbers']
    conn = connect_to_db(db_credentials)
    if conn:
        result = check_engine_cooling(conn, aircraft_no, date, aircraft_no, sortie_numbers)
        conn.close()
        return jsonify(result), 200
    else:
        return jsonify({"error": "Failed to connect to the database."}), 500

@app.route('/check-nl-compressor-rpm', methods=['POST', 'GET'])
def check_nl_compressor_rpm_api():
    req_data = request.json
    date = req_data['date']
    aircraft_no = req_data['aircraft_no']
    sortie_numbers = req_data['sortie_numbers']
    conn = connect_to_db(db_credentials)
    if conn:
        result = check_nl_compressor_rpm(conn, aircraft_no, date, aircraft_no, sortie_numbers)
        conn.close()
        return jsonify(result), 200
    else:
        return jsonify({"error": "Failed to connect to the database."}), 500

if __name__ == '__main__':
    app.run(debug=True)
