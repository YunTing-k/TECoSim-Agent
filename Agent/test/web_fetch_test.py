import httpx

from trafilatura import extract

url = "https://www.runoob.com/playwright/playwright-intro.html"

try:
    with httpx.Client(
            timeout=httpx.Timeout(timeout=15),
            follow_redirects=True,
            headers={"User-Agent": "ClaudeAgent-WebFetch/1.0"}
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        html = resp.text
except Exception as e:
    print(f"Fetch content from URL: {url} failed with error {e}")

"""convert content to markdown"""
markdown = extract(html, output_format="markdown", url=url)
if markdown is None:
    print(f"Convert content from URL: {url} to markdown failed")

print(markdown)
