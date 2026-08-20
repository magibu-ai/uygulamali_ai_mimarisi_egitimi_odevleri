# Simple Chat — Pattern Matching

> [!summary] Core idea
> A chatbot interface can look intelligent even when its responses come entirely from hard-coded rules. Streaming text is a presentation technique, not evidence that a model understands language.

## The ELIZA approach

The demo is inspired by **ELIZA**, Joseph Weizenbaum’s 1966 pattern-matching chatbot. It cleans and inspects the user’s text, then selects a response with simple conditions:

| Detected pattern | Example response |
|---|---|
| A greeting such as “hello” | “Hello! How can I help you today?” |
| “I feel X” | “Why do you feel X?” |
| “my X” | “Tell me more about your X.” |
| The word “worried” | A follow-up question |
| No known pattern | A random generic continuation |

The complete “intelligence” is a chain of string checks. It has no training process, learned parameters, semantic representation, or genuine understanding.

## Why can it still feel intelligent?

People naturally search for meaning in a conversation. A response that reflects part of the input can feel personal even when it was produced mechanically. ELIZA showed that convincing interaction does not necessarily imply deep reasoning.

The application also streams its canned response one word at a time using Server-Sent Events. This creates the familiar typing effect used by modern chat applications, but the same interface can sit in front of either a few rules or a billion-parameter model.

## Main limitation

A rule-based chatbot only handles patterns anticipated by its programmer. It cannot learn from examples, generalize to unfamiliar language, or build rich contextual representations. [[04_02 XOR Neural Net - Backpropagation|Neural networks]] replace hand-written response rules with parameters learned from data.
