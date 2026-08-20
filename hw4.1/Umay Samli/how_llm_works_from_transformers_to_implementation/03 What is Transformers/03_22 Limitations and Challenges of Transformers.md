Transformers are powerful, but their advantages have practical costs.

- **Quadratic attention cost:** standard self-attention builds a score for every token pair, so time and memory grow as $O(n^2)$ with sequence length. Long contexts quickly become expensive.
- **Large resource requirements:** strong models require substantial training data, compute, memory, money, and energy. Inference can also have high latency and deployment cost.
- **Data quality and reliability:** noisy or limited data can cause overfitting and spurious correlations. Even large models can produce confident but incorrect outputs.
- **Bias:** models learn social and cultural biases present in their training corpora, which can appear in downstream behavior.
- **Efficiency trade-offs:** sparse or approximate attention can reduce long-context cost, but may lose information or modeling accuracy.

Therefore theoretical scalability does not remove the need to balance model size and context length against efficiency, reliability, environmental impact, and responsible use. Long-context modeling remains an active research problem.
