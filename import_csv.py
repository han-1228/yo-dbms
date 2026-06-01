import os
import csv
import mysql.connector
from dotenv import load_dotenv
import time
import random

# 載入環境變數
load_dotenv()

def get_aiven_connection():
    return mysql.connector.connect(
        host='mysql-1af924e-yo-dbms.i.aivencloud.com',
        port=25889,
        user='avnadmin',
        password='my_password',  # 🌟 這裡改成等號 (=) 的假密碼即可
        database='schoolsystemdb',
        ssl_ca='ca.pem'
    )

def import_csv_to_table(cursor, table_name, file_path, sql_query, course_id_override=None):
    print(f"正在匯入 {table_name}...")
    if not os.path.exists(file_path):
        print(f"❌ 找不到檔案：{file_path}，跳過此表。")
        return

    param_count = sql_query.count('%s')

    try:
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            # 嘗試 header-aware
            try:
                reader = csv.DictReader(f)
                header = reader.fieldnames
                use_dict = bool(header and any(h and h.strip() for h in header))
            except Exception:
                use_dict = False
                f.seek(0)

            records = []
            if use_dict:
                expected = None
                if table_name.lower() == 'portfolios':
                    expected = ['PORTFO_ID','STU_ID','COURSE_ID','AST_ID','TITLE','UPLOAD_DATE','FILE_URL']
                elif table_name.lower() == 'students':
                    expected = ['STU_ID','STU_NAME','CLASS_NAME','SEAT_NUM']
                elif table_name.lower() == 'courses':
                    expected = ['COURSE_ID','COURSE_NAME','SEMESTER']
                elif table_name.lower() == 'enrollments':
                    expected = ['ENROLL_ID','STU_ID','COURSE_ID']
                elif table_name.lower() == 'assessments':
                    expected = ['AST_ID','COURSE_ID','AST_NAME','CATEGORY','WEIGHT']
                elif table_name.lower() == 'scores':
                    expected = ['SCORE_ID','STU_ID','AST_ID','SCORE']

                for row in reader:
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

                    if table_name.lower() == 'portfolios':
                        vals = []
                        for col in expected:
                            v = get_val(col)
                            if col == 'PORTFO_ID' and not v:
                                v = f"PF{int(time.time()*1000)}{random.randint(100,999)}"
                            if col == 'COURSE_ID' and not v and course_id_override:
                                v = course_id_override
                            vals.append(v)
                        records.append(tuple(vals))
                    else:
                        vals = []
                        for col in expected:
                            vals.append(get_val(col))
                        records.append(tuple(vals))
            else:
                f.seek(0)
                reader = csv.reader(f)
                next(reader, None)
                for row in reader:
                    if not any(row):
                        continue
                    processed = (row + [None] * param_count)[:param_count]
                    processed = [None if str(val).strip() == '' else val for val in processed]
                    if table_name.lower() == 'portfolios' and len(processed) == 5:
                        # 假設格式：STU_ID, AST_ID, TITLE, FILE_URL, UPLOAD_DATE
                        portfo_id = f"PF{int(time.time()*1000)}{random.randint(100,999)}"
                        course_id = course_id_override or None
                        ast_id = processed[1]
                        title = processed[2]
                        file_url = processed[3]
                        upload_date = processed[4]
                        records.append((portfo_id, processed[0], course_id, ast_id, title, upload_date, file_url))
                    else:
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

def main():
    try:
        conn = get_aiven_connection()
        cursor = conn.cursor()
        print("⚡ 成功連線至 Aiven 雲端資料庫！開始按順序寫入資料...\n")
        
        # -------------------------------------------------------------
        # 嚴格遵守外鍵約束順序限制
        # -------------------------------------------------------------
        
        # 1. 學生表 (主表)
        import_csv_to_table(
            cursor, "Students", "1.students.csv",
            "INSERT IGNORE INTO Students (STU_ID, STU_NAME, CLASS_NAME, SEAT_NUM) VALUES (%s, %s, %s, %s)"
        )

        # 2. 課程表 (主表)
        import_csv_to_table(
            cursor, "Courses", "2.courses.csv",
            "INSERT IGNORE INTO Courses (COURSE_ID, COURSE_NAME, SEMESTER) VALUES (%s, %s, %s)"
        )

        # 3. 修課表 (從表，依賴學生與課程)
        import_csv_to_table(
            cursor, "Enrollments", "3.enrollments.csv",
            "INSERT IGNORE INTO Enrollments (ENROLL_ID, STU_ID, COURSE_ID) VALUES (%s, %s, %s)"
        )

        # 4. 評量項目表 (從表，依賴課程)
        import_csv_to_table(
            cursor, "Assessments", "4.assessments.csv",
            "INSERT IGNORE INTO Assessments (AST_ID, COURSE_ID, AST_NAME, CATEGORY, WEIGHT) VALUES (%s, %s, %s, %s, %s)"
        )

        # 5. 成績表 (從表，依賴學生與評量)
        import_csv_to_table(
            cursor, "Scores", "5.scores.csv",
            "INSERT IGNORE INTO Scores (SCORE_ID, STU_ID, AST_ID, SCORE) VALUES (%s, %s, %s, %s)"
        )

        # 6. 學生作品表 (從表，依賴學生、課程與評量)
        import_csv_to_table(
            cursor, "Portfolios", "6.portfolios.csv",
            "INSERT IGNORE INTO Portfolios (PORTFO_ID, STU_ID, COURSE_ID, AST_ID, TITLE, UPLOAD_DATE, FILE_URL) VALUES (%s, %s, %s, %s, %s, %s, %s)"
        )

        # 若 Assessments 的 WEIGHT 被當成百分比儲存（>1），轉換為小數並按課程正規化
        try:
            cursor.execute("SELECT COUNT(*) FROM Assessments WHERE WEIGHT > 1")
            cnt_row = cursor.fetchone()
            cnt = cnt_row[0] if cnt_row else 0
            if cnt and cnt > 0:
                print(f"發現 {cnt} 筆 Assessments.WEIGHT > 1，將視為百分比並除以 100 轉為小數...")
                cursor.execute("UPDATE Assessments SET WEIGHT = WEIGHT / 100.0 WHERE WEIGHT > 1")
                cursor.execute("SELECT COURSE_ID, SUM(WEIGHT) FROM Assessments GROUP BY COURSE_ID")
                sums = cursor.fetchall()
                for row in sums:
                    course_id = row[0]
                    s = float(row[1]) if row[1] is not None else 0.0
                    if s > 0 and abs(s - 1.0) > 1e-9:
                        factor = 1.0 / s
                        cursor.execute("UPDATE Assessments SET WEIGHT = WEIGHT * %s WHERE COURSE_ID = %s", (factor, course_id))
                print('完成百分比轉換與按課程正規化。')
        except Exception as e:
            print('在轉換 Assessments 權重時發生錯誤:', e)

        # 提交所有變更
        conn.commit()
        print("\n🎉 所有資料皆已順利匯入 Aiven 雲端資料庫！")

    except mysql.connector.Error as e:
        print(f"連線失敗或發生重大錯誤: {e}")
    finally:
        if 'conn' in locals() and conn.is_connected():
            cursor.close()
            conn.close()
            print("🔌 資料庫連線已安全關閉。")

if __name__ == "__main__":
    main()
