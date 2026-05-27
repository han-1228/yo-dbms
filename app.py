from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3

app = Flask(__name__)

# 【核心設定】允許 Netlify 的前端網址跨網域連線到 Render
CORS(app)

# 你的 SQLite 資料庫檔案名稱 (請確認你的 GitHub 裡是不是這個檔名)
DB_FILE = 'yo-dbms.db' 

def get_db_connection():
    """建立資料庫連線的輔助函式"""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row 
    return conn

# ==========================================
# 1. 獲取學生列表 (GET) - 供測試連線與載入使用
# ==========================================
@app.route('/api/students', methods=['GET'])
def get_students():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM students")
        rows = cursor.fetchall()
        conn.close()

        students = [dict(row) for row in rows]
        return jsonify(students), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 2. 手動新增學生 (POST) - 接收前端表單資料
# ==========================================
@app.route('/api/students', methods=['POST'])
def add_student():
    try:
        data = request.get_json()
        student_id = data.get('student_id')
        name = data.get('name')
        email = data.get('email')

        if not student_id or not name or not email:
            return jsonify({"error": "請填寫所有必要欄位"}), 400

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO students (student_id, name, email) VALUES (?, ?, ?)",
            (student_id, name, email)
        )
        conn.commit()
        conn.close()

        return jsonify({"message": "學生資料已成功寫入資料庫！"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ==========================================
# 3. 查詢學生總成績排名 (GET) - 供第二區塊使用
# ==========================================
@app.route('/api/scores', methods=['GET'])
def get_scores_ranking():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 這裡的 SQL 語法是假設你們有 scores 和 students 兩張表
        # 如果你們資料庫結構不同，這裡的欄位名稱需要微調
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
        # 這裡補上了剛剛被截斷的部分！
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
