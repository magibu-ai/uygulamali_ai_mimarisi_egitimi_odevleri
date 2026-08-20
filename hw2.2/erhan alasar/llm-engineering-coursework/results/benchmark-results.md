# LangUsta Custom Benchmark Results

The benchmark contains 100 Turkish five-choice questions held out before fine-tuning.
All systems use greedy decoding and strict first-letter exact-match scoring.

| Model | Correct | Accuracy | Runtime (s) |
|---|---:|---:|---:|
| Qwen2.5-1.5B-Instruct | 33/100 | 33% | 20.90 |
| LangUsta-MCQ-Letter-LoRA | 29/100 | 29% | 21.29 |
| SmolLM2-1.7B-Instruct | 23/100 | 23% | 29.29 |
| Qwen2.5-0.5B-Instruct | 19/100 | 19% | 22.40 |
| Gemma-3-1B-Instruct-4bit | 19/100 | 19% | 30.35 |
