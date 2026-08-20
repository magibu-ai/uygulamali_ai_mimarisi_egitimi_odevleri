from huggingface_hub import login, upload_folder

# (optional) Login with your Hugging Face credentials
login()

# Push only the dataset release files (JSON + dataset card),
# not the whole project folder (scripts, raw PDFs, tokenizer, etc.)
upload_folder(folder_path="hf_release", repo_id="repo_id", repo_type="dataset")
