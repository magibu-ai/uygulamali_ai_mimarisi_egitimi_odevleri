"""HidroRisk'in model tarafindan cagirabilecegi 4 arac.

Her arac sade bir Python fonksiyonudur ve METIN dondurur; bu metin modele
geri beslenir. Hata olursa Turkce bir aciklama doner, sohbet dongusu cokmez.

TOOL_SCHEMAS listesi modele "elinde su araclar var" demenin JSON halidir.
"""

import html
import math
import re
from pathlib import Path
from urllib.parse import urlparse

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import requests
from scipy.stats import gamma, norm


TIMEOUT = 20
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}


# ---------------------------------------------------------------------------
# 1. Rasyonel Yontem - Pik Debi
# ---------------------------------------------------------------------------

def calculate_peak_runoff(
    runoff_coefficient: float,
    rainfall_intensity_mm_h: float,
    catchment_area_ha: float,
) -> str:
    """Rasyonel Yontem ile pik yuzeysel akis debisini hesaplar."""

    try:
        c = float(runoff_coefficient)
        intensity = float(rainfall_intensity_mm_h)
        area = float(catchment_area_ha)
    except (TypeError, ValueError):
        return "Hata: Tum girdiler sayisal olmalidir."

    if not 0 <= c <= 1:
        return "Hata: Akim katsayisi C, 0 ile 1 arasinda olmalidir."

    if intensity <= 0:
        return "Hata: Yagis siddeti sifirdan buyuk olmalidir."

    if area <= 0:
        return "Hata: Havza alani sifirdan buyuk olmalidir."

    # Q = C * i * A / 360
    # i: mm/saat, A: hektar, Q: m3/s
    discharge = c * intensity * area / 360.0

    return (
        "Rasyonel Yontem sonucu:\n"
        f"- Akim katsayisi C: {c:.3f}\n"
        f"- Yagis siddeti: {intensity:.2f} mm/saat\n"
        f"- Havza alani: {area:.2f} ha\n"
        f"- Pik debi: {discharge:.4f} m3/s\n"
        f"- Pik debi: {discharge * 1000:.2f} L/s"
    )


# ---------------------------------------------------------------------------
# 2. Manning - Acik Kanal Kapasitesi
# ---------------------------------------------------------------------------

def check_channel_capacity(
    design_discharge_m3_s: float,
    width_m: float,
    water_depth_m: float,
    manning_n: float,
    bed_slope: float,
) -> str:
    """Dikdortgen acik kanal kapasitesini Manning denklemi ile hesaplar."""

    try:
        design_q = float(design_discharge_m3_s)
        width = float(width_m)
        depth = float(water_depth_m)
        n = float(manning_n)
        slope = float(bed_slope)
    except (TypeError, ValueError):
        return "Hata: Tum girdiler sayisal olmalidir."

    if design_q < 0:
        return "Hata: Tasarim debisi negatif olamaz."

    if width <= 0 or depth <= 0:
        return "Hata: Kanal genisligi ve su derinligi sifirdan buyuk olmalidir."

    if n <= 0:
        return "Hata: Manning n katsayisi sifirdan buyuk olmalidir."

    if slope <= 0:
        return "Hata: Kanal taban egimi sifirdan buyuk olmalidir."

    # Dikdortgen kanal
    area = width * depth
    wetted_perimeter = width + 2 * depth
    hydraulic_radius = area / wetted_perimeter

    velocity = (
        (1 / n)
        * hydraulic_radius ** (2 / 3)
        * math.sqrt(slope)
    )

    capacity = area * velocity
    margin = capacity - design_q

    if capacity >= design_q:
        status = "YETERLI"
    else:
        status = "YETERSIZ"

    return (
        "Manning kanal kapasitesi sonucu:\n"
        f"- Tasarim debisi: {design_q:.4f} m3/s\n"
        f"- Kesit alani: {area:.4f} m2\n"
        f"- Islak cevre: {wetted_perimeter:.4f} m\n"
        f"- Hidrolik yaricap: {hydraulic_radius:.4f} m\n"
        f"- Ortalama hiz: {velocity:.4f} m/s\n"
        f"- Kanal kapasitesi: {capacity:.4f} m3/s\n"
        f"- Kapasite farki: {margin:.4f} m3/s\n"
        f"- Sonuc: {status}\n"
        "Not: Hesap dikdortgen kanal ve uniform akis varsayimina dayanir."
    )


# ---------------------------------------------------------------------------
# 3. SPI - Standartlastirilmis Yagis Indisi
# ---------------------------------------------------------------------------

def _classify_spi(value: float) -> str:
    """SPI degerini temel kuraklik/nemlilik sinifina ayirir."""

    if value >= 2.0:
        return "asiri nemli"
    if value >= 1.5:
        return "cok nemli"
    if value >= 1.0:
        return "orta derecede nemli"
    if value > -1.0:
        return "normale yakin"
    if value > -1.5:
        return "orta derecede kurak"
    if value > -2.0:
        return "siddetli kurak"

    return "asiri kurak"


def calculate_spi(
    file_path: str,
    scale: int = 12,
    date_column: str = "date",
    precipitation_column: str = "precipitation_mm",
) -> str:
    """CSV dosyasindaki aylik yagis verisinden SPI hesaplar."""

    try:
        scale = int(scale)
    except (TypeError, ValueError):
        return "Hata: SPI zaman olcegi tam sayi olmalidir."

    if scale < 1 or scale > 48:
        return "Hata: SPI zaman olcegi 1 ile 48 ay arasinda olmalidir."

    path = Path(file_path)

    if not path.is_absolute():
        path = Path.cwd() / path

    if not path.exists():
        return f"Hata: Dosya bulunamadi: {path}"

    try:
        data = pd.read_csv(path)
    except Exception as exc:
        return f"Hata: CSV okunamadi: {exc}"

    if date_column not in data.columns:
        return f"Hata: '{date_column}' sutunu bulunamadi."

    if precipitation_column not in data.columns:
        return f"Hata: '{precipitation_column}' sutunu bulunamadi."

    data = data[[date_column, precipitation_column]].copy()

    data[date_column] = pd.to_datetime(
        data[date_column],
        errors="coerce",
    )

    data[precipitation_column] = pd.to_numeric(
        data[precipitation_column],
        errors="coerce",
    )

    if data.isna().any().any():
        return "Hata: Tarih veya yagis sutununda eksik/gecersiz deger var."

    if (data[precipitation_column] < 0).any():
        return "Hata: Yagis degerleri negatif olamaz."

    data = data.sort_values(date_column).reset_index(drop=True)

    if len(data) < max(24, scale + 12):
        return (
            "Hata: SPI hesabi icin veri serisi cok kisa. "
            f"Kayit sayisi: {len(data)} ay."
        )

    # Secilen zaman olceginde birikimli yagis
    data["accumulated_precipitation"] = (
        data[precipitation_column]
        .rolling(scale)
        .sum()
    )

    data["spi"] = np.nan

    # Mevsimselligi korumak icin her takvim ayi ayri hesaplanir.
    for month in range(1, 13):

        mask = (
            (data[date_column].dt.month == month)
            & data["accumulated_precipitation"].notna()
        )

        values = data.loc[
            mask,
            "accumulated_precipitation",
        ].to_numpy(dtype=float)

        if len(values) < 4:
            continue

        positive = values[values > 0]

        if len(positive) < 3:
            continue

        zero_probability = np.mean(values == 0)

        try:
            shape, location, gamma_scale = gamma.fit(
                positive,
                floc=0,
            )
        except Exception:
            continue

        probabilities = []

        for value in values:

            if value <= 0:
                probability = zero_probability
            else:
                gamma_probability = gamma.cdf(
                    value,
                    shape,
                    loc=location,
                    scale=gamma_scale,
                )

                probability = (
                    zero_probability
                    + (1 - zero_probability) * gamma_probability
                )

            probability = np.clip(
                probability,
                1e-8,
                1 - 1e-8,
            )

            probabilities.append(probability)

        data.loc[mask, "spi"] = norm.ppf(probabilities)

    valid = data.dropna(subset=["spi"])

    if valid.empty:
        return "Hata: SPI degerleri hesaplanamadi."

    latest = valid.iloc[-1]

    latest_spi = float(latest["spi"])
    latest_date = latest[date_column].strftime("%Y-%m")
    spi_class = _classify_spi(latest_spi)

    output_path = path.with_name(
        f"{path.stem}_spi{scale}.csv"
    )

    output = data.copy()
    output[date_column] = output[date_column].dt.strftime("%Y-%m")
    output.to_csv(output_path, index=False)

    warning = ""

    if len(data) < 360:
        warning = (
            "\n- Uyari: Veri serisi 30 yildan kisadir; "
            "SPI parametreleri daha uzun serilerde daha kararli olabilir."
        )

    return (
        f"SPI-{scale} hesabi tamamlandi:\n"
        f"- Kayit sayisi: {len(data)} ay\n"
        f"- Son tarih: {latest_date}\n"
        f"- Son SPI-{scale}: {latest_spi:.3f}\n"
        f"- Sinif: {spi_class}\n"
        f"- Yorum siniri: Bu SPI-{scale} sinifi yalnizca {latest_date} donemini temsil eder; tum veri serisinin genel durumunu temsil etmez.\n"
        f"- Sonuc dosyasi: {output_path}"
        f"{warning}"
    )

# ---------------------------------------------------------------------------
# 4. SPI GRAFIGI
# ---------------------------------------------------------------------------

def plot_spi_series(
    file_path: str,
    scale: int = 12,
    date_column: str = "date",
) -> str:
    """SPI sonucunu kullanarak zaman serisi grafigi uretir."""

    try:
        scale = int(scale)
    except (TypeError, ValueError):
        return "Hata: SPI zaman olcegi tam sayi olmalidir."

    path = Path(file_path)

    if not path.is_absolute():
        path = Path.cwd() / path

    if not path.exists():
        return f"Hata: Dosya bulunamadi: {path}"

    # Gerekirse once SPI sonuc dosyasini olustur
    spi_result = calculate_spi(
        file_path=str(path),
        scale=scale,
        date_column=date_column,
    )

    if not spi_result.startswith(f"SPI-{scale} hesabi tamamlandi"):
        return f"SPI grafigi olusturulamadi. {spi_result}"

    spi_output_path = path.with_name(f"{path.stem}_spi{scale}.csv")

    if not spi_output_path.exists():
        return f"Hata: SPI sonuc dosyasi bulunamadi: {spi_output_path}"

    try:
        data = pd.read_csv(spi_output_path)
    except Exception as exc:
        return f"Hata: SPI sonuc dosyasi okunamadi: {exc}"

    if date_column not in data.columns:
        return f"Hata: '{date_column}' sutunu sonuc dosyasinda bulunamadi."

    if "spi" not in data.columns:
        return "Hata: Sonuc dosyasinda 'spi' sutunu bulunamadi."

    data = data[[date_column, "spi"]].copy()
    data[date_column] = pd.to_datetime(data[date_column], errors="coerce")
    data["spi"] = pd.to_numeric(data["spi"], errors="coerce")
    data = data.dropna(subset=[date_column, "spi"]).reset_index(drop=True)

    if data.empty:
        return "Hata: Grafik icin kullanilabilir SPI verisi bulunamadi."

    output_dir = Path.cwd() / "outputs"
    output_dir.mkdir(exist_ok=True)

    plot_path = output_dir / f"{path.stem}_spi{scale}_plot.png"

    plt.figure(figsize=(12, 5))
    plt.plot(data[date_column], data["spi"], label=f"SPI-{scale}")
    plt.axhline(0, linestyle="--")
    plt.axhline(1, linestyle=":")
    plt.axhline(-1, linestyle=":")
    plt.axhline(1.5, linestyle=":")
    plt.axhline(-1.5, linestyle=":")
    plt.axhline(2, linestyle=":")
    plt.axhline(-2, linestyle=":")

    plt.yticks([-2, -1.5, -1, 0, 1, 1.5, 2])

    ax = plt.gca()

    for value, label in zip(ax.get_yticks(), ax.get_yticklabels()):
        if abs(value) == 1.5:
            label.set_fontsize(8)
        else:
            label.set_fontsize(10)

    plt.title(f"SPI-{scale} Zaman Serisi")
    plt.xlabel("Tarih")
    plt.ylabel("SPI")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()

    try:
        plt.savefig(plot_path, dpi=150)
    except Exception as exc:
        plt.close()
        return f"Hata: Grafik kaydedilemedi: {exc}"

    plt.close()

    latest_spi = float(data.iloc[-1]["spi"])
    latest_date = data.iloc[-1][date_column].strftime("%Y-%m")
    spi_class = _classify_spi(latest_spi)

    return (
        f"SPI-{scale} grafigi olusturuldu:\n"
        f"- Son tarih: {latest_date}\n"
        f"- Son SPI-{scale}: {latest_spi:.3f}\n"
        f"- Sinif: {spi_class}\n"
        f"- Yorum siniri: Bu SPI-{scale} sinifi yalnizca {latest_date} donemini temsil eder; tum veri serisinin genel durumunu temsil etmez.\n"
        f"- Grafik dosyasi: {plot_path}"
    )

# ---------------------------------------------------------------------------
# 5. Internet Aramasi
# ---------------------------------------------------------------------------

def internet_search(query: str, max_results: int = 5) -> str:
    """DuckDuckGo'nun sade (lite) arayüzünde arama yapar.

    Konuya özel alt sayfaları genel kurum ana sayfalarına göre önceliklendirir.
    """

    try:
        response = requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query},
            headers=HEADERS,
            timeout=TIMEOUT,
        )
        response.raise_for_status()

        pairs = re.findall(
            r"""<a[^>]*href="([^"]+)"[^>]*class=['"]result-link['"][^>]*>(.*?)</a>""",
            response.text,
            flags=re.DOTALL,
        )

        # Filtreleme yapabilmek için istenenden daha fazla aday incelenir.
        candidate_limit = max(max_results * 4, 12)

        specific_results = []
        homepage_results = []
        seen_urls = set()

        for url, raw_title in pairs[:candidate_limit]:
            url = html.unescape(url).strip()

            title = html.unescape(
                re.sub(r"<[^>]+>", "", raw_title)
            ).strip()

            if not title or not url or url in seen_urls:
                continue

            seen_urls.add(url)

            try:
                parsed = urlparse(url)
                path = parsed.path.rstrip("/")

                # Örnek:
                # https://takk.dsi.gov.tr/  -> genel ana sayfa
                # https://dsi.gov.tr/Sayfa/Detay/1872 -> konuya özel alt sayfa
                is_homepage = not path and not parsed.query

            except ValueError:
                is_homepage = False

            item = (title, url)

            if is_homepage:
                homepage_results.append(item)
            else:
                specific_results.append(item)

        # Önce doğrudan içerik/alt sayfalar, yetmezse ana sayfalar.
        ranked_results = specific_results + homepage_results

        selected = ranked_results[:max_results]

        if selected:
            results = []

            for index, (title, url) in enumerate(selected, start=1):
                results.append(
                    f"{index}. {title}\n"
                    f"   {url}"
                )

            return (
                f"'{query}' için internet sonuçları:\n"
                + "\n".join(results)
            )

    except requests.RequestException:
        pass

    return _wikipedia_search(query, max_results)


def _wikipedia_search(query: str, max_results: int) -> str:
    """Yedek arama: Turkce Wikipedia API'si."""

    try:
        data = requests.get(
            "https://tr.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": max_results,
                "format": "json",
            },
            headers=HEADERS,
            timeout=TIMEOUT,
        ).json()

        items = data.get("query", {}).get("search", [])

        if not items:
            return f"'{query}' icin sonuc bulunamadi."

        lines = []

        for i, item in enumerate(items, start=1):
            snippet = html.unescape(
                re.sub(
                    r"<[^>]+>",
                    "",
                    item.get("snippet", ""),
                )
            )

            slug = item["title"].replace(" ", "_")

            lines.append(
                f"{i}. {item['title']}\n"
                f"   {snippet}\n"
                f"   https://tr.wikipedia.org/wiki/{slug}"
            )

        return (
            f"'{query}' icin Wikipedia sonuclari:\n"
            + "\n".join(lines)
        )

    except requests.RequestException as exc:
        return f"Arama yapilamadi: {exc}"


# ---------------------------------------------------------------------------
# Tool isimleri ile Python fonksiyonlarini eslestirir.
# ---------------------------------------------------------------------------

TOOLS = {
    "calculate_peak_runoff": calculate_peak_runoff,
    "check_channel_capacity": check_channel_capacity,
    "calculate_spi": calculate_spi,
    "plot_spi_series": plot_spi_series,
    "internet_search": internet_search,
}


# ---------------------------------------------------------------------------
# Modele gonderilecek tool semalari
# ---------------------------------------------------------------------------

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "calculate_peak_runoff",
            "description": (
                "Rasyonel Yontem ile pik yuzeysel akis debisini hesaplar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "runoff_coefficient": {
                        "type": "number",
                        "description": "Akim katsayisi C, 0-1 arasinda.",
                    },
                    "rainfall_intensity_mm_h": {
                        "type": "number",
                        "description": "Yagis siddeti, mm/saat.",
                    },
                    "catchment_area_ha": {
                        "type": "number",
                        "description": "Havza alani, hektar.",
                    },
                },
                "required": [
                    "runoff_coefficient",
                    "rainfall_intensity_mm_h",
                    "catchment_area_ha",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_channel_capacity",
            "description": (
                "Manning denklemi ile dikdortgen acik kanal kapasitesini "
                "hesaplar ve tasarim debisine gore yeterliligini kontrol eder."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "design_discharge_m3_s": {
                        "type": "number",
                        "description": "Tasarim debisi, m3/s.",
                    },
                    "width_m": {
                        "type": "number",
                        "description": "Kanal genisligi, metre.",
                    },
                    "water_depth_m": {
                        "type": "number",
                        "description": "Su derinligi, metre.",
                    },
                    "manning_n": {
                        "type": "number",
                        "description": "Manning puruzluluk katsayisi.",
                    },
                    "bed_slope": {
                        "type": "number",
                        "description": (
                            "Kanal taban egimi, m/m. "
                            "Ornegin yuzde 0.1 icin 0.001."
                        ),
                    },
                },
                "required": [
                    "design_discharge_m3_s",
                    "width_m",
                    "water_depth_m",
                    "manning_n",
                    "bed_slope",
                ],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_spi",
            "description": (
                "Aylik yagis CSV dosyasindan SPI-1, SPI-3, SPI-6, "
                "SPI-12 gibi Standartlastirilmis Yagis Indisi hesaplar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": (
                            "CSV dosya yolu. Ornek: data/yagis_ornek.csv"
                        ),
                    },
                    "scale": {
                        "type": "integer",
                        "description": (
                            "SPI zaman olcegi. Ornek: 1, 3, 6 veya 12."
                        ),
                    },
                    "date_column": {
                        "type": "string",
                        "description": "Tarih sutunu. Varsayilan: date.",
                    },
                    "precipitation_column": {
                        "type": "string",
                        "description": (
                            "Yagis sutunu. Varsayilan: precipitation_mm."
                        ),
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "plot_spi_series",
            "description": (
                "Aylik yagis CSV dosyasindan secilen zaman olceginde "
                "SPI zaman serisi grafigi olusturur ve PNG dosyasi olarak kaydeder."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": (
                            "CSV dosya yolu. Ornek: data/yagis_ornek.csv"
                        ),
                    },
                    "scale": {
                        "type": "integer",
                        "description": (
                            "SPI zaman olcegi. Ornek: 1, 3, 6 veya 12."
                        ),
                    },
                    "date_column": {
                        "type": "string",
                        "description": "Tarih sutunu. Varsayilan: date.",
                    },
                },
                "required": ["file_path"],
            },
        },
    },
    
    {
        "type": "function",
        "function": {
            "name": "internet_search",
            "description": (
                "Guncel bilgi, standart, mevzuat veya genel bilgi "
                "icin internette arama yapar."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Arama sorgusu.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Sonuc sayisi, varsayilan 5.",
                    },
                },
                "required": ["query"],
            },
        },
    },
]