

import os
import openai
import json
from tqdm import tqdm
import time
from tree_sitter import Language, Parser


def analyse(code,lan='c_sharp'): # lan='c-sharp' / 'python'
    PY_LANGUAGE = Language(r'', lan)
    parser = Parser()
    parser.set_language(PY_LANGUAGE)

    tree = parser.parse(bytes(code, "utf8"))
    root_node = tree.root_node
    if root_node.has_error:
        return 1
    return 0

def main():
    mode = 'codesyn' # codesyn
    if mode == 'codetrans':
        dataset_name = r'C:\Users\Admin\PycharmProjects\node2vec\openai\pl2pl_codetrans\codex\INCON_train.jsonl'
        with open(dataset_name, 'r', encoding='utf-8') as f:
            rawcodelist = f.readlines()
            length = len(rawcodelist)
            total_error = 0
            for idx, rawcode in tqdm(enumerate(rawcodelist)):
                line=rawcode.strip()
                js=json.loads(line)
                src_code = js['src_code']
                tgt_code = js['tgt_code']
                has_error = analyse(tgt_code,lan='c_sharp')
                total_error += has_error
            print('total error is {} and error rate is {}'.format(total_error,float(total_error)/length))
    elif mode == 'codesyn':
        dataset_name = 'C:\Users\Admin\PycharmProjects\node2vec\openai\pl2nl\conala-corpus\INCON_conala_refine_train_CodeXans.jsonl'    # 0.0248
        # dataset_name = r'C:\Users\Admin\PycharmProjects\node2vec\openai\pl2nl\conala-corpus\ZEROCOT_conala_refine_train_CodeXans.jsonl'  # 0.0462
        # dataset_name = r'C:\Users\Admin\PycharmProjects\node2vec\openai\pl2nl\conala-corpus\conala_refine_train_CodeXans.jsonl'  # 0.0240

        with open(dataset_name, 'r', encoding='utf-8') as f:
            rawcodelist = f.readlines()
            length = len(rawcodelist)
            total_error = 0

            for idx, rawcode in tqdm(enumerate(rawcodelist)):
                line=rawcode.strip()
                js=json.loads(line)
                code = js['response']['choices'][0]['text'].strip()
                has_error = analyse(code,lan='python')
                total_error += has_error
                print('total error is {} and error rate is {}'.format(total_error, round(float(total_error) / length,5) ))


main()