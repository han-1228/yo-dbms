import os
from flask import Flask, jsonify, request
from flask_cors import CORS
import mysql.connector
from dotenv import load_dotenv
import csv

load_dotenv()

app = Flask(__name__)
CORS(app)

# 使用專案目錄作為基準路徑，確保在不同工作目錄下仍能正確找到 CSV 與憑證
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def get_mysql_connection():
    host = os.getenv('DB_HOST', 'mysql-1af924e-yo-dbms.i.aivencloud.com')
    port = int(os.getenv('DB_PORT', 25889))
    user = os.getenv('DB_USER', 'avnadmin')
    password = os.getenv('DB_PASSWORD', 'my_password')
    database = os.getenv('DB_NAME', 'schoolsystemdb')
    ssl_ca_path = os.path.join(BASE_DIR, 'ca.pem')

    conn_kwargs = {
        'host': host,
        'port': port,
        'user': user,
        'password': password,
        'database': database
    }
    if os.path.exists(ssl_ca_path):
        conn_kwargs['ssl_ca'] = ssl_ca_path

    return mysql.connector.connect(**conn_kwargs)

def import_csv_to_mysql(cursor, table_name, file_path, sql_query):
    print(f"正在匯入 {table_name}...")
    if not os.path.exists(file_path):
        print(f"❌ 找不到檔案：{file_path}，跳過此表。")
        return

    param_count = sql_query.count('%s')

    try:
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader, None)
            records = []
            for row in reader:
                if not any(row):
                    continue
                processed = (row + [None] * param_count)[:param_count]
                processed = [None if str(v).strip() == '' else v for v in processed]
                records.append(tuple(processed))

            if records:
                cursor.executemany(sql_query, records)
                print(f"✅ {table_name} 匯入成功！共 {cursor.rowcount} 筆資料。")
            else:
                print(f"⚠️ {file_path} 裡面沒有資料（或是只有標題）。")
    except mysql.connector.Error as err:
        print(f"❌ {table_name} 匯入失敗。錯誤原因: {err}")
    except Exception as e:
        print(f"❌ {table_name} 發生未知的錯誤: {e}")


def init_db_from_csv_mysql():
    try:
        conn = get_mysql_connection()
        cursor = conn.cursor()

        # 建表（若不存在）
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Students (
                STU_ID VARCHAR(50) PRIMARY KEY,
                STU_NAME VARCHAR(200),
                CLASS_NAME VARCHAR(100),
                SEAT_NUM INT
            ) ENGINE=InnoDB;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Courses (
                COURSE_ID VARCHAR(50) PRIMARY KEY,
                COURSE_NAME VARCHAR(255),
                SEMESTER VARCHAR(50)
            ) ENGINE=InnoDB;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Enrollments (
                ENROLL_ID VARCHAR(50) PRIMARY KEY,
                STU_ID VARCHAR(50),
                COURSE_ID VARCHAR(50),
                FOREIGN KEY (STU_ID) REFERENCES Students(STU_ID),
                FOREIGN KEY (COURSE_ID) REFERENCES Courses(COURSE_ID)
            ) ENGINE=InnoDB;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Assessments (
                AST_ID VARCHAR(50) PRIMARY KEY,
                COURSE_ID VARCHAR(50),
                AST_NAME VARCHAR(255),
                CATEGORY VARCHAR(100),
                WEIGHT INT,
                FOREIGN KEY (COURSE_ID) REFERENCES Courses(COURSE_ID)
            ) ENGINE=InnoDB;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Scores (
                SCORE_ID VARCHAR(50) PRIMARY KEY,
                STU_ID VARCHAR(50),
                AST_ID VARCHAR(50),
                SCORE INT,
                FOREIGN KEY (STU_ID) REFERENCES Students(STU_ID),
                FOREIGN KEY (AST_ID) REFERENCES Assessments(AST_ID)
            ) ENGINE=InnoDB;
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS Portfolios (
                PORTFO_ID VARCHAR(50) PRIMARY KEY,
                STU_ID VARCHAR(50),
                COURSE_ID VARCHAR(50),
                AST_ID VARCHAR(50),
                TITLE VARCHAR(255),
                UPLOAD_DATE VARCHAR(50),
                FILE_URL VARCHAR(255),
                FOREIGN KEY (STU_ID) REFERENCES Students(STU_ID),
                FOREIGN KEY (COURSE_ID) REFERENCES Courses(COURSE_ID),
                FOREIGN KEY (AST_ID) REFERENCES Assessments(AST_ID)
            ) ENGINE=InnoDB;
        """)

        # 匯入 CSV（以 BASE_DIR 為根目錄）
        files_to_import = [
            ("Students", os.path.join(BASE_DIR, 'students.csv'),
             "INSERT IGNORE INTO Students (STU_ID, STU_NAME, CLASS_NAME, SEAT_NUM) VALUES (%s, %s, %s, %s)"),
            ("Courses", os.path.join(BASE_DIR, 'courses.csv'),
             "INSERT IGNORE INTO Courses (COURSE_ID, COURSE_NAME, SEMESTER) VALUES (%s, %s, %s)"),
            ("Enrollments", os.path.join(BASE_DIR, 'enrollments.csv'),
             "INSERT IGNORE INTO Enrollments (ENROLL_ID, STU_ID, COURSE_ID) VALUES (%s, %s, %s)"),
            ("Assessments", os.path.join(BASE_DIR, 'assessments.csv'),
             "INSERT IGNORE INTO Assessments (AST_ID, COURSE_ID, AST_NAME, CATEGORY, WEIGHT) VALUES (%s, %s, %s, %s, %s)"),
            ("Scores", os.path.join(BASE_DIR, 'scores.csv'),
             "INSERT IGNORE INTO Scores (SCORE_ID, STU_ID, AST_ID, SCORE) VALUES (%s, %s, %s, %s)"),
            ("Portfolios", os.path.join(BASE_DIR, 'portfolios.csv'),
             "INSERT IGNORE INTO Portfolios (PORTFO_ID, STU_ID, COURSE_ID, AST_ID, TITLE, UPLOAD_DATE, FILE_URL) VALUES (%s, %s, %s, %s, %s, %s, %s)")
        ]

        for table_name, path, query in files_to_import:
            if os.path.exists(path):
                import_csv_to_mysql(cursor, table_name, path, query)

        conn.commit()
        cursor.close()
        conn.close()
        print("🎉 MySQL 資料庫表格建立並匯入完成！")
    except mysql.connector.Error as e:
        print(f"MySQL 連線或操作失敗: {e}")

# 初始化（建立表格並匯入 CSV）
init_db_from_csv_mysql()

# helper: 將 cursor.fetchall() 與 column_names 轉為 list[dict]
def rows_to_dicts(cursor, rows):
    cols = cursor.column_names
    return [dict(zip(cols, row)) for row in rows]

@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "API 伺服器（MySQL）正常運作中！"}), 200

@app.route('/api/students', methods=['GET'])
def get_students():
    try:
        conn = get_mysql_connection()
        cur = conn.cursor()
        cur.execute("SELECT STU_ID, STU_NAME, CLASS_NAME, SEAT_NUM FROM Students")
        rows = cur.fetchall()
        data = rows_to_dicts(cur, rows)
        cur.close()
        conn.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/courses', methods=['GET'])
def get_courses():
    try:
        conn = get_mysql_connection()
        cur = conn.cursor()
        cur.execute("SELECT COURSE_ID, COURSE_NAME, SEMESTER FROM Courses")
        rows = cur.fetchall()
        data = rows_to_dicts(cur, rows)
        cur.close()
        conn.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/course/<course_id>/roster', methods=['GET'])
def get_course_roster(course_id):
    try:
        conn = get_mysql_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT s.STU_ID, s.STU_NAME, s.CLASS_NAME, s.SEAT_NUM FROM Enrollments e JOIN Students s ON e.STU_ID = s.STU_ID WHERE e.COURSE_ID = %s",
            (course_id,)
        )
        rows = cur.fetchall()
        data = rows_to_dicts(cur, rows)
        cur.close()
        conn.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/course/<course_id>/scores', methods=['GET'])
def get_course_scores(course_id):
    try:
        conn = get_mysql_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT sc.SCORE_ID, sc.STU_ID, st.STU_NAME, st.CLASS_NAME, st.SEAT_NUM, sc.AST_ID, a.AST_NAME, sc.SCORE "
            "FROM Scores sc "
            "JOIN Students st ON sc.STU_ID = st.STU_ID "
            "JOIN Assessments a ON sc.AST_ID = a.AST_ID "
            "WHERE a.COURSE_ID = %s",
            (course_id,)
        )
        rows = cur.fetchall()
        data = rows_to_dicts(cur, rows)
        cur.close()
        conn.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/course/<course_id>/portfolios', methods=['GET'])
def get_course_portfolios(course_id):
    try:
        conn = get_mysql_connection()
        cur = conn.cursor()
        # 回傳前端需要的欄位：PORTFO_ID, STU_ID, AST_ID, TITLE, FILE_URL, UPLOAD_DATE
        cur.execute(
            "SELECT p.PORTFO_ID, p.STU_ID, p.AST_ID, p.TITLE, p.FILE_URL, p.UPLOAD_DATE "
            "FROM Portfolios p "
            "WHERE p.COURSE_ID = %s",
            (course_id,)
        )
        rows = cur.fetchall()
        data = rows_to_dicts(cur, rows)
        cur.close()
        conn.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/students/<stu_id>', methods=['DELETE'])
def delete_student(stu_id):
    try:
        conn = get_mysql_connection()
        cur = conn.cursor()
        # 開始交易，先刪除從屬資料以避免 FK 錯誤
        conn.start_transaction()
        cur.execute("DELETE FROM Scores WHERE STU_ID = %s", (stu_id,))
        scores_deleted = cur.rowcount
        cur.execute("DELETE FROM Portfolios WHERE STU_ID = %s", (stu_id,))
        portfolios_deleted = cur.rowcount
        cur.execute("DELETE FROM Enrollments WHERE STU_ID = %s", (stu_id,))
        enrollments_deleted = cur.rowcount
        cur.execute("DELETE FROM Students WHERE STU_ID = %s", (stu_id,))
        students_deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            "ok": True,
            "deleted": {
                "students": students_deleted,
                "enrollments": enrollments_deleted,
                "scores": scores_deleted,
                "portfolios": portfolios_deleted
            }
        }), 200
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        return jsonify({"error": str(e)}), 500

@app.route('/api/courses/<course_id>', methods=['DELETE'])
def delete_course(course_id):
    try:
        conn = get_mysql_connection()
        cur = conn.cursor()
        conn.start_transaction()
        # 刪除作品與修課紀錄直接關聯到課程
        cur.execute("DELETE FROM Portfolios WHERE COURSE_ID = %s", (course_id,))
        portfolios_deleted = cur.rowcount
        cur.execute("DELETE FROM Enrollments WHERE COURSE_ID = %s", (course_id,))
        enrollments_deleted = cur.rowcount
        # 先找出該課程的評量項目，再刪除對應的成績
        cur.execute("SELECT AST_ID FROM Assessments WHERE COURSE_ID = %s", (course_id,))
        ast_rows = cur.fetchall()
        ast_ids = [r[0] for r in ast_rows]
        scores_deleted = 0
        if ast_ids:
            placeholders = ','.join(['%s'] * len(ast_ids))
            cur.execute(f"DELETE FROM Scores WHERE AST_ID IN ({placeholders})", tuple(ast_ids))
            scores_deleted = cur.rowcount
        # 刪除評量項目
        cur.execute("DELETE FROM Assessments WHERE COURSE_ID = %s", (course_id,))
        assessments_deleted = cur.rowcount
        # 最後刪除課程
        cur.execute("DELETE FROM Courses WHERE COURSE_ID = %s", (course_id,))
        courses_deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            "ok": True,
            "deleted": {
                "courses": courses_deleted,
                "assessments": assessments_deleted,
                "scores": scores_deleted,
                "enrollments": enrollments_deleted,
                "portfolios": portfolios_deleted
            }
        }), 200
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        return jsonify({"error": str(e)}), 500

@app.route('/api/diag', methods=['GET'])
def api_diag():
    """回傳目前 Flask 註冊的路由清單，供部署診斷使用。"""
    try:
        routes = []
        for rule in app.url_map.iter_rules():
            routes.append({
                'rule': str(rule),
                'endpoint': rule.endpoint,
                'methods': sorted(list(rule.methods))
            })
        return jsonify({'routes': routes}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/echo', methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'])
def api_echo():
    """回顯請求資訊（method/path/query/headers/body），方便外部測試路由是否可達。"""
    try:
        data = {
            'method': request.method,
            'path': request.path,
            'query': request.args.to_dict(),
            'headers': dict(request.headers),
            'json': request.get_json(silent=True)
        }
        return jsonify({'echo': data}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/course/<course_id>/enrollments/<stu_id>', methods=['DELETE'])
def remove_enrollment(course_id, stu_id):
    """刪除某學生在指定課程的修課紀錄，同步刪除該課程相關的成績與作品（若有）。"""
    try:
        conn = get_mysql_connection()
        cur = conn.cursor()
        conn.start_transaction()
        # 1) 刪除該學生在此課程評量相關的成績（透過 Assessments 找出 AST_ID）
        cur.execute("SELECT AST_ID FROM Assessments WHERE COURSE_ID = %s", (course_id,))
        ast_rows = cur.fetchall()
        ast_ids = [r[0] for r in ast_rows]
        scores_deleted = 0
        if ast_ids:
            placeholders = ','.join(['%s'] * len(ast_ids))
            cur.execute(f"DELETE FROM Scores WHERE STU_ID = %s AND AST_ID IN ({placeholders})", tuple([stu_id] + ast_ids))
            scores_deleted = cur.rowcount
        # 2) 刪除該學生在此課程的作品
        cur.execute("DELETE FROM Portfolios WHERE STU_ID = %s AND COURSE_ID = %s", (stu_id, course_id))
        portfolios_deleted = cur.rowcount
        # 3) 刪除修課紀錄
        cur.execute("DELETE FROM Enrollments WHERE STU_ID = %s AND COURSE_ID = %s", (stu_id, course_id))
        enrollments_deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({
            'ok': True,
            'deleted': {
                'enrollments': enrollments_deleted,
                'scores': scores_deleted,
                'portfolios': portfolios_deleted
            }
        }), 200
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        return jsonify({'error': str(e)}), 500

@app.route('/api/course/<course_id>/portfolios/<portfo_id>', methods=['DELETE'])
def delete_portfolio(course_id, portfo_id):
    """刪除單一作品（依 PORTFO_ID），只處理該筆作品。"""
    try:
        conn = get_mysql_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM Portfolios WHERE PORTFO_ID = %s AND COURSE_ID = %s", (portfo_id, course_id))
        deleted = cur.rowcount
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'ok': True, 'deleted': deleted}), 200
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        return jsonify({'error': str(e)}), 500

@app.route('/api/courses/search', methods=['GET'])
def search_courses():
    """後端搜尋課程：接受 query params 'field' 與 'q'，在指定欄位做 SQL LIKE 搜尋。
    field 可為 COURSE_ID, COURSE_NAME, SEMESTER。
    若 q 為空則回傳全部課程。
    """
    try:
        field = request.args.get('field', 'COURSE_ID')
        q = request.args.get('q', '') or ''
        allowed = {'COURSE_ID', 'COURSE_NAME', 'SEMESTER'}
        if field not in allowed:
            return jsonify({'error': 'invalid field parameter'}), 400

        conn = get_mysql_connection()
        cur = conn.cursor()
        if q.strip() == '':
            cur.execute("SELECT COURSE_ID, COURSE_NAME, SEMESTER FROM Courses")
        else:
            sql = f"SELECT COURSE_ID, COURSE_NAME, SEMESTER FROM Courses WHERE {field} LIKE %s"
            cur.execute(sql, (f"%{q}%",))
        rows = cur.fetchall()
        data = rows_to_dicts(cur, rows)
        cur.close()
        conn.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
