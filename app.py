from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3  # 如果你們使用 PostgreSQL，請換成 psycopg2；MySQL 換成 pymysql

app = Flask(__name__)

# 【核心設定】這一行超級重要！允許 Netlify 的前端網址跨網域連線到 Render
CORS(app)

# 請更換成你們實際的資料庫檔案名稱路徑
DB_FILE = 'database.db' 

def get_db_connection():
    """建立資料庫連線的輔助函式"""
    conn = sqlite3.connect(DB_FILE)
    # 讓撈出來的資料可以用欄位名稱（如 row['name']）直接存取，方便轉成 JSON
    conn.row_factory = sqlite3.Row 
    return conn


# ==========================================
# 功能一：獲取學生列表 (GET) - 供測試連線與載入使用
# ==========================================
@app.route('/api/students', methods=['GET'])
def get_students():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students")
        rows = cursor.fetchall()
        conn.close()

        # 將資料庫的資料轉換成前端看得懂的 List[dict] 格式
        students = [dict(row) for row in rows]
        return jsonify(students), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==========================================
# 功能二：手動新增學生 (POST) - 接收前端表單資料
# ==========================================
@app.route('/api/students', methods=['POST'])
def add_student():
    try:
        # 接收前端傳過來的 JSON 資料
        data = request.get_json()
        student_id = data.get('student_id')
        name = data.get('name')
        email = data.get('email')

        # 防呆機制：檢查欄位是否齊全
        if not student_id or not name or not email:
            return jsonify({"error": "請填寫所有必要欄位"}), 400

        # 連接資料庫並執行 INSERT INTO 指令
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO students (student_id, name, email) VALUES (?, ?, ?)",
            (student_id, name, email)
        )
        conn.commit()  # 確認寫入資料庫
        conn.close()

        return jsonify({"message": "學生資料已成功寫入資料庫！"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==========================================
# 功能三：查詢學生總成績排名 (GET) - 關聯式資料庫查詢
# ==========================================
@app.route('/api/scores', methods=['GET'])
def get_scores_ranking():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 這裡寫一個 JOIN 語法，把學生表和成績表串聯，並用成績由高到低排序 (DESC)
        # 【注意】請根據你們 yo-dbms.sql 實際的資料表與欄位名稱修改此處的 SQL 語法
        query = """
            SELECT s.student_id, s.name, sc.score 
            FROM students s
            JOIN scores sc ON s.student_id = sc.student_id
            ORDER BY sc.score DESC
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        conn.close()

        rankings = [dict(row) for row in rows]
        return jsonify(rankings), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # 啟動伺服器，在本機測試時會運行在 http://127.0.0.1:5000
    app.run(debug=True, port=5000)
