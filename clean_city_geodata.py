import json
import sqlite3

with open("cities.json") as json_file:
    data = json.load(json_file)

names = []
for element in data["elements"]:
    if "tags" in element and "name" in element["tags"]:
        try:
            name = element["tags"]["name:sk"]
        except KeyError:
            name = element["tags"]["name"]
        names.append(name)


conn = sqlite3.connect("anna.db")
cursor = conn.cursor()

cursor.execute(
    """
    CREATE TABLE IF NOT EXISTS places (
        id INTEGER PRIMARY KEY,
        name TEXT UNIQUE,
        name_locative TEXT
    )
"""
)

for name in names:
    cursor.execute("INSERT OR IGNORE INTO places (name) VALUES (?)", (name,))

conn.commit()
conn.close()
