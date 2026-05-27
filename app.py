import os
from dotenv import load_dotenv

# 告訴 Python 不要去找預設的 .env，去抓我的 data.env！
load_dotenv('data.env')

from flask import Flask, jsonify, request
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error

app = Flask(__name__)
CORS(app) 

app.json.ensure_ascii = False

# ==========================================
# 資料庫連線設定
# ==========================================
db_config = {
    'host': 'mysql-1af924e-yo-dbms.i.aivencloud.com',
    'port': 25889,
    'user': 'avnadmin',
    
    # 🌟 3. 安全地改回這個寫法，現在它一定讀得到了！
    'password': os.environ.get('DB_PASSWORD'), 
    
    'database': 'schoolsystemdb',               
    'ssl_ca': 'ca.pem'                          
}

def get_db_connection():
    try:
        conn = mysql.connector.connect(**db_config)
        return conn
    except Error as e:
        print(f"資料庫連線失敗: {e}")
        return None


# ==========================================
# 喚醒路由 (專留給 UptimeRobot 戳門用)
# ==========================================
@app.route('/keep-alive', methods=['GET'])
def keep_alive():
    return jsonify({"status": "alive", "message": "Server is awake!"}), 200


# ==========================================
# API 路由區塊 (前後端資料交換中心)
# ==========================================

# 1. 測試與讀取用：撈取所有學生資料 (GET) -> 【這就是原本的步驟二！】
@app.route('/api/students', methods=['GET'])
def get_all_students():
    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "資料庫連線失敗"}), 500

    try:
        cursor = conn.cursor(dictionary=True) # dictionary=True 讓回傳結果自動變成 JSON 格式
        cursor.execute("SELECT * FROM Students")
        students = cursor.fetchall()
        
        cursor.close()
        conn.close()
        return jsonify(students), 200
    except Error as e:
        return jsonify({"status": "error", "message": f"查詢失敗: {e}"}), 400


# 2. 接收前端傳來的資料，新增學生 (POST)
@app.route('/api/students', methods=['POST'])
def add_student():
    data = request.json 
    
    # 驗證前端傳來的 JSON 欄位（配合前端組員的習慣，這裡維持大寫）
    if not data or 'STUDENTID' not in data or 'STUDENTNAME' not in data:
        return jsonify({"status": "error", "message": "缺少必要欄位 (學號或姓名)"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "資料庫連線失敗"}), 500

    try:
        cursor = conn.cursor()
        # 🌟 這裡已將欄位修改為與 Aiven 資料庫一致的 STU_ID, STU_NAME, CLASS_NAME, SEAT_NUM
        sql = """
            INSERT INTO Students (STU_ID, STU_NAME, CLASS_NAME, SEAT_NUM) 
            VALUES (%s, %s, %s, %s)
        """
        values = (
            data['STUDENTID'], 
            data['STUDENTNAME'], 
            data.get('CLASSNAME'), 
            data.get('SEATNUMBER')
        )
        
        cursor.execute(sql, values)
        conn.commit() # 真正寫入雲端
        
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "message": f"成功新增學生：{data['STUDENTNAME']}"}), 201
    except Error as e:
        return jsonify({"status": "error", "message": f"資料庫寫入失敗: {e}"}), 400


# 3. 接收前端傳來的資料，新增成績 (POST)
@app.route('/api/scores', methods=['POST'])
def add_score():
    data = request.json
    
    if not data or not all(k in data for k in ['SCOREID', 'STUDENTID', 'ASSESSMENTID', 'SCORE']):
        return jsonify({"status": "error", "message": "欄位不完整"}), 400

    conn = get_db_connection()
    if not conn:
        return jsonify({"status": "error", "message": "資料庫連線失敗"}), 500

    try:
        cursor = conn.cursor()
        # 🌟 這裡已將欄位修改為與 Aiven 資料庫一致的 SCORE_ID, STU_ID, AST_ID, SCORE
        sql = """
            INSERT INTO Scores (SCORE_ID, STU_ID, AST_ID, SCORE) 
            VALUES (%s, %s, %s, %s)
        """
        values = (data['SCOREID'], data['STUDENTID'], data['ASSESSMENTID'], data['SCORE'])
        
        cursor.execute(sql, values)
        conn.commit()
        
        cursor.close()
        conn.close()
        return jsonify({"status": "success", "message": "成績新增成功！"}), 201
    except Error as e:
        return jsonify({"status": "error", "message": f"新增失敗 (請檢查學號或評量代碼是否存在): {e}"}), 400


# ==========================================
# 啟動 Flask 伺服器 (必須放在程式碼的最底部)
# ==========================================
if __name__ == '__main__':
    # 這裡將 port 改為 5001。等之後部署到 Render 時，Render 會自動幫你注入正確的外部 Port
    app.run(debug=True, port=5001)
