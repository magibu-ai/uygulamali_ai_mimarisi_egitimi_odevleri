# Similarity Threshold Calibration Report

This report presents the empirical calibration results for **Ollama (`embeddinggemma:300m`)** and **ChromaDB** using **20 Positive (Relevant Medical)** and **10 Negative (Irrelevant Non-Medical)** queries evaluated against **446 medical text chunks**.

> 💡 **Data & Script Reference:** The dataset queries (20 positive & 10 negative benchmark queries), data collection, and score evaluation logic are defined in [benchmark_threshold.py](file:///c:/Users/90535/source/magibu/MedRAG/benchmark_threshold.py). Run `python benchmark_threshold.py` to reproduce these statistical metrics.

---

## 📊 1. Statistical Similarity Score Distribution

| Metric | Relevant Queries (20 Positive) | Irrelevant Queries (10 Negative) | Margin / Difference |
| :--- | :---: | :---: | :---: |
| **Minimum Score** | **0.4465** | 0.2320 | **+0.2145** |
| **Maximum Score** | 0.8790 | **0.4901** | **+0.3889** |
| **Mean Score** | **0.6365** | **0.3720** | **+0.2645** |
| **Median Score** | 0.6151 | 0.3765 | +0.2386 |

### 📌 Key Findings:
1. Highest similarity score for an irrelevant query: **`0.4901`** (*"siber güvenlik"*).
2. Lowest similarity score for a relevant query: **`0.4465`** (*"Bebeklerde burun tıkanıklığı"*).
3. The mean score for relevant queries is **`0.6365`**, whereas irrelevant queries average **`0.3720`**.

---

## 🧪 2. Threshold Simulation & Accuracy Metrics

| Threshold (T) | True Positives (TP) | False Positives (FP) | False Negatives (FN) | Accuracy |
| :---: | :---: | :---: | :---: | :---: |
| **0.300** | 20 | 8 | 0 | 73.3% |
| **0.350** | 20 | 7 | 0 | 76.7% |
| **0.400** | 20 | 3 | 0 | 90.0% |
| **0.425** | 20 | 2 | 0 | **93.3%** |
| **🏆 0.450** | **19** | **1** | **1** | **93.3%** |
| **🏆 0.480** | **18** | **1** | **2** | **90.0%** |
| **0.500** | 16 | 0 | 4 | 86.7% |
| **0.550** | 16 | 0 | 4 | 86.7% |

---

## 🏆 3. Conclusion & Parameter Selection

- Thresholds of **`0.500` and above** begin dropping weakly-matched relevant queries (increasing False Negatives).
- Thresholds of **`0.400` and below** risk admitting off-topic queries (increasing False Positives).
- **Optimal Configured Threshold: `0.480`**

### Rationale for `0.480`:
1. Filters out ~90% of off-topic queries.
2. Captures ~90% of genuine medical queries.

> Configured in `config.py` as **`SIMILARITY_THRESHOLD = 0.48`**.
