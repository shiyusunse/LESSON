# CALL



This repository belongs to our submitted manuscript:
> **C**ausality-**A**ided Evaluation and Explanation of **L**arge **L**anguage Model-based Code Generation

## Introduction

While code generation has been widely used in various software development scenarios, the quality of the generated code is not guaranteed. This has been a particular concern in the era of large language models (LLMs)-based code generation, where LLMs, deemed a complex and powerful black-box model, are instructed by a high-level natural language specification, namely a prompt, to generate code. Nevertheless, effectively evaluating and explaining the code generation capability of LLMs is inherently challenging, given the complexity of LLMs and the lack of transparency. In this paper, we launch a causality analysis-based approach to systematically analyze the causal relations between the LLM input prompts and the generated code. We first propose a novel causal graph-based representation of the prompt and the generated code, which is established over the fine-grained, human-understandable concepts in the input prompts. The formed causal graph is then used to identify the causal relations between the prompt and the derived code. We illustrate the insights that our framework can provide by studying over 12 popular LLMs for code generation and two datasets. The results of these studies illustrate the potential of our technique to provide insights into LLM effectiveness and aid end-users in understanding predictions. Additionally, we demonstrate that our approach provides actionable insights to improve the quality of the LLM-generated code by properly calibrating the prompt.


## Dependency

We list the main dependencies for running the code in `./requirements.txt`.

## Information

./Figure7.xlsx: The full data of Figure 7 in the paper.

./Human evaluation of learned causal graph(1-5).xlsx: Human evaluation results.
