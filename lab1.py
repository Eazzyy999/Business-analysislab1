import os
import json
import csv
import sqlite3
import xml.etree.ElementTree as ET
from requests import get
from bs4 import BeautifulSoup
from urllib.parse import urljoin


# 1. Налаштування та джерело даних
BASE_URL = "https://en.wikipedia.org"
URL = f"{BASE_URL}/wiki/List_of_S%26P_500_companies"
HEADERS = {
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
os.makedirs("output", exist_ok=True)
os.makedirs("output/images", exist_ok=True)

companies_list = []
company_details_list = []
images_list = []

print("1. Завантаження головної сторінки S&P 500...")
page = get(URL, headers=HEADERS)
if page.status_code == 200:
    print("Сторінка успішно завантажена (Статична).")
    print(f"Частина HTML: {page.text[:200]}...\n")
else:
    print("Помилка завантаження сторінки!")

soup = BeautifulSoup(page.content, "html.parser")

table = soup.find(id="constituents")
rows = table.find_all("tr")[1:10]

for row in rows:
    columns = row.find_all("td")
    if columns:
        a_tag = columns[1].find("a")
        comp_name = a_tag.text.strip()
        comp_url = urljoin(BASE_URL, a_tag.get("href"))
        print(f"Обробка компанії: {comp_name}")
        companies_list.append({"name": comp_name, "url": comp_url})

        comp_page = get(comp_url, headers=HEADERS)
        comp_soup = BeautifulSoup(comp_page.content, "html.parser")

        infobox = comp_soup.find("table", class_="infobox")

        if infobox:
            for tr in infobox.find_all("tr"):
                th = tr.find("th")
                td = tr.find("td")

                if th and td:
                    key = th.text.strip()
                    value = td.text.strip().replace("\n", ", ")
                    if key and value:
                        company_details_list.append({
                            "company": comp_name,
                            "attribute": key,
                            "value": value
                        })

            images = infobox.find_all("img")
            logo_found = False

            for img in images:
                img_src = img.get("src")

                if img_src and not img_src.startswith("data:"):
                    if img_src.startswith("//"):
                        img_url = "https:" + img_src
                    else:
                        img_url = urljoin(BASE_URL, img_src)

                    img_name = img_url.split('/')[-1].split('?')[0]

                    if any(ext in img_name.lower() for ext in ['.png', '.jpg', '.jpeg', '.svg']):
                        images_list.append({
                            "company": comp_name,
                            "filename": img_name,
                            "url": img_url
                        })

                        try:
                            img_data = get(img_url, headers=HEADERS).content
                            with open(f"output/images/{img_name}", 'wb') as f:
                                f.write(img_data)
                            print(f"  [+] Завантажено лого: {img_name}")
                            logo_found = True
                        except Exception as e:
                            print(f"  [-] Помилка завантаження для {comp_name}: {e}")

                        break

            if not logo_found:
                print(f"  [i] На сторінці {comp_name} немає відповідного логотипу.")
print("\nЗбереження даних у файли...")

# 3. Збереження компаній в TXT та XML
with open("output/companies.txt", "w", encoding="utf-8") as f:
    for comp in companies_list:
        f.write(f"{comp['name']} | {comp['url']}\n")

root = ET.Element("Companies")
for comp in companies_list:
    comp_el = ET.SubElement(root, "Company")
    ET.SubElement(comp_el, "Name").text = comp["name"]
    ET.SubElement(comp_el, "URL").text = comp["url"]
ET.ElementTree(root).write("output/companies.xml", encoding="utf-8", xml_declaration=True)

# 4. Збереження деталей (об'єктів) в JSON та TXT
with open("output/company_details.json", "w", encoding="utf-8") as f:
    json.dump(company_details_list, f, ensure_ascii=False, indent=4)

with open("output/company_details.txt", "w", encoding="utf-8") as f:
    for detail in company_details_list:
        f.write(f"[{detail['company']}] {detail['attribute']}: {detail['value']}\n")

# 5. Збереження зображень в CSV та TXT
with open("output/images.csv", "w", newline='', encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["company", "filename", "url"])
    writer.writeheader()
    writer.writerows(images_list)

with open("output/images.txt", "w", encoding="utf-8") as f:
    for img in images_list:
        f.write(f"{img['filename']} - {img['url']}\n")

# 6. Збереження в базу даних SQLite
print("Запис у базу даних...")
db_path = "output/economics_data.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS companies (id INTEGER PRIMARY KEY, name TEXT, url TEXT)''')
cursor.execute(
    '''CREATE TABLE IF NOT EXISTS details (id INTEGER PRIMARY KEY, company TEXT, attribute TEXT, value TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS images (id INTEGER PRIMARY KEY, company TEXT, filename TEXT, url TEXT)''')

cursor.execute('DELETE FROM companies')
cursor.execute('DELETE FROM details')
cursor.execute('DELETE FROM images')

for comp in companies_list:
    cursor.execute('INSERT INTO companies (name, url) VALUES (?, ?)', (comp['name'], comp['url']))
for detail in company_details_list:
    cursor.execute('INSERT INTO details (company, attribute, value) VALUES (?, ?, ?)',
                   (detail['company'], detail['attribute'], detail['value']))
for img in images_list:
    cursor.execute('INSERT INTO images (company, filename, url) VALUES (?, ?, ?)',
                   (img['company'], img['filename'], img['url']))

conn.commit()
conn.close()

print(f"Готово! Всі дані збережено. Спарсено компаній: {len(companies_list)}")