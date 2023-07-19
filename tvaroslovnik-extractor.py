import asyncio
import aiohttp
from bs4 import BeautifulSoup
import sqlite3

offset_case = 5  # selects locative

conn = sqlite3.connect("anna.db")
cursor = conn.cursor()

word_database = cursor.execute("SELECT * FROM places").fetchall()


async def process_word(id, word):
    url = f"https://tvaroslovnik.ics.upjs.sk/base?word={word}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            content = await response.text()
            soup = BeautifulSoup(content, "html.parser")
            href_elems = soup.select("a[href]")

            if len(href_elems) == 0:
                print(f"No href found for '{word}'. Continuing to the next word.")
                return

            found_href = None

            for href_elem in href_elems:
                href_text = href_elem.text.strip()

                if href_text == word:
                    found_href = href_elem["href"]
                    break

            if found_href is None:
                print(
                    f"No matching href found for '{word}'. Continuing to the next word."
                )
                return

            href_number = int(found_href.split("/")[-1]) + offset_case
            new_url = f"https://tvaroslovnik.ics.upjs.sk/id/{href_number}"

            async with session.get(new_url) as new_response:
                new_content = await new_response.text()
                new_soup = BeautifulSoup(new_content, "html.parser")
                word_in_offset_case = new_soup.find(
                    "div", {"id": "wordPanel"}
                ).text.strip()

                return word_in_offset_case, id


async def main():
    tasks = []
    for id, word, _ in word_database:
        await asyncio.sleep(0.08)
        task = asyncio.create_task(process_word(id, word))
        tasks.append(task)

    results = await asyncio.gather(*tasks)

    updates = [(result[0], result[1]) for result in results if result is not None]

    cursor.executemany("UPDATE places SET name_locative = ? WHERE id = ?", updates)
    conn.commit()
    conn.close()


asyncio.run(main())
