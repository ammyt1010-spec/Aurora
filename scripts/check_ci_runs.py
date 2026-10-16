import json
import urllib.request

SHA = "d9c8f51e9b2ecc41f22c6dec5f229cccd81b0ee1"
url = f"https://api.github.com/repos/ammyt1010-spec/Aurora/commits/{SHA}/check-runs"
req = urllib.request.Request(url, headers={"User-Agent": "CI-Monitor", "Accept": "application/vnd.github.v3+json"})

with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode())
    print(f"Total check runs for commit {SHA[:7]}: {data.get('total_count', 0)}")
    for cr in data.get("check_runs", []):
        print(f"- Job: {cr['name']:<22} | Status: {cr['status']:<10} | Conclusion: {cr['conclusion']} | Run ID: {cr.get('html_url', '').split('/')[-3] if 'html_url' in cr else ''}")
