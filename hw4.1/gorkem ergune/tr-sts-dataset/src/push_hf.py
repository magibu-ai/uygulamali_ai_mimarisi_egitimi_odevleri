from huggingface_hub import HfApi, create_repo

REPO_ID = "gorkemergune/stsb-tr"
api = HfApi()

url = create_repo(REPO_ID, repo_type="dataset", private=False, exist_ok=True)
print("repo:", url)

api.upload_folder(
    repo_id=REPO_ID,
    repo_type="dataset",
    folder_path="hf_dataset",
    commit_message="Add Turkish STS dataset (39 manual + 1000 synthetic, magibu-200m scored)",
)
print("Yuklendi -> https://huggingface.co/datasets/" + REPO_ID)
