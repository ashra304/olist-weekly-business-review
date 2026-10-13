import sqlite3
from pathlib import Path

db_path = Path("olist.db")
sql_folder = Path("sql/analytics")

conn = sqlite3.connect(db_path)

sql_files = sorted(sql_folder.glob("*.sql"))

if not sql_files:
    print("ERROR: No SQL files found in sql/analytics/")
else:
    for file in sql_files:
        print("\n" + "=" * 60)
        print("QUERY:", file.name)
        print("=" * 60)

        try:
            query = file.read_text(encoding="utf-8")
            cursor = conn.execute(query)

            columns = [column[0] for column in cursor.description]
            print("Columns:", columns)

            rows = cursor.fetchmany(12)

            if rows:
                for row in rows:
                    print(row)
            else:
                print("Query executed successfully. No rows returned.")

        except Exception as error:
            print("ERROR:", error)

conn.close()