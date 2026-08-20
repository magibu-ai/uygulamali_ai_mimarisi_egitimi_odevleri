from huggingface_hub import login, upload_folder, create_repo

# 1. Giriş yap
login()

repo_id = "repo_id"

# 2. Repo yoksa otomatik oluştur
create_repo(repo_id=repo_id, repo_type="model", exist_ok=True)

# 3. Yalnızca tokenizer klasöründeki dosyaları repo köküne yükle
upload_folder(
    folder_path="PATH",
    repo_id=repo_id,
    repo_type="model"
)

print("✅ Sadece tokenizer dosyaları başarıyla yüklendi!")


