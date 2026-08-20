import sqlite3
import os

# Connect to your existing database
db_path = os.path.join("instance", "shophub.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

try:
    # Inject the two new columns
    cursor.execute("ALTER TABLE app_settings ADD COLUMN bg_image VARCHAR(255);")
    cursor.execute("ALTER TABLE app_settings ADD COLUMN bg_opacity FLOAT DEFAULT 0.05;")
    print("✅ Successfully updated the database! You can now use background images.")
except sqlite3.OperationalError as e:
    print(f"⚠️ Notice: {e} (The columns might already exist!)")

conn.commit()
conn.close()