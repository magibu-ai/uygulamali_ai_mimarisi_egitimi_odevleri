import os
import subprocess
import tempfile
import time
import requests
from dotenv import load_dotenv
from exa_py import Exa

load_dotenv()
EXA_API_KEY = os.getenv("EXA_API_KEY")
exa_client = Exa(api_key=EXA_API_KEY)


def get_coordinates(city: str) -> tuple:
    """
    Verilen şehir için enlem ve boylam koordinatlarını döner.
    Input:
        city (str): Koordinatları alınacak şehir adı.
    Output:
        tuple: Şehrin enlem boylam koordinatları ve şehir adı. Örnek:
            (41.015137, 28.979232, "İstanbul")
    """
    geo_url = f"https://geocoding-api.open-meteo.com/v1/search?name={city}&count=1&language=tr&format=json"
    response = requests.get(geo_url)
    if response.status_code == 200:
        data = response.json()
        if data["results"]:
            latitude = data["results"][0]["latitude"]
            longitude = data["results"][0]["longitude"]
            city_name = data["results"][0]["name"]

    elif response.status_code != 200:
        print("Şehir bulunamadı.")
        return ()
    return latitude, longitude, city_name

    print(response.json())


def get_weather(city: str) -> dict:
    """
    Verilen şehir için hava durumu verilerini döner.
    Input:
        city (str): Hava durumu alınacak şehir adı.
    Output:
        dict: Şehrin hava durumu verileri. Örnek:
            {
               "city_name": "İstanbul",
                "temperature": "25°C",
                "humidity": "%60",
                "wind_speed": "10km/s"
            }
    """
    lat, lon, city_name = get_coordinates(city)
    weather_url = (
        f"https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m"
        f"&timezone=Europe%2FIstanbul"
    )
    response = requests.get(weather_url)
    if response.status_code == 200:
        data = response.json()
        temperature = data["current"]["temperature_2m"]
        humidity = data["current"]["relative_humidity_2m"]
        wind_speed = data["current"]["wind_speed_10m"]

    elif response.status_code != 200:
        print("Hava durumu verileri alınamadı.")
        return {}

    return {
        "city_name": city_name,
        "temperature": f"{temperature}°C",
        "humidity": f"% {humidity}",
        "wind_speed": f"{wind_speed}km/s",
    }


def internet_search(query: str):
    """
    İnternet üzerinde arama yapar ve sonuçları döner.
    Input:
        query (str): Arama yapılacak sorgu.
    Output:
        result (str): Arama sonuçları
    """
    try:
        response = exa_client.search(
            query=query, num_results=3, type="auto", contents={"highlights": True}
        )
        formatted = []
        for r in response.results:
            highlights = " ".join(r.highlights) if r.highlights else ""
            formatted.append(f"Başlık: {r.title}\nURL: {r.url}\nİçerik: {highlights}\n")
        return "\n".join(formatted)
    except Exception as e:
        return f"Exa arama hatası: {str(e)}"


def execute_code(code: str) -> str:
    """
    Verilen Python kodunu çalıştırır ve çıktısını döner.
    Input:
        code (str): Çalıştırılacak Python kodu.
    Output:
        str: Kodun çıktısı veya hata mesajı.
    """

    print("\nÇalıştırılacak Kod:\n")
    print(code)
    print("--------------------------")

    confirm = input("Bu kodu çalıştırmak istediğinize emin misiniz? (E/H): ")
    if confirm.lower() != "e":
        return "Kod çalıştırma işlemi iptal edildi."
    if confirm.lower() == "e":
        with tempfile.NamedTemporaryFile(
            suffix=".py", delete=False, mode="w", encoding="utf-8"
        ) as temp_file:
            temp_file.write(code)
            temp_file_path = temp_file.name
    try:
        result = subprocess.run(
            ["python", temp_file_path],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        os.unlink(temp_file_path)
        if result.returncode == 0:
            return result.stdout
        else:
            return result.stderr
    except subprocess.TimeoutExpired:
        os.unlink(temp_file_path)
        return (
            "Hata: Kod zaman aşımına uğradı (Çok uzun sürdü veya sonsuz döngü oluştu)."
        )
        return result.stdout
    except Exception as e:
        return f"Hata oluştu:\n{e}"
