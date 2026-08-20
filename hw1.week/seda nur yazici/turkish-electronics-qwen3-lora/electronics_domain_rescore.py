import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

INPUT_CANDIDATES = [
    Path('electronics_benchmark_v3_results/electronics_benchmark_v3_results.json'),
    Path('electronics_benchmark_v3_results.json'),
]
OUTPUT_DIR = Path('electronics_benchmark_v3_1_results')
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_FILE = OUTPUT_DIR / 'electronics_benchmark_v3_1_rescored.json'

WEIGHTS = {
    'selection': 0.55,
    'criterion': 0.15,
    'numeric': 0.10,
    'hallucination_free': 0.10,
    'format': 0.10,
}


def load_source() -> tuple[dict[str, Any], Path]:
    for path in INPUT_CANDIDATES:
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8')), path
    raise FileNotFoundError(
        'electronics_benchmark_v3_results.json bulunamadı. '
        'Dosyayı script ile aynı klasöre veya '
        'electronics_benchmark_v3_results/ klasörüne koy.'
    )


def normalize(value: Any) -> str:
    text = unicodedata.normalize('NFKD', str(value or ''))
    text = ''.join(c for c in text if not unicodedata.combining(c))
    text = text.casefold()
    return re.sub(r'\s+', ' ', text).strip()


def extract_reason(response: str) -> str:
    match = re.search(r'gerekçe\s*:\s*(.*)', response, flags=re.I | re.S)
    if match:
        return match.group(1).strip()
    lines = [line.strip() for line in response.splitlines() if line.strip()]
    return ' '.join(lines[1:]) if len(lines) > 1 else ''


def canonical_number(value: str) -> str:
    return value.replace(',', '.').replace(' ', '').lower()


def extract_specs(text: str) -> dict[str, set[str]]:
    text = normalize(text)
    specs = {
        'ram': set(),
        'storage': set(),
        'gpu': set(),
        'refresh_rate': set(),
        'screen_size': set(),
    }

    for pattern in [
        r'\b(\d{1,3})\s*gb\s*(?:ram|bellek)\b',
        r'\b(\d{1,3})\s*gb\s*(?:ddr[345]?)\b',
    ]:
        for m in re.finditer(pattern, text, flags=re.I):
            specs['ram'].add(f'{m.group(1)}gb')

    for m in re.finditer(r'\b(\d{1,3})\s*gb\b', text, flags=re.I):
        trailing = text[m.end():m.end() + 20]
        if re.match(r'\s*(?:ssd|hdd|ekran|gpu|vram)', trailing):
            continue
        value = int(m.group(1))
        if value in {4, 6, 8, 12, 16, 18, 24, 32, 36, 48, 64, 96, 128}:
            specs['ram'].add(f'{value}gb')

    for pattern in [
        r'\b(\d+(?:[.,]\d+)?)\s*(gb|tb)\s*(?:m\.?2\s*)?(?:ssd|hdd)\b',
        r'\b(\d+(?:[.,]\d+)?)\s*(gb|tb)\b',
    ]:
        for m in re.finditer(pattern, text, flags=re.I):
            specs['storage'].add(canonical_number(m.group(1)) + m.group(2).lower())

    for m in re.finditer(r'\b(rtx|gtx|rx)\s*[- ]?(\d{3,4})(?:\s*(ti|super))?\b', text, flags=re.I):
        suffix = m.group(3) or ''
        specs['gpu'].add(f'{m.group(1)}{m.group(2)}{suffix}'.replace(' ', '').lower())

    for m in re.finditer(r'\b(\d{2,3})\s*hz\b', text, flags=re.I):
        specs['refresh_rate'].add(f'{m.group(1)}hz')

    for pattern in [
        r'\b(\d{2}(?:[.,]\d)?)\s*(?:inç|inc|inch)\b',
        r'\b(\d{2}(?:[.,]\d)?)\s*[\"\']',
    ]:
        for m in re.finditer(pattern, text, flags=re.I):
            specs['screen_size'].add(canonical_number(m.group(1)) + 'inch')

    return specs


def corrected_hallucination(response: str, predicted_product: str | None) -> dict[str, Any]:
    reason_specs = extract_specs(extract_reason(response))
    product_specs = extract_specs(predicted_product or '')
    supported, unsupported = [], []

    for field, claims in reason_specs.items():
        for claim in claims:
            row = {'field': field, 'value': claim}
            if claim in product_specs[field]:
                supported.append(row)
            else:
                unsupported.append(row)

    count = len(supported) + len(unsupported)
    return {
        'supported_technical_claims': supported,
        'unsupported_technical_claims': unsupported,
        'technical_claim_count': count,
        'technical_claim_coverage': int(count > 0),
        'technical_claim_factuality': len(supported) / count if count else 1.0,
        'corrected_hallucination_free': int(not unsupported),
    }


def rescore_item(item: dict[str, Any]) -> dict[str, Any]:
    numeric_count = int(item.get('numeric_claim_count', 0))
    numeric_old = float(item.get('numeric_factuality', 0.0))
    numeric_coverage = int(numeric_count > 0)
    numeric_quality = numeric_old if numeric_coverage else 0.5

    hall = corrected_hallucination(
        item.get('response', ''),
        item.get('predicted_product'),
    )

    selection = float(item.get('selection_correct', False))
    criterion = float(item.get('criterion_mention_score', 0.0))
    formatting = float(item.get('format_compliance', item.get('format_compliance_score', 0.0)))

    composite = (
        WEIGHTS['selection'] * selection
        + WEIGHTS['criterion'] * criterion
        + WEIGHTS['numeric'] * numeric_quality
        + WEIGHTS['hallucination_free'] * hall['corrected_hallucination_free']
        + WEIGHTS['format'] * formatting
    )

    return {
        **item,
        'numeric_claim_coverage': numeric_coverage,
        'corrected_numeric_quality': numeric_quality,
        **hall,
        'corrected_composite_score': composite,
    }


def average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    grouped = defaultdict(list)
    for item in results:
        grouped[item['sample_id']].append(item)

    unique = len(grouped)
    robust = sum(all(x['selection_correct'] for x in group) for group in grouped.values())
    consistent = sum(len({x.get('predicted_product') for x in group}) == 1 for group in grouped.values())

    tasks = {}
    for task in sorted({x['task'] for x in results}):
        subset = [x for x in results if x['task'] == task]
        tasks[task] = {
            'cases': len(subset),
            'selection_accuracy': average([float(x['selection_correct']) for x in subset]),
            'corrected_composite_score': average([x['corrected_composite_score'] for x in subset]),
            'corrected_hallucination_free_rate': average([x['corrected_hallucination_free'] for x in subset]),
        }

    tech_claim_items = [x for x in results if x['technical_claim_count'] > 0]

    return {
        'inference_cases': len(results),
        'unique_samples': unique,
        'selection_accuracy': average([float(x['selection_correct']) for x in results]),
        'robust_accuracy': robust / unique if unique else 0.0,
        'permutation_consistency': consistent / unique if unique else 0.0,
        'valid_prediction_rate': average([float(x.get('predicted_product') is not None) for x in results]),
        'criterion_mention_score': average([float(x.get('criterion_mention_score', 0.0)) for x in results]),
        'numeric_claim_coverage': average([x['numeric_claim_coverage'] for x in results]),
        'corrected_numeric_quality': average([x['corrected_numeric_quality'] for x in results]),
        'technical_claim_coverage': average([x['technical_claim_coverage'] for x in results]),
        'technical_claim_factuality': average([x['technical_claim_factuality'] for x in tech_claim_items]),
        'corrected_hallucination_free_rate': average([x['corrected_hallucination_free'] for x in results]),
        'format_compliance': average([float(x.get('format_compliance', x.get('format_compliance_score', 0.0))) for x in results]),
        'first_position_selection_rate': average([float(x.get('first_position_selected', False)) for x in results]),
        'corrected_composite_score': average([x['corrected_composite_score'] for x in results]),
        'by_task': tasks,
    }


def rescore_section(section: dict[str, Any]) -> dict[str, Any]:
    results = [rescore_item(item) for item in section['results']]
    return {'summary': summarize(results), 'results': results}


def rescore_model(model: dict[str, Any]) -> dict[str, Any]:
    return {
        'model': model['model'],
        'model_id': model['model_id'],
        'recommendation': rescore_section(model['recommendation']),
        'comparison': rescore_section(model['comparison']),
    }


def print_section(title: str, base: dict[str, Any], lora: dict[str, Any]) -> None:
    base = base['summary']
    lora = lora['summary']
    print('\n' + title)
    print('-' * 96)

    metrics = [
        ('selection_accuracy', 'Selection accuracy'),
        ('robust_accuracy', 'Robust accuracy'),
        ('permutation_consistency', 'Permutation consistency'),
        ('valid_prediction_rate', 'Valid prediction'),
        ('criterion_mention_score', 'Criterion mention'),
        ('numeric_claim_coverage', 'Numeric claim coverage'),
        ('corrected_numeric_quality', 'Corrected numeric quality'),
        ('technical_claim_coverage', 'Technical claim coverage'),
        ('technical_claim_factuality', 'Technical claim factuality'),
        ('corrected_hallucination_free_rate', 'Corrected hallucination-free'),
        ('format_compliance', 'Format compliance'),
        ('first_position_selection_rate', 'First-position selection'),
        ('corrected_composite_score', 'Corrected composite'),
    ]

    for key, label in metrics:
        b = base[key] * 100
        l = lora[key] * 100
        print(f'{label:31s} | Base: {b:6.2f}% | LoRA: {l:6.2f}% | Delta: {l-b:+6.2f}')

    print('\nGörev bazlı corrected composite:')
    for task in sorted(set(base['by_task']) | set(lora['by_task'])):
        b = base['by_task'][task]['corrected_composite_score'] * 100
        l = lora['by_task'][task]['corrected_composite_score'] * 100
        print(f'{task:18s} | Base: {b:6.2f}% | LoRA: {l:6.2f}% | Delta: {l-b:+6.2f}')


def main() -> None:
    print('=' * 96)
    print('TURKISH ELECTRONICS BENCHMARK V3.1 OFFLINE RESCORING')
    print('=' * 96)

    source, source_path = load_source()
    print('Kaynak:', source_path.resolve())
    print('Yeni inference yapılmayacak; mevcut cevaplar yeniden puanlanacak.')

    output = {
        'config': {
            'source_file': str(source_path.resolve()),
            'rescoring_version': '3.1',
            'new_model_inference': False,
            'composite_weights': WEIGHTS,
            'corrections': [
                'Ürün adındaki teknik özellikler halüsinasyon sayılmaz.',
                'Yalnızca gerekçe bölümündeki teknik iddialar kontrol edilir.',
                'Sayısal iddia yoksa otomatik 1.0 yerine nötr 0.5 verilir.',
                'Sayısal ve teknik iddia coverage metrikleri ayrı raporlanır.',
            ],
        },
        'base': rescore_model(source['base']),
        'lora': rescore_model(source['lora']),
    }

    OUTPUT_FILE.write_text(
        json.dumps(output, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )

    print_section(
        'V3.1 RECOMMENDATION',
        output['base']['recommendation'],
        output['lora']['recommendation'],
    )
    print_section(
        'V3.1 COMPARISON',
        output['base']['comparison'],
        output['lora']['comparison'],
    )

    print('\n' + '=' * 96)
    print('RESCORING TAMAMLANDI')
    print('=' * 96)
    print('Çıktı:', OUTPUT_FILE.resolve())


if __name__ == '__main__':
    main()