import os
from dotenv import load_dotenv

# 告訴 Python 不要去找預設的 .env，去抓我的 data.env！
load_dotenv('data.env')

from flask import Flask, jsonify, request
from flask_cors import CORS
import mysql.connector
from mysql.connector import Error

import csv
import io

app = Flask(__name__)
CORS(app)

db_config = {
    'host': 'mysql-1af924e-yo-dbms.i.aivencloud.com',
    'port': 25889,
    'user': 'avnadmin',
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


def init_db_from_csv():
    conn = get_db_connection()
    if not conn:
        print("⚠️ 無法建立資料庫連線，略過初始匯入。")
        return
    cursor = conn.cursor()

    # 逐一建立表格（使用 MySQL 語法與 InnoDB 以支援外鍵）
    create_stmts = [
        """
        CREATE TABLE IF NOT EXISTS Students (
            STU_ID VARCHAR(50) PRIMARY KEY,
            STU_NAME VARCHAR(200),
            CLASS_NAME VARCHAR(100),
            SEAT_NUM INT
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS Courses (
            COURSE_ID VARCHAR(50) PRIMARY KEY,
            COURSE_NAME VARCHAR(300),
            SEMESTER VARCHAR(50)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS Enrollments (
            ENROLL_ID VARCHAR(50) PRIMARY KEY,
            STU_ID VARCHAR(50),
            COURSE_ID VARCHAR(50),
            FOREIGN KEY (STU_ID) REFERENCES Students(STU_ID),
            FOREIGN KEY (COURSE_ID) REFERENCES Courses(COURSE_ID)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS Assessments (
            AST_ID VARCHAR(50) PRIMARY KEY,
            COURSE_ID VARCHAR(50),
            AST_NAME VARCHAR(300),
            CATEGORY VARCHAR(100),
            WEIGHT INT,
            FOREIGN KEY (COURSE_ID) REFERENCES Courses(COURSE_ID)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS Scores (
            SCORE_ID VARCHAR(50) PRIMARY KEY,
            STU_ID VARCHAR(50),
            AST_ID VARCHAR(50),
            SCORE DECIMAL(8,2),
            FOREIGN KEY (STU_ID) REFERENCES Students(STU_ID),
            FOREIGN KEY (AST_ID) REFERENCES Assessments(AST_ID)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
        """
        CREATE TABLE IF NOT EXISTS Portfolios (
            PORT_ID VARCHAR(50) PRIMARY KEY,
            STU_ID VARCHAR(50),
            COURSE_ID VARCHAR(50),
            PORT_NAME VARCHAR(300),
            PORT_LINK VARCHAR(1000),
            UPLOAD_DATE VARCHAR(50),
            FOREIGN KEY (STU_ID) REFERENCES Students(STU_ID),
            FOREIGN KEY (COURSE_ID) REFERENCES Courses(COURSE_ID)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
    ]

    try:
        for stmt in create_stmts:
            cursor.execute(stmt)

        files_to_import = {
            'students.csv': ("INSERT IGNORE INTO Students (STU_ID, STU_NAME, CLASS_NAME, SEAT_NUM) VALUES (%s, %s, %s, %s)", [3]),
            'courses.csv': ("INSERT IGNORE INTO Courses (COURSE_ID, COURSE_NAME, SEMESTER) VALUES (%s, %s, %s)", [2]),
            'enrollments.csv': ("INSERT IGNORE INTO Enrollments (ENROLL_ID, STU_ID, COURSE_ID) VALUES (%s, %s, %s)", [2]),
            'assessments.csv': ("INSERT IGNORE INTO Assessments (AST_ID, COURSE_ID, AST_NAME, CATEGORY, WEIGHT) VALUES (%s, %s, %s, %s, %s)", [4]),
            'scores.csv': ("INSERT IGNORE INTO Scores (SCORE_ID, STU_ID, AST_ID, SCORE) VALUES (%s, %s, %s, %s)", [3]),
            'portfolios.csv': ("INSERT IGNORE INTO Portfolios (PORT_ID, STU_ID, COURSE_ID, PORT_NAME, PORT_LINK, UPLOAD_DATE) VALUES (%s, %s, %s, %s, %s, %s)", [5])
        }

        for filename, (query, idxs) in files_to_import.items():
            if os.path.exists(filename):
                with open(filename, 'r', encoding='utf-8-sig') as f:
                    reader = csv.reader(f)
                    next(reader, None)
                    params = []
                    for row in reader:
                        if not any([str(cell).strip() for cell in row]):
                            continue
                        # 補足到需要的欄位數
                        param_count = query.count('%s')
                        r = (row + [None] * param_count)[:param_count]
                        # 轉換空字串為 None
                        r = [None if (str(c).strip() == '') else c for c in r]
                        # 嘗試對某些索引欄位轉成數字（若可能）
                        for i in range(len(r)):
                            if r[i] is not None and isinstance(r[i], str) and r[i].strip().isdigit():
                                # 盡量轉成 int
                                try:
                                    r[i] = int(r[i])
                                except Exception:
                                    pass
                        params.append(tuple(r))
                    if params:
                        cursor.executemany(query, params)
                        print(f"匯入 {filename} 完成，新增/略過 {cursor.rowcount} 筆（視情況）。")
        conn.commit()
        print("🎉 初始 CSV 匯入完成。")
    except Exception as e:
        print(f"初始化時發生錯誤: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


# 只在啟動時嘗試初始匯入
init_db_from_csv()


@app.route('/', methods=['GET'])
def home():
    return jsonify({"message": "API 伺服器正常運作中！"}), 200


@app.route('/api/students', methods=['GET'])
def get_students():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "無法連線資料庫"}), 500
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT STU_ID, STU_NAME, CLASS_NAME, SEAT_NUM FROM Students")
        rows = cur.fetchall()
        return jsonify(rows), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/api/courses', methods=['GET'])
def get_courses():
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "無法連線資料庫"}), 500
    cur = conn.cursor(dictionary=True)
    try:
        cur.execute("SELECT COURSE_ID, COURSE_NAME, SEMESTER FROM Courses")
        rows = cur.fetchall()
        return jsonify(rows), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/api/course/<course_id>/roster', methods=['GET'])
def get_course_roster(course_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "無法連線資料庫"}), 500
    cur = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT s.STU_ID, s.STU_NAME, s.CLASS_NAME, s.SEAT_NUM
            FROM Students s
            JOIN Enrollments e ON s.STU_ID = e.STU_ID
            WHERE e.COURSE_ID = %s
        """
        cur.execute(query, (course_id,))
        rows = cur.fetchall()
        return jsonify(rows), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/api/course/<course_id>/scores', methods=['GET'])
def get_course_scores(course_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "無法連線資料庫"}), 500
    cur = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT s.STU_ID, s.CLASS_NAME, s.SEAT_NUM, s.STU_NAME, a.AST_NAME, sc.SCORE
            FROM Scores sc
            JOIN Students s ON sc.STU_ID = s.STU_ID
            JOIN Assessments a ON sc.AST_ID = a.AST_ID
            WHERE a.COURSE_ID = %s
        """
        cur.execute(query, (course_id,))
        rows = cur.fetchall()
        return jsonify(rows), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/api/course/<course_id>/portfolios', methods=['GET'])
def get_course_portfolios(course_id):
    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "無法連線資料庫"}), 500
    cur = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT s.CLASS_NAME, s.SEAT_NUM, s.STU_NAME, p.PORT_NAME, p.PORT_LINK, p.UPLOAD_DATE
            FROM Portfolios p
            JOIN Students s ON p.STU_ID = s.STU_ID
            WHERE p.COURSE_ID = %s
        """
        cur.execute(query, (course_id,))
        rows = cur.fetchall()
        return jsonify(rows), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


@app.route('/api/upload', methods=['POST'])
def upload_csv():
    file = request.files.get('file')
    upload_type = (request.form.get('type') or '').lower()
    if not file:
        return jsonify({"error": "沒有上傳檔案"}), 400

    filename = file.filename or 'uploaded.csv'
    if upload_type in ('', 'unknown'):
        name_l = filename.lower()
        if 'student' in name_l: upload_type = 'students'
        elif 'course' in name_l: upload_type = 'courses'
        elif 'enroll' in name_l: upload_type = 'enrollments'
        elif 'assess' in name_l: upload_type = 'assessments'
        elif 'score' in name_l: upload_type = 'scores'
        elif 'port' in name_l: upload_type = 'portfolios'

    def rows_from_file(file_storage):
        text = io.TextIOWrapper(file_storage.stream, encoding='utf-8-sig', errors='ignore')
        reader = csv.reader(text)
        next(reader, None)
        for row in reader:
            if not any([str(cell).strip() for cell in row]):
                continue
            yield [None if (str(c).strip() == '') else c for c in row]

    conn = get_db_connection()
    if not conn:
        return jsonify({"error": "無法連線資料庫"}), 500
    cur = conn.cursor()
    inserted = 0
    try:
        if upload_type == 'students':
            q = "INSERT IGNORE INTO Students (STU_ID, STU_NAME, CLASS_NAME, SEAT_NUM) VALUES (%s, %s, %s, %s)"
            params = []
            for r in rows_from_file(file):
                r2 = (r + [None]*4)[:4]
                # convert seat num
                if r2[3] is not None:
                    try:
                        r2[3] = int(r2[3])
                    except:
                        r2[3] = None
                params.append(tuple(r2))
            if params: cur.executemany(q, params); inserted = cur.rowcount
        elif upload_type == 'courses':
            q = "INSERT IGNORE INTO Courses (COURSE_ID, COURSE_NAME, SEMESTER) VALUES (%s, %s, %s)"
            params = [tuple((r + [None]*3)[:3]) for r in rows_from_file(file)]
            if params: cur.executemany(q, params); inserted = cur.rowcount
        elif upload_type == 'enrollments':
            q = "INSERT IGNORE INTO Enrollments (ENROLL_ID, STU_ID, COURSE_ID) VALUES (%s, %s, %s)"
            params = [tuple((r + [None]*3)[:3]) for r in rows_from_file(file)]
            if params: cur.executemany(q, params); inserted = cur.rowcount
        elif upload_type == 'assessments':
            q = "INSERT IGNORE INTO Assessments (AST_ID, COURSE_ID, AST_NAME, CATEGORY, WEIGHT) VALUES (%s, %s, %s, %s, %s)"
            params = []
            for r in rows_from_file(file):
                r2 = (r + [None]*5)[:5]
                if r2[4] is not None:
                    try:
                        r2[4] = int(r2[4])
                    except:
                        r2[4] = None
                params.append(tuple(r2))
            if params: cur.executemany(q, params); inserted = cur.rowcount
        elif upload_type == 'scores':
            q = "INSERT IGNORE INTO Scores (SCORE_ID, STU_ID, AST_ID, SCORE) VALUES (%s, %s, %s, %s)"
            params = []
            for r in rows_from_file(file):
                r2 = (r + [None]*4)[:4]
                if r2[3] is not None:
                    try:
                        r2[3] = float(r2[3])
                    except:
                        r2[3] = None
                params.append(tuple(r2))
            if params: cur.executemany(q, params); inserted = cur.rowcount
        elif upload_type == 'portfolios':
            q = "INSERT IGNORE INTO Portfolios (PORT_ID, STU_ID, COURSE_ID, PORT_NAME, PORT_LINK, UPLOAD_DATE) VALUES (%s, %s, %s, %s, %s, %s)"
            params = [tuple((r + [None]*6)[:6]) for r in rows_from_file(file)]
            if params: cur.executemany(q, params); inserted = cur.rowcount
        else:
            return jsonify({"error": f"無法判定上傳類型: {upload_type}"}), 400

        conn.commit()
        return jsonify({"message": f"已匯入 {inserted} 筆資料至 {upload_type}."}), 200
    except Exception as e:
        conn.rollback()
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
        conn.close()


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get("PORT", 5000)))
