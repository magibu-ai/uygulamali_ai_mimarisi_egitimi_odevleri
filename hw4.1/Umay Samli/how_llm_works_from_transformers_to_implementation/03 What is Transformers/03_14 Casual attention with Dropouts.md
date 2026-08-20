**Dropout** is a regularization technique that randomly removes some activations or connections during training. It prevents the network from depending too strongly on a few dominant features and forces it to learn redundant, robust patterns.

In causal self-attention, dropout is applied to the attention probabilities after causal masking and softmax. Some otherwise valid attention connections are randomly set to zero, while future connections remain permanently forbidden by the causal mask.

Frameworks such as PyTorch scale the surviving values by $1/(1-p)$, where $p$ is the dropout probability. This keeps the expected activation magnitude approximately unchanged even though an individual row may no longer sum to exactly one during a training step.

Dropout is stochastic only during training. During evaluation or inference it is disabled, so all permitted attention connections are used and the model behaves deterministically. Causal masking and dropout therefore have different jobs: masking enforces the autoregressive rule, while dropout reduces overfitting.
