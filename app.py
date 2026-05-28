import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import sqlite3
import csv

app = Flask(__name__)

# 允許所有來源跨網域連線 (很重要，這樣 Netlify 才抓得到)
CORS(app)

DB_FILE = 'yo-dbms.db'

def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row 
    return conn

# ==========================================
# 🌟 自動建立資料表，並讀取 GitHub 上的 CSV 檔案
# ==========================================
def init_db_from_csv():
    # 如果舊的資料庫存在，先刪除，確保每次重開都是讀取最新的 CSV 資料
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # 1. 建立資料庫結構 (關聯式表格)
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
    conn.commit()
    print("📋 資料庫核心資料表建立成功！")

    # 2. 自動讀取並匯入學生的 CSV
    if os.path.exists('students.csv'):
        with open('students.csv', 'r', encoding='utf-8-sig') as f: # 用 utf-8-sig 避免 BOM 亂碼
            reader = csv.reader(f)
            next(reader, None) # 跳過第一行的欄位名稱
            for row in reader:
                if row and len(row) >= 4: # 確保不是空行且欄位數足夠
                    try:
                        cursor.execute("INSERT OR IGNORE INTO Students VALUES (?, ?, ?, ?)", (row[0], row[1], row[2], row[3]))
                    except Exception as e:
                        print(f"寫入 Students 錯誤: {e}")
        print("✅ 成功匯入真實學生資料！")

    # 3. 自動讀取並匯入課程的 CSV
    if os.path.exists('courses.csv'):
        with open('courses.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if row and len(row) >= 3:
                    try:
                        cursor.execute("INSERT OR IGNORE INTO Courses VALUES (?, ?, ?)", (row[0], row[1], row[2]))
                    except Exception as e:
                        print(f"寫入 Courses 錯誤: {e}")
        print("✅ 成功匯入真實課程資料！")

    # 4. 自動讀取並匯入評量的 CSV
    if os.path.exists('assessments.csv'):
        with open('assessments.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if row and len(row) >= 5:
                    try:
                        cursor.execute("INSERT OR IGNORE INTO Assessments VALUES (?, ?, ?, ?, ?)", (row[0], row[1], row[2], row[3], row[4]))
                    except Exception as e:
                        print(f"寫入 Assessments 錯誤: {e}")
        print("✅ 成功匯入真實評量項目！")

    # 5. 自動讀取並匯入成績的 CSV
    if os.path.exists('scores.csv'):
        with open('scores.csv', 'r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader, None)
            for row in reader:
                if row and len(row) >= 4:
                    try:
                        cursor.execute("INSERT OR IGNORE INTO Scores VALUES (?, ?, ?, ?)", (row[0], row[1], row[2], row[3]))
                    except Exception as e:
                        print(f"寫入 Scores 錯誤: {e}")
        print("✅ 成功匯入真實成績資料！")

    conn.commit()
    conn.close()
    print("🎉 所有真實 CSV 資料已成功轉移至 SQLite 關聯式資料庫！")

# 每次伺服器開機，就重新讀取 CSV 轉成資料庫
init_db_from_csv()


# ==========================================
# 網頁要求的 API 接口
# ==========================================

# 讓 Render 檢查服務是否活著的基本路徑
@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "API 伺服器正常運作中，準備好提供資料！"}), 200


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
        # 這裡會動態整合（JOIN）你匯入的學生表格與成績表格
        query = """
            SELECT s.STU_ID AS student_id, s.STU_NAME AS name, SUM(sc.SCORE) AS score 
            FROM Students s 
            JOIN Scores sc ON s.STU_ID = sc.STU_ID
            GROUP BY s.STU_ID, s.STU_NAME 
            ORDER BY score DESC
        """
        rows = conn.execute(query).fetchall()
        conn.close()
        return jsonify([dict(row) for row in rows]), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # 注意：Render 需要綁定 0.0.0.0，並且動態抓取 PORT
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
