import requests
from bs4 import BeautifulSoup
import time
import re
from urllib.parse import urljoin, urldefrag
import pandas as pd

HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; UniversityTP01-QuoteScraper/1.0; educational use)"}
REQUEST_DELAY = 0.8
TARGET_QUOTES = 1000
OUTPUT_CSV = "wikiquote.csv"
BASE = "https://en.wikiquote.org"

SEEDS = [
    "https://en.wikiquote.org/wiki/Albert_Einstein",
    "https://en.wikiquote.org/wiki/Mark_Twain",
    "https://en.wikiquote.org/wiki/Oscar_Wilde",
    "https://en.wikiquote.org/wiki/Aristotle",
    "https://en.wikiquote.org/wiki/Winston_Churchill",
    "https://en.wikiquote.org/wiki/Mahatma_Gandhi",
    "https://en.wikiquote.org/wiki/Friedrich_Nietzsche",
]

STOP_SECTIONS = ("about", "quotes about", "see also", "external links",
                 "references", "further reading", "notes")


def fetch_html(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        return r.text
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return None


def extract_quotes_from_page(html):
    soup = BeautifulSoup(html, "html.parser")

    title_tag = soup.find("h1", id="firstHeading")
    author = title_tag.get_text(strip=True) if title_tag else ""

    content = soup.find("div", class_="mw-parser-output")
    if content is None:
        return []

    elements = []
    for e in content.find_all(["h2", "ul"]):
        if e.name == "ul" and (e.find_parent("li") or e.find_parent("table")):
            continue
        elements.append(e)

    quotes = []
    for el in elements:
        if el.name == "h2":
            heading = el.get_text(" ", strip=True).lower()
            if heading.startswith(STOP_SECTIONS):
                break
            continue

        for li in el.find_all("li", recursive=False):
            source_note = ""
            nested = li.find("ul")
            if nested:
                first_li = nested.find("li")
                if first_li:
                    source_note = first_li.get_text(" ", strip=True)
                nested.extract()

            text = li.get_text(" ", strip=True)
            text = re.sub(r"\[\d+\]", "", text)
            text = re.sub(r"\s+", " ", text).strip()

            if len(text) < 30 or len(text.split()) < 5:
                continue

            quotes.append({"quote": text, "author": author, "reference": source_note})

    return quotes


def extract_links(html):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if not href.startswith("/wiki/"):
            continue
        name = href[len("/wiki/"):]
        if ":" in name or name.startswith("Main_Page") or name.startswith("List_of"):
            continue
        full, _ = urldefrag(urljoin(BASE, href))
        links.append(full)
    return links


def crawl_wikiquote(seeds, target):
    collected = []
    seen_quotes = set()
    visited = set()
    to_visit = list(seeds)

    while to_visit and len(collected) < target:
        url = to_visit.pop(0)
        if url in visited:
            continue
        visited.add(url)

        html = fetch_html(url)
        time.sleep(REQUEST_DELAY)
        if html is None:
            continue

        if len(visited) == 1:
            print("\n----- HTML source (first 1000 chars) -----")
            print(html[:1000])
            print("-------------------------------------------\n")

        found = extract_quotes_from_page(html)
        added = 0
        for item in found:
            if len(collected) >= target:
                break
            if item["quote"] not in seen_quotes:
                seen_quotes.add(item["quote"])
                collected.append({**item, "source": url})
                added += 1

        print(f"Fetched: {url}  (+{added} quotes, total: {len(collected)})")

        for link in extract_links(html):
            if link not in visited and link not in to_visit:
                to_visit.append(link)

    return collected


if __name__ == "__main__":
    quotes = crawl_wikiquote(SEEDS, TARGET_QUOTES)
    print(f"\nTotal collected: {len(quotes)}")

    df = pd.DataFrame(quotes)
    df.to_csv(OUTPUT_CSV, index=False, encoding="utf-8")
    print(f"Saved {len(df)} quotes to {OUTPUT_CSV}")

    if len(df) >= 1000:
        print("OK: the file contains at least 1000 rows.")
    else:
        print("Warning: less than 1000 rows, add more seeds or raise the crawl limit.")
