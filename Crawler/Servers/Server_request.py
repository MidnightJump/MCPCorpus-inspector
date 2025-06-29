import requests
import re
import time
import os
import json

RETRY = 3
SLEEP_BETWEEN_RETRY = 2

def extract_hrefs(response_text):
    # Extract all hrefs
    return re.findall(r'"href":"(/server/[^"]+)"', response_text)

def main():
    output_file = "mcpso_all_hrefs.json"
    visited = set()
    href_list = []
    # Resume: load already saved hrefs
    if os.path.exists(output_file):
        with open(output_file, "r", encoding="utf-8") as f:
            try:
                href_list = json.load(f)
                for item in href_list:
                    visited.add(item["href"])
            except Exception:
                pass

    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cookie": "Your Cookie",
        "Next-Url": "/en/servers",
        "Priority": "u=1, i",
        "Referer": "https://mcp.so/servers",
        "Rsc": "1",
        "Sec-Ch-Ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
        "Sec-Ch-Ua-Arch": "arm",
        "Sec-Ch-Ua-Bitness": "64",
        "Sec-Ch-Ua-Full-Version": "136.0.7103.114",
        "Sec-Ch-Ua-Full-Version-List": '"Chromium";v="136.0.7103.114", "Google Chrome";v="136.0.7103.114", "Not.A/Brand";v="99.0.0.0"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Model": '""',
        "Sec-Ch-Ua-Platform": '"macOS"',
        "Sec-Ch-Ua-Platform-Version": '"15.3.0"',
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin"
    }

    for page in range(1, 477):
        url = f"https://mcp.so/servers?page={page}"
        print(f"Requesting page {page}: {url}")
        for attempt in range(1, RETRY + 1):
            try:
                resp = requests.get(url, headers=headers, timeout=30)
                if resp.status_code != 200:
                    print(f"Page {page} failed: HTTP {resp.status_code}, attempt {attempt}/{RETRY}")
                    time.sleep(SLEEP_BETWEEN_RETRY)
                    continue
                hrefs = extract_hrefs(resp.text)
                new_hrefs = [h for h in hrefs if h not in visited]
                for h in new_hrefs:
                    href_list.append({"href": h})
                    visited.add(h)
                # Save in real time
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(href_list, f, ensure_ascii=False, indent=2)
                print(f"Page {page} got {len(new_hrefs)} new, total {len(href_list)}")
                time.sleep(1)
                break
            except Exception as e:
                print(f"Page {page} exception: {e}, attempt {attempt}/{RETRY}")
                time.sleep(SLEEP_BETWEEN_RETRY)
                continue
        else:
            print(f"Page {page} failed after {RETRY} retries.")
    print(f"All done. Total unique hrefs: {len(href_list)}. Saved to {output_file}")

if __name__ == "__main__":
    main() 