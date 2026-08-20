import os
import sys

# Ensure UTF-8 output on Windows console
sys.stdout.reconfigure(encoding='utf-8')

from huggingface_hub import HfApi, whoami

def deploy_to_hf_space(space_name: str = "calendar-assistant"):
    """
    Automatically creates a free Hugging Face Static Space under the logged in account
    and uploads the current project files.
    """
    api = HfApi()
    
    try:
        user_info = whoami()
        username = user_info.get("name") or user_info.get("fullname") or "aliFurkan123"
        print(f"✅ Logged in to Hugging Face as user: {username}")
    except Exception as e:
        print(f"❌ Error getting HF identity: {e}")
        print("Please ensure you are logged in via 'hf auth login' or have set HF_TOKEN environment variable.")
        return

    current_dir = os.path.dirname(os.path.abspath(__file__))
    repo_id = f"{username}/{space_name}"
    print(f"🚀 Accessing Hugging Face Space: {repo_id}...")

    # Keep env_config.js empty for security
    config_js_path = os.path.join(current_dir, "env_config.js")
    with open(config_js_path, "w", encoding="utf-8") as f:
        f.write('// Auto-generated environment config (Kept empty for security)\nwindow.EMBEDDED_GEMINI_KEY = "";\n')

    print("📤 Uploading repository files to Hugging Face Space...")
    
    try:
        api.upload_folder(
            folder_path=current_dir,
            repo_id=repo_id,
            repo_type="space",
            ignore_patterns=[
                ".git*",
                "__pycache__",
                "*.pyc",
                ".venv",
                "venv",
                "node_modules",
                ".gemini",
                ".vs",
                "bin",
                "obj"
            ]
        )
        print("\n" + "=" * 65)
        print("🎉 SUCCESS! Static Space uploaded to Hugging Face Space.")
        print(f"🔗 Live Space Link: https://huggingface.co/spaces/{repo_id}")
        print("=" * 65)
    except Exception as e:
        print(f"❌ Error uploading files to HF Space: {e}")

if __name__ == "__main__":
    deploy_to_hf_space()
