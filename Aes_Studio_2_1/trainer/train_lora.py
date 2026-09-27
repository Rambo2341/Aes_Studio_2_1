"""Aes Model Factory - LoRA SFT trainer.

This intentionally trains a new adapter/version only from datasets the owner supplies.
It does not download or bundle a proprietary model. The base model's own license still applies.
"""
from __future__ import annotations
import argparse, json
from pathlib import Path


def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument('--base',required=True,help='Hugging Face model id or local model folder')
    p.add_argument('--dataset',required=True,help='Aes JSONL exported from Training Lab')
    p.add_argument('--output',required=True,help='Output adapter folder')
    p.add_argument('--epochs',type=float,default=1.0)
    p.add_argument('--lr',type=float,default=2e-4)
    p.add_argument('--batch',type=int,default=1)
    p.add_argument('--grad-accum',type=int,default=8)
    p.add_argument('--max-seq',type=int,default=4096)
    p.add_argument('--qlora',action='store_true',help='load the base in 4-bit (bitsandbytes) to fit 7B models on ~8-12 GB GPUs')
    p.add_argument('--rank',type=int,default=32,help='LoRA rank (16 saves memory)')
    return p.parse_args()


def main():
    a=parse_args()
    try:
        import torch
        from datasets import load_dataset
        from transformers import AutoModelForCausalLM, AutoTokenizer
        from peft import LoraConfig
        from trl import SFTConfig, SFTTrainer
    except Exception as e:
        raise SystemExit('Install trainer/requirements-training.txt first. '+str(e))

    tok=AutoTokenizer.from_pretrained(a.base,use_fast=True,trust_remote_code=True)
    if tok.pad_token is None: tok.pad_token=tok.eos_token
    dtype=torch.bfloat16 if torch.cuda.is_available() and torch.cuda.is_bf16_supported() else torch.float16
    model=None
    if a.qlora:
        from transformers import BitsAndBytesConfig
        from peft import prepare_model_for_kbit_training
        q=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',bnb_4bit_use_double_quant=True,bnb_4bit_compute_dtype=dtype)
        model=AutoModelForCausalLM.from_pretrained(a.base,quantization_config=q,device_map='auto',trust_remote_code=True)
        model=prepare_model_for_kbit_training(model,use_gradient_checkpointing=True)
    if model is None: model=AutoModelForCausalLM.from_pretrained(a.base,torch_dtype=dtype if torch.cuda.is_available() else None,device_map='auto' if torch.cuda.is_available() else None,trust_remote_code=True)
    ds=load_dataset('json',data_files=a.dataset,split='train')

    def format_row(ex):
        msgs=ex['messages']
        if hasattr(tok,'apply_chat_template'):
            return tok.apply_chat_template(msgs,tokenize=False,add_generation_prompt=False)
        return '\n'.join(f"{m['role'].upper()}: {m['content']}" for m in msgs)

    peft=LoraConfig(r=a.rank,lora_alpha=a.rank*2,lora_dropout=0.05,bias='none',task_type='CAUSAL_LM',target_modules='all-linear')
    kw=dict(output_dir=a.output,num_train_epochs=a.epochs,learning_rate=a.lr,per_device_train_batch_size=a.batch,gradient_accumulation_steps=a.grad_accum,logging_steps=5,save_strategy='epoch',report_to='none',packing=True,gradient_checkpointing=a.qlora)
    try: cfg=SFTConfig(max_seq_length=a.max_seq,**kw)   # trl < 0.20
    except TypeError: cfg=SFTConfig(max_length=a.max_seq,**kw)
    trainer=SFTTrainer(model=model,args=cfg,train_dataset=ds,peft_config=peft,formatting_func=format_row,processing_class=tok)
    trainer.train(); trainer.save_model(a.output); tok.save_pretrained(a.output)
    Path(a.output,'aes_candidate.json').write_text(json.dumps({'base':a.base,'dataset':str(Path(a.dataset).resolve()),'epochs':a.epochs,'learning_rate':a.lr,'type':'QLoRA-SFT' if a.qlora else 'LoRA-SFT'},indent=2),encoding='utf-8')
    print('Aes adapter saved to',a.output)

if __name__=='__main__':main()
