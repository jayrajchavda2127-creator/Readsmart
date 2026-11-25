import pymysql

conn = pymysql.connect(host='localhost', user='root', password='', database='readsmart')
cursor = conn.cursor()

# Check current columns in user_activity
cursor.execute("DESCRIBE user_activity")
cols = [row[0] for row in cursor.fetchall()]
print("user_activity columns:", cols)

alters = []

if 'id' not in cols:
    # Need to add id as auto_increment primary key
    # First drop existing PK if any
    alters.append("ALTER TABLE user_activity DROP PRIMARY KEY")
    alters.append("ALTER TABLE user_activity ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY FIRST")

if 'created_at' not in cols:
    alters.append("ALTER TABLE user_activity ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")

for sql in alters:
    try:
        cursor.execute(sql)
        print('OK:', sql[:80])
    except Exception as e:
        print('SKIP:', str(e)[:100])

conn.commit()

# Also check reviews table
cursor.execute("DESCRIBE reviews")
rev_cols = [row[0] for row in cursor.fetchall()]
print("reviews columns:", rev_cols)

rev_alters = []
if 'id' not in rev_cols:
    rev_alters.append("ALTER TABLE reviews DROP PRIMARY KEY")
    rev_alters.append("ALTER TABLE reviews ADD COLUMN id INT AUTO_INCREMENT PRIMARY KEY FIRST")
if 'book_id' not in rev_cols:
    rev_alters.append("ALTER TABLE reviews ADD COLUMN book_id INT NULL")
if 'created_at' not in rev_cols:
    rev_alters.append("ALTER TABLE reviews ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP")

for sql in rev_alters:
    try:
        cursor.execute(sql)
        print('OK:', sql[:80])
    except Exception as e:
        print('SKIP:', str(e)[:100])

conn.commit()
conn.close()
print('\nDone.')
