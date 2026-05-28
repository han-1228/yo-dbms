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
    
    # 2. 自動讀取對應的 CSV 並塞入資料表
    files_to_import = {
        '1.students.csv': "INSERT OR IGNORE INTO Students VALUES (?, ?, ?, ?)",
        '2.courses.csv': "INSERT OR IGNORE INTO Courses VALUES (?, ?, ?)",
        '3.enrollments.csv': "INSERT OR IGNORE INTO Enrollments VALUES (?, ?)",
        '4.assessments.csv': "INSERT OR IGNORE INTO Assessments VALUES (?, ?, ?, ?, ?)",
        '5.scores.csv': "INSERT OR IGNORE INTO Scores VALUES (?, ?, ?, ?)",
        '6.portfolios.csv': "INSERT OR IGNORE INTO Portfolios VALUES (?, ?, ?, ?, ?, ?)"
    }

    for filename, query in files_to_import.items():
        if os.path.exists(filename):
            # 使用 utf-8-sig 避免 Windows CSV 產生的 BOM 亂碼
            with open(filename, 'r', encoding='utf-8-sig') as f:
                reader = csv.reader(f)
                next(reader, None) # 跳過標題列
                for row in reader:
                    if row: # 確保不是空行
                        try:
                            # 取 row 的前 N 個元素，N 由 query 裡面的問號數量決定
                            param_count = query.count('?')
                            cursor.execute(query, row[:param_count])
                        except Exception as e:
                            print(f"寫入 {filename} 時略過一筆錯誤資料: {e}")

    conn.commit()
    conn.close()
    print("🎉 資料庫及 6 張表格全數建立並匯入完成！")

# 開機自動執行建庫腳本
init_db_from_csv()


# ==========================================
# 網頁要求的 API 接口 (SQL JOIN 實作)
# ==========================================

# [系統狀態 API]
@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "API 伺服器正常運作中！"}), 200

# [全校學生名單 API]
@app.route('/api/students', methods=['GET'])
def get_students():
    try:
        conn = get_db_connection()
        rows = conn.execute("SELECT STU_ID, STU_NAME, CLASS_NAME, SEAT_NUM FROM Students").fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# [全校開課清單 API]
@app.route('/api/courses', methods=['GET'])
def get_courses():
    try:
        conn = get_db_connection()
        rows = conn.execute("SELECT COURSE_ID, COURSE_NAME, SEMESTER FROM Courses").fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# [特定課程 API 1：修課名單 (JOIN Enrollments & Students)]
@app.route('/api/course/<course_id>/roster', methods=['GET'])
def get_course_roster(course_id):
    try:
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# [特定課程 API 2：學生成績 (JOIN Scores, Students & Assessments)]
@app.route('/api/course/<course_id>/scores', methods=['GET'])
def get_course_scores(course_id):
    try:
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# [特定課程 API 3：作品集 (JOIN Portfolios & Students)]
@app.route('/api/course/<course_id>/portfolios', methods=['GET'])
def get_course_portfolios(course_id):
    try:
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
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
