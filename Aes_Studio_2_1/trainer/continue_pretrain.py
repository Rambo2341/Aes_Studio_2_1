"""Continued pretraining on an owner-provided text corpus.
Use only data you have the right to train on. This can be expensive and can degrade a model if misconfigured.
"""
from __future__ import annotations
import argparse

def main():
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--dataset',required=True);p.add_argument('--output',required=True);p.add_argument('--steps',type=int,default=500);p.add_argument('--lr',type=float,default=2e-5);p.add_argument('--seq',type=int,default=2048);a=p.parse_args()
    import torch
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM,AutoTokenizer,TrainingArguments,Trainer,DataCollatorForLanguageModeling
    tok=AutoTokenizer.from_pretrained(a.base,trust_remote_code=True,use_fast=True)
    if tok.pad_token is None:tok.pad_token=tok.eos_token
    model=AutoModelForCausalLM.from_pretrained(a.base,trust_remote_code=True,device_map='auto' if torch.cuda.is_available() else None,torch_dtype=(torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else None))
    ds=load_dataset('json',data_files=a.dataset,split='train')
    def enc(ex):return tok(ex['text'],truncation=True,max_length=a.seq)
    ds=ds.map(enc,remove_columns=ds.column_names)
    args=TrainingArguments(output_dir=a.output,max_steps=a.steps,learning_rate=a.lr,per_device_train_batch_size=1,gradient_accumulation_steps=8,logging_steps=5,save_steps=max(50,a.steps//5),report_to='none',bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),fp16=torch.cuda.is_available() and not torch.cuda.is_bf16_supported())
    trainer=Trainer(model=model,args=args,train_dataset=ds,data_collator=DataCollatorForLanguageModeling(tok,mlm=False));trainer.train();trainer.save_model(a.output);tok.save_pretrained(a.output)
    print('Continued-pretrained model saved to',a.output)
if __name__=='__main__':main()
