import io
import json
import logging
import math
import random
import numpy as np
import os
import pprint
import sys
import time
import transformers
import torch


# for timing and debugging
from datetime import datetime, date
from tqdm import tqdm


question = (
    ""
)
re_question = "\nQUESTION:\n" + question + "\n" + "\ndef solution(strng):\n\t"
re_question += "\nUse Call-Based format"
re_question += "\nANSWER:\n"


# Tokenizer
tokenizer = transformers.GPT2Tokenizer.from_pretrained("gpt2")
# tokenizer = transformers.AutoTokenizer.from_pretrained(args.arch)

# Set up model
print("Loading model...")
model = transformers.GPTNeoForCausalLM.from_pretrained("")
model.cuda()
print(f"Loaded model.")

code_list = []
try:
    with torch.no_grad():
        input_ids = (
            torch.LongTensor(tokenizer.encode(re_question, verbose=False))
            .unsqueeze(0)
            .cuda()
        )
        output_ids = model.generate(
            input_ids,
            num_beams=5,
            early_stopping=True,
            max_length=1024 - len(input_ids),
        )
        output_str = tokenizer.decode(output_ids[0])
except Exception as e:
    if (
        isinstance(e, UnboundLocalError)
        and str(e) == "local variable 'next_tokens' referenced before assignment"
    ):
        # See https://github.com/huggingface/transformers/issues/5118
        print("Problem text was > 1024 tokens, so cannot do generation")
        print(e)
    else:
        print("Unexpected exception in generating solution")
        print(e)
    # Default to empty string on errors
    output_str = ""
output_str = output_str.split("ANSWER:\n")[1].replace("<|endoftext|>", "")
print("Generated code:\n", output_str)


def solution(strng):
    count = 0
    for x in strng:
        if x.islower():
            count += 1
    return count
