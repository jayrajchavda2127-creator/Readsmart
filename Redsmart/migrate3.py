import pymysql

conn = pymysql.connect(host='localhost', user='root', password='', database='readsmart')
cursor = conn.cursor()

# ── Fix user_activity ──
# Back up data, drop, recreate with id column, restore
try:
    cursor.execute("SELECT user_id, activity_type, description, created_at FROM user_activity")
    ua_rows = cursor.fetchall()
    print(f"Backed up {len(ua_rows)} user_activity rows")

    cursor.execute("SET FOREIGN_KEY_CHECKS=0")
    cursor.execute("DROP TABLE IF EXISTS user_activity")
    cursor.execute("""
        CREATE TABLE user_activity (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            activity_type VARCHAR(100) NOT NULL,
            description TEXT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    """)
    print("user_activity recreated")

    for row in ua_rows:
        cursor.execute(
            "INSERT INTO user_activity (user_id, activity_type, description, created_at) VALUES (%s, %s, %s, %s)",
            row
        )
    print(f"Restored {len(ua_rows)} rows into user_activity")
except Exception as e:
    print("ERROR user_activity:", e)

# ── Fix reviews ──
try:
    cursor.execute("SELECT user_id, book_title, review_text, rating, book_id, created_at FROM reviews")
    rev_rows = cursor.fetchall()
    print(f"Backed up {len(rev_rows)} reviews rows")

    cursor.execute("DROP TABLE IF EXISTS reviews")
    cursor.execute("""
        CREATE TABLE reviews (
            id INT AUTO_INCREMENT PRIMARY KEY,
            user_id INT NOT NULL,
            book_id INT NULL,
            book_title VARCHAR(255) NULL,
            review_text TEXT NOT NULL,
            rating INT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id),
            FOREIGN KEY (book_id) REFERENCES books(id)
        )
    """)
    print("reviews recreated")

    for row in rev_rows:
        cursor.execute(
            "INSERT INTO reviews (user_id, book_title, review_text, rating, book_id, created_at) VALUES (%s, %s, %s, %s, %s, %s)",
            row
        )
    print(f"Restored {len(rev_rows)} rows into reviews")
except Exception as e:
    print("ERROR reviews:", e)

cursor.execute("SET FOREIGN_KEY_CHECKS=1")
conn.commit()
conn.close()
print("\nAll done.")
