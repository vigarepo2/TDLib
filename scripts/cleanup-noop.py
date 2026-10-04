#!/usr/bin/env python3
"""Remove only verified successful, unchanged scheduled checks after completion."""
import argparse
import io
import json
import os
import zipfile
from workflow_common import GitHub

BUILD_PATH = ".github/workflows/build-and-publish.yml"
CLEANUP_PATH = ".github/workflows/cleanup-noop.yml"


def eligible_run(run, repository, workflow_id):
    return (run.get("repository", {}).get("full_name") == repository
            and run.get("head_repository", {}).get("full_name") == repository
            and run.get("workflow_id") == workflow_id
            and run.get("path") == BUILD_PATH
            and run.get("event") == "schedule"
            and run.get("status") == "completed"
            and run.get("conclusion") == "success")


def eligible_marker(marker, run, repository):
    return (marker.get("schema") == 1 and marker.get("changed") is False
            and marker.get("repository") == repository
            and marker.get("event") == "schedule"
            and marker.get("run_id") == str(run["id"])
            and marker.get("head_sha") == run["head_sha"]
            and len(marker.get("upstream", {}).get("commit", "")) == 40
            and len(marker.get("build_fingerprint", "")) == 64)


def read_marker(payload):
    if len(payload) > 100_000:
        raise ValueError("Unexpected marker archive size")
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        if archive.namelist() != ["check-result.json"] or archive.getinfo("check-result.json").file_size > 16_000:
            raise ValueError("Unexpected marker archive contents")
        return json.loads(archive.read("check-result.json"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True, type=int)
    args = parser.parse_args()
    api = GitHub()
    prefix = f"/repos/{api.repository}"
    workflow = api.request(prefix + "/actions/workflows/build-and-publish.yml")
    run = api.request(prefix + f"/actions/runs/{args.run_id}")
    if not eligible_run(run, api.repository, workflow["id"]):
        print("Retaining this run: it is not a successful scheduled build check.")
    else:
        artifacts = api.request(prefix + f"/actions/runs/{args.run_id}/artifacts")["artifacts"]
        candidates = [artifact for artifact in artifacts if artifact["name"] == "upstream-check" and not artifact["expired"]]
        if len(candidates) != 1:
            raise RuntimeError("Refusing cleanup: exactly one live upstream-check artifact is required")
        marker = read_marker(api.request(candidates[0]["archive_download_url"], accept="application/vnd.github+json"))
        if eligible_marker(marker, run, api.repository):
            jobs = [job for page in api.pages(prefix + f"/actions/runs/{args.run_id}/jobs") for job in page["jobs"]]
            # A no-change run can only have completed its check job. Any real build
            # or publish job is enough to retain it, even if a marker was incorrect.
            completed = [job for job in jobs if job.get("conclusion") != "skipped"]
            if len(completed) != 1 or completed[0].get("name") != "Check official upstream" or completed[0].get("conclusion") != "success":
                raise RuntimeError("Refusing cleanup: the run contains more than an upstream check")
            api.request(prefix + f"/actions/runs/{args.run_id}", method="DELETE")
            print(f"Deleted unchanged scheduled check {args.run_id}.")
        else:
            print("Retaining this run: upstream or build recipes changed.")
    # GitHub cannot delete the currently running cleanup workflow. Keep that one
    # and remove only older, completed successful runs of this exact cleanup.
    own_id = int(os.environ["GITHUB_RUN_ID"])
    cleanup = api.request(prefix + "/actions/workflows/cleanup-noop.yml")
    for page in api.pages(prefix + f"/actions/workflows/{cleanup['id']}/runs?event=workflow_run&status=success"):
        for old in page["workflow_runs"]:
            if old["id"] < own_id and old.get("path") == CLEANUP_PATH and old.get("event") == "workflow_run" and old.get("status") == "completed" and old.get("conclusion") == "success" and old.get("head_repository", {}).get("full_name") == api.repository:
                api.request(prefix + f"/actions/runs/{old['id']}", method="DELETE")
                print(f"Deleted older successful cleanup run {old['id']}.")


if __name__ == "__main__":
    main()
