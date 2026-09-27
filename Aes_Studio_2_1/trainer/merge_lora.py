from __future__ import annotations
import argparse

def main():
    p=argparse.ArgumentParser();p.add_argument('--base',required=True);p.add_argument('--adapter',required=True);p.add_argument('--output',required=True);a=p.parse_args()
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from peft import PeftModel
    base=AutoModelForCausalLM.from_pretrained(a.base,device_map='auto',trust_remote_code=True)
    model=PeftModel.from_pretrained(base,a.adapter).merge_and_unload();model.save_pretrained(a.output,safe_serialization=True,max_shard_size='5GB')
    AutoTokenizer.from_pretrained(a.base,trust_remote_code=True).save_pretrained(a.output)
    print('Merged model saved to',a.output)
if __name__=='__main__':main()
