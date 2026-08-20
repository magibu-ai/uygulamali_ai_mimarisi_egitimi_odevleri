from pathlib import Path
import json

import numpy as np
import pandas as pd


# ============================================================
# AYARLAR
# ============================================================

INPUT_FILE = Path(
    "analysis/benchmark_results.csv"
)

THRESHOLD_SCAN_OUTPUT = Path(
    "analysis/threshold_scan.csv"
)

THRESHOLD_JSON_OUTPUT = Path(
    "analysis/selected_threshold.json"
)

THRESHOLD_TXT_OUTPUT = Path(
    "analysis/selected_threshold.txt"
)


# ============================================================
# BENCHMARK BEKLENTİLERİ
# ============================================================

EXPECTED_TOTAL = 30
EXPECTED_POSITIVE = 20
EXPECTED_NEGATIVE = 10


# ============================================================
# THRESHOLD SCAN
# ============================================================

THRESHOLD_MIN = 0.20
THRESHOLD_MAX = 0.80
THRESHOLD_STEP = 0.001


# ============================================================
# BAŞLANGIÇ
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "07 - THRESHOLD SELECTION"
)

print(
    "=" * 80
)


# ============================================================
# INPUT KONTROLÜ
# ============================================================

if not INPUT_FILE.exists():

    raise FileNotFoundError(
        f"{INPUT_FILE} bulunamadı.\n"
        "Önce 06_run_benchmark.py çalıştırılmalıdır."
    )


print(
    f"\nInput dosyası:\n"
    f"{INPUT_FILE}"
)


# ============================================================
# VERİYİ OKU
# ============================================================

df = pd.read_csv(
    INPUT_FILE
)


print(
    f"\nToplam benchmark satırı: "
    f"{len(df)}"
)


# ============================================================
# GEREKLİ KOLONLAR
# ============================================================

required_columns = [
    "question_number",
    "question_type",
    "question",
    "top1_similarity",
    "top1_title",
]


missing_columns = [
    column
    for column in required_columns
    if column not in df.columns
]


if missing_columns:

    raise ValueError(
        "Eksik kolonlar bulundu:\n"
        + "\n".join(
            missing_columns
        )
    )


# ============================================================
# LABEL NORMALIZATION
# ============================================================

df[
    "question_type"
] = (
    df[
        "question_type"
    ]
    .astype(str)
    .str.strip()
    .str.lower()
)


valid_labels = {
    "positive",
    "negative",
}


invalid_labels = set(
    df[
        "question_type"
    ].unique()
) - valid_labels


if invalid_labels:

    raise ValueError(
        "Geçersiz question_type değerleri bulundu:\n"
        f"{invalid_labels}"
    )


# ============================================================
# SIMILARITY KONTROLÜ
# ============================================================

df[
    "top1_similarity"
] = pd.to_numeric(
    df[
        "top1_similarity"
    ],
    errors="raise"
)


if not np.isfinite(
    df[
        "top1_similarity"
    ].to_numpy()
).all():

    raise ValueError(
        "Similarity değerlerinde "
        "NaN veya Inf bulundu."
    )


# ============================================================
# BENCHMARK SAYILARI
# ============================================================

total_count = len(
    df
)


positive_count = int(
    (
        df[
            "question_type"
        ]
        == "positive"
    ).sum()
)


negative_count = int(
    (
        df[
            "question_type"
        ]
        == "negative"
    ).sum()
)


print(
    f"\nToplam   : {total_count}"
)

print(
    f"Pozitif  : {positive_count}"
)

print(
    f"Negatif  : {negative_count}"
)


if total_count != EXPECTED_TOTAL:

    raise ValueError(
        "Toplam benchmark sayısı beklenenden farklı."
    )


if positive_count != EXPECTED_POSITIVE:

    raise ValueError(
        "Pozitif benchmark sayısı beklenenden farklı."
    )


if negative_count != EXPECTED_NEGATIVE:

    raise ValueError(
        "Negatif benchmark sayısı beklenenden farklı."
    )


print(
    "\nBenchmark validation: OK"
)


# ============================================================
# LABEL -> 0 / 1
# ============================================================

# positive = dokümanlarda cevap bulunuyor
# negative = dokümanlarda cevap bulunmuyor

y_true = (
    df[
        "question_type"
    ]
    .map(
        {
            "positive": 1,
            "negative": 0,
        }
    )
    .to_numpy(
        dtype=np.int32
    )
)


scores = (
    df[
        "top1_similarity"
    ]
    .to_numpy(
        dtype=np.float64
    )
)


# ============================================================
# METRIC FONKSİYONU
# ============================================================

def calculate_metrics(
    threshold
):

    # ----------------------------------------
    # SCORE >= THRESHOLD -> POSITIVE
    # ----------------------------------------

    y_pred = (
        scores
        >= threshold
    ).astype(
        np.int32
    )


    # ----------------------------------------
    # CONFUSION MATRIX
    # ----------------------------------------

    tp = int(
        np.sum(
            (y_true == 1)
            & (y_pred == 1)
        )
    )


    tn = int(
        np.sum(
            (y_true == 0)
            & (y_pred == 0)
        )
    )


    fp = int(
        np.sum(
            (y_true == 0)
            & (y_pred == 1)
        )
    )


    fn = int(
        np.sum(
            (y_true == 1)
            & (y_pred == 0)
        )
    )


    # ----------------------------------------
    # ACCURACY
    # ----------------------------------------

    accuracy = (
        (tp + tn)
        / len(y_true)
    )


    # ----------------------------------------
    # PRECISION
    # ----------------------------------------

    if (
        tp + fp
    ) > 0:

        precision = (
            tp
            / (tp + fp)
        )

    else:

        precision = 0.0


    # ----------------------------------------
    # RECALL / SENSITIVITY
    # ----------------------------------------

    if (
        tp + fn
    ) > 0:

        recall = (
            tp
            / (tp + fn)
        )

    else:

        recall = 0.0


    # ----------------------------------------
    # SPECIFICITY
    # ----------------------------------------

    if (
        tn + fp
    ) > 0:

        specificity = (
            tn
            / (tn + fp)
        )

    else:

        specificity = 0.0


    # ----------------------------------------
    # F1
    # ----------------------------------------

    if (
        precision + recall
    ) > 0:

        f1 = (
            2
            * precision
            * recall
            / (
                precision
                + recall
            )
        )

    else:

        f1 = 0.0


    # ----------------------------------------
    # BALANCED ACCURACY
    # ----------------------------------------

    balanced_accuracy = (
        recall
        + specificity
    ) / 2


    return {

        "threshold": float(
            threshold
        ),

        "tp": tp,

        "tn": tn,

        "fp": fp,

        "fn": fn,

        "accuracy": float(
            accuracy
        ),

        "precision": float(
            precision
        ),

        "recall": float(
            recall
        ),

        "specificity": float(
            specificity
        ),

        "f1": float(
            f1
        ),

        "balanced_accuracy": float(
            balanced_accuracy
        ),
    }


# ============================================================
# SCORE DISTRIBUTION
# ============================================================

positive_scores = (
    df.loc[
        df[
            "question_type"
        ]
        == "positive",
        "top1_similarity"
    ]
    .to_numpy(
        dtype=np.float64
    )
)


negative_scores = (
    df.loc[
        df[
            "question_type"
        ]
        == "negative",
        "top1_similarity"
    ]
    .to_numpy(
        dtype=np.float64
    )
)


positive_min = float(
    positive_scores.min()
)


positive_max = float(
    positive_scores.max()
)


positive_mean = float(
    positive_scores.mean()
)


negative_min = float(
    negative_scores.min()
)


negative_max = float(
    negative_scores.max()
)


negative_mean = float(
    negative_scores.mean()
)


gap = (
    positive_min
    - negative_max
)


print(
    "\n"
    + "=" * 80
)

print(
    "SCORE DAĞILIMI"
)

print(
    "=" * 80
)


print(
    f"""
Pozitif:
    mean : {positive_mean:.6f}
    min  : {positive_min:.6f}
    max  : {positive_max:.6f}

Negatif:
    mean : {negative_mean:.6f}
    min  : {negative_min:.6f}
    max  : {negative_max:.6f}

Gap:
    {gap:.6f}
"""
)


# ============================================================
# THRESHOLD SCAN
# ============================================================

print(
    "=" * 80
)

print(
    "THRESHOLD SCAN"
)

print(
    "=" * 80
)


thresholds = np.arange(
    THRESHOLD_MIN,
    THRESHOLD_MAX + THRESHOLD_STEP / 2,
    THRESHOLD_STEP,
)


scan_rows = []


for threshold in thresholds:

    metrics = (
        calculate_metrics(
            threshold
        )
    )


    scan_rows.append(
        metrics
    )


scan_df = pd.DataFrame(
    scan_rows
)


# ============================================================
# OUTPUT DİZİNİ
# ============================================================

THRESHOLD_SCAN_OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True
)


# ============================================================
# SCAN CSV
# ============================================================

scan_df.to_csv(
    THRESHOLD_SCAN_OUTPUT,
    index=False,
    encoding="utf-8-sig",
)


print(
    f"\nToplam test edilen threshold: "
    f"{len(scan_df)}"
)


# ============================================================
# EN İYİ F1
# ============================================================

best_f1 = float(
    scan_df[
        "f1"
    ].max()
)


best_f1_rows = (
    scan_df[
        np.isclose(
            scan_df[
                "f1"
            ],
            best_f1,
            atol=1e-12,
        )
    ]
    .copy()
)


best_accuracy = float(
    scan_df[
        "accuracy"
    ].max()
)


print(
    f"\nEn iyi F1       : "
    f"{best_f1:.6f}"
)


print(
    f"En iyi Accuracy : "
    f"{best_accuracy:.6f}"
)


# ============================================================
# FINAL THRESHOLD SEÇİMİ
# ============================================================

# Eğer pozitif ve negatifler tamamen ayrışıyorsa:
#
#     max negative < min positive
#
# iki grubun arasındaki boşluğun orta noktasını seçiyoruz.
#
# Bu yaklaşım threshold'u sınırlardan birine yapıştırmak
# yerine iki sınıfa da eşit mesafede bırakır.

if gap > 0:

    selection_method = (
        "midpoint_between_max_negative_and_min_positive"
    )


    exact_threshold = (
        negative_max
        + positive_min
    ) / 2


    # İnsan tarafından okunması ve final RAG kodunda
    # rahat kullanılması için 3 decimal.
    selected_threshold = round(
        exact_threshold,
        3
    )


    # Yuvarlama yanlışlıkla gap dışına çıkarsa
    # exact değeri kullan.
    if not (
        negative_max
        < selected_threshold
        <= positive_min
    ):

        selected_threshold = (
            exact_threshold
        )


else:

    # --------------------------------------------------------
    # OVERLAP VARSA
    # --------------------------------------------------------
    #
    # Öncelik:
    #   1. F1
    #   2. Accuracy
    #   3. Balanced Accuracy
    #
    # Aynı performansı veren birden fazla threshold varsa
    # bunların orta threshold'u seçilir.
    # --------------------------------------------------------

    selection_method = (
        "best_f1_accuracy_balanced_accuracy"
    )


    ranked_df = (
        scan_df
        .sort_values(
            by=[
                "f1",
                "accuracy",
                "balanced_accuracy",
            ],
            ascending=[
                False,
                False,
                False,
            ],
        )
        .copy()
    )


    best_row = (
        ranked_df.iloc[0]
    )


    target_f1 = float(
        best_row[
            "f1"
        ]
    )


    target_accuracy = float(
        best_row[
            "accuracy"
        ]
    )


    target_balanced = float(
        best_row[
            "balanced_accuracy"
        ]
    )


    tied = (
        scan_df[
            np.isclose(
                scan_df[
                    "f1"
                ],
                target_f1
            )
            &
            np.isclose(
                scan_df[
                    "accuracy"
                ],
                target_accuracy
            )
            &
            np.isclose(
                scan_df[
                    "balanced_accuracy"
                ],
                target_balanced
            )
        ]
    )


    selected_threshold = float(
        tied[
            "threshold"
        ].median()
    )


    exact_threshold = (
        selected_threshold
    )


# ============================================================
# SELECTED THRESHOLD METRICS
# ============================================================

selected_metrics = (
    calculate_metrics(
        selected_threshold
    )
)


# ============================================================
# CONFUSION MATRIX
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "SEÇİLEN THRESHOLD"
)

print(
    "=" * 80
)


print(
    f"""
Seçim yöntemi:
{selection_method}

Exact threshold:
{exact_threshold:.6f}

Final threshold:
{selected_threshold:.6f}

Observed negative max:
{negative_max:.6f}

Observed positive min:
{positive_min:.6f}
"""
)


print(
    "=" * 80
)

print(
    "CONFUSION MATRIX"
)

print(
    "=" * 80
)


print(
    f"""
                 Predicted
                 NEG     POS

Actual NEG       {selected_metrics['tn']:>3}     {selected_metrics['fp']:>3}

Actual POS       {selected_metrics['fn']:>3}     {selected_metrics['tp']:>3}
"""
)


# ============================================================
# METRICS
# ============================================================

print(
    "=" * 80
)

print(
    "FINAL METRICS"
)

print(
    "=" * 80
)


print(
    f"""
Accuracy          : {selected_metrics['accuracy']:.6f}
Precision         : {selected_metrics['precision']:.6f}
Recall            : {selected_metrics['recall']:.6f}
Specificity       : {selected_metrics['specificity']:.6f}
F1                : {selected_metrics['f1']:.6f}
Balanced Accuracy : {selected_metrics['balanced_accuracy']:.6f}
"""
)


# ============================================================
# HER SORUNUN FINAL PREDICTION'I
# ============================================================

df[
    "predicted_type"
] = np.where(
    df[
        "top1_similarity"
    ]
    >= selected_threshold,
    "positive",
    "negative",
)


df[
    "threshold_correct"
] = (
    df[
        "question_type"
    ]
    == df[
        "predicted_type"
    ]
)


# ============================================================
# HATALI SINIFLANDIRMALAR
# ============================================================

errors_df = (
    df[
        ~df[
            "threshold_correct"
        ]
    ]
    .copy()
)


print(
    "\n"
    + "=" * 80
)

print(
    "HATALI SINIFLANDIRMALAR"
)

print(
    "=" * 80
)


if len(
    errors_df
) == 0:

    print(
        "\nHatalı sınıflandırma yok."
    )

else:

    print(
        errors_df[
            [
                "question_number",
                "question_type",
                "question",
                "top1_similarity",
                "predicted_type",
                "top1_title",
            ]
        ]
        .to_string(
            index=False
        )
    )


# ============================================================
# THRESHOLD'A EN YAKIN SORULAR
# ============================================================

df[
    "distance_to_threshold"
] = np.abs(
    df[
        "top1_similarity"
    ]
    - selected_threshold
)


closest_df = (
    df
    .sort_values(
        "distance_to_threshold"
    )
    .head(10)
)


print(
    "\n"
    + "=" * 80
)

print(
    "THRESHOLD'A EN YAKIN 10 SORU"
)

print(
    "=" * 80
)


print(
    closest_df[
        [
            "question_number",
            "question_type",
            "question",
            "top1_similarity",
            "distance_to_threshold",
            "top1_title",
        ]
    ]
    .to_string(
        index=False
    )
)


# ============================================================
# JSON OUTPUT
# ============================================================

threshold_data = {

    "selected_threshold": float(
        selected_threshold
    ),

    "exact_threshold": float(
        exact_threshold
    ),

    "selection_method": (
        selection_method
    ),

    "embedding_model": (
        "Qwen/Qwen3-Embedding-0.6B"
    ),

    "distance_metric": (
        "cosine"
    ),

    "benchmark_total": int(
        total_count
    ),

    "benchmark_positive": int(
        positive_count
    ),

    "benchmark_negative": int(
        negative_count
    ),

    "positive_min_similarity": float(
        positive_min
    ),

    "negative_max_similarity": float(
        negative_max
    ),

    "observed_gap": float(
        gap
    ),

    "metrics": {

        "tp": int(
            selected_metrics[
                "tp"
            ]
        ),

        "tn": int(
            selected_metrics[
                "tn"
            ]
        ),

        "fp": int(
            selected_metrics[
                "fp"
            ]
        ),

        "fn": int(
            selected_metrics[
                "fn"
            ]
        ),

        "accuracy": float(
            selected_metrics[
                "accuracy"
            ]
        ),

        "precision": float(
            selected_metrics[
                "precision"
            ]
        ),

        "recall": float(
            selected_metrics[
                "recall"
            ]
        ),

        "specificity": float(
            selected_metrics[
                "specificity"
            ]
        ),

        "f1": float(
            selected_metrics[
                "f1"
            ]
        ),

        "balanced_accuracy": float(
            selected_metrics[
                "balanced_accuracy"
            ]
        ),
    },
}


with open(
    THRESHOLD_JSON_OUTPUT,
    "w",
    encoding="utf-8"
) as file:

    json.dump(
        threshold_data,
        file,
        ensure_ascii=False,
        indent=4,
    )


# ============================================================
# TXT OUTPUT
# ============================================================

with open(
    THRESHOLD_TXT_OUTPUT,
    "w",
    encoding="utf-8"
) as file:

    file.write(
        "TURKISH MEDICAL RAG - THRESHOLD SELECTION\n"
    )

    file.write(
        "=" * 60
        + "\n\n"
    )

    file.write(
        f"Selected threshold: "
        f"{selected_threshold:.6f}\n"
    )

    file.write(
        f"Exact midpoint     : "
        f"{exact_threshold:.6f}\n"
    )

    file.write(
        f"Selection method   : "
        f"{selection_method}\n\n"
    )

    file.write(
        f"Positive min       : "
        f"{positive_min:.6f}\n"
    )

    file.write(
        f"Negative max       : "
        f"{negative_max:.6f}\n"
    )

    file.write(
        f"Observed gap       : "
        f"{gap:.6f}\n\n"
    )

    file.write(
        f"Accuracy           : "
        f"{selected_metrics['accuracy']:.6f}\n"
    )

    file.write(
        f"Precision          : "
        f"{selected_metrics['precision']:.6f}\n"
    )

    file.write(
        f"Recall             : "
        f"{selected_metrics['recall']:.6f}\n"
    )

    file.write(
        f"Specificity        : "
        f"{selected_metrics['specificity']:.6f}\n"
    )

    file.write(
        f"F1                 : "
        f"{selected_metrics['f1']:.6f}\n"
    )


# ============================================================
# FINAL OUTPUT
# ============================================================

print(
    "\n"
    + "=" * 80
)

print(
    "OUTPUT DOSYALARI"
)

print(
    "=" * 80
)


print(
    f"""
Threshold scan:
{THRESHOLD_SCAN_OUTPUT}

Selected threshold JSON:
{THRESHOLD_JSON_OUTPUT}

Selected threshold TXT:
{THRESHOLD_TXT_OUTPUT}
"""
)


print(
    "=" * 80
)

print(
    "07 THRESHOLD SELECTION TAMAMLANDI"
)

print(
    "=" * 80
)