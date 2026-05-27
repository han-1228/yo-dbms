import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3

app = Flask(__name__)

# 允許跨網域連線
CORS(app)

DB_FILE = 'yo-dbms.db'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row 
    return conn

# ==========================================
# 🌟 魔法核心：自動建立資料庫與寫入測試資料
# ==========================================
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 執行你的 SQL 藍圖 (如果沒有這些表，就自動建立)
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS Students (
            STU_ID VARCHAR(10) PRIMARY KEY,
            STU_NAME VARCHAR(50) NOT NULL,
            CLASS_NAME VARCHAR(20) NOT NULL,
            SEAT_NUM INT
        );
        CREATE TABLE IF NOT EXISTS Courses (
            COURSE_ID VARCHAR(10) PRIMARY KEY,
            COURSE_NAME VARCHAR(100) NOT NULL,
            SEMESTER VARCHAR(20) NOT NULL
        );
        CREATE TABLE IF NOT EXISTS Assessments (
            AST_ID VARCHAR(10) PRIMARY KEY,
            COURSE_ID VARCHAR(10),
            AST_NAME VARCHAR(100) NOT NULL,
            CATEGORY VARCHAR(50),
            WEIGHT INT,
            FOREIGN KEY (COURSE_ID) REFERENCES Courses(COURSE_ID)
        );
        CREATE TABLE IF NOT EXISTS Scores (
            SCORE_ID VARCHAR(10) PRIMARY KEY,
            STU_ID VARCHAR(10),
            AST_ID VARCHAR(10),
            SCORE INT,
            FOREIGN KEY (STU_ID) REFERENCES Students(STU_ID),
            FOREIGN KEY (AST_ID) REFERENCES Assessments(AST_ID)
        );
    """)

    # 2. 檢查有沒有資料，沒有的話就塞入測試資料讓網頁撈得到東西！
    cursor.execute("SELECT COUNT(*) FROM Students")
    if cursor.fetchone()[0] == 0:
        cursor.executescript("""
            INSERT INTO Students (STU_ID, STU_NAME, CLASS_NAME, SEAT_NUM) VALUES 
            ('S101', '王小明', '甲班', 1),
            ('S102', '李小華', '甲班', 2),
            ('S103', '陳大砲', '乙班', 1);

            INSERT INTO Courses (COURSE_ID, COURSE_NAME, SEMESTER) VALUES 
            ('C001', '資料庫系統', '112-2');

            INSERT INTO Assessments (AST_ID, COURSE_ID, AST_NAME, CATEGORY, WEIGHT) VALUES 
            ('A001', 'C001', '期末專題', '報告', 100);

            INSERT INTO Scores (SCORE_ID, STU_ID, AST_ID, SCORE) VALUES 
            ('SC01', 'S101', 'A001', 95),
            ('SC02', 'S102', 'A001', 82),
            ('SC03', 'S103', 'A001', 60);
        """)
        
    conn.commit()
    conn.close()

# 每次伺服器啟動時，自動執行上面的建表檢查
init_db()


# ==========================================
# 1. 獲取學生列表 (GET) - 測試連線用
# ==========================================
@app.route('/api/students', methods=['GET'])
def get_students():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT STU_ID AS student_id, STU_NAME AS name, CLASS_NAME AS class_name FROM Students")
        rows = cursor.fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 2. 手動新增學生 (POST)
# ==========================================
@app.route('/api/students', methods=['POST'])
def add_student():
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        name = data.get('name')
        class_name = data.get('email', '未分班') # 前端傳 email，我們存進班級

        if not student_id or not name:
            return jsonify({"error": "請填寫必要欄位"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO Students (STU_ID, STU_NAME, CLASS_NAME, SEAT_NUM) VALUES (?, ?, ?, ?)",
            (student_id, name, class_name, 0)
        )
        conn.commit()
        conn.close()
        return jsonify({"message": "學生資料已成功寫入資料庫！"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 3. 查詢學生總成績排名 (GET) - 給第二區塊使用
# ==========================================
@app.route('/api/scores', methods=['GET'])
def get_scores_ranking():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 完美匹配你的資料庫欄位，JOIN 表格並計算總分
        query = """
            SELECT 
                s.STU_ID AS student_id, 
                s.STU_NAME AS name, 
                SUM(sc.SCORE) AS score 
            FROM Students s
            JOIN Scores sc ON s.STU_ID = sc.STU_ID
            GROUP BY s.STU_ID, s.STU_NAME
            ORDER BY score DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
