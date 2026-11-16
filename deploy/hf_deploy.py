"""Create or update the Hugging Face Space and set its secret. Usage: HF_TOKEN=hf_... python deploy/hf_deploy.py <user>

Reads GEMINI_API_KEY from the environment or .env and stores it as a Space secret (never in the files).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

from huggingface_hub import HfApi

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from desirepaths import env as _env  # noqa: E402,F401  (loads .env)


def main() -> None:
    user = sys.argv[1]
    repo = f"{user}/desire-paths"
    api = HfApi(token=os.environ["HF_TOKEN"])
    api.create_repo(repo, repo_type="space", space_sdk="docker", exist_ok=True)
    api.upload_folder(repo_id=repo, repo_type="space", folder_path=str(ROOT / "deploy" / "hf-space"),
                      commit_message="Desire Paths: HydraDB + dashboard (prebuilt image)")
    api.add_space_secret(repo, "GEMINI_API_KEY", os.environ["GEMINI_API_KEY"])
    print(f"https://huggingface.co/spaces/{repo}  ->  https://{user.lower()}-desire-paths.hf.space")


if __name__ == "__main__":
    main()
