import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3

app = Flask(__name__)

# 允許所有來源跨網域連線
CORS(app)

DB_FILE = 'yo-dbms.db'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row 
    return conn

# ==========================================
# 🌟 自動建立資料庫與測試資料
# ==========================================
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS Students (
            STU_ID VARCHAR(10) PRIMARY KEY, STU_NAME VARCHAR(50) NOT NULL,
            CLASS_NAME VARCHAR(20) NOT NULL, SEAT_NUM INT
        );
        CREATE TABLE IF NOT EXISTS Courses (
            COURSE_ID VARCHAR(10) PRIMARY KEY, COURSE_NAME VARCHAR(100) NOT NULL,
            SEMESTER VARCHAR(20) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS Assessments (
            AST_ID VARCHAR(10) PRIMARY KEY, COURSE_ID VARCHAR(10),
            AST_NAME VARCHAR(100) NOT NULL, CATEGORY VARCHAR(50), WEIGHT INT,
            FOREIGN KEY (COURSE_ID) REFERENCES Courses(COURSE_ID)
        );
        CREATE TABLE IF NOT EXISTS Scores (
            SCORE_ID VARCHAR(10) PRIMARY KEY, STU_ID VARCHAR(10),
            AST_ID VARCHAR(10), SCORE INT,
            FOREIGN KEY (STU_ID) REFERENCES Students(STU_ID),
            FOREIGN KEY (AST_ID) REFERENCES Assessments(AST_ID)
        );
    """)
    cursor.execute("SELECT COUNT(*) FROM Students")
    if cursor.fetchone()[0] == 0:
        cursor.executescript("""
            INSERT INTO Students VALUES ('S101', '王小明', '甲班', 1), ('S102', '李小華', '甲班', 2), ('S103', '陳大砲', '乙班', 1);
            INSERT INTO Courses VALUES ('C001', '資料庫系統', '112-2');
            INSERT INTO Assessments VALUES ('A001', 'C001', '期末專題', '報告', 100);
            INSERT INTO Scores VALUES ('SC01', 'S101', 'A001', 95), ('SC02', 'S102', 'A001', 82), ('SC03', 'S103', 'A001', 60);
        """)
    conn.commit()
    conn.close()

# 啟動時建立資料庫
init_db()

# ==========================================
# API 路由
# ==========================================
@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "API 伺服器正常運作中！"}), 200

@app.route('/api/students', methods=['GET'])
def get_students():
    try:
        conn = get_db_connection()
        rows = conn.execute("SELECT STU_ID AS student_id, STU_NAME AS name FROM Students").fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/scores', methods=['GET'])
def get_scores_ranking():
    try:
        conn = get_db_connection()
        query = """
            SELECT s.STU_ID AS student_id, s.STU_NAME AS name, SUM(sc.SCORE) AS score 
            FROM Students s JOIN Scores sc ON s.STU_ID = sc.STU_ID
            GROUP BY s.STU_ID, s.STU_NAME ORDER BY score DESC
        """
        rows = conn.execute(query).fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # 注意：Render 需要綁定 0.0.0.0
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
