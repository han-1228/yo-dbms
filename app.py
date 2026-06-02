import os
from flask import Flask, jsonify, request, send_file
from flask_cors import CORS
import mysql.connector
from dotenv import load_dotenv
import csv
import time
import random
import io
import re

load_dotenv()

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False
app.json.ensure_ascii = False
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
                WEIGHT FLOAT,
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
                FILE_URL TEXT,
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

        # 轉換：若 Assessments 裡的 WEIGHT 是以百分比 (例如 30 或 100) 儲存（>1），自動除以 100 轉為小數
        try:
            cursor.execute("SELECT COUNT(*) FROM Assessments WHERE WEIGHT > 1")
            cnt_row = cursor.fetchone()
            cnt = cnt_row[0] if cnt_row else 0
            if cnt and cnt > 0:
                print(f"發現 {cnt} 筆 Assessments.WEIGHT > 1，將視為百分比並除以 100 轉為小數...")
                cursor.execute("UPDATE Assessments SET WEIGHT = WEIGHT / 100.0 WHERE WEIGHT > 1")
                # 進行每門課程的總和正規化，避免因除法或資料不一致導致總和 != 1
                cursor.execute("SELECT COURSE_ID, SUM(WEIGHT) as s FROM Assessments GROUP BY COURSE_ID")
                sums = cursor.fetchall()
                for row in sums:
                    course_id = row[0]
                    s = float(row[1]) if row[1] is not None else 0.0
                    if s > 0:
                        # 若總和與 1 相差較大，按比例調整
                        if abs(s - 1.0) > 1e-9:
                            factor = 1.0 / s
                            cursor.execute("UPDATE Assessments SET WEIGHT = WEIGHT * %s WHERE COURSE_ID = %s", (factor, course_id))
                print('完成百分比轉換與按課程正規化。')
        except Exception as e:
            print('在轉換 Assessments 權重時發生錯誤:', e)

        conn.commit()
        cursor.close()
        conn.close()
        print("🎉 MySQL 資料庫表格建立並匯入完成！")
    except mysql.connector.Error as e:
        print(f"MySQL 連線或操作失敗: {e}")

# 初始化（建立表格並匯入 CSV）
# 預設不要在模組載入時自動執行，改以環境變數啟用，避免部署時阻塞或失敗。
if os.environ.get('INIT_DB', '0') == '1':
    init_db_from_csv_mysql()

# helper: 將 cursor.fetchall() 與 column_names 轉為 list[dict]
def rows_to_dicts(cursor, rows):
    cols = cursor.column_names
    return [dict(zip(cols, row)) for row in rows]

@app.route('/', methods=['GET'])
def home():
    index_path = os.path.join(BASE_DIR, 'index.html')
    if os.path.exists(index_path):
        try:
            with open(index_path, 'r', encoding='utf-8') as f:
                content = f.read()
            api_base = os.getenv('API_BASE_URL', '/api')
            # Dynamically replace the baseUrl inside index.html based on environmental variable
            import re
            content = re.sub(
                r"(const|let)\s+baseUrl\s*=\s*['\"].*?['\"];",
                f"const baseUrl = '{api_base}';",
                content,
                count=1
            )
            from flask import make_response
            resp = make_response(content)
            resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp.headers['Pragma'] = 'no-cache'
            resp.headers['Expires'] = '0'
            return resp
        except Exception as e:
            from flask import make_response
            resp = make_response(send_file(index_path))
            resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            resp.headers['Pragma'] = 'no-cache'
            resp.headers['Expires'] = '0'
            return resp
    return jsonify({"message": "API 伺服器（MySQL）正常運作中！"}), 200


# 新增：支援 /api 與 /api/ 的健康檢查（供前端暖機使用）
@app.route('/api', methods=['GET'])
@app.route('/api/', methods=['GET'])
def api_root():
    try:
        return jsonify({"message": "API (MySQL) 正常運作中！", "ok": True}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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

@app.route('/api/students', methods=['POST'])
def save_student():
    try:
        payload = request.get_json(silent=True) or {}
        stu_id = payload.get('STU_ID')
        stu_name = payload.get('STU_NAME')
        class_name = payload.get('CLASS_NAME')
        seat_num = payload.get('SEAT_NUM')
        
        if not stu_id or not stu_name:
            return jsonify({'error': '學號與姓名為必填欄位！'}), 400
            
        conn = get_mysql_connection()
        cur = conn.cursor()
        
        # 檢查該學生是否存在
        cur.execute("SELECT STU_ID FROM Students WHERE STU_ID = %s", (stu_id,))
        row = cur.fetchone()
        
        if row:
            # 更新
            cur.execute(
                "UPDATE Students SET STU_NAME = %s, CLASS_NAME = %s, SEAT_NUM = %s WHERE STU_ID = %s",
                (stu_name, class_name, seat_num, stu_id)
            )
            message = "更新成功"
        else:
            # 新增
            cur.execute(
                "INSERT INTO Students (STU_ID, STU_NAME, CLASS_NAME, SEAT_NUM) VALUES (%s, %s, %s, %s)",
                (stu_id, stu_name, class_name, seat_num)
            )
            message = "新增成功"
            
        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'ok': True, 'message': message}), 200
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
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

@app.route('/api/course/<course_id>/portfolios', methods=['GET'])
def get_course_portfolios(course_id):
    """取得某課程的所有作品，包含學號、評量ID、班級、座號、姓名、作品標題、連結、上傳日期。"""
    try:
        conn = get_mysql_connection()
        cur = conn.cursor()
        query = """
            SELECT p.STU_ID, p.AST_ID, s.CLASS_NAME, s.SEAT_NUM, s.STU_NAME, 
                   p.TITLE, p.FILE_URL, p.UPLOAD_DATE 
            FROM Portfolios p 
            JOIN Students s ON p.STU_ID = s.STU_ID 
            WHERE p.COURSE_ID = %s
        """
        
        cur.execute(query, (course_id,))
        rows = cur.fetchall()
        data = rows_to_dicts(cur, rows)
        # 新增：將 FILE_URL 與 TITLE 組成 HTML 超連結欄位 FILE_LINK
        for item in data:
            url = (item.get('FILE_URL') or '').strip()
            title = item.get('TITLE') or url
            if url:
                # 確保 url 加上協定，避免瀏覽器當作本機相對路徑
                href_url = url
                if not (url.startswith('http://') or url.startswith('https://')):
                    href_url = f"https://{url}"
                # 使用雙引號並加上安全屬性，前端可直接插入為超連結
                item['FILE_LINK'] = f"<a href=\"{href_url}\" target=\"_blank\" rel=\"noopener noreferrer\">{title}</a>"
            else:
                item['FILE_LINK'] = None
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
        query = """
            SELECT 
                s.STU_ID, 
                s.STU_NAME, 
                s.CLASS_NAME, 
                s.SEAT_NUM, 
                a.AST_ID, 
                a.AST_NAME, 
                sc.SCORE 
            FROM Enrollments e
            JOIN Students s ON e.STU_ID = s.STU_ID
            JOIN Assessments a ON e.COURSE_ID = a.COURSE_ID
            LEFT JOIN Scores sc ON s.STU_ID = sc.STU_ID AND a.AST_ID = sc.AST_ID
            WHERE e.COURSE_ID = %s
            ORDER BY s.CLASS_NAME, s.SEAT_NUM, a.AST_ID
        """
        cur.execute(query, (course_id,))
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

@app.route('/api/students/search', methods=['GET'])
def search_students():
    """後端搜尋學生：接受 query params 'field' 與 'q'，在指定欄位做 SQL LIKE 搜尋。
    field 可為 STU_ID, STU_NAME。
    若 q 為空則回傳全部學生。
    """
    try:
        field = request.args.get('field', 'STU_ID')
        q = request.args.get('q', '') or ''
        allowed = {'STU_ID', 'STU_NAME'}
        if field not in allowed:
            return jsonify({'error': 'invalid field parameter'}), 400

        conn = get_mysql_connection()
        cur = conn.cursor()
        if q.strip() == '':
            cur.execute("SELECT STU_ID, STU_NAME, CLASS_NAME, SEAT_NUM FROM Students")
        else:
            sql = f"SELECT STU_ID, STU_NAME, CLASS_NAME, SEAT_NUM FROM Students WHERE {field} LIKE %s"
            cur.execute(sql, (f"%{q}%",))
        rows = cur.fetchall()
        data = rows_to_dicts(cur, rows)
        cur.close()
        conn.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/course/<course_id>/assessments', methods=['GET'])
def get_course_assessments(course_id):
    try:
        conn = get_mysql_connection()
        cur = conn.cursor()
        cur.execute("SELECT AST_ID, COURSE_ID, AST_NAME, WEIGHT FROM Assessments WHERE COURSE_ID = %s", (course_id,))
        rows = cur.fetchall()
        data = rows_to_dicts(cur, rows)
        cur.close()
        conn.close()
        return jsonify(data), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/course/<course_id>/assessments/<ast_id>', methods=['PATCH'])
def update_assessment_weight(course_id, ast_id):
    try:
        payload = request.get_json(silent=True) or {}
        if 'weight' not in payload:
            return jsonify({'error': 'weight is required'}), 400
        try:
            weight = float(payload.get('weight'))
        except:
            return jsonify({'error': 'invalid weight'}), 400
        if weight < 0 or weight > 1:
            return jsonify({'error': 'weight must be between 0 and 1'}), 400

        conn = get_mysql_connection()
        cur = conn.cursor()
        conn.start_transaction()

        # 確認該評量存在於此課程
        cur.execute("SELECT AST_ID FROM Assessments WHERE AST_ID = %s AND COURSE_ID = %s", (ast_id, course_id))
        if cur.fetchone() is None:
            cur.close()
            conn.close()
            return jsonify({'error': 'assessment not found for this course'}), 404

        # 先取得所有評量的當前權重
        cur.execute("SELECT AST_ID, WEIGHT FROM Assessments WHERE COURSE_ID = %s", (course_id,))
        rows = cur.fetchall()
        items = [(r[0], float(r[1]) if r[1] is not None else 0.0) for r in rows]
        ast_ids = [it[0] for it in items]

        if ast_id not in ast_ids:
            cur.close()
            conn.close()
            return jsonify({'error': 'assessment not found for this course'}), 404

        # 設定目標評量為使用者輸入的權重
        remaining = 1.0 - weight
        other_sum = sum(w for aid, w in items if aid != ast_id)

        if other_sum <= 0:
            other_ids = [aid for aid, _ in items if aid != ast_id]
            n = len(other_ids)
            for aid in other_ids:
                new_w = (remaining / n) if n > 0 else 0.0
                cur.execute("UPDATE Assessments SET WEIGHT = %s WHERE AST_ID = %s AND COURSE_ID = %s", (new_w, aid, course_id))
            cur.execute("UPDATE Assessments SET WEIGHT = %s WHERE AST_ID = %s AND COURSE_ID = %s", (weight, ast_id, course_id))
        else:
            # 先把目標設為使用者輸入，再按比例縮放其他項目
            cur.execute("UPDATE Assessments SET WEIGHT = %s WHERE AST_ID = %s AND COURSE_ID = %s", (weight, ast_id, course_id))
            for aid, w in items:
                if aid == ast_id:
                    continue
                new_w = (w / other_sum) * remaining
                cur.execute("UPDATE Assessments SET WEIGHT = %s WHERE AST_ID = %s AND COURSE_ID = %s", (new_w, aid, course_id))

        # 強制正規化：重新讀取所有權重，若總和不等於 1 則按比例調整（或全部為 0 時平均分配）
        cur.execute("SELECT AST_ID, WEIGHT FROM Assessments WHERE COURSE_ID = %s", (course_id,))
        updated_rows_tmp = cur.fetchall()
        tmp_items = [(r[0], float(r[1]) if r[1] is not None else 0.0) for r in updated_rows_tmp]
        total = sum(w for _, w in tmp_items)

        if abs(total - 1.0) > 1e-9:
            if total == 0:
                # 全部為 0，平均分配
                n = len(tmp_items)
                for aid, _ in tmp_items:
                    cur.execute("UPDATE Assessments SET WEIGHT = %s WHERE AST_ID = %s AND COURSE_ID = %s", ((1.0 / n) if n>0 else 0.0, aid, course_id))
            else:
                factor = 1.0 / total
                for aid, w in tmp_items:
                    new_w = w * factor
                    cur.execute("UPDATE Assessments SET WEIGHT = %s WHERE AST_ID = %s AND COURSE_ID = %s", (new_w, aid, course_id))

        # 最後讀取並回傳正規化後的清單
        cur.execute("SELECT AST_ID, AST_NAME, WEIGHT FROM Assessments WHERE COURSE_ID = %s", (course_id,))
        final_rows = cur.fetchall()
        data = rows_to_dicts(cur, final_rows)
        total_after = sum([float(d.get('WEIGHT') or 0) for d in data])

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'ok': True, 'updated': True, 'total_weight': float(total_after), 'assessments': data}), 200
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        return jsonify({'error': str(e)}), 500

@app.route('/api/course/<course_id>/scores', methods=['POST'])
def save_course_scores(course_id):
    """接收 JSON 陣列，每個 item 包含 STU_ID, AST_ID, SCORE，選擇性包含 SCORE_ID。
    會驗證 AST_ID 是否屬於 course_id，並對成績做更新或新增（upsert）。
    回傳已新增與已更新的筆數。
    """
    try:
        data = request.get_json(silent=True)
        if not isinstance(data, list):
            return jsonify({'error': 'expected a JSON array'}), 400

        conn = get_mysql_connection()
        cur = conn.cursor()
        inserted = 0
        updated = 0

        for item in data:
            stu_id = item.get('STU_ID')
            ast_id = item.get('AST_ID')
            score_val = item.get('SCORE')
            score_id = item.get('SCORE_ID')
            if stu_id is None or ast_id is None or score_val is None:
                continue

            # 驗證該 AST_ID 是否屬於此課程
            cur.execute("SELECT AST_ID FROM Assessments WHERE AST_ID = %s AND COURSE_ID = %s", (ast_id, course_id))
            if cur.fetchone() is None:
                # skip 不屬於此課程的評量
                continue

            # 若提供 SCORE_ID，優先以其為主
            if score_id:
                cur.execute("SELECT SCORE_ID FROM Scores WHERE SCORE_ID = %s", (score_id,))
                if cur.fetchone():
                    cur.execute("UPDATE Scores SET SCORE = %s, STU_ID = %s, AST_ID = %s WHERE SCORE_ID = %s", (score_val, stu_id, ast_id, score_id))
                    updated += cur.rowcount
                else:
                    cur.execute("INSERT INTO Scores (SCORE_ID, STU_ID, AST_ID, SCORE) VALUES (%s, %s, %s, %s)", (score_id, stu_id, ast_id, score_val))
                    inserted += cur.rowcount
            else:
                # 以 (STU_ID, AST_ID) 嘗試更新，否則新增
                cur.execute("SELECT SCORE_ID FROM Scores WHERE STU_ID = %s AND AST_ID = %s", (stu_id, ast_id))
                row = cur.fetchone()
                if row:
                    cur.execute("UPDATE Scores SET SCORE = %s WHERE STU_ID = %s AND AST_ID = %s", (score_val, stu_id, ast_id))
                    updated += cur.rowcount
                else:
                    new_id = f"SC{int(time.time()*1000)}{random.randint(100,999)}"
                    cur.execute("INSERT INTO Scores (SCORE_ID, STU_ID, AST_ID, SCORE) VALUES (%s, %s, %s, %s)", (new_id, stu_id, ast_id, score_val))
                    inserted += cur.rowcount

        conn.commit()
        cur.close()
        conn.close()
        return jsonify({'ok': True, 'inserted': inserted, 'updated': updated}), 200
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        return jsonify({'error': str(e)}), 500

def convert_google_link(url):
    if not url:
        return url
    u = str(url).strip()
    # 移除周圍引號
    if (u.startswith('"') and u.endswith('"')) or (u.startswith("'") and u.endswith("'")):
        u = u[1:-1]
    # 先處理 drive open?id= 格式
    m = re.search(r'[?&]id=([a-zA-Z0-9_-]+)', u)
    if m:
        file_id = m.group(1)
        return f'https://drive.google.com/uc?export=download&id={file_id}'
    # 處理 /d/<id>/ 型式
    m2 = re.search(r'/d/([a-zA-Z0-9_-]+)', u)
    if m2:
        file_id = m2.group(1)
        if 'presentation' in u or 'slides' in u:
            return f'https://docs.google.com/presentation/d/{file_id}/preview'
        if 'document' in u:
            return f'https://docs.google.com/document/d/{file_id}/preview'
        if 'spreadsheets' in u or 'sheet' in u:
            return f'https://docs.google.com/spreadsheets/d/{file_id}/preview'
        # generic drive file
        return f'https://drive.google.com/uc?export=download&id={file_id}'
    # 若包含 /edit, 替換為 /preview 並去掉 query
    if 'docs.google.com' in u and '/edit' in u:
        u = u.split('/edit')[0] + '/preview'
        return u
    return url

@app.route('/api/upload', methods=['POST'])
def api_upload():
    """接受 multipart/form-data 的 CSV 上傳，支援 header-aware parsing。
    對 portfolios 支援多種 CSV 格式（包含短格式：STU_ID,AST_ID,TITLE,FILE_URL,UPLOAD_DATE），
    若 PORTFO_ID 或 COURSE_ID 缺少可自動補 (PORTFO_ID 會自動產生，COURSE_ID 可由 form 傳入 course_id)。
    """
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'no file part'}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'no selected file'}), 400
        ftype = (request.form.get('type') or '').lower()
        course_id_override = request.form.get('course_id')
        allowed = {'students','courses','enrollments','assessments','scores','portfolios'}
        if ftype not in allowed:
            return jsonify({'error': 'invalid type parameter'}), 400

        stream = io.TextIOWrapper(file.stream, encoding='utf-8-sig')

        # SQL 與期望欄位對應（順序對應到 INSERT 中的欄位順序）
        cols_map = {
            'students': ['STU_ID','STU_NAME','CLASS_NAME','SEAT_NUM'],
            'courses': ['COURSE_ID','COURSE_NAME','SEMESTER'],
            'enrollments': ['ENROLL_ID','STU_ID','COURSE_ID'],
            'assessments': ['AST_ID','COURSE_ID','AST_NAME','CATEGORY','WEIGHT'],
            'scores': ['SCORE_ID','STU_ID','AST_ID','SCORE'],
            'portfolios': ['PORTFO_ID','STU_ID','COURSE_ID','AST_ID','TITLE','UPLOAD_DATE','FILE_URL']
        }
        sql_map = {
            'students': "INSERT IGNORE INTO Students (STU_ID, STU_NAME, CLASS_NAME, SEAT_NUM) VALUES (%s, %s, %s, %s)",
            'courses': "INSERT IGNORE INTO Courses (COURSE_ID, COURSE_NAME, SEMESTER) VALUES (%s, %s, %s)",
            'enrollments': "INSERT IGNORE INTO Enrollments (ENROLL_ID, STU_ID, COURSE_ID) VALUES (%s, %s, %s)",
            'assessments': "INSERT IGNORE INTO Assessments (AST_ID, COURSE_ID, AST_NAME, CATEGORY, WEIGHT) VALUES (%s, %s, %s, %s, %s)",
            'scores': "INSERT IGNORE INTO Scores (SCORE_ID, STU_ID, AST_ID, SCORE) VALUES (%s, %s, %s, %s)",
            # 使用 upsert：若 PORTFO_ID 已存在則更新欄位，否則插入新筆
            'portfolios': (
                "INSERT INTO Portfolios (PORTFO_ID, STU_ID, COURSE_ID, AST_ID, TITLE, UPLOAD_DATE, FILE_URL) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "STU_ID=VALUES(STU_ID), COURSE_ID=VALUES(COURSE_ID), AST_ID=VALUES(AST_ID), "
                "TITLE=VALUES(TITLE), UPLOAD_DATE=VALUES(UPLOAD_DATE), FILE_URL=VALUES(FILE_URL)"
            )
        }

        expected_cols = cols_map[ftype]
        sql = sql_map[ftype]

        # 使用 generator 逐列解析 CSV，避免一次把所有資料讀入記憶體
        def get_clean_lines():
            """從 stream 產生不含註解 (以 // 開頭) 與空白行的行供 csv 使用。"""
            stream.seek(0)
            for raw in stream:
                if raw is None:
                    continue
                line = raw
                if line.strip() == '':
                    continue
                if line.lstrip().startswith('//'):
                    continue
                yield line

        # 驗證 CSV 表頭是否符合 SQL 要求
        try:
            clean_lines = get_clean_lines()
            first_line = next(clean_lines, None)
            if not first_line:
                return jsonify({'error': '格式錯誤：上傳的檔案為空！'}), 400
            
            reader = csv.reader([first_line])
            header_row = next(reader, None)
            if not header_row:
                return jsonify({'error': '格式錯誤：無法讀取 CSV 表頭！'}), 400

            csv_headers_normalized = {h.strip().lower().replace(' ', '').replace('_', '') for h in header_row if h}
            required_cols_map = {
                'students': {'stuid', 'stuname', 'classname', 'seatnum'},
                'courses': {'courseid', 'coursename', 'semester'},
                'enrollments': {'enrollid', 'stuid', 'courseid'},
                'assessments': {'astid', 'courseid', 'astname', 'category', 'weight'},
                'scores': {'scoreid', 'stuid', 'astid', 'score'},
                'portfolios': {'stuid', 'astid', 'title', 'uploaddate', 'fileurl'}
            }
            req = required_cols_map.get(ftype, set())
            missing = req - csv_headers_normalized
            if missing:
                col_name_mapping = {
                    'stuid': 'STU_ID', 'stuname': 'STU_NAME', 'classname': 'CLASS_NAME', 'seatnum': 'SEAT_NUM',
                    'courseid': 'COURSE_ID', 'coursename': 'COURSE_NAME', 'semester': 'SEMESTER',
                    'enrollid': 'ENROLL_ID', 'astid': 'AST_ID', 'astname': 'AST_NAME', 'category': 'CATEGORY',
                    'weight': 'WEIGHT', 'scoreid': 'SCORE_ID', 'score': 'SCORE', 'title': 'TITLE',
                    'uploaddate': 'UPLOAD_DATE', 'fileurl': 'FILE_URL'
                }
                missing_names = [col_name_mapping.get(m, m.upper()) for m in missing]
                return jsonify({'error': f'格式錯誤：上傳的 CSV 缺少必要的欄位：{", ".join(missing_names)}'}), 400
        except Exception as e:
            return jsonify({'error': f'格式錯誤：剖析表頭失敗。{str(e)}'}), 400


        def records_generator():
            # 先用 get_clean_lines() 來過濾註解/空行
            try:
                dict_reader = csv.DictReader(get_clean_lines())
                header = dict_reader.fieldnames
                use_dict = bool(header and any(h and h.strip() for h in header))
            except Exception:
                use_dict = False

            if use_dict:
                for row in dict_reader:
                    if not any((v and str(v).strip()) for v in row.values()):
                        continue
                    norm = {k.strip().lower().replace(' ', '').replace('_',''): (v if v is not None else '') for k,v in row.items()}
                    def get_val(col_name):
                        keys = [col_name, col_name.lower(), col_name.lower().replace('_',''), col_name.lower().replace('_','').replace(' ', '')]
                        for k in keys:
                            nk = k.strip().lower().replace(' ', '').replace('_','')
                            if nk in norm and norm[nk] != '':
                                return norm[nk]
                        return None

                    if ftype == 'portfolios':
                        vals = []
                        for col in expected_cols:
                            v = get_val(col)
                            if col == 'PORTFO_ID' and not v:
                                v = f"PF{int(time.time()*1000)}{random.randint(100,999)}"
                            if col == 'COURSE_ID' and not v and course_id_override:
                                v = course_id_override
                            vals.append(v)
                        # convert link
                        if len(vals) >= 7:
                            vals[6] = convert_google_link(vals[6])
                        yield tuple(vals)
                    else:
                        vals = []
                        for col in expected_cols:
                            vals.append(get_val(col))
                        yield tuple(vals)
            else:
                reader = csv.reader(get_clean_lines())
                # csv.reader 不需要再跳過 header，get_clean_lines 已經過濾掉註解
                next(reader, None)
                param_count = sql.count('%s')
                for row in reader:
                    if not any(row):
                        continue
                    processed = (row + [None] * param_count)[:param_count]
                    processed = [None if str(v).strip() == '' else v for v in processed]
                    if ftype == 'portfolios' and len(processed) == 5:
                        portfo_id = f"PF{int(time.time()*1000)}{random.randint(100,999)}"
                        course_id = course_id_override or None
                        ast_id = processed[1]
                        title = processed[2]
                        file_url = convert_google_link(processed[3])
                        upload_date = processed[4]
                        yield (portfo_id, processed[0], course_id, ast_id, title, upload_date, file_url)
                    else:
                        if ftype == 'portfolios' and len(processed) >= 7:
                            processed[6] = convert_google_link(processed[6])
                        yield tuple(processed)

        table_map = {
            'students': 'Students',
            'courses': 'Courses',
            'enrollments': 'Enrollments',
            'assessments': 'Assessments',
            'scores': 'Scores',
            'portfolios': 'Portfolios'
        }
        table_name = table_map.get(ftype)

        # 實際分批寫入資料庫
        conn = get_mysql_connection()
        cur = conn.cursor()

        # 支援 debug/preview 模式：若傳入 debug=1，僅解析並回傳前 20 筆結果，不寫入資料庫
        debug_flag = (request.form.get('debug') == '1') or (request.args.get('debug') == '1')
        if debug_flag:
            samples = []
            gen = records_generator()
            for i, rec in enumerate(gen):
                if i >= 20:
                    break
                # 將 tuple 轉成可 JSON 化的 list
                samples.append([None if v is None else v for v in rec])
            cur.close()
            conn.close()
            return jsonify({'preview_count': len(samples), 'samples': samples}), 200

        # 查詢寫入前的總數
        count_before = 0
        if table_name:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                count_before = cur.fetchone()[0]
            except:
                pass

        # 讀取所有待寫入的紀錄
        records = list(records_generator())
        total_uploaded = len(records)

        # 分批執行寫入
        chunk_size = 500
        for i in range(0, len(records), chunk_size):
            chunk = records[i:i+chunk_size]
            cur.executemany(sql, chunk)
        conn.commit()

        # 查詢寫入後的總數
        count_after = count_before
        if table_name:
            try:
                cur.execute(f"SELECT COUNT(*) FROM {table_name}")
                count_after = cur.fetchone()[0]
            except:
                pass

        new_inserted = max(0, count_after - count_before)
        duplicates = max(0, total_uploaded - new_inserted)

        cur.close()
        conn.close()

        # 回傳包含詳細上傳統計資訊的訊息
        msg = f"匯入完成！上傳資料共 {total_uploaded} 筆，成功新增 {new_inserted} 筆，重複/忽略 {duplicates} 筆。"
        return jsonify({
            'message': msg,
            'total_uploaded': total_uploaded,
            'new_inserted': new_inserted,
            'duplicates': duplicates
        }), 200
    except Exception as e:
        try:
            conn.rollback()
        except:
            pass
        return jsonify({'error': str(e)}), 500

def executemany_in_chunks(conn, cur, sql, records_iter, chunk_size=500):
    total = 0
    chunk = []
    for rec in records_iter:
        chunk.append(rec)
        if len(chunk) >= chunk_size:
            cur.executemany(sql, chunk)
            conn.commit()
            total += cur.rowcount
            chunk = []
    if chunk:
        cur.executemany(sql, chunk)
        conn.commit()
        total += cur.rowcount
    return total


if __name__ == '__main__':
    # 本機啟動：預設使用 .env 的 PORT，host 預設為 127.0.0.1
    port = int(os.getenv('PORT', 5000))
    host = os.getenv('HOST', '127.0.0.1')

    # 若需要初始化資料庫（開發時偶爾使用），可在啟動前設定 INIT_DB=1
    if os.environ.get('INIT_DB', '0') == '1':
        print('INIT_DB=1 -> 初始化資料庫（從 CSV 匯入）')
        init_db_from_csv_mysql()

    print(f"啟動本機伺服器：http://{host}:{port}")
    app.run(host=host, port=port, debug=True)
