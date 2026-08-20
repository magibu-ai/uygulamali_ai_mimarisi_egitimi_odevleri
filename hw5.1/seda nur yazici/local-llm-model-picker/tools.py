"""ModelPicker tools."""

import json
import os
import platform
import subprocess

import psutil

import ollama_client


# =============================================================================
# HELPERS
# =============================================================================

def _to_json(data) -> str:

    return json.dumps(
        data,
        ensure_ascii=False,
        indent=2,
    )


def _bytes_to_gib(value) -> float:

    if not value:
        return 0.0

    return round(
        value / (1024 ** 3),
        2,
    )


# =============================================================================
# WINDOWS INFO
# =============================================================================

def _get_windows_info() -> dict:

    if platform.system() != "Windows":

        return {
            "name": platform.system(),
            "version": platform.release(),
            "architecture": platform.machine(),
        }

    try:

        import winreg

        path = (
            r"SOFTWARE\Microsoft\Windows NT"
            r"\CurrentVersion"
        )

        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            path,
        ) as key:

            def read(
                name: str,
                default=None,
            ):

                try:

                    value, _ = (
                        winreg.QueryValueEx(
                            key,
                            name,
                        )
                    )

                    return value

                except FileNotFoundError:

                    return default

            build = str(
                read(
                    "CurrentBuildNumber",
                    "",
                )
            )

            ubr = read(
                "UBR",
                None,
            )

            display_version = read(
                "DisplayVersion",
                "",
            )

            edition_id = read(
                "EditionID",
                "",
            )

            try:

                build_number = int(
                    build
                )

            except (
                TypeError,
                ValueError,
            ):

                build_number = 0

            if build_number >= 22000:

                family = "Windows 11"

            else:

                family = "Windows 10"

            edition_mapping = {
                "Core": "Home",
                "CoreSingleLanguage": (
                    "Home Single Language"
                ),
                "Professional": "Pro",
                "Enterprise": "Enterprise",
                "Education": "Education",
            }

            edition = edition_mapping.get(
                edition_id,
                edition_id,
            )

            name = family

            if edition:

                name += (
                    f" {edition}"
                )

            full_build = build

            if ubr is not None:

                full_build = (
                    f"{build}.{ubr}"
                )

            return {
                "name": name,
                "windows_family": family,
                "edition": edition,
                "display_version": (
                    display_version
                ),
                "build": full_build,
                "architecture": (
                    platform.machine()
                ),
                "source": (
                    "Windows Registry"
                ),
            }

    except Exception as exc:

        return {
            "name": "Windows",
            "version": platform.version(),
            "architecture": platform.machine(),
            "source": "platform fallback",
            "error": str(exc),
        }


# =============================================================================
# CPU
# =============================================================================

def _get_cpu_name() -> str:

    if platform.system() == "Windows":

        try:

            import winreg

            path = (
                r"HARDWARE\DESCRIPTION\System"
                r"\CentralProcessor\0"
            )

            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                path,
            ) as key:

                value, _ = (
                    winreg.QueryValueEx(
                        key,
                        "ProcessorNameString",
                    )
                )

                return str(
                    value
                ).strip()

        except Exception:
            pass

    return (
        platform.processor()
        or os.getenv(
            "PROCESSOR_IDENTIFIER"
        )
        or "Bilinmiyor"
    )


# =============================================================================
# GPU
# =============================================================================

def _get_nvidia_gpus() -> list[dict]:

    command = [
        "nvidia-smi",

        "--query-gpu="
        "name,"
        "memory.total,"
        "memory.used,"
        "memory.free,"
        "utilization.gpu,"
        "driver_version",

        "--format=csv,noheader,nounits",
    ]

    try:

        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=8,
            check=False,
        )

    except (
        FileNotFoundError,
        subprocess.SubprocessError,
    ):

        return []

    if result.returncode != 0:
        return []

    gpus = []

    for line in (
        result.stdout
        .strip()
        .splitlines()
    ):

        parts = [
            part.strip()
            for part
            in line.split(",")
        ]

        if len(parts) != 6:
            continue

        try:

            total_mb = float(
                parts[1]
            )

            used_mb = float(
                parts[2]
            )

            free_mb = float(
                parts[3]
            )

            if total_mb > 0:

                vram_usage = round(
                    used_mb
                    / total_mb
                    * 100,
                    1,
                )

            else:

                vram_usage = None

            gpus.append(
                {
                    "name": parts[0],

                    "vram_total_gb": round(
                        total_mb / 1024,
                        2,
                    ),

                    "vram_used_gb": round(
                        used_mb / 1024,
                        2,
                    ),

                    "vram_free_gb": round(
                        free_mb / 1024,
                        2,
                    ),

                    "vram_usage_percent": (
                        vram_usage
                    ),

                    "gpu_compute_utilization_percent": (
                        float(parts[4])
                    ),

                    "driver_version": (
                        parts[5]
                    ),
                }
            )

        except ValueError:
            continue

    return gpus


# =============================================================================
# MODEL FIND
# =============================================================================

def _find_installed_model(
    model_name: str,
) -> dict:

    requested = (
        model_name
        .strip()
        .lower()
    )

    models = (
        ollama_client.list_models()
    )

    for model in models:

        names = {
            str(
                model.get(
                    "name",
                    "",
                )
            ).lower(),

            str(
                model.get(
                    "model",
                    "",
                )
            ).lower(),
        }

        if requested in names:
            return model

    raise ValueError(
        (
            f"'{model_name}' Ollama'da "
            "kurulu görünmüyor."
        )
    )


# =============================================================================
# TOOL 1 - SYSTEM SPECS
# =============================================================================

def get_system_specs() -> str:
    """Gerçek yerel sistem özelliklerini getirir."""

    memory = (
        psutil.virtual_memory()
    )

    data = {
        "operating_system": (
            _get_windows_info()
        ),

        "cpu": {
            "name": _get_cpu_name(),

            "physical_cores": (
                psutil.cpu_count(
                    logical=False
                )
            ),

            "logical_processors": (
                psutil.cpu_count(
                    logical=True
                )
            ),
        },

        "ram": {
            "total_gb": _bytes_to_gib(
                memory.total
            ),

            "used_gb": _bytes_to_gib(
                memory.used
            ),

            "available_gb": (
                _bytes_to_gib(
                    memory.available
                )
            ),

            "usage_percent": (
                memory.percent
            ),
        },

        "gpu": (
            _get_nvidia_gpus()
        ),
    }

    if not data["gpu"]:

        data["gpu_note"] = (
            "nvidia-smi üzerinden "
            "NVIDIA GPU bilgisi alınamadı."
        )

    return _to_json(
        data
    )


# =============================================================================
# TOOL 2 - LIST OLLAMA MODELS
# =============================================================================

def list_ollama_models(
    include_capabilities: bool = True,
    max_models: int = 20,
) -> str:
    """Bilgisayardaki kurulu Ollama modellerini getirir."""

    installed = (
        ollama_client.list_models()
    )

    try:

        running = (
            ollama_client.running_models()
        )

    except RuntimeError:

        running = []

    running_map = {
        item.get("name"): item
        for item
        in running
    }

    models = []

    for model in installed[
        :max_models
    ]:

        name = model.get(
            "name"
        )

        details = (
            model.get(
                "details"
            )
            or {}
        )

        item = {
            "name": name,

            "parameter_size": (
                details.get(
                    "parameter_size"
                )
            ),

            "quantization": (
                details.get(
                    "quantization_level"
                )
            ),

            "family": (
                details.get(
                    "family"
                )
            ),

            # DİSK BOYUTUDUR.
            # VRAM DEĞİLDİR.
            "disk_size_gb": (
                _bytes_to_gib(
                    model.get(
                        "size",
                        0,
                    )
                )
            ),

            "currently_loaded": (
                name
                in running_map
            ),
        }

        # ---------------------------------------------------------------------
        # RUNNING MODEL
        # ---------------------------------------------------------------------

        if name in running_map:

            runtime = (
                running_map[name]
            )

            item[
                "measured_vram_gb"
            ] = _bytes_to_gib(
                runtime.get(
                    "size_vram",
                    0,
                )
            )

            item[
                "runtime_context_length"
            ] = runtime.get(
                "context_length"
            )

        # ---------------------------------------------------------------------
        # CAPABILITIES
        # ---------------------------------------------------------------------

        if include_capabilities:

            try:

                info = (
                    ollama_client.show_model(
                        name
                    )
                )

                item[
                    "capabilities"
                ] = info.get(
                    "capabilities",
                    [],
                )

                model_info = (
                    info.get(
                        "model_info",
                        {},
                    )
                )

                max_context = None

                for (
                    key,
                    value,
                ) in model_info.items():

                    if key.endswith(
                        ".context_length"
                    ):

                        max_context = (
                            value
                        )

                        break

                item[
                    "max_context_length"
                ] = max_context

            except RuntimeError as exc:

                item[
                    "capabilities_error"
                ] = str(exc)

        models.append(
            item
        )

    return _to_json(
        {
            "installed_model_count": (
                len(installed)
            ),

            "models": models,
        }
    )


# =============================================================================
# TOOL 3 - VRAM
# =============================================================================

def estimate_vram(
    model_name: str,
    context_length: int = 4096,
) -> str:
    """Kurulu modelin VRAM durumunu değerlendirir."""

    model = (
        _find_installed_model(
            model_name
        )
    )

    canonical_name = (
        model.get(
            "name"
        )
    )

    # -------------------------------------------------------------------------
    # MODEL RUNNING → GERÇEK ÖLÇÜM
    # -------------------------------------------------------------------------

    try:

        running = (
            ollama_client.running_models()
        )

    except RuntimeError:

        running = []

    for runtime in running:

        if (
            runtime.get("name")
            != canonical_name
        ):
            continue

        measured_vram = (
            _bytes_to_gib(
                runtime.get(
                    "size_vram",
                    0,
                )
            )
        )

        gpus = (
            _get_nvidia_gpus()
        )

        selected_gpu = None
        model_share = None

        if gpus:

            selected_gpu = max(
                gpus,
                key=lambda gpu: (
                    gpu[
                        "vram_total_gb"
                    ]
                ),
            )

            total_vram = (
                selected_gpu[
                    "vram_total_gb"
                ]
            )

            if total_vram > 0:

                model_share = round(
                    measured_vram
                    / total_vram
                    * 100,
                    1,
                )

        return _to_json(
            {
                "model": (
                    canonical_name
                ),

                "measurement_type": (
                    "ollama_measured"
                ),

                "measured_vram_gb": (
                    measured_vram
                ),

                "model_share_of_total_vram_percent": (
                    model_share
                ),

                "runtime_context_length": (
                    runtime.get(
                        "context_length"
                    )
                ),

                "gpu": (
                    selected_gpu
                ),

                "note": (
                    "measured_vram_gb "
                    "Ollama /api/ps üzerinden "
                    "alınmıştır."
                ),
            }
        )

    # -------------------------------------------------------------------------
    # NOT RUNNING → HEURISTIC
    # -------------------------------------------------------------------------

    disk_size_gb = (
        model.get(
            "size",
            0,
        )
        / (1024 ** 3)
    )

    runtime_overhead = max(
        0.5,
        disk_size_gb * 0.12,
    )

    context_overhead = max(
        0.35,
        0.35
        * (
            context_length
            / 4096
        ),
    )

    estimated_vram = (
        disk_size_gb
        + runtime_overhead
        + context_overhead
    )

    gpus = (
        _get_nvidia_gpus()
    )

    selected_gpu = None

    estimated_share = None

    if gpus:

        selected_gpu = max(
            gpus,
            key=lambda gpu: (
                gpu[
                    "vram_total_gb"
                ]
            ),
        )

        total_vram = (
            selected_gpu[
                "vram_total_gb"
            ]
        )

        if total_vram > 0:

            estimated_share = round(
                estimated_vram
                / total_vram
                * 100,
                1,
            )

    return _to_json(
        {
            "model": canonical_name,

            "measurement_type": (
                "heuristic_estimate"
            ),

            "model_disk_size_gb": (
                round(
                    disk_size_gb,
                    2,
                )
            ),

            "requested_context_length": (
                context_length
            ),

            "estimated_runtime_vram_gb": (
                round(
                    estimated_vram,
                    2,
                )
            ),

            "estimated_share_of_total_vram_percent": (
                estimated_share
            ),

            "gpu": (
                selected_gpu
            ),

            "warning": (
                "Bu gerçek VRAM ölçümü "
                "değildir. Yaklaşık tahmindir."
            ),
        }
    )


# =============================================================================
# TOOL 4 - BENCHMARK
# =============================================================================

def benchmark_model(
    model_name: str,
    runs: int = 2,
) -> str:
    """Modeli gerçek inference ile benchmark eder."""

    model = (
        _find_installed_model(
            model_name
        )
    )

    canonical_name = (
        model.get(
            "name"
        )
    )

    runs = max(
        1,
        min(
            int(runs),
            3,
        ),
    )

    prompt = (
        "Python'da bir listedeki en büyük "
        "elemanı bulmanın iki yöntemini "
        "iki kısa maddede açıkla."
    )

    benchmark_runs = []

    # -------------------------------------------------------------------------
    # INFERENCE TEST
    # -------------------------------------------------------------------------

    for run_number in range(
        1,
        runs + 1,
    ):

        result = (
            ollama_client.chat_raw(
                model=canonical_name,

                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],

                temperature=0.0,
            )
        )

        eval_count = (
            result.get(
                "eval_count",
                0,
            )
        )

        eval_duration = (
            result.get(
                "eval_duration",
                0,
            )
        )

        total_duration = (
            result.get(
                "total_duration",
                0,
            )
        )

        load_duration = (
            result.get(
                "load_duration",
                0,
            )
        )

        tokens_per_second = None

        if (
            eval_count
            and eval_duration
        ):

            seconds = (
                eval_duration
                / 1_000_000_000
            )

            if seconds > 0:

                tokens_per_second = (
                    round(
                        eval_count
                        / seconds,
                        2,
                    )
                )

        benchmark_runs.append(
            {
                "run": run_number,

                "generated_tokens": (
                    eval_count
                ),

                "tokens_per_second": (
                    tokens_per_second
                ),

                "total_seconds": (
                    round(
                        total_duration
                        / 1_000_000_000,
                        3,
                    )
                ),

                "load_seconds": (
                    round(
                        load_duration
                        / 1_000_000_000,
                        3,
                    )
                ),
            }
        )

    # -------------------------------------------------------------------------
    # TOOL CALLING TEST
    # -------------------------------------------------------------------------

    test_tool = [
        {
            "type": "function",

            "function": {
                "name": (
                    "multiply_numbers"
                ),

                "description": (
                    "İki sayıyı çarpar."
                ),

                "parameters": {
                    "type": "object",

                    "properties": {
                        "a": {
                            "type": "number",
                        },

                        "b": {
                            "type": "number",
                        },
                    },

                    "required": [
                        "a",
                        "b",
                    ],
                },
            },
        }
    ]

    tool_calling_test = {
        "passed": False,
    }

    try:

        test_result = (
            ollama_client.chat_raw(
                model=canonical_name,

                messages=[
                    {
                        "role": "user",
                        "content": (
                            "19 ile 7'yi çarpmak "
                            "için verilen aracı kullan."
                        ),
                    }
                ],

                tools=test_tool,

                temperature=0.0,
            )
        )

        tool_calls = (
            test_result
            .get(
                "message",
                {},
            )
            .get(
                "tool_calls",
                [],
            )
        )

        if tool_calls:

            function_data = (
                tool_calls[0]
                .get(
                    "function",
                    {},
                )
            )

            arguments = (
                function_data.get(
                    "arguments",
                    {},
                )
                or {}
            )

            try:

                a = float(
                    arguments.get(
                        "a"
                    )
                )

                b = float(
                    arguments.get(
                        "b"
                    )
                )

                correct_arguments = (
                    sorted([a, b])
                    == [7.0, 19.0]
                )

            except (
                TypeError,
                ValueError,
            ):

                correct_arguments = (
                    False
                )

            tool_calling_test = {
                "passed": (
                    function_data.get(
                        "name"
                    )
                    == "multiply_numbers"
                    and correct_arguments
                ),

                "called_tool": (
                    function_data.get(
                        "name"
                    )
                ),

                "arguments": (
                    arguments
                ),
            }

    except Exception as exc:

        tool_calling_test = {
            "passed": False,
            "error": str(exc),
        }

    # -------------------------------------------------------------------------
    # AVERAGE TPS
    # -------------------------------------------------------------------------

    valid_tps = [
        run[
            "tokens_per_second"
        ]
        for run
        in benchmark_runs
        if run[
            "tokens_per_second"
        ]
        is not None
    ]

    average_tps = None

    if valid_tps:

        average_tps = round(
            sum(valid_tps)
            / len(valid_tps),
            2,
        )

    # -------------------------------------------------------------------------
    # MEASURED VRAM
    # -------------------------------------------------------------------------

    measured_vram = None

    try:

        for runtime in (
            ollama_client.running_models()
        ):

            if (
                runtime.get("name")
                == canonical_name
            ):

                measured_vram = (
                    _bytes_to_gib(
                        runtime.get(
                            "size_vram",
                            0,
                        )
                    )
                )

                break

    except RuntimeError:
        pass

    return _to_json(
        {
            "model": canonical_name,

            "average_tokens_per_second": (
                average_tps
            ),

            "measured_vram_gb": (
                measured_vram
            ),

            "benchmark_runs": (
                benchmark_runs
            ),

            "tool_calling_test": (
                tool_calling_test
            ),
        }
    )


# =============================================================================
# TOOL 5 - INTERNET SEARCH
# =============================================================================

def internet_search(
    query: str,
    max_results: int = 5,
) -> str:
    """Güncel web araması yapar.

    Bir arama motoru sonuç döndürmezse diğer backend'lere sırayla geçer.
    """

    try:
        from ddgs import DDGS

    except ImportError:

        return _to_json(
            {
                "query": query,
                "result_count": 0,
                "results": [],
                "error": (
                    "ddgs paketi kurulu değil. "
                    "'pip install -U ddgs' çalıştırın."
                ),
            }
        )

    max_results = max(
        1,
        min(
            int(max_results),
            10,
        ),
    )

    # "auto" yerine tek tek deniyoruz.
    # Böylece bir backend'in hatası diğer sonuçları düşürmez.
    backends = [
        "google",
        "bing",
        "duckduckgo",
        "brave",
    ]

    errors = []

    for backend in backends:

        try:

            raw_results = DDGS(
                timeout=15,
            ).text(
                query=query,

                # Teknik/global model aramalarında
                # İngilizce global sonuçlar daha kullanışlı.
                region="us-en",

                safesearch="moderate",

                max_results=max_results,

                backend=backend,
            )

            results = []

            for item in (
                raw_results
                or []
            ):

                title = (
                    item.get(
                        "title"
                    )
                    or ""
                ).strip()

                url = (
                    item.get(
                        "href"
                    )
                    or ""
                ).strip()

                snippet = (
                    item.get(
                        "body"
                    )
                    or ""
                ).strip()

                if (
                    not title
                    and not url
                ):
                    continue

                results.append(
                    {
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                    }
                )

            # Bu backend gerçekten sonuç verdiyse dön.
            if results:

                return _to_json(
                    {
                        "query": query,

                        "backend": backend,

                        "result_count": (
                            len(results)
                        ),

                        "results": results,
                    }
                )

        except Exception as exc:

            errors.append(
                {
                    "backend": backend,
                    "error": str(exc),
                }
            )

    # Hiçbir backend sonuç vermedi.
    return _to_json(
        {
            "query": query,

            "result_count": 0,

            "results": [],

            "backends_tried": backends,

            "errors": errors,

            "error": (
                "Denenecek tüm arama backend'leri "
                "sonuç vermedi."
            ),
        }
    )

# =============================================================================
# TOOL REGISTRY
# =============================================================================

TOOLS = {
    "get_system_specs": (
        get_system_specs
    ),

    "list_ollama_models": (
        list_ollama_models
    ),

    "estimate_vram": (
        estimate_vram
    ),

    "benchmark_model": (
        benchmark_model
    ),

    "internet_search": (
        internet_search
    ),
}


# =============================================================================
# TOOL SCHEMAS
# =============================================================================

TOOL_SCHEMAS = [

    # -------------------------------------------------------------------------
    # SYSTEM SPECS
    # -------------------------------------------------------------------------

    {
        "type": "function",

        "function": {
            "name": (
                "get_system_specs"
            ),

            "description": (
                "Kullanıcının gerçek yerel bilgisayarındaki "
                "işletim sistemi, Windows sürümü/build, CPU, "
                "RAM, GPU ve VRAM bilgilerini getirir. "
                "Kullanıcının bilgisayarı veya donanımı "
                "hakkındaki sorularda bu aracı kullan."
            ),

            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },

    # -------------------------------------------------------------------------
    # LIST MODELS
    # -------------------------------------------------------------------------

    {
        "type": "function",

        "function": {
            "name": (
                "list_ollama_models"
            ),

            "description": (
                "Kullanıcının bilgisayarında gerçekten kurulu "
                "olan Ollama modellerini listeler. Model adı, "
                "parameter size, quantization, disk boyutu, "
                "context ve capabilities bilgilerini getirir. "
                "Kurulu modeller veya yerel model seçimi "
                "gerekiyorsa bu aracı kullan. "
                "disk_size_gb VRAM değildir."
            ),

            "parameters": {
                "type": "object",

                "properties": {
                    "include_capabilities": {
                        "type": "boolean",
                        "description": (
                            "Model capability ve metadata "
                            "bilgilerini de getir."
                        ),
                    },

                    "max_models": {
                        "type": "integer",
                        "description": (
                            "Listelenecek maksimum model sayısı."
                        ),
                    },
                },
            },
        },
    },

    # -------------------------------------------------------------------------
    # VRAM
    # -------------------------------------------------------------------------

    {
        "type": "function",

        "function": {
            "name": (
                "estimate_vram"
            ),

            "description": (
                "Ollama'da kurulu belirli bir modelin VRAM "
                "durumunu değerlendirir. Model çalışıyorsa "
                "gerçek Ollama /api/ps VRAM ölçümünü, "
                "çalışmıyorsa yaklaşık heuristic tahmini döndürür. "
                "Kurulu bir modelin kullanıcının GPU'suna "
                "uygunluğunu değerlendirirken kullan."
            ),

            "parameters": {
                "type": "object",

                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": (
                            "Ollama'da kurulu modelin tam adı."
                        ),
                    },

                    "context_length": {
                        "type": "integer",
                        "description": (
                            "Tahmin için kullanılacak çalışma "
                            "context değeri. Varsayılan 4096."
                        ),
                    },
                },

                "required": [
                    "model_name",
                ],
            },
        },
    },

    # -------------------------------------------------------------------------
    # BENCHMARK
    # -------------------------------------------------------------------------

    {
        "type": "function",

        "function": {
            "name": (
                "benchmark_model"
            ),

            "description": (
                "Kurulu bir Ollama modelini gerçekten "
                "çalıştırarak token/s, inference süresi, "
                "VRAM kullanımı ve tool-calling testi yapar. "
                "Kullanıcı benchmark, gerçek hız, token/s, "
                "performans veya tool-calling testi istediğinde kullan."
            ),

            "parameters": {
                "type": "object",

                "properties": {
                    "model_name": {
                        "type": "string",
                        "description": (
                            "Benchmark yapılacak kurulu model."
                        ),
                    },

                    "runs": {
                        "type": "integer",
                        "description": (
                            "Benchmark tekrar sayısı. "
                            "1 ile 3 arasında."
                        ),
                    },
                },

                "required": [
                    "model_name",
                ],
            },
        },
    },

    # -------------------------------------------------------------------------
    # WEB SEARCH
    # -------------------------------------------------------------------------

    {
        "type": "function",

        "function": {
            "name": (
                "internet_search"
            ),

            "description": (
                "Güncel ve zamana duyarlı bilgileri web üzerinde "
                "araştırır. Yeni çıkan LLM modelleri, güncel model "
                "sürümleri, belirli bir yılda çıkan modeller, "
                "son gelişmeler veya internette doğrulanması gereken "
                "bilgiler için kullan. Kullanıcı güncel veya mevcut "
                "zamana bağlı bilgi istediğinde kendi eski model "
                "bilgine güvenmek yerine bu aracı kullan."
            ),

            "parameters": {
                "type": "object",

                "properties": {
                    "query": {
                        "type": "string",
                        "description": (
                            "Web arama sorgusu."
                        ),
                    },

                    "max_results": {
                        "type": "integer",
                        "description": (
                            "Döndürülecek maksimum sonuç sayısı."
                        ),
                    },
                },

                "required": [
                    "query",
                ],
            },
        },
    },
]