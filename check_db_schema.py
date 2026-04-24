import sqlite3
import sys

conn = sqlite3.connect('data/market_radar.db')
cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [row[0] for row in cursor.fetchall()]

with open('db_tables.txt', 'w', encoding='utf-8') as f:
    f.write(f'Total tables: {len(tables)}\n\n')
    for t in tables:
        f.write(f'- {t}\n')
        
        # Get schema
        cursor2 = conn.execute(f"PRAGMA table_info({t})")
        cols = cursor2.fetchall()
        for col in cols:
            f.write(f'    {col[1]} ({col[2]})\n')
        f.write('\n')

print(f"Schema written to db_tables.txt ({len(tables)} tables)")
