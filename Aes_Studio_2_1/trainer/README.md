# Aes Model Factory

Three different mechanisms serve different goals:

1. **Knowledge/RAG** — use the Knowledge page when Aes should be able to look information up. This is the safest way to give Aes books/manuals without changing weights.
2. **SFT / LoRA** — use `train_lora.py` when you want to change how Aes behaves, follows workflows, uses tools, writes code, etc.
3. **Continued pretraining** — use `build_text_corpus.py` + `continue_pretrain.py` only for large lawful domain corpora when you intentionally want to alter the base model's learned distribution. It needs more compute and can cause catastrophic forgetting/regressions.

Always run Aes evals before promoting a candidate. The owner decides what becomes Aes 2.1/3.0.
