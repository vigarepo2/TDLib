"""Small, dependency-free GitHub API helpers used by trusted workflows."""
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        redirected = super().redirect_request(request, fp, code, msg, headers, newurl)
        if redirected and urllib.parse.urlsplit(request.full_url).netloc != urllib.parse.urlsplit(newurl).netloc:
            redirected.remove_header("Authorization")
        return redirected


class GitHub:
    def __init__(self, repository=None, token=None):
        self.repository = repository or os.environ["GITHUB_REPOSITORY"]
        self.token = token if token is not None else os.environ.get("GH_TOKEN", "")

    def request(self, path, method="GET", body=None, accept="application/vnd.github+json"):
        url = path if path.startswith("https://") else "https://api.github.com" + path
        # Never forward the GitHub token to arbitrary download hosts.
        headers = {"Accept": accept, "User-Agent": "vs69-tdlib-workflows", "X-GitHub-Api-Version": "2022-11-28"}
        if self.token and urllib.parse.urlsplit(url).hostname == "api.github.com":
            headers["Authorization"] = "Bearer " + self.token
        data = json.dumps(body).encode() if body is not None else None
        if data is not None:
            headers["Content-Type"] = "application/json"
        for attempt in range(4):
            try:
                with urllib.request.build_opener(SafeRedirect()).open(urllib.request.Request(url, data=data, headers=headers, method=method), timeout=90) as response:
                    content = response.read()
                    return json.loads(content) if content and "json" in response.headers.get("Content-Type", "") else content
            except urllib.error.HTTPError as error:
                if error.code not in (429, 502, 503, 504) or attempt == 3:
                    raise
                time.sleep(min(2 ** attempt, 8))

    def pages(self, path):
        separator = "&" if "?" in path else "?"
        for page in range(1, 101):
            result = self.request(f"{path}{separator}per_page=100&page={page}")
            yield result
            records = result if isinstance(result, list) else next((result[k] for k in ("workflow_runs", "artifacts", "jobs") if k in result), [])
            if len(records) < 100:
                return
        raise RuntimeError("Unexpectedly large GitHub result; refusing an incomplete operation")

    def download(self, url):
        # GitHub release downloads redirect to signed object storage URLs. urllib's
        # default redirect handler would copy Authorization; use anonymous public URLs.
        host = urllib.parse.urlsplit(url).hostname or ""
        if host not in ("github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"):
            raise ValueError("Unexpected public download host")
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "vs69-tdlib-workflows"}), timeout=120) as response:
            return response.read()
