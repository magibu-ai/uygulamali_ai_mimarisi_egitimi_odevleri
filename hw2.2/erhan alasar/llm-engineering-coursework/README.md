# P02.2 - LangUsta Custom Benchmark

This project evaluates LangUsta and four comparison models on a custom Turkish
multiple-choice benchmark. The benchmark contains 100 records held out before
the `langusta-mcq-letter-lora` training run.

## Evaluation Protocol

- Source: `AhmetSemih/Deepseek-mcq-reasoning-dataset`
- Test size: 100 records
- Choices: five (`A`–`E`)
- Decoding: greedy, maximum four new tokens
- Scoring: exact first-letter match
- Reported metrics: accuracy, valid-format rate, correct count, and runtime

Five systems are evaluated under the same protocol:

1. LangUsta MCQ Letter LoRA
2. Qwen2.5-0.5B-Instruct
3. Qwen2.5-1.5B-Instruct
4. SmolLM2-1.7B-Instruct
5. Gemma 3 1B Instruct 4-bit

## Results

| Model | Correct | Accuracy |
| --- | ---: | ---: |
| Qwen2.5-1.5B-Instruct | 33/100 | 33% |
| LangUsta-MCQ-Letter-LoRA | 29/100 | 29% |
| SmolLM2-1.7B-Instruct | 23/100 | 23% |
| Qwen2.5-0.5B-Instruct | 19/100 | 19% |
| Gemma-3-1B-Instruct-4bit | 19/100 | 19% |

Detailed predictions and machine-readable summaries are available in the
`results/` directory.

## Kaggle

1. Upload `notebooks/LangUstaCustomBenchmark.ipynb` to Kaggle.
2. Add the extracted `langusta-mcq-letter-lora` folder as a Kaggle Dataset input.
3. Enable Internet and select a GPU accelerator.
4. Run all cells.
5. Download `/kaggle/working/langusta-custom-benchmark.zip`.

The archive contains the benchmark JSONL, per-model predictions, a machine-readable
summary, and a Markdown report for GitHub and the Hugging Face model card.
