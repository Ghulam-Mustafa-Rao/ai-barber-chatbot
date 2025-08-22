import os
import subprocess
from huggingface_hub import HfFolder
from dotenv import load_dotenv
import shutil
import stat
from huggingface_hub import login
# ---------------- Load Environment ----------------
load_dotenv()
# Load .env file (make sure .env is in project root)
token = os.getenv("HF_TOKEN_LOGIN")

if not token:
    # Try loading again (or fallback)
    load_dotenv()
    token = os.getenv("HF_TOKEN_LOGIN")

if not token:
    raise ValueError("HF_TOKEN_LOGIN not found. Please set it in your .env file.")

# Login to HuggingFace
login(token)
HF_TOKEN = os.getenv("HF_TOKEN_LOGIN")  # Hugging Face token
SPACE_ID = os.getenv("HF_SPACE_ID")     # e.g. "username/AI_Barber_Chat_Bot"
APP_DIR = "app"
TEMP_DIR = "tmp_hf_space"

if not HF_TOKEN or not SPACE_ID:
    raise ValueError("Please set HF_TOKEN_LOGIN and HF_SPACE_ID in your .env file")

# Save token for Hugging Face Python API
HfFolder.save_token(HF_TOKEN)

# ---------------- Helper Functions ----------------
def remove_readonly(func, path, _):
    """Handle read-only files on Windows when deleting directories"""
    os.chmod(path, stat.S_IWRITE)
    func(path)

# ---------------- Remove old clone ----------------
if os.path.exists(TEMP_DIR):
    shutil.rmtree(TEMP_DIR, onerror=remove_readonly)

# ---------------- Clone Space Repo ----------------
repo_url = f"https://huggingface.co/spaces/{SPACE_ID}"
print(f"Cloning {repo_url}...")
# Use token with GIT_ASKPASS to avoid password prompt
env = os.environ.copy()
env["GIT_ASKPASS"] = "echo"
env["GIT_USERNAME"] = "hf"     # username is ignored
env["GIT_PASSWORD"] = HF_TOKEN  # your token

subprocess.run(["git", "clone", repo_url, TEMP_DIR], check=True, env=env)

# ---------------- Copy App Files ----------------
for item in os.listdir(APP_DIR):
    s = os.path.join(APP_DIR, item)
    d = os.path.join(TEMP_DIR, item)
    if item == ".git":
        continue
    if os.path.isdir(s):
        shutil.copytree(s, d, dirs_exist_ok=True)
    else:
        shutil.copy2(s, d)

# ---------------- Git Add ----------------
subprocess.run(["git", "-C", TEMP_DIR, "add", "."], check=True, env=env)

# ---------------- Commit Only If Changes ----------------
diff_result = subprocess.run(
    ["git", "-C", TEMP_DIR, "diff", "--cached", "--quiet"],
    env=env
)
if diff_result.returncode != 0:  # changes exist
    subprocess.run(["git", "-C", TEMP_DIR, "commit", "-m", "Update app deployment"], check=True, env=env)
    subprocess.run(["git", "-C", TEMP_DIR, "push"], check=True, env=env)
    print("Deployment successful! App updated on Hugging Face Space.")
else:
    print("No changes detected. Nothing to commit.")
