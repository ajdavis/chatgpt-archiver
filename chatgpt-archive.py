import asyncio
import re
import sys
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from playwright.async_api import async_playwright
import requests


async def save_chatgpt_cleaned_html(url: str, output_file: str):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()

        print(f"Opening {url}")
        await page.goto(url, wait_until='networkidle')

        # Scroll to trigger lazy-loaded content
        await page.evaluate("""() => {
            return new Promise((resolve) => {
                let totalHeight = 0;
                const distance = 300;
                const timer = setInterval(() => {
                    window.scrollBy(0, distance);
                    totalHeight += distance;
                    if (totalHeight >= document.body.scrollHeight) {
                        clearInterval(timer);
                        resolve();
                    }
                }, 100);
            });
        }""")
        await page.wait_for_timeout(1000)

        # Get page HTML
        html = await page.content()
        soup = BeautifulSoup(html, 'html.parser')

        for link_tag in soup.find_all("link", rel="stylesheet"):
            href = link_tag.get("href")
            if not href:
                continue
            css_url = urljoin(url, href)
            print(f"Inlining CSS from: {css_url}")
            css_content = requests.get(css_url, timeout=10).text
            style_tag = soup.new_tag("style")
            style_tag.string = css_content
            link_tag.replace_with(style_tag)

        # Remove all <script> tags
        for script in soup.find_all('script'):
            script.decompose()

        # Remove inline JS event handlers (onclick, onload, etc.)
        for tag in soup.find_all(True):
            for attr in list(tag.attrs):
                if attr.lower().startswith('on'):
                    del tag.attrs[attr]

        # Remove UI controls
        for div in soup.find_all('div'):
            for child in div.find_all('button', recursive=False):
                if 'cursor-pointer' in child.get('class', []):
                    div.decompose()
                    break  # Avoid modifying during iteration

        # Remove chat box
        for div in soup.find_all('div'):
            for child in div.find_all('form', recursive=False):
                if "w-full" in child.get('class', []):
                    div.decompose()
                    break

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(str(soup))

        print(f"Saved cleaned HTML to {output_file}")
        await browser.close()


url = sys.argv[1]
match = re.match(r"https://chatgpt.com/share/([0-9a-f-]+)", url)
if not match:
    print(f"Invalid URL: {url}")
    sys.exit(1)

output_file = f"chatgpt_{match.group(1)}.html"
asyncio.run(save_chatgpt_cleaned_html(url, output_file))
