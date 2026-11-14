import os, sqlite3
p = "data/safarnama.db"
print("File maujood hai:", os.path.exists(p))
c = sqlite3.connect(p)
tables = [r[0] for r in c.execute("select name from sqlite_master where type='table'")]
print("Tables:", tables)
for t in tables:
    if t == "sqlite_sequence":
        continue
    print("\n---", t, "---")
    print("Columns:", [r[1] for r in c.execute(f"pragma table_info({t})")])
    for row in c.execute(f"select * from {t}"):
        print(row)
