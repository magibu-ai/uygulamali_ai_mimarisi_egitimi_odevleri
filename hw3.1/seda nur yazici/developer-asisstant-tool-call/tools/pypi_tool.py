from typing import Any

import requests

from config import PYPI_API


def search_pypi(package_name: str) -> dict[str, Any]:
    """
    PyPI API üzerinden bir Python paketinin meta verilerini getirir.
    """

    package_name = package_name.strip()

    if not package_name:
        raise ValueError("Paket adı boş olamaz.")

    url = f"{PYPI_API}/{package_name}/json"

    try:
        response = requests.get(
            url,
            timeout=20,
        )
    except requests.RequestException as exc:
        return {
            "success": False,
            "package_name": package_name,
            "error": f"PyPI API isteği başarısız oldu: {exc}",
        }

    if response.status_code == 404:
        return {
            "success": False,
            "package_name": package_name,
            "error": "Paket PyPI üzerinde bulunamadı.",
        }

    if response.status_code != 200:
        return {
            "success": False,
            "package_name": package_name,
            "status_code": response.status_code,
            "error": "PyPI API beklenmeyen bir yanıt döndürdü.",
        }

    try:
        data = response.json()
    except ValueError:
        return {
            "success": False,
            "package_name": package_name,
            "error": "PyPI API geçerli bir JSON yanıtı döndürmedi.",
        }

    info = data.get("info", {})

    return {
        "success": True,
        "package_name": info.get("name") or package_name,
        "version": info.get("version"),
        "summary": info.get("summary"),
        "author": info.get("author"),
        "license": info.get("license"),
        "python_requires": info.get("requires_python"),
        "home_page": info.get("home_page"),
        "project_url": info.get("project_url"),
        "package_url": info.get("package_url"),
    }