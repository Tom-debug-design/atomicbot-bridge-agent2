import os
from flask import Flask, request
from git import Repo

app = Flask(__name__)

GH_PAT = os.getenv('GH_PAT')
REPO_URL = os.getenv('TARGET_REPO_URL')  # eks: https://x-access-token:GH_PAT@github.com/Tom-debug-design/atomicbot-agent.git
LOCAL_PATH = "/tmp/targetrepo"

@app.route('/push', methods=['POST'])
def push_file():
    filename = request.form['filename']
    content = request.form['content']

    repo_url = REPO_URL.replace('GH_PAT', GH_PAT)
    if not os.path.exists(LOCAL_PATH):
        Repo.clone_from(repo_url, LOCAL_PATH)

    # Lag/oppdater fil
    file_path = os.path.join(LOCAL_PATH, filename)
    with open(file_path, "w") as f:
        f.write(content)

    repo = Repo(LOCAL_PATH)
    repo.git.add(all=True)
    repo.git.commit('-m', f"Auto-push: {filename}")
    repo.git.push()
    return f"Pushet {filename} til target-repo", 200

@app.route('/')
def index():
    return "Bridge-agent kjører! POST til /push for å sende fil.", 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
