#!/usr/bin/env python3
import os, json, time, base64, zipfile, io, requests

TOKEN = os.environ.get('GH_TOKEN')
REPO = os.environ.get('REPO')
HEADERS = {'Authorization': f'Bearer {TOKEN}', 'Accept': 'application/vnd.github+json'}

def create_workflow_file(filename, content):
    url = f'https://api.github.com/repos/{REPO}/contents/.github/workflows/{filename}'
    encoded = base64.b64encode(content.encode()).decode()
    data = {'message': f'Create {filename}', 'content': encoded}
    resp = requests.put(url, headers=HEADERS, json=data)
    if resp.status_code in [200, 201]:
        return resp.json().get('content', {}).get('sha')
    raise Exception(f"Create failed: {resp.status_code} {resp.text}")

def delete_workflow_file(filename, sha):
    url = f'https://api.github.com/repos/{REPO}/contents/.github/workflows/{filename}'
    data = {'message': f'Delete {filename}', 'sha': sha}
    resp = requests.delete(url, headers=HEADERS, json=data)
    if resp.status_code in [200, 204]:
        return True
    raise Exception(f"Delete failed: {resp.status_code} {resp.text}")

def trigger_workflow(workflow_id, inputs=None):
    url = f'https://api.github.com/repos/{REPO}/actions/workflows/{workflow_id}/dispatches'
    data = {'ref': 'main'}
    if inputs:
        data['inputs'] = inputs
    resp = requests.post(url, headers=HEADERS, json=data)
    if resp.status_code == 204:
        return True
    raise Exception(f"Trigger failed: {resp.status_code} {resp.text}")

def get_running_workers(workflow_name):
    url = f'https://api.github.com/repos/{REPO}/actions/workflows/{workflow_name}/runs'
    params = {'status': 'in_progress', 'per_page': 100}
    resp = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code == 200:
        runs = resp.json().get('workflow_runs', [])
        return len(runs)
    return 0

def get_latest_completed_run(workflow_id):
    url = f'https://api.github.com/repos/{REPO}/actions/workflows/{workflow_id}/runs'
    params = {'status': 'completed', 'per_page': 1}
    resp = requests.get(url, headers=HEADERS, params=params)
    if resp.status_code == 200:
        runs = resp.json().get('workflow_runs', [])
        if runs:
            return runs[0]
    return None

def download_artifact(run_id):
    url = f'https://api.github.com/repos/{REPO}/actions/runs/{run_id}/artifacts'
    resp = requests.get(url, headers=HEADERS)
    if resp.status_code != 200:
        return None
    artifacts = resp.json().get('artifacts', [])
    for art in artifacts:
        if art['name'] == 'result':
            dl_resp = requests.get(art['archive_download_url'], headers=HEADERS, stream=True)
            if dl_resp.status_code == 200:
                z = zipfile.ZipFile(io.BytesIO(dl_resp.content))
                with z.open('upload/result.json') as f:
                    return json.load(f)
    return None

def wait_for_completion(workflow_id, timeout=600, interval=10):
    start = time.time()
    while time.time() - start < timeout:
        run = get_latest_completed_run(workflow_id)
        if run:
            return run.get('id')
        time.sleep(interval)
    raise TimeoutError(f"Workflow {workflow_id} did not complete within {timeout}s")

if __name__ == '__main__':
    print("✅ GitHub ops module loaded")
