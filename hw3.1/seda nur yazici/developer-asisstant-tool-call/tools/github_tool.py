from typing import Any

import requests

from config import GITHUB_API, GITHUB_TOKEN


def _github_headers() -> dict[str, str]:
    """
    GitHub API isteklerinde kullanılacak HTTP başlıklarını oluşturur.
    Token tanımlıysa Authorization başlığını da ekler.
    """

    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "AI-Developer-Assistant",
    }

    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"

    return headers


def _request_github(
    endpoint: str,
    params: dict[str, Any] | None = None,
) -> tuple[requests.Response | None, str | None]:
    """
    GitHub API isteğini gerçekleştirir.

    Başarısız bağlantı durumunda response yerine None,
    hata açıklaması döndürür.
    """

    url = f"{GITHUB_API}{endpoint}"

    try:
        response = requests.get(
            url,
            headers=_github_headers(),
            params=params,
            timeout=20,
        )
        return response, None

    except requests.RequestException as exc:
        return None, f"GitHub API isteği başarısız oldu: {exc}"


def search_github_repo(
    owner: str,
    repo: str,
) -> dict[str, Any]:
    """
    Belirli bir GitHub repository'sinin temel bilgilerini getirir.
    """

    owner = owner.strip()
    repo = repo.strip()

    if not owner:
        raise ValueError("GitHub kullanıcı veya organizasyon adı boş olamaz.")

    if not repo:
        raise ValueError("Repository adı boş olamaz.")

    response, request_error = _request_github(
        endpoint=f"/repos/{owner}/{repo}"
    )

    if request_error:
        return {
            "success": False,
            "owner": owner,
            "repo": repo,
            "error": request_error,
        }

    if response is None:
        return {
            "success": False,
            "owner": owner,
            "repo": repo,
            "error": "GitHub API yanıtı alınamadı.",
        }

    if response.status_code == 404:
        return {
            "success": False,
            "owner": owner,
            "repo": repo,
            "error": "Repository bulunamadı veya erişim izni yok.",
        }

    if response.status_code == 403:
        return {
            "success": False,
            "owner": owner,
            "repo": repo,
            "status_code": response.status_code,
            "error": (
                "GitHub API erişimi reddetti. "
                "Rate limit aşılmış veya token yetkisiz olabilir."
            ),
        }

    if response.status_code != 200:
        return {
            "success": False,
            "owner": owner,
            "repo": repo,
            "status_code": response.status_code,
            "error": "GitHub API beklenmeyen bir yanıt döndürdü.",
        }

    try:
        data = response.json()
    except ValueError:
        return {
            "success": False,
            "owner": owner,
            "repo": repo,
            "error": "GitHub API geçerli bir JSON yanıtı döndürmedi.",
        }

    license_data = data.get("license") or {}
    owner_data = data.get("owner") or {}

    return {
        "success": True,
        "full_name": data.get("full_name"),
        "name": data.get("name"),
        "owner": owner_data.get("login"),
        "description": data.get("description"),
        "html_url": data.get("html_url"),
        "stars": data.get("stargazers_count"),
        "forks": data.get("forks_count"),
        "watchers": data.get("subscribers_count"),
        "open_issues": data.get("open_issues_count"),
        "language": data.get("language"),
        "license": license_data.get("spdx_id"),
        "topics": data.get("topics", []),
        "default_branch": data.get("default_branch"),
        "created_at": data.get("created_at"),
        "updated_at": data.get("updated_at"),
        "pushed_at": data.get("pushed_at"),
        "archived": data.get("archived"),
        "visibility": data.get("visibility"),
    }


def search_github_repositories(
    keyword: str,
    limit: int = 5,
) -> dict[str, Any]:
    """
    GitHub üzerinde anahtar kelimeye göre repository arar.
    Sonuçları yıldız sayısına göre azalan biçimde getirir.
    """

    keyword = keyword.strip()

    if not keyword:
        raise ValueError("GitHub arama ifadesi boş olamaz.")

    limit = max(1, min(limit, 10))

    response, request_error = _request_github(
        endpoint="/search/repositories",
        params={
            "q": keyword,
            "sort": "stars",
            "order": "desc",
            "per_page": limit,
        },
    )

    if request_error:
        return {
            "success": False,
            "keyword": keyword,
            "error": request_error,
        }

    if response is None:
        return {
            "success": False,
            "keyword": keyword,
            "error": "GitHub API yanıtı alınamadı.",
        }

    if response.status_code == 403:
        return {
            "success": False,
            "keyword": keyword,
            "status_code": response.status_code,
            "error": (
                "GitHub API erişimi reddetti. "
                "Rate limit aşılmış veya token yetkisiz olabilir."
            ),
        }

    if response.status_code != 200:
        return {
            "success": False,
            "keyword": keyword,
            "status_code": response.status_code,
            "error": "GitHub repository araması başarısız oldu.",
        }

    try:
        data = response.json()
    except ValueError:
        return {
            "success": False,
            "keyword": keyword,
            "error": "GitHub API geçerli bir JSON yanıtı döndürmedi.",
        }

    repositories = []

    for item in data.get("items", []):
        license_data = item.get("license") or {}

        repositories.append(
            {
                "full_name": item.get("full_name"),
                "description": item.get("description"),
                "html_url": item.get("html_url"),
                "stars": item.get("stargazers_count"),
                "forks": item.get("forks_count"),
                "open_issues": item.get("open_issues_count"),
                "language": item.get("language"),
                "license": license_data.get("spdx_id"),
                "updated_at": item.get("updated_at"),
                "topics": item.get("topics", []),
            }
        )

    return {
        "success": True,
        "keyword": keyword,
        "total_count": data.get("total_count", 0),
        "returned_count": len(repositories),
        "repositories": repositories,
    }