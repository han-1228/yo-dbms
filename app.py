import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import csv

app = Flask(__name__)
CORS(app)

DB_FILE = 'yo-dbms.db'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db_from_csv():
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
   
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS Students (
            STU_ID VARCHAR(10) PRIMARY KEY, STU_NAME VARCHAR(50), CLASS_NAME VARCHAR(20), SEAT_NUM INT
        );
        CREATE TABLE IF NOT EXISTS Courses (
            COURSE_ID VARCHAR(10) PRIMARY KEY, COURSE_NAME VARCHAR(100), SEMESTER VARCHAR(20)
        );
        CREATE TABLE IF NOT EXISTS Enrollments (
            ENROLL_ID VARCHAR(10) PRIMARY KEY, 
            STU_ID VARCHAR(10), COURSE_ID VARCHAR(10),
            FOREIGN KEY (STU_ID) REFERENCES Students(STU_ID),
            FOREIGN KEY (COURSE_ID) REFERENCES Courses(COURSE_ID)
        );
        CREATE TABLE IF NOT EXISTS Assessments (
            AST_ID VARCHAR(10) PRIMARY KEY, COURSE_ID VARCHAR(10), AST_NAME VARCHAR(100), CATEGORY VARCHAR(50), WEIGHT INT,
            FOREIGN KEY (COURSE_ID) REFERENCES Courses(COURSE_ID)
        );
        CREATE TABLE IF NOT EXISTS Scores (
            SCORE_ID VARCHAR(10) PRIMARY KEY, STU_ID VARCHAR(10), AST_ID VARCHAR(10), SCORE INT,
            FOREIGN KEY (STU_ID) REFERENCES Students(STU_ID),
            FOREIGN KEY (AST_ID) REFERENCES Assessments(AST_ID)
        );
        CREATE TABLE IF NOT EXISTS Portfolios (
            PORT_ID VARCHAR(10) PRIMARY KEY, STU_ID VARCHAR(10), COURSE_ID VARCHAR(10), PORT_NAME VARCHAR(100), PORT_LINK VARCHAR(255), UPLOAD_DATE VARCHAR(20),
            FOREIGN KEY (STU_ID) REFERENCES Students(STU_ID),
            FOREIGN KEY (COURSE_ID) REFERENCES Courses(COURSE_ID)
        );
    """)
    
  
    files_to_import = {
        'students.csv': "INSERT OR IGNORE INTO Students VALUES (?, ?, ?, ?)",
        'courses.csv': "INSERT OR IGNORE INTO Courses VALUES (?, ?, ?)",
        'enrollments.csv': "INSERT OR IGNORE INTO Enrollments VALUES (?, ?, ?)",
        'assessments.csv': "INSERT OR IGNORE INTO Assessments VALUES (?, ?, ?, ?, ?)",
        'scores.csv': "INSERT OR IGNORE INTO Scores VALUES (?, ?, ?, ?)",
        'portfolios.csv': "INSERT OR IGNORE INTO Portfolios VALUES (?, ?, ?, ?, ?, ?)"
    }

    for filename, query in files_to_import.items():
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if row:
                        try:
                            param_count = query.count('?')
                            cursor.execute(query, row[:param_count])
                        except Exception as e:
                            print(f"寫入 {filename} 時略過錯誤: {e}")

    conn.commit()
    conn.close()
    print("🎉 資料庫及 6 張表格全數建立並匯入完成！")

init_db_from_csv()

@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "API 伺服器正常運作中！"}), 200

@app.route('/api/students', methods=['GET'])
def get_students():
        return jsonify({"error": str(e)}), 500

@app.route('/api/courses', methods=['GET'])
def get_courses():
        return jsonify({"error": str(e)}), 500

@app.route('/api/course/<course_id>/roster', methods=['GET'])
def get_course_roster(course_id):
        return jsonify({"error": str(e)}), 500

@app.route('/api/course/<course_id>/scores', methods=['GET'])
def get_course_scores(course_id):
        return jsonify({"error": str(e)}), 500

@app.route('/api/course/<course_id>/portfolios', methods=['GET'])
def get_course_portfolios(course_id):
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
