# ModelPicker — Local LLM Advisor

import argparse
import inspect
import json
import os
import re
from datetime import datetime

import ollama_client
import tools


# =============================================================================
# SETTINGS
# =============================================================================

DEBUG_TOOLS = os.getenv("DEBUG_TOOLS", "0") == "1"

MAX_AGENT_ROUNDS = 8
MAX_WEB_SEARCHES_PER_TURN = 8
MAX_CURRENT_TECHNICAL_TARGETS = 2
MAX_ALTERNATIVE_TECHNICAL_TARGETS = 6

CURRENT_DATE = datetime.now().astimezone().strftime("%Y-%m-%d")
CURRENT_YEAR = datetime.now().astimezone().year


# =============================================================================
# REGEX / CONSTANTS
# =============================================================================

PARAMETER_ONLY_PATTERN = re.compile(
    r"^\s*\d+(?:\.\d+)?\s*[BT]\s*$",
    re.IGNORECASE,
)

QUANT_ONLY_PATTERN = re.compile(
    (
        r"^\s*("
        r"Q2(?:_[A-Za-z0-9_]+)?|"
        r"Q3(?:_[A-Za-z0-9_]+)?|"
        r"Q4(?:_[A-Za-z0-9_]+)?|"
        r"Q5(?:_[A-Za-z0-9_]+)?|"
        r"Q6(?:_[A-Za-z0-9_]+)?|"
        r"Q8(?:_[A-Za-z0-9_]+)?|"
        r"INT4|INT8|FP8|FP16|BF16|MXFP4|MXFP8"
        r")\s*$"
    ),
    re.IGNORECASE,
)

GPU_ONLY_PATTERN = re.compile(
    r"^\s*(RTX\s*\d+|GTX\s*\d+|RX\s*\d+).*$",
    re.IGNORECASE,
)

RELEASE_WORD_PATTERN = re.compile(
    (
        r"\b("
        r"released|release|"
        r"launched|launch|"
        r"announced|announcement|"
        r"introduced|unveiled|published"
        r")\b"
    ),
    re.IGNORECASE,
)

PARAMETER_MENTION_PATTERN = re.compile(
    r"\b(\d+(?:\.\d+)?)\s*([BT])\b",
    re.IGNORECASE,
)

TOTAL_PARAMETER_PATTERNS = [
    re.compile(
        r"\b(\d+(?:\.\d+)?)\s*([BT])\s+(?:total\s+)?parameters?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\btotal\s+(?:parameter\s+count|parameters?)\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*([BT])\b",
        re.IGNORECASE,
    ),
]

ACTIVE_PARAMETER_PATTERNS = [
    re.compile(
        r"\b(\d+(?:\.\d+)?)\s*([BT])\s+(?:active|activated)\s+parameters?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:active|activated)\s+parameters?\s*[:\-]?\s*(\d+(?:\.\d+)?)\s*([BT])\b",
        re.IGNORECASE,
    ),
]

QUANT_PATTERN = re.compile(
    (
        r"\b("
        r"MXFP4|MXFP8|"
        r"Q2(?:_[A-Za-z0-9_]+)?|"
        r"Q3(?:_[A-Za-z0-9_]+)?|"
        r"Q4(?:_[A-Za-z0-9_]+)?|"
        r"Q5(?:_[A-Za-z0-9_]+)?|"
        r"Q6(?:_[A-Za-z0-9_]+)?|"
        r"Q8(?:_[A-Za-z0-9_]+)?|"
        r"INT4|INT8|FP8|FP16|BF16"
        r")\b"
    ),
    re.IGNORECASE,
)

GENERIC_MODEL_FAMILY_NAMES = {
    "llama",
    "qwen",
    "qwen3",
    "mistral",
    "deepseek",
    "gemma",
    "phi",
    "kimi",
    "gpt",
    "claude",
    "gemini",
    "grok",
}

WEIGHT_BITS_BY_QUANT = {
    "INT4": 4,
    "MXFP4": 4,
    "INT8": 8,
    "FP8": 8,
    "MXFP8": 8,
    "FP16": 16,
    "BF16": 16,
}


# =============================================================================
# SYSTEM PROMPT
# =============================================================================

SYSTEM_PROMPT = f"""
Sen ModelPicker isimli Türkçe konuşan bir Local LLM seçim ve analiz
asistanısın.

Bugünün tarihi:
{CURRENT_DATE}

Şu anki yıl:
{CURRENT_YEAR}

Temel görevin kullanıcının gerçek donanımı, kurulu Ollama modelleri,
VRAM ölçümleri, benchmark sonuçları ve gerektiğinde güncel web
evidence kullanarak kanıta dayalı Local LLM önerisi vermektir.

Tool'lar:

get_system_specs:
Gerçek CPU, RAM, GPU ve VRAM bilgilerini getirir.

list_ollama_models:
Bilgisayarda kurulu Ollama modellerini getirir.

estimate_vram:
Kurulu model için gerçek Ollama /api/ps VRAM ölçümü veya heuristik
tahmin döndürür.

benchmark_model:
Gerçek inference benchmark ve tool-calling testi yapar.

internet_search:
Güncel web bilgisini getirir.

Kurallar:

- Tool sonucunda olmayan teknik bilgi uydurma.
- Test edilmeyen model için kesin performans iddiası üretme.
- currently_loaded=false modelin kurulu olmadığı anlamına gelmez.
- disk_size_gb ile VRAM'i karıştırma.
- measured_vram_gb model VRAM'idir; sistem genelindeki vram_used_gb
  ile aynı şey değildir.
- capabilities içinde tools bulunması gerçek benchmark değildir.
- Güncel release bilgisi gerekiyorsa internet_search kullan.
- Bir modelin {CURRENT_YEAR} tarihli bir rehberde geçmesi, modelin
  {CURRENT_YEAR} yılında yayınlandığını kanıtlamaz.
- Release doğrulaması için model adı + release/launch/announce ifadesi
  + yıl aynı evidence içinde ilişkili olmalıdır.
- 7B, 13B, 2.8T, Q4, MXFP4, 8GB ve RTX 4050 tek başına model adı değildir.
- Web'de açık VRAM gereksinimi yoksa ama toplam parametre sayısı ve
  weight precision/quantization açıkça bulunuyorsa, yalnızca ağırlıklar
  için teorik minimum bellek alt sınırı hesaplanabilir. Bunu gerçek
  runtime VRAM ölçümü gibi sunma.
- MoE modellerde active parameter sayısı, tüm model ağırlıklarının
  bellekte tutulması gerekmeyeceği anlamına gelmez. Donanım alt sınırı
  için mümkünse total parameter count kullan.
- Türkçe, kısa ve teknik cevap ver.
"""


# =============================================================================
# CLI
# =============================================================================

parser = argparse.ArgumentParser(
    description="ModelPicker - Local LLM Advisor"
)

parser.add_argument(
    "--chat-model",
    default=ollama_client.CHAT_MODEL,
    help="Agent modeli",
)

args = parser.parse_args()


# =============================================================================
# TOOL / MODEL HELPERS
# =============================================================================

def get_tool_schemas(allowed_names=None):
    if allowed_names is None:
        return tools.TOOL_SCHEMAS

    allowed = set(allowed_names)

    return [
        schema
        for schema in tools.TOOL_SCHEMAS
        if schema.get("function", {}).get("name") in allowed
    ]


def call_model(messages, allowed_tools=None):
    if allowed_tools == []:
        schemas = None
    elif allowed_tools is None:
        schemas = get_tool_schemas()
    else:
        schemas = get_tool_schemas(allowed_tools)

    return ollama_client.chat(
        messages=messages,
        model=args.chat_model,
        tools=schemas,
        temperature=0.0,
    )


def parse_json(text, default=None):
    if default is None:
        default = {}

    if not text:
        return default

    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return default


def extract_json_object(text):
    if not text:
        return None

    cleaned = text.strip()

    cleaned = re.sub(
        r"^```(?:json)?",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )

    cleaned = re.sub(
        r"```$",
        "",
        cleaned,
    ).strip()

    try:
        value = json.loads(cleaned)
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start == -1 or end == -1 or end <= start:
        return None

    try:
        value = json.loads(cleaned[start:end + 1])
        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    return None


def normalize_arguments(arguments):
    if arguments is None:
        return {}

    if isinstance(arguments, dict):
        return arguments

    if isinstance(arguments, str):
        try:
            parsed = json.loads(arguments)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass

    return {}


def invoke_tool(name, arguments):
    function = tools.TOOLS.get(name)

    if function is None:
        return json.dumps(
            {"error": f"Tool bulunamadı: {name}"},
            ensure_ascii=False,
        )

    signature = inspect.signature(function)
    valid_parameters = set(signature.parameters.keys())

    filtered_arguments = {
        key: value
        for key, value in arguments.items()
        if key in valid_parameters
    }

    try:
        result = function(**filtered_arguments)

        if isinstance(result, str):
            return result

        return json.dumps(
            result,
            ensure_ascii=False,
        )

    except Exception as exc:
        return json.dumps(
            {
                "tool": name,
                "error": str(exc),
            },
            ensure_ascii=False,
        )


def execute_tool_calls(tool_calls, seen_outputs):
    tool_messages = []
    records = []

    for call in tool_calls:
        function_data = call.get("function", {})
        name = function_data.get("name")

        arguments = normalize_arguments(
            function_data.get("arguments")
        )

        signature = (
            name,
            json.dumps(
                arguments,
                ensure_ascii=False,
                sort_keys=True,
            ),
        )

        if signature in seen_outputs:
            output = seen_outputs[signature]

            print(
                f"♻️ {name}({arguments}) [cache]",
                flush=True,
            )
        else:
            print(
                f"🔧 {name}({arguments})",
                flush=True,
            )

            output = invoke_tool(
                name,
                arguments,
            )

            seen_outputs[signature] = output

        if DEBUG_TOOLS:
            print()
            print("--- TOOL OUTPUT ---")
            print(output)
            print("-------------------")
            print()

        tool_messages.append(
            {
                "role": "tool",
                "tool_name": name,
                "content": output,
            }
        )

        records.append(
            {
                "name": name,
                "arguments": arguments,
                "output": output,
            }
        )

    return tool_messages, records


def synthetic_tool_response(tool_name, arguments):
    return {
        "role": "assistant",
        "content": "",
        "tool_calls": [
            {
                "function": {
                    "name": tool_name,
                    "arguments": arguments,
                }
            }
        ],
    }


def execute_response_tools(
    response,
    messages,
    records,
    seen_outputs,
):
    calls = response.get("tool_calls") or []

    if not calls:
        return False

    messages.append(response)

    tool_messages, new_records = execute_tool_calls(
        calls,
        seen_outputs,
    )

    messages.extend(tool_messages)
    records.extend(new_records)

    return True


# =============================================================================
# MESSAGE HELPERS
# =============================================================================

def latest_user_question(messages):
    for message in reversed(messages):
        if message.get("role") == "user":
            return message.get("content") or ""

    return ""


def latest_tool_output(messages, tool_name):
    for message in reversed(messages):
        if (
            message.get("role") == "tool"
            and message.get("tool_name") == tool_name
        ):
            return message.get("content")

    return None


def count_tool(records, tool_name):
    return sum(
        1
        for record in records
        if record.get("name") == tool_name
    )


def recent_conversation_text(
    messages,
    max_messages=6,
):
    selected = []

    for message in reversed(messages):
        if message.get("role") not in {
            "user",
            "assistant",
        }:
            continue

        content = (
            message.get("content")
            or ""
        ).strip()

        if not content:
            continue

        selected.append(
            (
                message.get("role"),
                content,
            )
        )

        if len(selected) >= max_messages:
            break

    selected.reverse()

    return "\n\n".join(
        f"{role.upper()}: {content}"
        for role, content in selected
    )


# =============================================================================
# EVIDENCE PLANNER
# =============================================================================

DEFAULT_EVIDENCE_PLAN = {
    "needs_current_web": False,
    "needs_system_specs": False,
    "needs_installed_models": False,
    "needs_model_vram": False,
    "needs_benchmark": False,
}


def normalize_evidence_plan(data):
    plan = dict(DEFAULT_EVIDENCE_PLAN)

    if isinstance(data, dict):
        for key in plan:
            plan[key] = data.get(key) is True

    if plan["needs_model_vram"]:
        plan["needs_installed_models"] = True
        plan["needs_system_specs"] = True

    if plan["needs_benchmark"]:
        plan["needs_installed_models"] = True

    return plan


def plan_evidence_requirements(messages):
    question = latest_user_question(messages)

    prompt = f"""
EVIDENCE REQUIREMENT PLANNER

Bugünün tarihi:
{CURRENT_DATE}

Kullanıcının son sorusu:

{question}

Bu soruyu doğru ve kanıta dayalı cevaplamak için hangi evidence
kaynaklarının gerekli olduğunu belirle.

SADECE JSON döndür:

{{
  "needs_current_web": false,
  "needs_system_specs": false,
  "needs_installed_models": false,
  "needs_model_vram": false,
  "needs_benchmark": false
}}

needs_current_web:
Güncel bilgi, yeni model, yeni release veya internet doğrulaması
gerekiyorsa true.

needs_system_specs:
Kullanıcının kendi bilgisayarına uygunluk, GPU, RAM veya VRAM
bilgisi gerekiyorsa true.

needs_installed_models:
Kurulu Ollama modelleri gerekiyorsa true.

needs_model_vram:
Kurulu bir modelin runtime VRAM değerlendirmesi gerekiyorsa true.

needs_benchmark:
Gerçek token/s veya benchmark isteniyorsa true.

Örnek:

"{CURRENT_YEAR}'da çıkan local LLM'lerden hangileri benim
bilgisayarıma uygun?"

{{
  "needs_current_web": true,
  "needs_system_specs": true,
  "needs_installed_models": false,
  "needs_model_vram": false,
  "needs_benchmark": false
}}

"Bilgisayarımdaki kurulu modellerden hangisi uygun?"

{{
  "needs_current_web": false,
  "needs_system_specs": true,
  "needs_installed_models": true,
  "needs_model_vram": true,
  "needs_benchmark": false
}}

Markdown veya açıklama yazma.
"""

    response = call_model(
        messages=[
            {
                "role": "system",
                "content": (
                    "Yalnızca evidence gereksinimlerini "
                    "JSON olarak planla."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        allowed_tools=[],
    )

    plan = normalize_evidence_plan(
        extract_json_object(
            response.get("content")
        )
    )

    if DEBUG_TOOLS:
        print(
            "🧭 Evidence plan:",
            json.dumps(
                plan,
                ensure_ascii=False,
            ),
            flush=True,
        )
        print()

    return plan


def web_question_needs_hardware(messages):
    question = latest_user_question(messages)

    prompt = f"""
HARDWARE EVIDENCE CHECK

Kullanıcı sorusu:

{question}

Bu soruyu cevaplamak için kullanıcının gerçek GPU / VRAM / RAM
bilgilerini bilmek gerekiyor mu?

SADECE JSON:

{{
  "needs_hardware": true
}}

veya

{{
  "needs_hardware": false
}}
"""

    response = call_model(
        messages=[
            {
                "role": "system",
                "content": (
                    "Yalnızca hardware evidence gerekip "
                    "gerekmediğine karar ver."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        allowed_tools=[],
    )

    parsed = extract_json_object(
        response.get("content")
    )

    return (
        isinstance(parsed, dict)
        and parsed.get("needs_hardware") is True
    )


# =============================================================================
# SINGLE TOOL REQUESTS
# =============================================================================

def request_single_tool_call(
    messages,
    tool_name,
    instruction,
    fallback_arguments,
):
    response = call_model(
        messages=(
            messages
            + [
                {
                    "role": "user",
                    "content": instruction,
                }
            ]
        ),
        allowed_tools=[tool_name],
    )

    calls = [
        call
        for call in (response.get("tool_calls") or [])
        if (
            call
            .get("function", {})
            .get("name")
            == tool_name
        )
    ]

    if calls:
        result = dict(response)
        result["tool_calls"] = calls[:1]
        return result

    return synthetic_tool_response(
        tool_name,
        fallback_arguments,
    )


def request_system_specs(messages):
    return request_single_tool_call(
        messages=messages,
        tool_name="get_system_specs",
        instruction=(
            "Gerçek sistem donanımı evidence'ı gerekiyor. "
            "Şimdi get_system_specs çağır. Normal cevap üretme."
        ),
        fallback_arguments={},
    )


def request_model_list(messages):
    return request_single_tool_call(
        messages=messages,
        tool_name="list_ollama_models",
        instruction=(
            "Kurulu Ollama modelleri gerekiyor. "
            "Şimdi list_ollama_models çağır. "
            "include_capabilities=true kullan."
        ),
        fallback_arguments={
            "include_capabilities": True,
            "max_models": 20,
        },
    )


def fallback_model_from_installed_list(messages):
    data = parse_json(
        latest_tool_output(
            messages,
            "list_ollama_models",
        )
    )

    models = data.get("models") or []

    for model in models:
        if (
            model.get("currently_loaded") is True
            and model.get("name")
        ):
            return model["name"]

    for model in models:
        if model.get("name"):
            return model["name"]

    return None


def request_estimate_vram(messages):
    fallback_model = (
        fallback_model_from_installed_list(
            messages
        )
    )

    fallback_arguments = {}

    if fallback_model:
        fallback_arguments = {
            "model_name": fallback_model,
            "context_length": 4096,
        }

    response = request_single_tool_call(
        messages=messages,
        tool_name="estimate_vram",
        instruction=(
            "Konuşmada kurulu model listesi mevcut. "
            "Kullanıcının ihtiyacına göre tek modeli seç ve "
            "estimate_vram çağır. context_length=4096 kullan."
        ),
        fallback_arguments=fallback_arguments,
    )

    calls = response.get("tool_calls") or []

    if not calls:
        return None

    arguments = normalize_arguments(
        calls[0]
        .get("function", {})
        .get("arguments")
    )

    if not arguments.get("model_name"):
        return None

    return response


def request_benchmark(messages):
    fallback_model = (
        fallback_model_from_installed_list(
            messages
        )
    )

    fallback_arguments = {}

    if fallback_model:
        fallback_arguments = {
            "model_name": fallback_model,
            "runs": 2,
        }

    response = request_single_tool_call(
        messages=messages,
        tool_name="benchmark_model",
        instruction=(
            "Konuşmada kurulu model listesi mevcut. "
            "Benchmark edilecek modeli seç ve benchmark_model çağır."
        ),
        fallback_arguments=fallback_arguments,
    )

    calls = response.get("tool_calls") or []

    if not calls:
        return None

    arguments = normalize_arguments(
        calls[0]
        .get("function", {})
        .get("arguments")
    )

    if not arguments.get("model_name"):
        return None

    return response


# =============================================================================
# LOCAL FORMATTERS
# =============================================================================

def format_system_specs(raw_json):
    data = parse_json(raw_json)

    os_info = data.get(
        "operating_system",
        {},
    )

    cpu = data.get(
        "cpu",
        {},
    )

    ram = data.get(
        "ram",
        {},
    )

    gpus = data.get(
        "gpu",
        [],
    )

    lines = [
        "Sistem özellikleriniz:",
        "",
        (
            "- İşletim Sistemi: "
            f"{os_info.get('name', 'Bilinmiyor')}"
        ),
        (
            "- CPU: "
            f"{cpu.get('name', 'Bilinmiyor')} "
            f"({cpu.get('physical_cores', '?')} fiziksel / "
            f"{cpu.get('logical_processors', '?')} mantıksal)"
        ),
        (
            "- RAM: "
            f"{ram.get('total_gb', '?')} GB toplam, "
            f"{ram.get('available_gb', '?')} GB kullanılabilir"
        ),
    ]

    for gpu in gpus:
        lines.append(
            (
                "- GPU: "
                f"{gpu.get('name', 'Bilinmiyor')}"
            )
        )

        lines.append(
            (
                "  - VRAM: "
                f"{gpu.get('vram_used_gb', '?')} / "
                f"{gpu.get('vram_total_gb', '?')} GB "
                f"(%{gpu.get('vram_usage_percent', '?')})"
            )
        )

        lines.append(
            (
                "  - Boş VRAM: "
                f"{gpu.get('vram_free_gb', '?')} GB"
            )
        )

    return "\n".join(lines)


def format_benchmark(raw_json):
    data = parse_json(raw_json)

    lines = [
        (
            "Benchmark sonucu: "
            f"{data.get('model', 'Bilinmiyor')}"
        ),
        "",
    ]

    average_tps = data.get(
        "average_tokens_per_second"
    )

    if average_tps is not None:
        lines.append(
            (
                "- Ortalama üretim hızı: "
                f"{average_tps} token/s"
            )
        )

    measured_vram = data.get(
        "measured_vram_gb"
    )

    if measured_vram is not None:
        lines.append(
            (
                "- Ölçülen VRAM: "
                f"{measured_vram} GB"
            )
        )

    test = data.get(
        "tool_calling_test",
        {},
    )

    if test.get("passed") is True:
        lines.append(
            "- Tool-calling testi: Başarılı"
        )
    elif test.get("passed") is False:
        lines.append(
            "- Tool-calling testi: Başarısız"
        )

    return "\n".join(lines)


def format_local_recommendation(messages):
    models_data = parse_json(
        latest_tool_output(
            messages,
            "list_ollama_models",
        )
    )

    vram_data = parse_json(
        latest_tool_output(
            messages,
            "estimate_vram",
        )
    )

    model_name = vram_data.get("model")

    if not model_name:
        return None

    selected = next(
        (
            model
            for model in models_data.get(
                "models",
                [],
            )
            if model.get("name") == model_name
        ),
        {},
    )

    lines = [
        "Önerilen model:",
        f"**{model_name}**",
        "",
    ]

    if selected.get("parameter_size"):
        lines.append(
            (
                "- Parametre: "
                f"{selected['parameter_size']}"
            )
        )

    if selected.get("quantization"):
        lines.append(
            (
                "- Quantization: "
                f"{selected['quantization']}"
            )
        )

    measurement_type = vram_data.get(
        "measurement_type"
    )

    if measurement_type == "ollama_measured":
        lines.append(
            (
                "- Ölçülen model VRAM: "
                f"{vram_data.get('measured_vram_gb')} GB"
            )
        )

        lines.append(
            (
                "- Toplam VRAM kapasitesindeki payı: "
                f"%{vram_data.get('model_share_of_total_vram_percent')}"
            )
        )

    elif measurement_type == "heuristic_estimate":
        lines.append(
            (
                "- Tahmini runtime VRAM: "
                f"{vram_data.get('estimated_runtime_vram_gb')} GB"
            )
        )

        lines.append(
            "- Bu değer gerçek ölçüm değildir."
        )

    gpu = vram_data.get("gpu") or {}

    if gpu:
        lines.append(
            (
                "- GPU: "
                f"{gpu.get('name', 'Bilinmiyor')} "
                f"({gpu.get('vram_total_gb', '?')} GB)"
            )
        )

    if (
        "tools"
        in (
            selected.get(
                "capabilities"
            )
            or []
        )
    ):
        lines.append(
            (
                "- Tool capability: metadata'da mevcut; "
                "benchmark sonucu değildir."
            )
        )

    alternatives = []

    for model in models_data.get(
        "models",
        [],
    ):
        if model.get("name") == model_name:
            continue

        alternatives.append(
            (
                f"{model.get('name')} "
                f"({model.get('parameter_size', '?')}, "
                f"{model.get('quantization', '?')})"
            )
        )

    if alternatives:
        lines.append("")
        lines.append(
            "Diğer kurulu modeller:"
        )

        for item in alternatives:
            lines.append(
                f"- {item}"
            )

        lines.append(
            (
                "Bu modeller bu turda ayrıca VRAM veya "
                "benchmark açısından test edilmedi."
            )
        )

    return "\n".join(lines)


# =============================================================================
# WEB RESULT COLLECTION
# =============================================================================

def collect_web_results(records):
    results = []
    seen = set()

    for record in records:
        if record.get("name") != "internet_search":
            continue

        data = parse_json(
            record.get("output")
        )

        for item in (
            data.get("results")
            or []
        ):
            title = (
                item.get("title")
                or ""
            ).strip()

            url = (
                item.get("url")
                or item.get("href")
                or ""
            ).strip()

            snippet = (
                item.get("snippet")
                or item.get("body")
                or ""
            ).strip()

            key = (
                url.lower()
                or title.lower()
            )

            if not key:
                continue

            if key in seen:
                continue

            seen.add(key)

            results.append(
                {
                    "title": title,
                    "url": url,
                    "snippet": snippet,
                }
            )

    return results


def normalize_match_text(text):
    text = (
        text
        or ""
    ).lower()

    text = (
        text
        .replace("–", "-")
        .replace("—", "-")
    )

    text = re.sub(
        r"[^\w.\-\s]",
        " ",
        text,
        flags=re.UNICODE,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


# =============================================================================
# MODEL NAME / RELEASE VALIDATION
# =============================================================================

def is_valid_model_candidate(name):
    if not name:
        return False

    name = name.strip()

    if len(name) < 2:
        return False

    if PARAMETER_ONLY_PATTERN.fullmatch(name):
        return False

    if QUANT_ONLY_PATTERN.fullmatch(name):
        return False

    if GPU_ONLY_PATTERN.fullmatch(name):
        return False

    if (
        name.lower()
        in GENERIC_MODEL_FAMILY_NAMES
    ):
        return False

    if name.lower() in {
        "ollama",
        "gguf",
        "local llm",
        "llm",
        "model",
        "models",
        "vram",
        "ram",
        "gb",
    }:
        return False

    return True



def normalize_model_match_text(
    text,
):
    """
    Model adı eşleştirmesi için separator-insensitive canonical form.

    Örnek:
      Qwen 3.5
      Qwen3.5
      Qwen-3.5
      Qwen_3.5

    hepsi aynı canonical anahtara yaklaşır.

    Noktayı koruyoruz; böylece 3.5 ile 35 aynı şey sayılmaz.
    """
    normalized = normalize_match_text(
        text
    ).lower()

    normalized = re.sub(
        r"[\s\-_:/]+",
        "",
        normalized,
    )

    normalized = re.sub(
        r"[^a-z0-9.]+",
        "",
        normalized,
    )

    return normalized.strip()


def source_contains_candidate(
    candidate_name,
    source,
):
    candidate_key = normalize_model_match_text(
        candidate_name
    )

    source_key = normalize_model_match_text(
        (
            source.get("title", "")
            + " "
            + source.get("snippet", "")
        )
    )

    return (
        bool(candidate_key)
        and
        candidate_key in source_key
    )


def split_evidence_fragments(text):
    if not text:
        return []

    parts = re.split(
        r"(?<=[.!?;])\s+|\s+[|•]\s+",
        text,
    )

    return [
        part.strip()
        for part in parts
        if part.strip()
    ]


def explicit_release_years_for_source(
    model_name,
    source,
):
    """
    Bir modelin release yılını yalnızca model-adı + release/availability
    ifadesi + yıl aynı source alanında birbirine yakınsa kabul eder.

    Kritik güvenlik kuralı:
    - Bir snippet içinde hem makalenin 2026 tarihi hem de modelin gerçek
      2025 release tarihi varsa bütün yılları toplamaz.
    - Release ifadesine / model adına EN YAKIN yılı seçer.
    - "available/downloadable" gibi yıllar sonra da doğru olabilecek
      ifadeler release kanıtı sayılmaz.
    """

    candidate_pattern = model_name_regex(
        model_name
    )

    if candidate_pattern is None:
        return []

    years = []

    # Güçlü release kelimeleri.
    release_pattern = RELEASE_WORD_PATTERN

    # "open weights are live" gibi gerçekten yayınlanma anını işaret eden
    # availability ifadeleri. "available" ve "downloadable" özellikle yok;
    # çünkü eski bir model 2026'da hâlâ available olabilir.
    weights_live_pattern = re.compile(
        (
            r"\b(?:full\s+)?(?:open[- ]weights?|public\s+weights?|weights?)\b"
            r".{0,50}"
            r"\b(?:are\s+|is\s+)?"
            r"(?:live|published|released)\b"
        ),
        re.IGNORECASE,
    )

    for field in (
        source.get("title", "") or "",
        source.get("snippet", "") or "",
    ):
        if not field:
            continue

        fragments = (
            split_evidence_fragments(
                field
            )
            or [field]
        )

        for fragment in fragments:
            candidate_matches = list(
                candidate_pattern.finditer(
                    fragment
                )
            )

            if not candidate_matches:
                continue

            year_matches = list(
                re.finditer(
                    r"\b(20\d{2})\b",
                    fragment,
                )
            )

            if not year_matches:
                continue

            # ---------------------------------------------------------
            # 1) Normal release evidence
            # ---------------------------------------------------------
            for release_match in release_pattern.finditer(
                fragment
            ):
                nearest_candidate = min(
                    candidate_matches,
                    key=lambda match: abs(
                        match.start()
                        - release_match.start()
                    ),
                )

                candidate_release_distance = abs(
                    nearest_candidate.start()
                    - release_match.start()
                )

                if candidate_release_distance > 140:
                    continue

                # Yılı bütün fragment'tan toplamak yerine release ifadesine
                # en yakın olan yılı seç.
                nearest_year = min(
                    year_matches,
                    key=lambda match: min(
                        abs(
                            match.start()
                            - release_match.start()
                        ),
                        abs(
                            match.start()
                            - nearest_candidate.start()
                        ),
                    ),
                )

                year_distance = min(
                    abs(
                        nearest_year.start()
                        - release_match.start()
                    ),
                    abs(
                        nearest_year.start()
                        - nearest_candidate.start()
                    ),
                )

                if year_distance <= 180:
                    years.append(
                        int(
                            nearest_year.group(1)
                        )
                    )

            # ---------------------------------------------------------
            # 2) "open weights are live/published/released" fallback
            # ---------------------------------------------------------
            for availability_match in weights_live_pattern.finditer(
                fragment
            ):
                nearest_candidate = min(
                    candidate_matches,
                    key=lambda match: abs(
                        match.start()
                        - availability_match.start()
                    ),
                )

                if (
                    abs(
                        nearest_candidate.start()
                        - availability_match.start()
                    )
                    > 180
                ):
                    continue

                nearest_year = min(
                    year_matches,
                    key=lambda match: min(
                        abs(
                            match.start()
                            - availability_match.start()
                        ),
                        abs(
                            match.start()
                            - nearest_candidate.start()
                        ),
                    ),
                )

                year_distance = min(
                    abs(
                        nearest_year.start()
                        - availability_match.start()
                    ),
                    abs(
                        nearest_year.start()
                        - nearest_candidate.start()
                    ),
                )

                if year_distance <= 180:
                    years.append(
                        int(
                            nearest_year.group(1)
                        )
                    )

    return sorted(
        set(
            years
        )
    )


def strongest_release_evidence(
    model_name,
    web_results,
):
    """
    LLM'in verdiği tek source_index'e bağlı kalmaz.
    Model tüm web sonuçlarında taranır ve en güçlü release evidence seçilir.
    """
    other_year_candidate = None

    for index, source in enumerate(
        web_results,
        start=1,
    ):
        if not source_contains_candidate(
            model_name,
            source,
        ):
            continue

        years = explicit_release_years_for_source(
            model_name,
            source,
        )

        if CURRENT_YEAR in years:
            return {
                "release_verified": True,
                "release_year": CURRENT_YEAR,
                "source_index": index,
                "source": source,
            }

        if (
            years
            and other_year_candidate is None
        ):
            other_year_candidate = {
                "release_verified": True,
                "release_year": years[0],
                "source_index": index,
                "source": source,
            }

    if other_year_candidate is not None:
        return other_year_candidate

    return {
        "release_verified": False,
        "release_year": None,
        "source_index": None,
        "source": None,
    }




# =============================================================================
# LOCAL / OPEN-WEIGHT EVIDENCE
# =============================================================================

LOCAL_WEIGHT_STRONG_POSITIVE_PATTERNS = [
    re.compile(
        r"\b(?:released|published|downloadable|public)\s+(?:model\s+)?weights?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bweights?\s+(?:were\s+|are\s+|is\s+)?(?:released|published|available|downloadable|public)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bopen[- ]weights?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:GGUF|llama\.cpp)\b",
        re.IGNORECASE,
    ),
]

LOCAL_WEIGHT_WEAK_POSITIVE_PATTERNS = [
    re.compile(
        r"\b(?:run|running|runs)\b.{0,45}\blocally\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\blocal\s+(?:inference|deployment|deployment guide|setup)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bOllama\b",
        re.IGNORECASE,
    ),
]

LOCAL_WEIGHT_NEGATIVE_PATTERNS = [
    re.compile(
        r"\b(?:weights?|open[- ]weights?)\b.{0,45}\b(?:not|isn't|aren't|unavailable|unreleased|not confirmed)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:not|no)\b.{0,30}\b(?:public|open)[- ]?weights?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bweights?\b.{0,45}\b(?:scheduled|planned)\b.{0,30}\brelease\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:API[- ]only|cloud[- ]hosted|proprietary)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\blocal\s*=\s*WIP\b",
        re.IGNORECASE,
    ),
]


def _candidate_evidence_fragments(
    model_name,
    source,
):
    """
    Yalnız model adının geçtiği title/snippet fragment'larını döndürür.
    """
    candidate_pattern = model_name_regex(
        model_name
    ) if 'model_name_regex' in globals() else None

    fragments = []

    for field_name in (
        'title',
        'snippet',
    ):
        field = (
            source.get(field_name, '')
            or ''
        ).strip()

        if not field:
            continue

        parts = (
            split_evidence_fragments(field)
            or [field]
        )

        for part in parts:
            if candidate_pattern is not None:
                matched = bool(
                    candidate_pattern.search(part)
                )
            else:
                matched = (
                    normalize_model_match_text(model_name)
                    in normalize_model_match_text(part)
                )

            if matched:
                fragments.append(part)

    return fragments


def strongest_local_weights_evidence(
    model_name,
    web_results,
):
    """
    Modelin gerçekten indirilebilir/local ağırlık evidence'ını tüm web
    sonuçlarında arar.

    status:
      verified     -> güçlü local/open-weight evidence var
      contradicted -> açık negative evidence var ve güçlü positive yok
      unknown      -> yeterli evidence yok

    URL tabanlı güçlü sinyaller:
      - ollama.com/library/...   -> local runnable artifact
      - huggingface.co/...GGUF   -> indirilebilir GGUF artifact
    """
    best_positive = None
    best_negative = None

    for index, source in enumerate(
        web_results,
        start=1,
    ):
        if not source_contains_candidate(
            model_name,
            source,
        ):
            continue

        source_url = (
            source.get("url", "")
            or ""
        ).lower()

        source_title = (
            source.get("title", "")
            or ""
        ).lower()

        # URL-level evidence. This is stronger than generic prose.
        url_positive = False

        if "ollama.com/library/" in source_url:
            url_positive = True

        if (
            "huggingface.co/" in source_url
            and (
                "gguf" in source_url
                or "gguf" in source_title
            )
        ):
            url_positive = True

        if url_positive:
            candidate = {
                "status": "verified",
                "strength": 4,
                "source_index": index,
                "source": source,
                "fragment": (
                    source.get("title", "")
                    or source.get("snippet", "")
                ),
            }

            if (
                best_positive is None
                or candidate["strength"]
                > best_positive["strength"]
            ):
                best_positive = candidate

        fragments = _candidate_evidence_fragments(
            model_name,
            source,
        )

        for fragment in fragments:
            negative = any(
                pattern.search(fragment)
                for pattern in LOCAL_WEIGHT_NEGATIVE_PATTERNS
            )

            strong_positive = any(
                pattern.search(fragment)
                for pattern in LOCAL_WEIGHT_STRONG_POSITIVE_PATTERNS
            )

            weak_positive = any(
                pattern.search(fragment)
                for pattern in LOCAL_WEIGHT_WEAK_POSITIVE_PATTERNS
            )

            if strong_positive and not negative:
                candidate = {
                    "status": "verified",
                    "strength": 3,
                    "source_index": index,
                    "source": source,
                    "fragment": fragment,
                }

                if (
                    best_positive is None
                    or candidate["strength"]
                    > best_positive["strength"]
                ):
                    best_positive = candidate

            elif weak_positive and not negative:
                candidate = {
                    "status": "verified",
                    "strength": 2,
                    "source_index": index,
                    "source": source,
                    "fragment": fragment,
                }

                if (
                    best_positive is None
                    or candidate["strength"]
                    > best_positive["strength"]
                ):
                    best_positive = candidate

            if negative:
                candidate = {
                    "status": "contradicted",
                    "strength": 3,
                    "source_index": index,
                    "source": source,
                    "fragment": fragment,
                }

                if best_negative is None:
                    best_negative = candidate

    if best_positive is not None:
        return best_positive

    if best_negative is not None:
        return best_negative

    return {
        "status": "unknown",
        "strength": 0,
        "source_index": None,
        "source": None,
        "fragment": None,
    }

def candidate_local_weights_status(
    candidate,
):
    return candidate.get(
        'local_weights_status',
        'unknown',
    )


# =============================================================================
# STRUCTURED WEB MODEL EXTRACTION
# =============================================================================

def extract_structured_web_candidates(
    messages,
    web_results,
):
    if not web_results:
        return []

    evidence_lines = []

    for index, item in enumerate(
        web_results,
        start=1,
    ):
        evidence_lines.extend(
            [
                f"SOURCE {index}",
                (
                    "TITLE: "
                    + item.get(
                        "title",
                        "",
                    )
                ),
                (
                    "SNIPPET: "
                    + item.get(
                        "snippet",
                        "",
                    )
                ),
                "",
            ]
        )

    evidence_text = "\n".join(evidence_lines)

    prompt = f"""
STRUCTURED WEB MODEL EXTRACTION

Bugünün yılı:
{CURRENT_YEAR}

Kullanıcının sorusu:

{latest_user_question(messages)}

Gerçek web evidence:

{evidence_text}

Sadece evidence içindeki gerçek ve mümkün olduğunca TAM model veya
varyant isimlerini çıkar.

DeepSeek, Mistral, Llama, Qwen, Kimi, GPT, Claude, Gemini gibi
yalnız aile adı yazma. Sadece sürüm/model adı gerçekten spesifikse candidate
oluştur. Örn. Qwen 3.5, Gemma 4, Kimi K3, GPT-5.6 kabul; GPT veya Claude tek
başına kabul edilmez.

SADECE JSON:

{{
  "candidates": [
    {{
      "model_name": "tam model adı",
      "source_index": 1
    }}
  ]
}}

Kaynakta olmayan model veya sürüm ekleme.

ÇOK ÖNEMLİ:
- Seçim/ranking yapma.
- Evidence içinde literal olarak geçen TÜM model adlarını çıkar.
- Virgülle veya tire ile sıralanan model listelerinde hiçbir modeli atlama.
- Aynı source içinde birden fazla model varsa hepsini ayrı candidate yaz.
- Family + varyant birlikte yazılmışsa mümkün olan en spesifik adı kullan.

7B, 2.8T, Q4, MXFP4, 8GB, RTX 4090, Ollama ve GGUF tek başına
model adı değildir.

Markdown veya açıklama yazma.
"""

    response = call_model(
        messages=[
            {
                "role": "system",
                "content": (
                    "Yalnızca verilen web evidence üzerinden "
                    "structured model extraction yap."
                ),
            },
            {
                "role": "user",
                "content": prompt,
            },
        ],
        allowed_tools=[],
    )

    parsed = extract_json_object(
        response.get("content")
    )

    if not parsed:
        return []

    first_candidates = (
        parsed.get("candidates")
        or []
    )

    # -------------------------------------------------------------
    # Coverage audit
    #
    # 4B extraction modeli özellikle uzun, virgülle sıralanmış source
    # listelerinde bir modeli atlayabiliyor. İkinci, tool'suz local LLM
    # çağrısı yalnız coverage kontrolü yapar. Web search değildir.
    # -------------------------------------------------------------
    already_found_names = []

    for item in first_candidates:
        if not isinstance(item, dict):
            continue

        name = (
            item.get("model_name")
            or ""
        ).strip()

        if name:
            already_found_names.append(
                name
            )

    coverage_prompt = f"""
MODEL EXTRACTION COVERAGE AUDIT

Gerçek web evidence:

{evidence_text}

İlk extraction'ın bulduğu model adları:
{json.dumps(already_found_names, ensure_ascii=False)}

Görev:
Evidence içinde literal olarak geçen TÜM gerçek model adlarını yeniden tara.

Özellikle:
- virgülle sıralanan model listelerinde hiçbir adı atlama,
- yalnız family adı yerine source'taki en spesifik adı kullan,
- ilk listede eksik kalan adları da ekle,
- kaynakta olmayan hiçbir modeli uydurma,
- 7B, Q4, VRAM, Ollama, GGUF gibi teknik değerleri model adı sayma.
- GPT, Claude, Gemini, Llama, Qwen, Mistral gibi yalnızca genel aile adlarını candidate yazma.
- Ancak GPT-5.6, Qwen 3.5, Gemma 4, Kimi K3 gibi sürüm/model adı spesifikse yaz.

SADECE JSON:

{{
  "candidates": [
    {{
      "model_name": "tam model adı",
      "source_index": 1
    }}
  ]
}}
"""

    coverage_response = call_model(
        messages=[
            {
                "role": "system",
                "content": (
                    "Web evidence içindeki model adları için "
                    "coverage audit yap. Hiçbir literal model adını atlama."
                ),
            },
            {
                "role": "user",
                "content": coverage_prompt,
            },
        ],
        allowed_tools=[],
    )

    coverage_parsed = extract_json_object(
        coverage_response.get(
            "content"
        )
    )

    coverage_candidates = []

    if coverage_parsed:
        coverage_candidates = (
            coverage_parsed.get(
                "candidates"
            )
            or []
        )

    candidate_items = (
        list(first_candidates)
        + list(coverage_candidates)
    )

    merged = {}
    order = []

    for candidate in candidate_items:
        if not isinstance(candidate, dict):
            continue

        model_name = (
            candidate.get("model_name")
            or ""
        ).strip()

        if not is_valid_model_candidate(
            model_name
        ):
            continue

        try:
            source_index = int(
                candidate.get(
                    "source_index"
                )
            )
        except (TypeError, ValueError):
            continue

        if not (
            1
            <= source_index
            <= len(web_results)
        ):
            continue

        source = web_results[
            source_index - 1
        ]

        if not source_contains_candidate(
            model_name,
            source,
        ):
            continue

        model_key = normalize_model_match_text(
            model_name
        )

        release = strongest_release_evidence(
            model_name,
            web_results,
        )

        display_source = (
            release.get("source")
            or source
        )

        display_source_index = (
            release.get("source_index")
            or source_index
        )

        local_weights = strongest_local_weights_evidence(
            model_name,
            web_results,
        )

        entry = {
            "model_name": model_name,
            "source_index": display_source_index,
            "source": display_source,
            "release_year": release.get(
                "release_year"
            ),
            "release_verified": (
                release.get(
                    "release_verified"
                )
                is True
            ),
            "local_weights_status": local_weights.get(
                "status",
                "unknown",
            ),
            "local_weights_source": local_weights.get(
                "source"
            ),
            "local_weights_source_index": local_weights.get(
                "source_index"
            ),
        }

        if model_key not in merged:
            merged[model_key] = entry
            order.append(model_key)
            continue

        old = merged[model_key]

        if (
            entry["release_verified"]
            and not old["release_verified"]
        ):
            merged[model_key] = entry

        elif (
            entry["release_verified"]
            and old["release_verified"]
            and entry["release_year"] == CURRENT_YEAR
            and old["release_year"] != CURRENT_YEAR
        ):
            merged[model_key] = entry

    return [
        merged[key]
        for key in order
    ]


def candidate_related_results(
    candidate_name,
    web_results,
):
    related = []

    for item in web_results:
        if source_contains_candidate(
            candidate_name,
            item,
        ):
            related.append(
                item
            )

    return related

def candidate_context_windows(
    text,
    candidate_name,
    before=70,
    after=160,
):
    if not text or not candidate_name:
        return []

    lower_text = text.lower()
    lower_candidate = (
        candidate_name.lower()
    )

    windows = []
    offset = 0

    while True:
        index = lower_text.find(
            lower_candidate,
            offset,
        )

        if index == -1:
            break

        left = max(
            0,
            index - before,
        )

        right = min(
            len(text),
            (
                index
                + len(candidate_name)
                + after
            ),
        )

        windows.append(
            text[left:right]
        )

        offset = (
            index
            + len(candidate_name)
        )

    return windows


# =============================================================================
# TECHNICAL FACT EXTRACTION
# =============================================================================

def parameter_to_billions(
    value,
    unit,
):
    value = float(value)
    unit = unit.upper()

    if unit == "T":
        return value * 1000.0

    return value


def format_parameter_value(
    value_b,
):
    if value_b >= 1000:
        value_t = value_b / 1000.0

        if value_t.is_integer():
            return f"{int(value_t)}T"

        return (
            f"{value_t:.3f}"
            .rstrip("0")
            .rstrip(".")
            + "T"
        )

    if float(value_b).is_integer():
        return f"{int(value_b)}B"

    return (
        f"{value_b:.3f}"
        .rstrip("0")
        .rstrip(".")
        + "B"
    )


def extract_parameter_facts(
    text,
):
    """
    Dönüş:
    {
        "all_b": [...],
        "total_b": [...],
        "active_b": [...]
    }

    T değerlerini B karşılığına çevirir.
    2.8T -> 2800B
    """

    text = text or ""

    all_values = []

    for match in PARAMETER_MENTION_PATTERN.finditer(
        text
    ):
        value_b = parameter_to_billions(
            match.group(1),
            match.group(2),
        )

        if 0 < value_b <= 100000:
            all_values.append(value_b)

    total_values = []

    for pattern in TOTAL_PARAMETER_PATTERNS:
        for match in pattern.finditer(text):
            value_b = parameter_to_billions(
                match.group(1),
                match.group(2),
            )

            if 0 < value_b <= 100000:
                total_values.append(value_b)

    active_values = []

    for pattern in ACTIVE_PARAMETER_PATTERNS:
        for match in pattern.finditer(text):
            value_b = parameter_to_billions(
                match.group(1),
                match.group(2),
            )

            if 0 < value_b <= 100000:
                active_values.append(value_b)

    return {
        "all_b": sorted(set(all_values)),
        "total_b": sorted(set(total_values)),
        "active_b": sorted(set(active_values)),
    }


def extract_quantizations(text):
    values = [
        match.group(1).upper()
        for match in QUANT_PATTERN.finditer(
            text or ""
        )
    ]

    return list(
        dict.fromkeys(values)
    )


def extract_vram_values(text):
    values = []

    patterns = [
        re.compile(
            (
                r"\b(\d+(?:\.\d+)?)\s*GB"
                r"\s*(?:of\s*)?VRAM\b"
            ),
            re.IGNORECASE,
        ),
        re.compile(
            (
                r"\bVRAM\b"
                r"[^0-9]{0,30}"
                r"(\d+(?:\.\d+)?)\s*GB"
            ),
            re.IGNORECASE,
        ),
        re.compile(
            (
                r"(?:requires?|needs?|minimum)"
                r"[^0-9]{0,25}"
                r"(\d+(?:\.\d+)?)\s*GB"
                r"[^.]{0,25}"
                r"VRAM"
            ),
            re.IGNORECASE,
        ),
    ]

    for pattern in patterns:
        for match in pattern.finditer(
            text or ""
        ):
            try:
                value = float(
                    match.group(1)
                )
            except ValueError:
                continue

            if 0 < value <= 2048:
                values.append(value)

    return sorted(set(values))


def quantization_weight_bits(
    quantizations,
):
    """
    Weight precision için en uygun bit bilgisini bulur.

    Q4_K_M -> 4
    MXFP4  -> 4
    INT4   -> 4
    FP8    -> 8

    Birden fazla değer varsa ağırlık formatı olma ihtimali en güçlü olan
    düşük precision'ı seçer. Bu yalnızca teorik minimum weight-memory
    alt sınırı içindir.
    """

    bit_values = []

    for quant in quantizations:
        q = quant.upper()

        if q in WEIGHT_BITS_BY_QUANT:
            bit_values.append(
                WEIGHT_BITS_BY_QUANT[q]
            )
            continue

        match = re.match(
            r"Q([2-8])",
            q,
        )

        if match:
            bit_values.append(
                int(match.group(1))
            )

    if not bit_values:
        return None

    return min(bit_values)


def theoretical_weight_memory_gib(
    parameter_count_b,
    bits_per_weight,
):
    """
    Sadece model ağırlıkları için teorik minimum bellek.

    KV cache, activations, runtime overhead, allocator overhead ve
    framework memory dahil değildir.
    """

    total_bits = (
        parameter_count_b
        * 1_000_000_000
        * bits_per_weight
    )

    total_bytes = (
        total_bits / 8.0
    )

    return (
        total_bytes
        / (1024 ** 3)
    )


def model_name_regex(
    candidate_name,
):
    """
    Qwen 3.5 / Qwen3.5 / Qwen-3.5 gibi varyasyonları eşler.
    """
    tokens = re.findall(
        r"[A-Za-z]+|\d+(?:\.\d+)?",
        candidate_name or "",
    )

    if not tokens:
        return None

    separator = r"[\s\-_:/]*"

    pattern = (
        r"\b"
        + separator.join(
            re.escape(token)
            for token in tokens
        )
        + r"\b"
    )

    return re.compile(
        pattern,
        re.IGNORECASE,
    )

def candidate_bound_fragments(
    candidate_name,
    web_results,
):
    """
    Yalnızca candidate adının gerçekten geçtiği title/snippet parçalarını
    teknik fact extraction'a sokar.
    """
    candidate_pattern = model_name_regex(
        candidate_name
    )

    if candidate_pattern is None:
        return []

    fragments = []

    for item in candidate_related_results(
        candidate_name,
        web_results,
    ):
        for field_name in (
            "title",
            "snippet",
        ):
            field = (
                item.get(
                    field_name,
                    ""
                )
                or ""
            ).strip()

            if not field:
                continue

            parts = (
                split_evidence_fragments(
                    field
                )
                or [field]
            )

            for part in parts:
                if candidate_pattern.search(
                    part
                ):
                    fragments.append(
                        {
                            "text": part,
                            "source": item,
                            "field": field_name,
                        }
                    )

    return fragments


def _parameter_mentions_with_positions(
    text,
):
    mentions = []

    for match in PARAMETER_MENTION_PATTERN.finditer(
        text or ""
    ):
        value_b = parameter_to_billions(
            match.group(1),
            match.group(2),
        )

        if 0 < value_b <= 100000:
            mentions.append(
                {
                    "start": match.start(),
                    "end": match.end(),
                    "value_b": value_b,
                    "raw": match.group(0),
                }
            )

    return mentions


def _quant_mentions_with_positions(
    text,
):
    return [
        {
            "start": match.start(),
            "end": match.end(),
            "value": match.group(1).upper(),
        }
        for match in QUANT_PATTERN.finditer(
            text or ""
        )
    ]


def _vram_mentions_with_positions(
    text,
):
    patterns = [
        re.compile(
            r"\b(\d+(?:\.\d+)?)\s*GB\s*(?:of\s*)?VRAM\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\bVRAM\b[^0-9]{0,30}(\d+(?:\.\d+)?)\s*GB",
            re.IGNORECASE,
        ),
        re.compile(
            (
                r"(?:requires?|needs?|minimum)"
                r"[^0-9]{0,25}"
                r"(\d+(?:\.\d+)?)\s*GB"
                r"[^.]{0,25}VRAM"
            ),
            re.IGNORECASE,
        ),
    ]

    mentions = []

    for pattern in patterns:
        for match in pattern.finditer(
            text or ""
        ):
            try:
                value = float(
                    match.group(1)
                )
            except ValueError:
                continue

            if 0 < value <= 2048:
                mentions.append(
                    {
                        "start": match.start(),
                        "end": match.end(),
                        "value": value,
                    }
                )

    return mentions


def _nearest_forward_distance(
    candidate_matches,
    fact_start,
):
    """
    Fact'in candidate'dan SONRA gelmesini ister.

    Böylece:
    'Qwen 27B ... Gemma 4'
    gibi snippet'te 27B değeri Gemma 4'e bağlanmaz.
    """
    distances = []

    for candidate_match in candidate_matches:
        if (
            fact_start
            < candidate_match.end()
        ):
            continue

        distances.append(
            fact_start
            - candidate_match.end()
        )

    if not distances:
        return None

    return min(
        distances
    )


def extract_candidate_technical_facts(
    candidate_name,
    web_results,
):
    """
    False-positive öncelikli güvenli extraction.

    - Model adındaki 7B/27B gibi size candidate'a aittir.
    - Diğer fact'ler yalnız candidate adından SONRA ve yakınsa bağlanır.
    - Başka modellerden önce gelen 27B/35B/Q8/BF16 değerleri candidate'a
      taşınmaz.
    - Active parameter değeri full model weight-memory hesabında kullanılmaz.
    """

    name_parameter_facts = (
        extract_parameter_facts(
            candidate_name
        )
    )

    all_parameters_b = list(
        name_parameter_facts[
            "all_b"
        ]
    )

    total_parameters_b = []
    active_parameters_b = []
    vram_values = []
    quantizations = []

    candidate_pattern = model_name_regex(
        candidate_name
    )

    fragments = candidate_bound_fragments(
        candidate_name,
        web_results,
    )

    for fragment_info in fragments:
        fragment = fragment_info[
            "text"
        ]

        if candidate_pattern is None:
            continue

        candidate_matches = list(
            candidate_pattern.finditer(
                fragment
            )
        )

        if not candidate_matches:
            continue

        # ---------------------------------------------------------------------
        # PARAMETER FACTS
        # ---------------------------------------------------------------------
        for mention in _parameter_mentions_with_positions(
            fragment
        ):
            distance = _nearest_forward_distance(
                candidate_matches,
                mention["start"],
            )

            if distance is None:
                continue

            # Model adında açık size varsa snippet'teki başka size değerlerini
            # aynı modele eklemiyoruz.
            if (
                name_parameter_facts["all_b"]
                and
                mention["value_b"]
                not in name_parameter_facts["all_b"]
            ):
                continue

            local_left = max(
                0,
                mention["start"] - 35,
            )

            local_right = min(
                len(fragment),
                mention["end"] + 45,
            )

            local_text = fragment[
                local_left:local_right
            ]

            is_active = bool(
                re.search(
                    r"\b(active|activated)\b",
                    local_text,
                    re.IGNORECASE,
                )
            )

            is_total = bool(
                re.search(
                    r"\b(total|parameters?|parameter-count)\b",
                    local_text,
                    re.IGNORECASE,
                )
            )

            if is_active:
                if distance <= 120:
                    active_parameters_b.append(
                        mention["value_b"]
                    )
                    all_parameters_b.append(
                        mention["value_b"]
                    )
                continue

            if is_total:
                if distance <= 90:
                    total_parameters_b.append(
                        mention["value_b"]
                    )
                    all_parameters_b.append(
                        mention["value_b"]
                    )
                continue

            if distance <= 35:
                all_parameters_b.append(
                    mention["value_b"]
                )

        # ---------------------------------------------------------------------
        # QUANTIZATION / WEIGHT PRECISION
        # ---------------------------------------------------------------------
        for mention in _quant_mentions_with_positions(
            fragment
        ):
            distance = _nearest_forward_distance(
                candidate_matches,
                mention["start"],
            )

            if (
                distance is not None
                and distance <= 80
            ):
                quantizations.append(
                    mention["value"]
                )

        # ---------------------------------------------------------------------
        # EXPLICIT VRAM
        # ---------------------------------------------------------------------
        for mention in _vram_mentions_with_positions(
            fragment
        ):
            distance = _nearest_forward_distance(
                candidate_matches,
                mention["start"],
            )

            if (
                distance is not None
                and distance <= 140
            ):
                vram_values.append(
                    mention["value"]
                )

    all_parameters_b = sorted(
        set(
            all_parameters_b
        )
    )

    total_parameters_b = sorted(
        set(
            total_parameters_b
        )
    )

    active_parameters_b = sorted(
        set(
            active_parameters_b
        )
    )

    vram_values = sorted(
        set(
            vram_values
        )
    )

    quantizations = list(
        dict.fromkeys(
            quantizations
        )
    )

    weight_bits = quantization_weight_bits(
        quantizations
    )

    parameter_basis_b = None
    parameter_basis_type = None

    if total_parameters_b:
        parameter_basis_b = max(
            total_parameters_b
        )
        parameter_basis_type = (
            "total_parameters"
        )

    elif len(
        name_parameter_facts["all_b"]
    ) == 1:
        parameter_basis_b = (
            name_parameter_facts[
                "all_b"
            ][0]
        )
        parameter_basis_type = (
            "model_name_parameter"
        )

    elif (
        len(all_parameters_b) == 1
        and not active_parameters_b
    ):
        parameter_basis_b = (
            all_parameters_b[0]
        )
        parameter_basis_type = (
            "single_candidate_bound_parameter"
        )

    estimated_min_weight_gib = None

    if (
        parameter_basis_b is not None
        and
        weight_bits is not None
    ):
        estimated_min_weight_gib = (
            theoretical_weight_memory_gib(
                parameter_basis_b,
                weight_bits,
            )
        )

    return {
        "all_parameters_b": all_parameters_b,
        "total_parameters_b": (
            total_parameters_b
        ),
        "active_parameters_b": (
            active_parameters_b
        ),
        "vram_values": vram_values,
        "quantizations": quantizations,
        "weight_bits": weight_bits,
        "parameter_basis_b": (
            parameter_basis_b
        ),
        "parameter_basis_type": (
            parameter_basis_type
        ),
        "estimated_min_weight_gib": (
            estimated_min_weight_gib
        ),
    }


# =============================================================================
# RELEASE / CURRENT-YEAR HELPERS
# =============================================================================

def candidate_release_status(candidate):
    if (
        candidate.get(
            "release_verified"
        )
        is True
        and
        candidate.get(
            "release_year"
        )
        == CURRENT_YEAR
    ):
        return "current_year"

    if (
        candidate.get(
            "release_verified"
        )
        is True
        and
        candidate.get(
            "release_year"
        )
        is not None
    ):
        return "other_year"

    return "unknown"


def candidate_has_current_year_source(
    candidate_name,
    web_results,
):
    year = str(CURRENT_YEAR)

    for item in candidate_related_results(
        candidate_name,
        web_results,
    ):
        text = (
            item.get("title", "")
            + " "
            + item.get("snippet", "")
        )

        if year in text:
            return True

    return False


# =============================================================================
# WEB SEARCHES
# =============================================================================

def request_initial_web_search(messages):
    """
    İlk search deterministic.
    Release discovery'yi 7B / Q4 / 6GB gibi filtrelerle bozma.
    """

    return synthetic_tool_response(
        "internet_search",
        {
            "query": (
                f"{CURRENT_YEAR} newly released open weight LLM "
                "official release announcement local language model"
            ),
            "max_results": 5,
        },
    )


def need_second_discovery_search(
    messages,
    records,
):
    if (
        count_tool(
            records,
            "internet_search",
        )
        != 1
    ):
        return False

    web_results = collect_web_results(
        records
    )

    candidates = (
        extract_structured_web_candidates(
            messages,
            web_results,
        )
    )

    verified = [
        candidate
        for candidate in candidates
        if (
            candidate_release_status(
                candidate
            )
            == "current_year"
        )
    ]

    return len(verified) < 2


def request_second_discovery_search(
    messages,
):
    return synthetic_tool_response(
        "internet_search",
        {
            "query": (
                f"{CURRENT_YEAR} new open source open weight LLM "
                "released announced official model launch "
                "local inference"
            ),
            "max_results": 5,
        },
    )


def _unique_model_names(
    names,
):
    unique = []
    seen = set()

    for name in names:
        key = normalize_model_match_text(
            name
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(name)

    return unique


def refresh_candidate_evidence(
    candidate,
    web_results,
):
    """
    Discovery sırasında bulunan candidate adını korur; web sonuçları
    büyüdükçe yalnız evidence alanlarını yeniden hesaplar.

    Böylece 4B extractor daha sonraki uzun evidence listesinde eski bir
    candidate'ı unutsa bile candidate kaybolmaz.
    """
    name = candidate["model_name"]

    release = strongest_release_evidence(
        name,
        web_results,
    )

    local_weights = strongest_local_weights_evidence(
        name,
        web_results,
    )

    refreshed = dict(candidate)

    if release.get("release_verified") is True:
        refreshed["release_verified"] = True
        refreshed["release_year"] = release.get(
            "release_year"
        )
        refreshed["source"] = (
            release.get("source")
            or refreshed.get("source")
        )
        refreshed["source_index"] = (
            release.get("source_index")
            or refreshed.get("source_index")
        )

    refreshed["local_weights_status"] = (
        local_weights.get(
            "status",
            refreshed.get(
                "local_weights_status",
                "unknown",
            ),
        )
    )

    refreshed["local_weights_source"] = (
        local_weights.get("source")
        or refreshed.get(
            "local_weights_source"
        )
    )

    refreshed["local_weights_source_index"] = (
        local_weights.get("source_index")
        or refreshed.get(
            "local_weights_source_index"
        )
    )

    return refreshed


def discover_direct_size_variants(
    seed_candidates,
    web_results,
):
    """
    Discovery family adından doğrudan türeyen size varyantlarını
    web evidence içinden deterministik olarak çıkarır.

    Kabul örnekleri:
      Qwen3.5-0.8B
      Qwen 3.5 9B
      Gemma 4 12B

    Red örneği:
      Phi-4-mini-reasoning ... 3.8B
    çünkü size family adından hemen sonra gelmez.
    """
    variants = []
    seen = set()

    for seed in seed_candidates or []:
        seed_name = (
            seed.get("model_name")
            or ""
        ).strip()

        if not is_specific_release_family_name(
            seed_name
        ):
            continue

        family_pattern = model_name_regex(
            seed_name
        )

        if family_pattern is None:
            continue

        for source in web_results:
            for field_name in (
                "title",
                "snippet",
            ):
                field = (
                    source.get(
                        field_name,
                        ""
                    )
                    or ""
                )

                for family_match in family_pattern.finditer(
                    field
                ):
                    tail = field[
                        family_match.end():
                        family_match.end() + 24
                    ]

                    size_match = re.match(
                        (
                            r"[\s\-_:/]*"
                            r"(\d+(?:\.\d+)?)\s*([Bb])\b"
                        ),
                        tail,
                        re.IGNORECASE,
                    )

                    if not size_match:
                        continue

                    size_value = (
                        size_match.group(1)
                        + "B"
                    )

                    variant_name = (
                        seed_name.rstrip()
                        + "-"
                        + size_value
                    )

                    variant_key = normalize_model_match_text(
                        variant_name
                    )

                    if variant_key in seen:
                        continue

                    seen.add(
                        variant_key
                    )

                    release = strongest_release_evidence(
                        seed_name,
                        web_results,
                    )

                    local_weights = strongest_local_weights_evidence(
                        variant_name,
                        web_results,
                    )

                    variants.append(
                        {
                            "model_name": variant_name,
                            "source_index": (
                                local_weights.get(
                                    "source_index"
                                )
                                or release.get(
                                    "source_index"
                                )
                                or seed.get(
                                    "source_index"
                                )
                            ),
                            "source": (
                                local_weights.get(
                                    "source"
                                )
                                or release.get(
                                    "source"
                                )
                                or seed.get(
                                    "source"
                                )
                            ),
                            "release_year": (
                                release.get(
                                    "release_year"
                                )
                                or seed.get(
                                    "release_year"
                                )
                            ),
                            "release_verified": (
                                release.get(
                                    "release_verified"
                                )
                                is True
                                or seed.get(
                                    "release_verified"
                                )
                                is True
                            ),
                            "release_inherited_from_family": (
                                seed_name
                            ),
                            "local_weights_status": (
                                local_weights.get(
                                    "status",
                                    "unknown",
                                )
                            ),
                            "local_weights_source": (
                                local_weights.get(
                                    "source"
                                )
                            ),
                            "local_weights_source_index": (
                                local_weights.get(
                                    "source_index"
                                )
                            ),
                        }
                    )

    return variants


def merge_candidate_sets(
    seed_candidates,
    fresh_candidates,
    web_results,
):
    """
    Seed discovery candidates + daha sonraki technical-search'te keşfedilen
    spesifik varyantları birleştirir.
    """
    merged = {}
    order = []

    for candidate in (
        list(seed_candidates or [])
        + list(fresh_candidates or [])
    ):
        if not isinstance(candidate, dict):
            continue

        name = (
            candidate.get("model_name")
            or ""
        ).strip()

        if not name:
            continue

        key = normalize_model_match_text(
            name
        )

        refreshed = refresh_candidate_evidence(
            candidate,
            web_results,
        )

        if key not in merged:
            merged[key] = refreshed
            order.append(key)
            continue

        old = merged[key]

        # Release/local evidence daha güçlüyse yeni entry kazanır.
        old_score = (
            2 if old.get("release_verified") else 0
        ) + (
            1 if old.get("local_weights_status") == "verified" else 0
        )

        new_score = (
            2 if refreshed.get("release_verified") else 0
        ) + (
            1 if refreshed.get("local_weights_status") == "verified" else 0
        )

        if new_score > old_score:
            merged[key] = refreshed

    return [
        merged[key]
        for key in order
    ]


def is_specific_release_family_name(
    model_name,
):
    """
    Family release inheritance için seed adının yeterince spesifik
    olması gerekir.

    Kabul:
      Qwen 3.5
      Gemma 4
      Kimi K3
      Llama 4

    Red:
      GPT
      Claude
      Gemini
      Llama
      Qwen
    """
    if not is_valid_model_candidate(
        model_name
    ):
        return False

    normalized = normalize_model_match_text(
        model_name
    )

    if (
        normalized
        in GENERIC_MODEL_FAMILY_NAMES
    ):
        return False

    return bool(
        re.search(
            r"\d",
            normalized,
        )
    )


def inherit_release_from_seed_family(
    candidates,
    seed_candidates,
):
    """
    Technical search sırasında bulunan spesifik varyant, örneğin
    qwen3.5:4b, discovery'de doğrulanmış Qwen 3.5 ailesine aitse ve
    varyant local artifact olarak doğrulanmışsa family release yılını
    miras alabilir.

    Bu yalnız current runtime yılı içinde keşfedilen family/variant için
    kullanılır; user-text keyword routing değildir.
    """
    seed_current = []

    for seed in seed_candidates or []:
        if (
            candidate_release_status(seed)
            == "current_year"
            and
            is_specific_release_family_name(
                seed.get(
                    "model_name",
                    "",
                )
            )
        ):
            seed_current.append(seed)

    result = []

    for candidate in candidates:
        candidate = dict(candidate)

        if (
            candidate_release_status(candidate)
            == "current_year"
        ):
            result.append(candidate)
            continue

        if (
            candidate_local_weights_status(candidate)
            != "verified"
        ):
            result.append(candidate)
            continue

        candidate_key = normalize_model_match_text(
            candidate["model_name"]
        )

        inherited = None

        for seed in seed_current:
            seed_key = normalize_model_match_text(
                seed["model_name"]
            )

            if (
                candidate_key != seed_key
                and candidate_key.startswith(
                    seed_key
                )
            ):
                inherited = seed
                break

        if inherited is not None:
            candidate["release_verified"] = True
            candidate["release_year"] = CURRENT_YEAR
            candidate["source"] = (
                inherited.get("source")
                or candidate.get("source")
            )
            candidate["source_index"] = (
                inherited.get("source_index")
                or candidate.get("source_index")
            )
            candidate[
                "release_inherited_from_family"
            ] = inherited["model_name"]

        result.append(candidate)

    return result


def current_release_technical_targets(
    messages,
    records,
    seed_candidates=None,
):
    """
    Discovery sırasında doğrulanan current-year release adaylarını
    model-spesifik araştırır.

    Öncelik:
      1) local/open-weight evidence zaten doğrulanmış aday
      2) source'unda open-weight/local sinyali bulunan aday
      3) diğer current-year adaylar

    Generic GPT / Claude / Gemini gibi family adları candidate olamaz.
    """
    web_results = collect_web_results(
        records
    )

    if seed_candidates is None:
        candidates = extract_structured_web_candidates(
            messages,
            web_results,
        )
    else:
        candidates = merge_candidate_sets(
            seed_candidates,
            [],
            web_results,
        )

    scored = []

    for order, candidate in enumerate(
        candidates
    ):
        if (
            candidate_release_status(
                candidate
            )
            != "current_year"
        ):
            continue

        name = (
            candidate.get(
                "model_name"
            )
            or ""
        ).strip()

        if not is_valid_model_candidate(
            name
        ):
            continue

        local_status = (
            candidate_local_weights_status(
                candidate
            )
        )

        if local_status == "verified":
            priority = 0
        else:
            priority = 2

            for source in candidate_related_results(
                name,
                web_results,
            ):
                source_text = (
                    source.get(
                        "title",
                        ""
                    )
                    + " "
                    + source.get(
                        "snippet",
                        ""
                    )
                ).lower()

                if (
                    "open-weight" in source_text
                    or
                    "open weight" in source_text
                    or
                    "open weights" in source_text
                    or
                    "local" in source_text
                    or
                    "ollama" in source_text
                    or
                    "gguf" in source_text
                    or
                    "hugging face" in source_text
                ):
                    priority = 1
                    break

        scored.append(
            (
                priority,
                order,
                name,
            )
        )

    scored.sort()

    return _unique_model_names(
        [
            item[2]
            for item in scored
        ]
    )[:MAX_CURRENT_TECHNICAL_TARGETS]

def _preliminary_candidate_size_b(
    candidate_name,
    web_results,
):
    facts = extract_candidate_technical_facts(
        candidate_name,
        web_results,
    )

    values = (
        facts.get('total_parameters_b')
        or facts.get('all_parameters_b')
        or []
    )

    if not values:
        return None

    return min(values)


def alternative_technical_targets(
    messages,
    records,
):
    """
    Current-year local adaylardan uygun model bulunamazsa, current-year
    odaklı kaynaklarda geçen eski/güncel alternatifleri araştırır.

    Bilinen parameter size varsa daha küçük adaylara öncelik verir.
    Örneğin 3.8B gibi bir aday, size'ı bilinmeyen dev modellerden önce gelir.
    """
    web_results = collect_web_results(
        records
    )

    candidates = extract_structured_web_candidates(
        messages,
        web_results,
    )

    scored = []

    for order, candidate in enumerate(candidates):
        if (
            candidate_release_status(candidate)
            == 'current_year'
        ):
            continue

        name = candidate['model_name']

        if not candidate_has_current_year_source(
            name,
            web_results,
        ):
            continue

        size_b = _preliminary_candidate_size_b(
            name,
            web_results,
        )

        scored.append(
            (
                0 if size_b is not None else 1,
                size_b if size_b is not None else float('inf'),
                order,
                name,
            )
        )

    scored.sort()

    return _unique_model_names(
        [item[3] for item in scored]
    )[:MAX_ALTERNATIVE_TECHNICAL_TARGETS]


def has_suitable_current_local_candidate(
    messages,
    records,
    seed_candidates=None,
):
    web_results = collect_web_results(
        records
    )

    fresh_candidates = extract_structured_web_candidates(
        messages,
        web_results,
    )

    deterministic_variants = discover_direct_size_variants(
        seed_candidates or [],
        web_results,
    )

    candidates = merge_candidate_sets(
        seed_candidates or [],
        (
            list(fresh_candidates)
            + list(deterministic_variants)
        ),
        web_results,
    )

    candidates = inherit_release_from_seed_family(
        candidates,
        seed_candidates or [],
    )

    system_data = parse_json(
        latest_tool_output(
            messages,
            "get_system_specs",
        )
    )

    gpus = system_data.get("gpu") or []

    total_vram = (
        gpus[0].get("vram_total_gb")
        if gpus
        else None
    )

    for candidate in candidates:
        if (
            candidate_release_status(candidate)
            != "current_year"
        ):
            continue

        if (
            candidate_local_weights_status(candidate)
            != "verified"
        ):
            continue

        facts = extract_candidate_technical_facts(
            candidate["model_name"],
            web_results,
        )

        hardware = get_hardware_status(
            facts,
            total_vram,
        )

        if (
            hardware.get("status")
            == "potentially_suitable"
        ):
            return True

    return False


def build_technical_search_query_for_candidate(
    candidate_name,
):
    clean_name = candidate_name.replace(
        '"',
        "",
    )

    return (
        f'"{clean_name}" '
        f"{CURRENT_YEAR} released release date "
        "official GitHub Hugging Face ModelScope "
        "Ollama tags model variants small sizes "
        "0.8B 1B 2B 3B 4B 7B 8B 9B "
        "open weights GGUF Q4_K_M Q4 "
        "minimum VRAM model size local inference"
    )

def request_technical_web_search_for_candidate(
    candidate_name,
):
    return synthetic_tool_response(
        "internet_search",
        {
            "query": (
                build_technical_search_query_for_candidate(
                    candidate_name
                )
            ),
            "max_results": 5,
        },
    )


# =============================================================================
# HARDWARE SUITABILITY
# =============================================================================

def get_hardware_status(
    facts,
    total_vram,
):
    """
    Öncelik:
    1. Açık runtime VRAM evidence
    2. Total parameter count + weight quantization ile teorik minimum
       weight-memory alt sınırı
    3. Unknown

    theoretical_weight_memory gerçek runtime VRAM değildir.
    """

    explicit_vram = (
        facts.get("vram_values")
        or []
    )

    if (
        total_vram is not None
        and explicit_vram
    ):
        lowest = min(explicit_vram)

        if lowest <= total_vram:
            return {
                "status": (
                    "potentially_suitable"
                ),
                "reason": "explicit_vram",
                "lowest_vram": lowest,
            }

        return {
            "status": "too_large",
            "reason": "explicit_vram",
            "lowest_vram": lowest,
        }

    estimated_min_weight_gib = (
        facts.get(
            "estimated_min_weight_gib"
        )
    )

    if (
        total_vram is not None
        and
        estimated_min_weight_gib
        is not None
    ):
        # Minimum weight memory bile fiziksel VRAM'i aşıyorsa
        # local full-GPU inference adayı değildir.
        if (
            estimated_min_weight_gib
            > total_vram
        ):
            return {
                "status": "too_large",
                "reason": (
                    "theoretical_weight_memory"
                ),
                "estimated_min_weight_gib": (
                    estimated_min_weight_gib
                ),
            }

        return {
            "status": (
                "potentially_suitable"
            ),
            "reason": (
                "theoretical_weight_memory"
            ),
            "estimated_min_weight_gib": (
                estimated_min_weight_gib
            ),
        }

    return {
        "status": "unknown",
        "reason": "insufficient_evidence",
    }


def format_parameter_list(values):
    return ", ".join(
        format_parameter_value(
            value
        )
        for value in values
    )


def unique_candidate_source_urls(
    candidate_name,
    web_results,
):
    urls = []

    for item in candidate_related_results(
        candidate_name,
        web_results,
    ):
        url = item.get("url")

        if url and url not in urls:
            urls.append(url)

    return urls


# =============================================================================
# WEB CANDIDATE FORMATTER
# =============================================================================

def append_web_candidate(
    lines,
    candidate,
    web_results,
    total_vram,
    alternative=False,
):
    name = candidate["model_name"]

    facts = (
        extract_candidate_technical_facts(
            name,
            web_results,
        )
    )

    status = candidate_release_status(
        candidate
    )

    lines.append(
        f"**{name}**"
    )

    if status == "current_year":
        inherited_from = candidate.get(
            "release_inherited_from_family"
        )

        if inherited_from:
            lines.append(
                (
                    f"- Release: {CURRENT_YEAR} yılında çıkan "
                    f"{inherited_from} ailesinin local varyantı olarak "
                    "doğrulandı."
                )
            )
        else:
            lines.append(
                (
                    f"- Release: {CURRENT_YEAR} release'i "
                    "açık web evidence ile doğrulandı."
                )
            )

    elif status == "other_year":
        lines.append(
            (
                "- Release: Evidence içindeki doğrulanmış yıl "
                f"{candidate.get('release_year')}; "
                f"{CURRENT_YEAR} release'i değildir."
            )
        )

    else:
        lines.append(
            (
                f"- Release: {CURRENT_YEAR} yılında "
                "yayınlandığı doğrulanmadı."
            )
        )

    if alternative:
        lines.append(
            (
                f"- Neden gösteriliyor: {CURRENT_YEAR} odaklı "
                "güncel Local LLM kaynaklarında geçiyor."
            )
        )

    local_status = candidate_local_weights_status(
        candidate
    )

    if local_status == "verified":
        lines.append(
            "- Local/open-weight erişimi: doğrulandı."
        )
    elif local_status == "contradicted":
        lines.append(
            (
                "- Local/open-weight erişimi: mevcut evidence içinde "
                "açık biçimde desteklenmiyor veya ters evidence var."
            )
        )
    else:
        lines.append(
            (
                "- Local/open-weight erişimi: doğrulanamadı; "
                "bu nedenle gerçek local aday olarak kabul edilmiyor."
            )
        )

    total_params = (
        facts.get(
            "total_parameters_b"
        )
        or []
    )

    active_params = (
        facts.get(
            "active_parameters_b"
        )
        or []
    )

    all_params = (
        facts.get(
            "all_parameters_b"
        )
        or []
    )

    if total_params:
        lines.append(
            (
                "- Toplam parametre: "
                + format_parameter_list(
                    total_params
                )
            )
        )

    if active_params:
        lines.append(
            (
                "- Aktif parametre: "
                + format_parameter_list(
                    active_params
                )
            )
        )

    if (
        not total_params
        and
        not active_params
        and
        all_params
    ):
        lines.append(
            (
                "- Parametre evidence: "
                + format_parameter_list(
                    all_params
                )
            )
        )

    quantizations = (
        facts.get(
            "quantizations"
        )
        or []
    )

    if quantizations:
        lines.append(
            (
                "- Weight/precision evidence: "
                + ", ".join(
                    quantizations
                )
            )
        )

    explicit_vram = (
        facts.get(
            "vram_values"
        )
        or []
    )

    if explicit_vram:
        lines.append(
            (
                "- Runtime VRAM evidence: "
                + ", ".join(
                    f"{value:g} GB"
                    for value in explicit_vram
                )
            )
        )

    min_weight_gib = (
        facts.get(
            "estimated_min_weight_gib"
        )
    )

    if min_weight_gib is not None:
        basis = facts.get(
            "parameter_basis_b"
        )

        bits = facts.get(
            "weight_bits"
        )

        lines.append(
            (
                "- Teorik minimum ağırlık belleği: "
                f"yaklaşık {min_weight_gib:.1f} GiB "
                f"({format_parameter_value(basis)}, "
                f"{bits}-bit weight varsayımı)."
            )
        )

        lines.append(
            (
                "  Bu yalnızca ağırlıkların teorik alt sınırıdır; "
                "KV cache, activations ve runtime overhead dahil değildir."
            )
        )

    hardware = get_hardware_status(
        facts,
        total_vram,
    )

    if (
        hardware["status"]
        == "potentially_suitable"
    ):
        if (
            hardware["reason"]
            == "explicit_vram"
        ):
            lines.append(
                (
                    "- Donanım değerlendirmesi: "
                    f"En düşük açık VRAM gereksinimi "
                    f"{hardware['lowest_vram']:g} GB. "
                    f"Mevcut {total_vram:g} GB GPU VRAM "
                    "açısından potansiyel olarak uygun."
                )
            )

        else:
            lines.append(
                (
                    "- Donanım değerlendirmesi: "
                    "Yalnızca teorik ağırlık alt sınırı GPU kapasitesine "
                    "sığıyor. Gerçek runtime uygunluğu henüz doğrulanmadı."
                )
            )

    elif (
        hardware["status"]
        == "too_large"
    ):
        if (
            hardware["reason"]
            == "explicit_vram"
        ):
            lines.append(
                (
                    "- Donanım değerlendirmesi: Uygun değil. "
                    f"En düşük açık VRAM gereksinimi "
                    f"{hardware['lowest_vram']:g} GB; "
                    f"mevcut GPU {total_vram:g} GB."
                )
            )

        else:
            lines.append(
                (
                    "- Donanım değerlendirmesi: Uygun değil. "
                    "Yalnızca model ağırlıklarının teorik minimumu bile "
                    f"yaklaşık "
                    f"{hardware['estimated_min_weight_gib']:.1f} GiB; "
                    f"mevcut GPU {total_vram:g} GB VRAM."
                )
            )

            if active_params:
                lines.append(
                    (
                        "  Aktif parametre sayısının daha düşük olması, "
                        "tüm model ağırlıklarının yalnızca aktif parametre "
                        "kadar bellek kullanacağı anlamına gelmez."
                    )
                )

    else:
        lines.append(
            (
                "- Donanım değerlendirmesi: "
                "Açık runtime VRAM veya hesaplanabilir weight-memory "
                "evidence bulunmadığı için kesin uygunluk doğrulanamadı."
            )
        )

    urls = unique_candidate_source_urls(
        name,
        web_results,
    )

    if urls:
        lines.append(
            (
                "- Kaynak: "
                + urls[0]
            )
        )

    lines.append("")

    return facts


# =============================================================================
# WEB FINAL
# =============================================================================

def format_web_answer(
    messages,
    records,
    seed_candidates=None,
):
    web_results = collect_web_results(
        records
    )

    if not web_results:
        return (
            'Web araması yeterli sonuç döndürmedi.'
        )

    fresh_candidates = extract_structured_web_candidates(
        messages,
        web_results,
    )

    deterministic_variants = discover_direct_size_variants(
        seed_candidates or [],
        web_results,
    )

    candidates = merge_candidate_sets(
        seed_candidates or [],
        (
            list(fresh_candidates)
            + list(deterministic_variants)
        ),
        web_results,
    )

    candidates = inherit_release_from_seed_family(
        candidates,
        seed_candidates or [],
    )

    system_data = parse_json(
        latest_tool_output(
            messages,
            'get_system_specs',
        )
    )

    gpus = system_data.get('gpu') or []
    ram = system_data.get('ram') or {}

    total_vram = None

    if gpus:
        total_vram = gpus[0].get(
            'vram_total_gb'
        )

    lines = [
        'Güncel web araştırması:',
        '',
    ]

    if gpus or ram:
        lines.append('Donanımınız:')

        if gpus:
            lines.append(
                '- GPU: '
                + str(
                    gpus[0].get(
                        'name',
                        'Bilinmiyor',
                    )
                )
            )
            lines.append(
                '- Toplam VRAM: '
                + str(
                    gpus[0].get(
                        'vram_total_gb',
                        '?',
                    )
                )
                + ' GB'
            )

        if ram:
            lines.append(
                '- RAM: '
                + str(
                    ram.get(
                        'total_gb',
                        '?',
                    )
                )
                + ' GB'
            )

        lines.append('')

    if not candidates:
        lines.append(
            'Web sonuçlarında güvenilir biçimde doğrulanabilen model adayı bulunamadı.'
        )
        return '\n'.join(lines)

    # Spesifik local varyant bulunduğunda family-level satırı göstermeyelim.
    # Örn. Qwen 3.5-0.8B varsa Qwen 3.5 family satırı gereksiz ve
    # teknik fact'leri karıştırmaya daha açık.
    specific_local_keys = []

    for candidate in candidates:
        if (
            candidate_local_weights_status(
                candidate
            )
            != "verified"
        ):
            continue

        specific_local_keys.append(
            normalize_model_match_text(
                candidate.get(
                    "model_name",
                    ""
                )
            )
        )

    filtered_candidates = []

    for candidate in candidates:
        candidate_key = normalize_model_match_text(
            candidate.get(
                "model_name",
                ""
            )
        )

        has_more_specific_local = any(
            other_key != candidate_key
            and other_key.startswith(
                candidate_key
            )
            for other_key in specific_local_keys
        )

        if has_more_specific_local:
            continue

        filtered_candidates.append(
            candidate
        )

    candidates = filtered_candidates

    current_local = []
    current_not_local = []
    alternatives_local = []
    alternatives_unverified = []

    for candidate in candidates:
        release_status = candidate_release_status(
            candidate
        )
        local_status = candidate_local_weights_status(
            candidate
        )
        name = candidate['model_name']

        if release_status == 'current_year':
            if local_status == 'verified':
                current_local.append(candidate)
            else:
                current_not_local.append(candidate)
            continue

        if candidate_has_current_year_source(
            name,
            web_results,
        ):
            if local_status == 'verified':
                alternatives_local.append(candidate)
            else:
                alternatives_unverified.append(candidate)

    suitable_current = []
    unsuitable_current = []
    unknown_current = []

    if current_local:
        lines.append(
            f'{CURRENT_YEAR} release\'i ve local/open-weight erişimi doğrulanan modeller:'
        )
        lines.append('')

        for candidate in current_local:
            facts = append_web_candidate(
                lines=lines,
                candidate=candidate,
                web_results=web_results,
                total_vram=total_vram,
                alternative=False,
            )

            hardware = get_hardware_status(
                facts,
                total_vram,
            )

            if hardware['status'] == 'potentially_suitable':
                suitable_current.append(
                    candidate['model_name']
                )
            elif hardware['status'] == 'too_large':
                unsuitable_current.append(
                    candidate['model_name']
                )
            else:
                unknown_current.append(
                    candidate['model_name']
                )
    else:
        lines.append(
            f'{CURRENT_YEAR} release\'i ile birlikte local/open-weight erişimi doğrulanan yeni bir aday bulunamadı.'
        )
        lines.append('')

    # Release edilmiş ama local indirilebilirliği doğrulanmamış modelleri
    # local adaymış gibi sunmuyoruz.
    if current_not_local:
        lines.append(
            f'{CURRENT_YEAR} release\'i doğrulanan ancak local/open-weight erişimi doğrulanamayan modeller:'
        )
        lines.append('')

        for candidate in current_not_local[:4]:
            lines.append(
                f"- {candidate['model_name']}: local indirilebilir ağırlık evidence'ı yeterli değil; local öneri listesine alınmadı."
            )

        lines.append('')

    suitable_alternatives = []
    unsuitable_alternatives = []
    unknown_alternatives = []

    # Uygun current-year local aday yoksa local olduğu doğrulanmış daha eski
    # güncel alternatifleri gerçekten hardware açısından değerlendiriyoruz.
    if (
        not suitable_current
        and alternatives_local
    ):
        lines.append(
            f'Alternatif olarak {CURRENT_YEAR} odaklı güncel kaynaklarda geçen ve local/open-weight erişimi doğrulanan modeller:'
        )
        lines.append('')

        shown = set()

        for candidate in alternatives_local:
            key = normalize_model_match_text(
                candidate['model_name']
            )

            if key in shown:
                continue

            shown.add(key)

            facts = append_web_candidate(
                lines=lines,
                candidate=candidate,
                web_results=web_results,
                total_vram=total_vram,
                alternative=True,
            )

            hardware = get_hardware_status(
                facts,
                total_vram,
            )

            if hardware['status'] == 'potentially_suitable':
                suitable_alternatives.append(
                    candidate['model_name']
                )
            elif hardware['status'] == 'too_large':
                unsuitable_alternatives.append(
                    candidate['model_name']
                )
            else:
                unknown_alternatives.append(
                    candidate['model_name']
                )

    lines.append('Sonuç:')

    if suitable_current:
        lines.append(
            f'{CURRENT_YEAR} release\'i ve local erişimi doğrulanan modeller içinde donanımınız açısından potansiyel uygun adaylar: '
            + ', '.join(suitable_current)
            + '. Gerçek runtime uygunluğu yerel kurulum ve ölçümle kesinleşir.'
        )

    elif suitable_alternatives:
        lines.append(
            f'{CURRENT_YEAR} release\'i olarak hem local hem de donanımınıza uygunluğu doğrulanabilen yeni bir aday bulunamadı. '
            'Buna karşılık güncel kaynaklarda geçen şu local alternatifler donanım kapasiteniz açısından potansiyel uygun görünüyor: '
            + ', '.join(suitable_alternatives)
            + '. Gerçek runtime uygunluğu yerel kurulum ve ölçümle kesinleşir.'
        )

    elif current_local:
        if unsuitable_current:
            lines.append(
                f'{CURRENT_YEAR} release\'i ve local erişimi doğrulanan modeller bulundu ancak mevcut hardware evidence ile donanımınıza uygun bir yeni aday doğrulanamadı.'
            )
        else:
            lines.append(
                f'{CURRENT_YEAR} release\'i ve local erişimi doğrulanan modeller bulundu ancak hardware evidence kesin seçim için yetersiz kaldı.'
            )

    elif alternatives_local:
        lines.append(
            'Local/open-weight alternatifler bulundu ancak mevcut hardware evidence ile donanımınıza uygun bir aday doğrulanamadı.'
        )

    else:
        lines.append(
            f'Mevcut web evidence ile {CURRENT_YEAR} release\'i, local/open-weight erişimi ve donanım uygunluğu birlikte doğrulanan bir model bulunamadı.'
        )

    return '\n'.join(lines)


# =============================================================================
# GENERIC FINAL
# =============================================================================

def generate_grounded_final(
    messages,
    records,
):
    names = list(
        dict.fromkeys(
            record.get("name")
            for record in records
        )
    )

    instruction = f"""
FINAL RESPONSE

Bu turda çalışan tool'lar:

{", ".join(names) if names else "yok"}

Kullanıcının gerçek sorusuna kısa Türkçe cevap ver.

- Yeni tool çağırma.
- Tool sonucunda olmayan ölçüm uydurma.
- benchmark_model çalışmadıysa gerçek benchmark sonucu üretme.
- estimate_vram çalışmadıysa model VRAM'i ölçülmüş gibi davranma.
- internet_search çalıştıysa source'ta olmayan güncel model ekleme.
"""

    return call_model(
        messages=(
            messages
            + [
                {
                    "role": "user",
                    "content": instruction,
                }
            ]
        ),
        allowed_tools=[],
    )


# =============================================================================
# WEB FLOW
# =============================================================================

def run_web_flow(
    messages,
    plan,
):
    seen_outputs = {}
    records = []

    # 1) Deterministic release discovery
    first_search = request_initial_web_search(
        messages
    )

    execute_response_tools(
        first_search,
        messages,
        records,
        seen_outputs,
    )

    # 2) Hardware evidence
    needs_hardware = (
        plan["needs_system_specs"]
    )

    if not needs_hardware:
        needs_hardware = (
            web_question_needs_hardware(
                messages
            )
        )

        if DEBUG_TOOLS:
            print(
                (
                    "🖥️ Web hardware check: "
                    + (
                        "GEREKLİ"
                        if needs_hardware
                        else "GEREKLİ DEĞİL"
                    )
                ),
                flush=True,
            )
            print()

    if (
        needs_hardware
        and
        latest_tool_output(
            messages,
            "get_system_specs",
        )
        is None
    ):
        system_response = request_system_specs(
            messages
        )

        execute_response_tools(
            system_response,
            messages,
            records,
            seen_outputs,
        )

    # 3) Optional second release discovery
    if (
        count_tool(
            records,
            "internet_search",
        )
        < MAX_WEB_SEARCHES_PER_TURN
        and
        need_second_discovery_search(
            messages,
            records,
        )
    ):
        second_search = (
            request_second_discovery_search(
                messages
            )
        )

        execute_response_tools(
            second_search,
            messages,
            records,
            seen_outputs,
        )

    # Discovery candidate registry: bu noktada aday isimlerini sabitliyoruz.
    # Daha sonraki uzun technical evidence listeleri 4B extractor'ın eski
    # adayları unutmasına neden olamaz.
    discovery_web_results = collect_web_results(
        records
    )

    seed_candidates = extract_structured_web_candidates(
        messages,
        discovery_web_results,
    )

    # 4) Current-year model-specific technical searches
    #
    # Önce release'i doğrulanmış yeni modeller araştırılır. Technical search
    # local/open-weight erişimini de doğrulamaya çalışır.
    current_targets = current_release_technical_targets(
        messages,
        records,
        seed_candidates=seed_candidates,
    )

    for target in current_targets:
        if (
            count_tool(
                records,
                'internet_search',
            )
            >= MAX_WEB_SEARCHES_PER_TURN
        ):
            break

        technical_search = (
            request_technical_web_search_for_candidate(
                target
            )
        )

        execute_response_tools(
            technical_search,
            messages,
            records,
            seen_outputs,
        )

    # 5) Fallback alternative technical searches
    #
    # Current-year + local + hardware açısından potansiyel uygun aday yoksa
    # küçük/güncel alternatifler de gerçekten araştırılır. Böylece Phi-4 Mini
    # gibi 3.8B bir aday sadece listelenip bırakılmaz.
    if not has_suitable_current_local_candidate(
        messages,
        records,
        seed_candidates=seed_candidates,
    ):
        alternative_targets = alternative_technical_targets(
            messages,
            records,
        )

        for target in alternative_targets:
            if (
                count_tool(
                    records,
                    'internet_search',
                )
                >= MAX_WEB_SEARCHES_PER_TURN
            ):
                break

            technical_search = (
                request_technical_web_search_for_candidate(
                    target
                )
            )

            execute_response_tools(
                technical_search,
                messages,
                records,
                seen_outputs,
            )

    # 6) Final
    final_response = {
        "role": "assistant",
        "content": format_web_answer(
            messages,
            records,
            seed_candidates=seed_candidates,
        ),
    }

    messages.append(
        final_response
    )

    return final_response


# =============================================================================
# LOCAL FLOW
# =============================================================================

def run_local_model_flow(
    messages,
    plan,
):
    seen_outputs = {}
    records = []

    if (
        plan["needs_system_specs"]
        and
        latest_tool_output(
            messages,
            "get_system_specs",
        )
        is None
    ):
        response = request_system_specs(
            messages
        )

        execute_response_tools(
            response,
            messages,
            records,
            seen_outputs,
        )

    model_response = request_model_list(
        messages
    )

    execute_response_tools(
        model_response,
        messages,
        records,
        seen_outputs,
    )

    if plan["needs_benchmark"]:
        benchmark_response = (
            request_benchmark(
                messages
            )
        )

        if benchmark_response:
            execute_response_tools(
                benchmark_response,
                messages,
                records,
                seen_outputs,
            )

        raw = latest_tool_output(
            messages,
            "benchmark_model",
        )

        if raw:
            final_response = {
                "role": "assistant",
                "content": format_benchmark(
                    raw
                ),
            }
        else:
            final_response = (
                generate_grounded_final(
                    messages,
                    records,
                )
            )

        messages.append(
            final_response
        )

        return final_response

    if plan["needs_model_vram"]:
        estimate_response = (
            request_estimate_vram(
                messages
            )
        )

        if estimate_response:
            execute_response_tools(
                estimate_response,
                messages,
                records,
                seen_outputs,
            )

        answer = (
            format_local_recommendation(
                messages
            )
        )

        if answer:
            final_response = {
                "role": "assistant",
                "content": answer,
            }
        else:
            final_response = (
                generate_grounded_final(
                    messages,
                    records,
                )
            )

        messages.append(
            final_response
        )

        return final_response

    final_response = generate_grounded_final(
        messages,
        records,
    )

    messages.append(
        final_response
    )

    return final_response


# =============================================================================
# SYSTEM FLOW
# =============================================================================

def run_system_flow(messages):
    seen_outputs = {}
    records = []

    if (
        latest_tool_output(
            messages,
            "get_system_specs",
        )
        is None
    ):
        response = request_system_specs(
            messages
        )

        execute_response_tools(
            response,
            messages,
            records,
            seen_outputs,
        )

    raw = latest_tool_output(
        messages,
        "get_system_specs",
    )

    if raw:
        final_response = {
            "role": "assistant",
            "content": format_system_specs(
                raw
            ),
        }
    else:
        final_response = (
            generate_grounded_final(
                messages,
                records,
            )
        )

    messages.append(
        final_response
    )

    return final_response


# =============================================================================
# GENERIC AGENT
# =============================================================================

def run_generic_agent(messages):
    seen_outputs = {}
    records = []

    for _ in range(MAX_AGENT_ROUNDS):
        response = call_model(
            messages=messages,
            allowed_tools=None,
        )

        tool_calls = (
            response.get("tool_calls")
            or []
        )

        if tool_calls:
            messages.append(response)

            tool_messages, new_records = (
                execute_tool_calls(
                    tool_calls,
                    seen_outputs,
                )
            )

            messages.extend(
                tool_messages
            )

            records.extend(
                new_records
            )

            continue

        if not records:
            messages.append(response)
            return response

        final_response = (
            generate_grounded_final(
                messages,
                records,
            )
        )

        messages.append(
            final_response
        )

        return final_response

    if records:
        final_response = (
            generate_grounded_final(
                messages,
                records,
            )
        )

        messages.append(
            final_response
        )

        return final_response

    return {
        "role": "assistant",
        "content": (
            "Maksimum agent turu sayısına ulaşıldı."
        ),
    }


# =============================================================================
# MAIN AGENT
# =============================================================================

def run_agent(messages):
    plan = plan_evidence_requirements(
        messages
    )

    if plan["needs_current_web"]:
        return run_web_flow(
            messages,
            plan,
        )

    if (
        plan["needs_installed_models"]
        or plan["needs_model_vram"]
        or plan["needs_benchmark"]
    ):
        return run_local_model_flow(
            messages,
            plan,
        )

    if plan["needs_system_specs"]:
        return run_system_flow(
            messages
        )

    return run_generic_agent(
        messages
    )


# =============================================================================
# START
# =============================================================================

print()
print("=" * 60)
print("             ModelPicker - Local LLM Advisor")
print("=" * 60)
print(f"Agent modeli : {args.chat_model}")
print(f"Tarih        : {CURRENT_DATE}")
print(
    "Tool debug   : "
    + (
        "AÇIK"
        if DEBUG_TOOLS
        else "KAPALI"
    )
)
print("Çıkmak için  : çık")
print()


# =============================================================================
# CONVERSATION
# =============================================================================

messages = [
    {
        "role": "system",
        "content": SYSTEM_PROMPT,
    }
]


# =============================================================================
# MAIN LOOP
# =============================================================================

while True:
    try:
        question = input(
            "Siz > "
        ).strip()

    except (
        KeyboardInterrupt,
        EOFError,
    ):
        print()
        break

    if not question:
        continue

    if question.lower() in {
        "çık",
        "cik",
        "exit",
        "quit",
    }:
        break

    messages.append(
        {
            "role": "user",
            "content": question,
        }
    )

    try:
        response = run_agent(
            messages
        )

    except RuntimeError as exc:
        print(
            f"\nHata: {exc}\n"
        )
        continue

    except Exception as exc:
        print(
            (
                "\nBeklenmeyen hata: "
                f"{exc}\n"
            )
        )
        continue

    answer = (
        response.get("content")
        or ""
    ).strip()

    if not answer:
        answer = (
            "İşlem tamamlandı ancak "
            "nihai cevap üretilemedi."
        )

    print(
        (
            "\nModelPicker > "
            f"{answer}\n"
        )
    )
