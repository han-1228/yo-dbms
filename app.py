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
    
    # 建立全部 6 張關聯表
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS Students (
            STU_ID VARCHAR(10) PRIMARY KEY, STU_NAME VARCHAR(50), CLASS_NAME VARCHAR(20), SEAT_NUM INT
        );
        CREATE TABLE IF NOT EXISTS Courses (
            COURSE_ID VARCHAR(10) PRIMARY KEY, COURSE_NAME VARCHAR(100), SEMESTER VARCHAR(20)
        );
        CREATE TABLE IF NOT EXISTS Enrollments (
            STU_ID VARCHAR(10), COURSE_ID VARCHAR(10),
            PRIMARY KEY (STU_ID, COURSE_ID),
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
    
    # 讀取所有 CSV (加入防錯機制)
    files = {
        '1.students.csv': "INSERT OR IGNORE INTO Students VALUES (?, ?, ?, ?)",
        '2.courses.csv': "INSERT OR IGNORE INTO Courses VALUES (?, ?, ?)",
        '3.enrollments.csv': "INSERT OR IGNORE INTO Enrollments VALUES (?, ?)",
        '4.assessments.csv': "INSERT OR IGNORE INTO Assessments VALUES (?, ?, ?, ?, ?)",
        '5.scores.csv': "INSERT OR IGNORE INTO Scores VALUES (?, ?, ?, ?)",
        '6.portfolios.csv': "INSERT OR IGNORE INTO Portfolios VALUES (?, ?, ?, ?, ?, ?)"
    }

    for filename, query in files.items():
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if row:
                        try:
                            # 動態切齊參數長度
                            cursor.execute(query, row[:query.count('?')])
                        except Exception as e:
                            print(f"寫入 {filename} 發生錯誤: {e}")

    conn.commit()
    conn.close()
    print("🎉 資料庫及 6 張表格全數建立並匯入完成！")

init_db_from_csv()


# ==========================================
# 網頁 API 接口 (透過 SQL JOIN 聯動資料)
# ==========================================
@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "API 伺服器正常運作中！"}), 200

@app.route('/api/students', methods=['GET'])
def get_students():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM Students").fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows]), 200

@app.route('/api/courses', methods=['GET'])
def get_courses():
    conn = get_db_connection()
    rows = conn.execute("SELECT * FROM Courses").fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows]), 200

# 取得特定課程的「修課名單」
@app.route('/api/course/<course_id>/roster', methods=['GET'])
def get_course_roster(course_id):
    conn = get_db_connection()
    query = """
        SELECT s.STU_ID, s.STU_NAME, s.CLASS_NAME, s.SEAT_NUM 
        FROM Students s 
        JOIN Enrollments e ON s.STU_ID = e.STU_ID 
        WHERE e.COURSE_ID = ?
    """
    rows = conn.execute(query, (course_id,)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows]), 200

# 取得特定課程的「成績單」
@app.route('/api/course/<course_id>/scores', methods=['GET'])
def get_course_scores(course_id):
    conn = get_db_connection()
    query = """
        SELECT s.STU_ID, s.CLASS_NAME, s.SEAT_NUM, s.STU_NAME, a.AST_NAME, sc.SCORE 
        FROM Scores sc 
        JOIN Students s ON sc.STU_ID = s.STU_ID 
        JOIN Assessments a ON sc.AST_ID = a.AST_ID 
        WHERE a.COURSE_ID = ?
    """
    rows = conn.execute(query, (course_id,)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows]), 200

# 取得特定課程的「作品表」
@app.route('/api/course/<course_id>/portfolios', methods=['GET'])
def get_course_portfolios(course_id):
    conn = get_db_connection()
    query = """
        SELECT s.CLASS_NAME, s.SEAT_NUM, s.STU_NAME, p.PORT_NAME, p.PORT_LINK, p.UPLOAD_DATE 
        FROM Portfolios p 
        JOIN Students s ON p.STU_ID = s.STU_ID 
        WHERE p.COURSE_ID = ?
    """
    rows = conn.execute(query, (course_id,)).fetchall()
    conn.close()
    return jsonify([dict(row) for row in rows]), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
