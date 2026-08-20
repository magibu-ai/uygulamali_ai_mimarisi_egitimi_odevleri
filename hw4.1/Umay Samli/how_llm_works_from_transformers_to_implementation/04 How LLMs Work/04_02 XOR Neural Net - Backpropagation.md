# XOR Neural Net — Backpropagation

> [!summary] Core idea
> A neural network learns by adjusting weights and biases to reduce prediction error. Hidden layers let it represent nonlinear patterns that a single-layer perceptron cannot solve.

## The XOR problem

XOR outputs 1 when exactly one input is 1:

| x₁ | x₂ | XOR |
|---:|---:|---:|
| 0 | 0 | 0 |
| 0 | 1 | 1 |
| 1 | 0 | 1 |
| 1 | 1 | 0 |

These points are **not linearly separable**: no single straight decision boundary can place both positive cases on one side and both negative cases on the other.

## Why a single layer fails

A perceptron calculates:

$$\hat{y}=\sigma(x_1w_1+x_2w_2+b)$$

The weights control the importance of each input, the bias shifts the boundary, and sigmoid maps the result to a value between 0 and 1. Regardless of how its three parameters are adjusted, this architecture can only learn one linear boundary, so it cannot represent XOR.

## Why a hidden layer succeeds

The demo adds four hidden neurons, producing a **2 → 4 → 1** network. Hidden neurons learn intermediate detectors such as AND-like, OR-like, or NOR-like patterns. The output layer combines these simpler features into the nonlinear XOR result.

Training repeats four steps:

1. Run a forward pass and produce predictions.
2. Measure the error against the correct XOR outputs.
3. Use the chain rule to propagate error gradients backward.
4. Update every weight and bias in the direction that reduces the error.

This is **backpropagation**. The network’s learned behavior is stored entirely in its numerical weights and biases—not in new hand-written rules. Modern LLMs use vastly more parameters and more complex layers, but they are trained with the same basic forward-pass, loss, backward-pass, and update cycle.
