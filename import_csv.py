import os
import csv
import mysql.connector
from dotenv import load_dotenv

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

def import_csv_to_table(cursor, table_name, file_path, sql_query):
    print(f"正在匯入 {table_name}...")
    if not os.path.exists(file_path):
        print(f"❌ 找不到檔案：{file_path}，跳過此表。")
        return

    # 🌟 升級版魔法：自動計算 SQL 語句中需要幾個欄位 (幾個 %s)
    param_count = sql_query.count('%s')

    try:
        with open(file_path, mode='r', encoding='utf-8-sig') as f:
            reader = csv.reader(f)
            next(reader)  # 跳過第一行標題
            
            records = []
            for row in reader:
                if not any(row): 
                    continue # 跳過完全空白的行
                
                # 🌟 防護網 1：如果 CSV 欄位太多就切掉，太少就用 None 補齊
                processed_row = (row + [None] * param_count)[:param_count]
                
                # 🌟 防護網 2：把 CSV 裡的空字串 '' 轉換成 None (資料庫的 NULL)，防止型態錯誤
                processed_row = [None if str(val).strip() == '' else val for val in processed_row]
                
                records.append(tuple(processed_row))
            
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
