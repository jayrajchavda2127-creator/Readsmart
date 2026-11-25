import pymysql

conn = pymysql.connect(host='localhost', user='root', password='', database='readsmart')
cursor = conn.cursor()

alters = [
    "ALTER TABLE books ADD COLUMN description TEXT NULL",
    "ALTER TABLE books ADD COLUMN category VARCHAR(100) NULL DEFAULT 'General'",
    "ALTER TABLE books ADD COLUMN author VARCHAR(255) NULL",
    "ALTER TABLE reviews ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY FIRST",
    "ALTER TABLE reviews ADD COLUMN book_id INT NULL",
    "ALTER TABLE reviews ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP",
    "ALTER TABLE user_activity ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY FIRST",
    "ALTER TABLE user_activity MODIFY activity_type VARCHAR(100) NOT NULL",
    "ALTER TABLE user_activity MODIFY user_id INT NOT NULL",
]

for sql in alters:
    try:
        cursor.execute(sql)
        print('OK:', sql[:70])
    except Exception as e:
        print('SKIP:', str(e)[:90])

conn.commit()
conn.close()
print('\nMigration complete.')
