**Pretraining** teaches a Transformer broad, reusable representations from a very large, usually unlabeled dataset. A self-supervised objective such as next-token prediction supplies its own labels from the text. Through this process the model learns syntax, semantics, patterns, and long-range relationships without targeting one particular downstream task.

**Fine-tuning** starts from those pretrained weights and continues training on a smaller, task-specific or domain-specific labeled dataset. It adapts the general representations to tasks such as sentiment classification, question answering, or specialized text generation.

**Transfer learning** is the broader idea that knowledge learned for one setting can be reused in another. Pretraining plus fine-tuning is an effective transfer-learning workflow: one expensive foundation model supports many applications, reducing the data, time, and compute required compared with training a new model from scratch for every task.

The architecture remains mostly unchanged. Usually only the output head and training objective need to be adapted, while the Transformer backbone provides the reusable knowledge.
