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
# 1. 獲取學生列表 (GET)
# ==========================================
@app.route('/api/students', methods=['GET'])
def get_students():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 【修改重點】用 AS 把你的 STU_ID 假裝成 student_id 給前端看
        cursor.execute("SELECT STU_ID AS student_id, STU_NAME AS name, CLASS_NAME AS class_name FROM Students")
        rows = cursor.fetchall()
        conn.close()

        students = [dict(row) for row in rows]
        return jsonify(students), 200
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
        # 前端傳來的是 email，但你的資料庫是 CLASS_NAME，我們就先把它存進去
        class_name = data.get('email', '未分班')

        if not student_id or not name:
            return jsonify({"error": "請填寫必要欄位"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 【修改重點】對應你的 Students 表格真實欄位
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
# 3. 查詢學生總成績排名 (GET)
# ==========================================
@app.route('/api/scores', methods=['GET'])
def get_scores_ranking():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 【修改重點】完美結合你的 Students 與 Scores 表格，並且把該學生的多筆成績加總(SUM)
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

        rankings = [dict(row) for row in rows]
        return jsonify(rankings), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
