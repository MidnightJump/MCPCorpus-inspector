import os
import re
import sys
import json
import time
import requests
from urllib.parse import urlparse

def robust_request(url, headers=None, max_retries=5, timeout=30):
    """
    Robust requests.get with retry logic and GitHub API rate limit handling.
    """
    delay = 5
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            if resp.status_code == 403:
                # Check if it's rate limit
                if 'X-RateLimit-Remaining' in resp.headers and resp.headers['X-RateLimit-Remaining'] == '0':
                    reset_ts = int(resp.headers.get('X-RateLimit-Reset', time.time() + 60))
                    wait_sec = max(reset_ts - int(time.time()), 5)
                    print(f"[Rate Limit] API rate limit, waiting {wait_sec} seconds...")
                    time.sleep(wait_sec)
                    continue
                else:
                    print(f"[WARN] 403 Forbidden: {url}")
                    time.sleep(delay)
                    delay = min(delay * 2, 120)
                    continue
            elif resp.status_code in (429, 502, 503, 504):
                print(f"[WARN] {resp.status_code}, retrying {url}, waiting {delay} seconds...")
                time.sleep(delay)
                delay = min(delay * 2, 120)
                continue
            return resp
        except Exception as e:
            print(f"[ERROR] Network exception: {e}, retrying {url}, waiting {delay} seconds...")
            time.sleep(delay)
            delay = min(delay * 2, 120)
    print(f"[FATAL] Multiple retries failed: {url}")
    return None

def extract_github_repo(url):
    """Extract owner/repo from GitHub URL"""
    if not url or 'github.com' not in url:
        return None
    m = re.search(r'github.com/([\w\-\.]+)/([\w\-\.]+)', url)
    if m:
        return f"{m.group(1)}/{m.group(2)}"
    return None

def get_github_info(full_name, token=None):
    """Get GitHub repository information"""
    headers = {'Accept': 'application/vnd.github+json'}
    if token:
        headers['Authorization'] = f'token {token}'
    api_url = f'https://api.github.com/repos/{full_name}'
    repo_resp = robust_request(api_url, headers)
    if not repo_resp or repo_resp.status_code != 200:
        print(f"[WARN] Failed to get repository info: {full_name}")
        return None
    repo = repo_resp.json()
    # Contributors count
    contrib_url = f'https://api.github.com/repos/{full_name}/contributors?per_page=1&anon=true'
    contrib_resp = robust_request(contrib_url, headers)
    contributors_count = 0
    if contrib_resp and contrib_resp.status_code == 200:
        if 'Link' in contrib_resp.headers and 'last' in contrib_resp.headers['Link']:
            last_link = contrib_resp.headers['Link'].split(',')[-1]
            m = re.search(r'&page=(\d+)>; rel="last"', last_link)
            if m:
                contributors_count = int(m.group(1))
        else:
            contributors_count = len(contrib_resp.json())
    # Language statistics
    lang_url = f'https://api.github.com/repos/{full_name}/languages'
    lang_resp = robust_request(lang_url, headers)
    languages = lang_resp.json() if lang_resp and lang_resp.status_code == 200 else {}
    # File detection
    tree_url = f'https://api.github.com/repos/{full_name}/git/trees/{repo.get('default_branch', 'main')}?recursive=1'
    tree_resp = robust_request(tree_url, headers)
    has_docker = has_readme = has_requirements = False
    if tree_resp and tree_resp.status_code == 200:
        files = [item['path'].lower() for item in tree_resp.json().get('tree', []) if item['type'] == 'blob']
        has_docker = any('dockerfile' in f for f in files)
        has_readme = any(f.startswith('readme') for f in files)
        has_requirements = any('requirements.txt' in f for f in files)
    # Last commit
    commit_url = f'https://api.github.com/repos/{full_name}/commits?per_page=1'
    commit_resp = robust_request(commit_url, headers)
    last_commit = None
    if commit_resp and commit_resp.status_code == 200 and len(commit_resp.json()) > 0:
        last_commit = commit_resp.json()[0]['commit']['committer']['date']
    # license
    license_name = repo['license']['name'] if repo.get('license') else None
    return {
        "full_name": full_name,
        "stargazers_count": repo.get('stargazers_count', 0),
        "forks_count": repo.get('forks_count', 0),
        "open_issues_count": repo.get('open_issues_count', 0),
        "contributors_count": contributors_count,
        "language": repo.get('language'),
        "languages": languages,
        "license": license_name,
        "archived": repo.get('archived', False),
        "has_docker": has_docker,
        "has_readme": has_readme,
        "has_requirements": has_requirements,
        "last_commit": last_commit
    }

def update_json_file(json_path, token=None):
    with open(json_path, 'r', encoding='utf-8') as f:
        servers = json.load(f)
    changed = False
    for idx, item in enumerate(servers):
        url = item.get('url')
        if not url or 'github.com' not in url:
            continue
        if 'github' in item and item['github']:
            continue  # Already collected
        full_name = extract_github_repo(url)
        if not full_name:
            continue
        print(f"[{idx+1}/{len(servers)}] Collecting {full_name} ...")
        info = get_github_info(full_name, token)
        if info:
            item['github'] = info
            changed = True
            # Write back in real time
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(servers, f, ensure_ascii=False, indent=2)
        time.sleep(0.5)  # Prevent API rate limiting
    if changed:
        print(f"All collection completed, written back to {json_path}")
    else:
        print("No repositories need to be updated.")

def test_single_url(url, token=None):
    full_name = extract_github_repo(url)
    if not full_name:
        print("Not a valid GitHub URL")
        return
    info = get_github_info(full_name, token)
    print(json.dumps(info, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Batch/single collection of GitHub repository information')
    parser.add_argument('--file', type=str, default='mcpso_servers.json', help='JSON file path')
    parser.add_argument('--url', type=str, help='Single GitHub repository URL')
    parser.add_argument('--token', type=str, help='GitHub API Token (optional)')
    args = parser.parse_args()
    if args.url:
        test_single_url(args.url, args.token)
    else:
        update_json_file(args.file, args.token) 