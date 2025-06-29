import requests
import re
import json
import time
import os

def extract_current_project(text):
    # 1. Locate currentProject start position
    key = '"currentProject":'
    start = text.find(key)
    if start == -1:
        print("currentProject not found!")
        return None
    start = start + len(key)
    # 2. Starting from the first {, use bracket counting method to find matching }
    while start < len(text) and text[start] not in '{':
        start += 1
    if start == len(text):
        print("currentProject JSON start not found!")
        return None
    brace_count = 0
    end = start
    for i, c in enumerate(text[start:]):
        if c == '{':
            brace_count += 1
        elif c == '}':
            brace_count -= 1
        if brace_count == 0:
            end = start + i + 1
            break
    json_str = text[start:end]
    try:
        profile = json.loads(json_str)
        return profile
    except Exception as e:
        print(f"JSON decode error: {e}")
        return None

def request_server_detail(url, headers):
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        print(f"Status code: {resp.status_code} for {url}")
        if resp.status_code == 200:
            profile = extract_current_project(resp.text)
            return profile
        else:
            print(f"Failed to get detail: HTTP {resp.status_code}")
            return None
    except Exception as e:
        print(f"Exception: {e}")
        return None

def batch_request_servers():
    # Read mcpso_servers.json
    servers_path = os.path.join(os.path.dirname(__file__), 'mcpso_servers.json')
    with open(servers_path, 'r', encoding='utf-8') as f:
        servers = json.load(f)
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Encoding": "gzip, deflate, br, zstd",
        "Accept-Language": "zh-CN,zh;q=0.9",
        "Cookie": "Your Cookie",
        "Next-Url": "/en/server/zhipu-web-search/BigModel",
        "Priority": "u=1, i",
        "Referer": "https://mcp.so/server/zhipu-web-search/BigModel",
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
    for idx, item in enumerate(servers):
        # Skip already collected items (already have name field)
        if 'name' in item and 'metadata' in item:
            continue
        href = item.get('href')
        if not href:
            continue
        detail_url = f"https://mcp.so{href}"
        print(f"Requesting: {detail_url}")
        profile = request_server_detail(detail_url, headers)
        if not profile:
            print(f"Skip {href} due to extraction failure.")
            continue
        name = profile.get('name')
        url = profile.get('url')
        metadata = profile.copy()
        metadata.pop('name', None)
        metadata.pop('url', None)
        item['name'] = name
        item['url'] = url
        item['metadata'] = metadata
        # Write back in real time
        with open(servers_path, 'w', encoding='utf-8') as f:
            json.dump(servers, f, ensure_ascii=False, indent=2)
        print(f"Updated {idx+1}/{len(servers)}: {name}")
        time.sleep(1)
    print(f"All servers updated in {servers_path}")

if __name__ == "__main__":
    # 
    # url = "https://mcp.so/server/zhipu-web-search/BigModel?_rsc=n713a"
    # headers = {
    #     "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
    #     "Accept": "*/*",
    #     "Accept-Encoding": "gzip, deflate, br, zstd",
    #     "Accept-Language": "zh-CN,zh;q=0.9",
    #     "Next-Url": "/en/server/zhipu-web-search/BigModel",
    #     "Priority": "u=1, i",
    #     "Referer": "https://mcp.so/server/zhipu-web-search/BigModel",
    #     "Rsc": "1",
    #     "Sec-Ch-Ua": '"Chromium";v="136", "Google Chrome";v="136", "Not.A/Brand";v="99"',
    #     "Sec-Ch-Ua-Arch": "arm",
    #     "Sec-Ch-Ua-Bitness": "64",
    #     "Sec-Ch-Ua-Full-Version": "136.0.7103.114",
    #     "Sec-Ch-Ua-Full-Version-List": '"Chromium";v="136.0.7103.114", "Google Chrome";v="136.0.7103.114", "Not.A/Brand";v="99.0.0.0"',
    #     "Sec-Ch-Ua-Mobile": "?0",
    #     "Sec-Ch-Ua-Model": '""',
    #     "Sec-Ch-Ua-Platform": '"macOS"',
    #     "Sec-Ch-Ua-Platform-Version": '"15.3.0"',
    #     "Sec-Fetch-Dest": "empty",
    #     "Sec-Fetch-Mode": "cors",
    #     "Sec-Fetch-Site": "same-origin"
    # }
    # profile = request_server_detail(url, headers)
    # if profile:
    #     with open("server_zhipu-web-search_BigModel_profile.json", "w", encoding="utf-8") as f:
    #         json.dump(profile, f, ensure_ascii=False, indent=2)
    #     print("Profile saved to server_zhipu-web-search_BigModel_profile.json")
    # else:
    #     print("Profile extraction failed!")
    # 
    batch_request_servers() 