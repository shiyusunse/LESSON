import os
import re
import math
import json
import time
import random
import argparse
import numpy as np
import pandas as pd
from typing import *
from tqdm import tqdm, trange
import openai
import spacy

# spacy.require_cpu()
spacy.prefer_gpu()
import nltk
from nltk.tokenize import word_tokenize
from nltk.tokenize.treebank import TreebankWordDetokenizer
from nltk.corpus import wordnet
from nltk.corpus import stopwords
import lftk
from lingfeat import extractor
from datasets import load_dataset

import myUtils
from myUtils import time_statistic, logme, print_time_statistic, TimeoutError
from llm import openai_set, openai_rephrase, INSTRUCTION_DICT, ROLE_DICT, SCENARIO_DICT

DATASETS_DICT = {
    "apps": "codeparrot/apps",
    "contests": "deepmind/code_contests",
}
STOP_WORDS = set(stopwords.words("english"))


@time_statistic
def extract_LFTK_features(text: str) -> Dict[str, Union[float, int]]:
    text = text.replace("\n", " ")
    # spacy.prefer_gpu()
    nlp = spacy.load("en_core_web_sm")
    doc = nlp(text)
    LFTK = lftk.Extractor(docs=doc)
    LFTK.customize(round_decimal=2)
    feature_dict = LFTK.extract()
    return feature_dict


@time_statistic
def extract_LingFeat_features(text: str) -> Dict[str, Union[float, int]]:
    text = text.replace("\n", " ")
    ret_dict = {}

    LingFeat = extractor.pass_text(text)
    LingFeat.preprocess()

    TrSF = LingFeat.TrSF_()
    WoKF = LingFeat.WoKF_()  # Wikipedia Knowledge Features
    WBKF = LingFeat.WBKF_()  # WeeBit Corpus Knowledge Features
    OSKF = LingFeat.OSKF_()  # OneStopEng Corpus Knowledge Features

    ret_dict.update(TrSF)
    ret_dict.update(WoKF)
    ret_dict.update(WBKF)
    ret_dict.update(OSKF)
    for k, v in ret_dict.items():
        if isinstance(v, float):
            ret_dict[k] = round(v, 2)
    return ret_dict


def get_synonyms(word: str) -> List[str]:
    synonyms = set()

    for syn in wordnet.synsets(word):
        for l in syn.lemmas():
            synonym = l.name().replace("_", " ").replace("-", " ").lower()
            synonym = "".join(
                [char for char in synonym if char in " qwertyuiopasdfghjklzxcvbnm"]
            )
            synonyms.add(synonym)

    if word in synonyms:
        synonyms.remove(word)
    return list(synonyms)


@time_statistic
def random_synonym_replace(text: str, part_replace: float = 0.1) -> str:
    # replace one random word in the text with its synonyms
    words = word_tokenize(text)
    if part_replace == -1:
        n_to_replace = 1
    else:
        n_to_replace = int(len(words) * part_replace)

    checked_words = set()
    replaced_count = 0
    while replaced_count < n_to_replace:
        idx = np.random.randint(0, len(words))
        if idx in checked_words:
            continue
        word = words[idx]
        checked_words.add(idx)
        synonyms = get_synonyms(word)

        if len(synonyms) >= 1:
            synonym = random.choice(list(synonyms))
            words[idx] = synonym
            replaced_count += 1

    return TreebankWordDetokenizer().detokenize(words)


@time_statistic
def rephrase(text: str, context: str, instruction, n_out, engine) -> List[str]:
    try:
        ret_list = openai_rephrase(text, context, instruction, n_out, engine)
        return ret_list
    except TimeoutError:
        return []


class DataCollector(object):
    def __init__(
        self,
        dataset_name: str,
        save_path: str,
        sample_num: int,
        split_name: str,
        openai_choice: int,
        n_out: int = 1,
    ) -> None:
        self.name: str = dataset_name
        self.n_out: int = n_out
        assert self.name is not None and self.name in DATASETS_DICT.keys()
        origin_dataset = load_dataset(DATASETS_DICT[self.name])
        assert split_name in origin_dataset.keys()
        self.split_name = split_name
        self.dataset = origin_dataset[self.split_name]
        self.filtered_save_path = os.path.join(
            save_path, f"{self.name}_{self.split_name}.txt"
        )
        self.filtered_list = self.read_filtered()
        if len(self.dataset) - len(self.filtered_list) < sample_num:
            sample_num = len(self.dataset) - len(self.filtered_list)
        self.sample_num = sample_num
        self.save_path = save_path
        self.collected_df = pd.DataFrame()
        self.re_collected_df = pd.DataFrame()
        self.start_timestamp = time.time()
        self.engine = openai_set(openai_choice)

    @time_statistic
    def preprocess_text(self, text: str) -> Tuple[str, str]:
        lines_list = text.split("\n")
        # iterate over lines, lower case, remove punctuations, to find the first line that starts with "example"
        split_idx = -1
        for idx, line in enumerate(lines_list):
            line = line.lower()
            line = re.sub(r"[^\w\s]", "", line)
            if line.startswith("example"):
                split_idx = idx
                break

        if split_idx != -1:
            nl_text = "\n".join(lines_list[:split_idx])
            eg_text = "\n".join(lines_list[split_idx:])
        else:
            nl_text = text
            eg_text = ""
        return nl_text, eg_text

    @time_statistic
    def extract_data_features(self) -> Tuple[str, Dict[str, Union[float, int]]]:
        raise NotImplementedError

    def read_filtered(self) -> List[int]:
        # if the file does not exist, create one
        if not os.path.exists(self.filtered_save_path):
            with open(self.filtered_save_path, "w") as f:
                f.write("")
            return []
        else:
            with open(self.filtered_save_path, "r") as f:
                filtered = f.readlines()
            return [int(idx) for idx in filtered]

    def append_filtered(self, filtered_id: int) -> None:
        with open(self.filtered_save_path, "a") as f:
            f.write(f"{filtered_id}\n")

    def save_filtered(self) -> None:
        with open(self.filtered_save_path, "w") as f:
            for idx in self.filtered_list:
                f.write(f"{idx}\n")

    def save_to_csv(self) -> None:
        file_path = os.path.join(
            self.save_path,
            self.name,
            f"{self.split_name}_{self.start_timestamp}.csv",
        )
        self.collected_df.to_csv(file_path, index=False)

    def append_to_csv(self, add_df: pd.DataFrame, suffix: str = "") -> None:
        file_path = os.path.join(
            self.save_path,
            self.name,
            f"{self.split_name}_{suffix}_{self.start_timestamp}.csv",
        )
        add_df.to_csv(
            file_path, mode="a", header=not os.path.exists(file_path), index=False
        )

    def prior_run(self) -> None:
        sample_count = 0
        pbar = tqdm(total=self.sample_num)
        is_error = False
        while sample_count < self.sample_num and not is_error:
            data_df = pd.DataFrame()
            re_data_df = pd.DataFrame()
            p_idx = np.random.randint(0, len(self.dataset))
            if p_idx in self.filtered_list:
                continue
            status = True
            row = self.dataset[p_idx]
            data_row = {}
            data_row["p_idx"] = p_idx
            question, data_features = self.extract_data_features(row)
            if question == "ERROR":
                continue
            nl_quest, eg_quest = self.preprocess_text(question)
            if nl_quest == "":
                continue
            data_row["question_NL"] = repr(nl_quest)
            data_row["question_example"] = repr(eg_quest)
            data_row.update(data_features)

            # extract original question features
            orig_LFTK_features = extract_LFTK_features(nl_quest)
            orig_LingFeat_features = extract_LingFeat_features(nl_quest)
            data_row.update(orig_LFTK_features)
            data_row.update(orig_LingFeat_features)
            data_df = pd.concat([data_df, pd.DataFrame([data_row])])

            # extract rephrased question features
            for inst in INSTRUCTION_DICT.keys():
                if not status or is_error:
                    break
                rephrased_list = rephrase(
                    nl_quest, "", INSTRUCTION_DICT[inst], self.n_out, self.engine
                )
                if rephrased_list != []:
                    if len(rephrased_list) == 1 and rephrased_list[0] == "ERROR":
                        is_error = True
                        break
                    for r_idx, rephrased in enumerate(rephrased_list):
                        re_data_row = {}
                        re_data_row["p_idx"] = p_idx
                        re_data_row["re_idx"] = r_idx
                        re_data_row["Instruction"] = inst
                        re_data_row["Role"] = "None"
                        re_data_row["Scenario"] = "None"
                        re_data_row["Base"] = "None"
                        re_data_row["re_question_NL"] = repr(rephrased)
                        LFTK_features = extract_LFTK_features(rephrased)
                        LingFeat_features = extract_LingFeat_features(rephrased)
                        re_data_row.update(LFTK_features)
                        re_data_row.update(LingFeat_features)
                        re_data_df = pd.concat(
                            [re_data_df, pd.DataFrame([re_data_row])]
                        )
                else:
                    status = False
                    break

            for role in ROLE_DICT.keys():
                if not status or is_error:
                    break
                rephrased_list = rephrase(
                    nl_quest, " ".join(ROLE_DICT[role]), "", self.n_out, self.engine
                )
                if rephrased_list != []:
                    if len(rephrased_list) == 1 and rephrased_list[0] == "ERROR":
                        is_error = True
                        break
                    for r_idx, rephrased in enumerate(rephrased_list):
                        re_data_row = {}
                        re_data_row["p_idx"] = p_idx
                        re_data_row["re_idx"] = r_idx
                        re_data_row["Instruction"] = "None"
                        re_data_row["Role"] = role
                        re_data_row["Scenario"] = "None"
                        re_data_row["Base"] = "None"
                        re_data_row["re_question_NL"] = repr(rephrased)
                        LFTK_features = extract_LFTK_features(rephrased)
                        LingFeat_features = extract_LingFeat_features(rephrased)
                        re_data_row.update(LFTK_features)
                        re_data_row.update(LingFeat_features)
                        re_data_df = pd.concat(
                            [re_data_df, pd.DataFrame([re_data_row])]
                        )
                else:
                    status = False
                    break

            for scenario in SCENARIO_DICT.keys():
                if not status or is_error:
                    break
                rephrased_list = rephrase(
                    nl_quest, SCENARIO_DICT[scenario], "", self.n_out, self.engine
                )
                if rephrased_list != []:
                    if len(rephrased_list) == 1 and rephrased_list[0] == "ERROR":
                        is_error = True
                        break
                    for r_idx, rephrased in enumerate(rephrased_list):
                        re_data_row = {}
                        re_data_row["p_idx"] = p_idx
                        re_data_row["re_idx"] = r_idx
                        re_data_row["Instruction"] = "None"
                        re_data_row["Role"] = "None"
                        re_data_row["Scenario"] = scenario
                        re_data_row["Base"] = "None"
                        re_data_row["re_question_NL"] = repr(rephrased)
                        LFTK_features = extract_LFTK_features(rephrased)
                        LingFeat_features = extract_LingFeat_features(rephrased)
                        re_data_row.update(LFTK_features)
                        re_data_row.update(LingFeat_features)
                        re_data_df = pd.concat(
                            [re_data_df, pd.DataFrame([re_data_row])]
                        )
                else:
                    status = False
                    break

            # random rephrase
            rephrased_list = rephrase(nl_quest, "", "", self.n_out, self.engine)
            if rephrased_list != []:
                for r_idx, rephrased in enumerate(rephrased_list):
                    re_data_row = {}
                    re_data_row["p_idx"] = p_idx
                    re_data_row["re_idx"] = r_idx
                    re_data_row["Instruction"] = "None"
                    re_data_row["Role"] = "None"
                    re_data_row["Scenario"] = "None"
                    re_data_row["Base"] = "random"
                    re_data_row["re_question_NL"] = repr(rephrased)
                    LFTK_features = extract_LFTK_features(rephrased)
                    LingFeat_features = extract_LingFeat_features(rephrased)
                    re_data_row.update(LFTK_features)
                    re_data_row.update(LingFeat_features)
                    re_data_df = pd.concat([re_data_df, pd.DataFrame([re_data_row])])

            # random synonym replace one word
            mutated = random_synonym_replace(nl_quest, part_replace=-1)
            re_data_row = {}
            re_data_row["p_idx"] = p_idx
            re_data_row["re_idx"] = 0
            re_data_row["Instruction"] = "None"
            re_data_row["Role"] = "None"
            re_data_row["Scenario"] = "None"
            re_data_row["Base"] = "synonym_one"
            re_data_row["re_question_NL"] = repr(mutated)
            LFTK_features = extract_LFTK_features(mutated)
            LingFeat_features = extract_LingFeat_features(mutated)
            re_data_row.update(LFTK_features)
            re_data_row.update(LingFeat_features)
            re_data_df = pd.concat([re_data_df, pd.DataFrame([re_data_row])])

            # random synonym replace 10% words
            mutated = random_synonym_replace(nl_quest, part_replace=0.1)
            re_data_row = {}
            re_data_row["p_idx"] = p_idx
            re_data_row["re_idx"] = 0
            re_data_row["Instruction"] = "None"
            re_data_row["Role"] = "None"
            re_data_row["Scenario"] = "None"
            re_data_row["Base"] = "synonym_10p"
            re_data_row["re_question_NL"] = repr(mutated)
            LFTK_features = extract_LFTK_features(mutated)
            LingFeat_features = extract_LingFeat_features(mutated)
            re_data_row.update(LFTK_features)
            re_data_row.update(LingFeat_features)
            re_data_df = pd.concat([re_data_df, pd.DataFrame([re_data_row])])

            if is_error:
                print("Error! Sleeping...")
                break

            if status:
                self.append_to_csv(data_df, suffix="original")
                self.append_to_csv(re_data_df, suffix="rephrased")
                self.filtered_list.append(p_idx)
                self.append_filtered(p_idx)
                sample_count += 1
                pbar.update(1)

    def base_run(self) -> None:
        print("Base run...")
        original_df = pd.read_csv(
        )
        for index, text_row in tqdm(original_df.iterrows(), total=original_df.shape[0]):
            if index < 0:
                continue
            re_data_df = pd.DataFrame()
            nl_quest = eval(text_row["question_NL"])
            p_idx = int(text_row["p_idx"])

            # random rephrase
            rephrased_list = rephrase(nl_quest, "", "", self.n_out, self.engine)
            if rephrased_list != []:
                for r_idx, rephrased in enumerate(rephrased_list):
                    re_data_row = {}
                    re_data_row["p_idx"] = p_idx
                    re_data_row["re_idx"] = r_idx
                    re_data_row["Base"] = "random"
                    re_data_row["re_question_NL"] = repr(rephrased)
                    LFTK_features = extract_LFTK_features(rephrased)
                    LingFeat_features = extract_LingFeat_features(rephrased)
                    re_data_row.update(LFTK_features)
                    re_data_row.update(LingFeat_features)
                    re_data_df = pd.concat([re_data_df, pd.DataFrame([re_data_row])])

            # random synonym replace one word
            mutated = random_synonym_replace(nl_quest, part_replace=-1)
            re_data_row = {}
            re_data_row["p_idx"] = p_idx
            re_data_row["re_idx"] = 0
            re_data_row["Base"] = "synonym_one"
            re_data_row["re_question_NL"] = repr(mutated)
            LFTK_features = extract_LFTK_features(mutated)
            LingFeat_features = extract_LingFeat_features(mutated)
            re_data_row.update(LFTK_features)
            re_data_row.update(LingFeat_features)
            re_data_df = pd.concat([re_data_df, pd.DataFrame([re_data_row])])

            # random synonym replace 10% words
            mutated = random_synonym_replace(nl_quest, part_replace=0.1)
            re_data_row = {}
            re_data_row["p_idx"] = p_idx
            re_data_row["re_idx"] = 0
            re_data_row["Base"] = "synonym_10p"
            re_data_row["re_question_NL"] = repr(mutated)
            LFTK_features = extract_LFTK_features(mutated)
            LingFeat_features = extract_LingFeat_features(mutated)
            re_data_row.update(LFTK_features)
            re_data_row.update(LingFeat_features)
            re_data_df = pd.concat([re_data_df, pd.DataFrame([re_data_row])])

            self.append_to_csv(re_data_df, suffix="base")

    def run(self) -> None:
        sample_count = 0
        pbar = tqdm(total=self.sample_num)
        is_error = False
        while sample_count < self.sample_num and not is_error:
            data_df = pd.DataFrame()
            re_data_df = pd.DataFrame()
            p_idx = np.random.randint(0, len(self.dataset))
            if p_idx in self.filtered_list:
                continue
            status = True
            row = self.dataset[p_idx]
            data_row = {}
            data_row["p_idx"] = p_idx
            question, data_features = self.extract_data_features(row)
            if question == "ERROR":
                continue
            nl_quest, eg_quest = self.preprocess_text(question)
            if nl_quest == "":
                continue
            data_row["question_NL"] = repr(nl_quest)
            data_row["question_example"] = repr(eg_quest)
            data_row.update(data_features)

            # extract original question features
            orig_LFTK_features = extract_LFTK_features(nl_quest)
            orig_LingFeat_features = extract_LingFeat_features(nl_quest)
            data_row.update(orig_LFTK_features)
            data_row.update(orig_LingFeat_features)
            data_df = pd.concat([data_df, pd.DataFrame([data_row])])

            # extract rephrased question features
            for inst in INSTRUCTION_DICT.keys():
                if not status or is_error:
                    break
                rephrased_list = rephrase(
                    nl_quest, "", INSTRUCTION_DICT[inst], self.n_out, self.engine
                )
                if rephrased_list != []:
                    if len(rephrased_list) == 1 and rephrased_list[0] == "ERROR":
                        is_error = True
                        break
                    for r_idx, rephrased in enumerate(rephrased_list):
                        re_data_row = {}
                        re_data_row["p_idx"] = p_idx
                        re_data_row["re_idx"] = r_idx
                        re_data_row["Instruction"] = inst
                        re_data_row["Role"] = "None"
                        re_data_row["Scenario"] = "None"
                        re_data_row["Base"] = "None"
                        re_data_row["re_question_NL"] = repr(rephrased)
                        LFTK_features = extract_LFTK_features(rephrased)
                        LingFeat_features = extract_LingFeat_features(rephrased)
                        re_data_row.update(LFTK_features)
                        re_data_row.update(LingFeat_features)
                        re_data_df = pd.concat(
                            [re_data_df, pd.DataFrame([re_data_row])]
                        )
                else:
                    status = False
                    break

            for role in ROLE_DICT.keys():
                if not status or is_error:
                    break
                rephrased_list = rephrase(
                    nl_quest, " ".join(ROLE_DICT[role]), "", self.n_out, self.engine
                )
                if rephrased_list != []:
                    if len(rephrased_list) == 1 and rephrased_list[0] == "ERROR":
                        is_error = True
                        break
                    for r_idx, rephrased in enumerate(rephrased_list):
                        re_data_row = {}
                        re_data_row["p_idx"] = p_idx
                        re_data_row["re_idx"] = r_idx
                        re_data_row["Instruction"] = "None"
                        re_data_row["Role"] = role
                        re_data_row["Scenario"] = "None"
                        re_data_row["Base"] = "None"
                        re_data_row["re_question_NL"] = repr(rephrased)
                        LFTK_features = extract_LFTK_features(rephrased)
                        LingFeat_features = extract_LingFeat_features(rephrased)
                        re_data_row.update(LFTK_features)
                        re_data_row.update(LingFeat_features)
                        re_data_df = pd.concat(
                            [re_data_df, pd.DataFrame([re_data_row])]
                        )
                else:
                    status = False
                    break

            for scenario in SCENARIO_DICT.keys():
                if not status or is_error:
                    break
                rephrased_list = rephrase(
                    nl_quest, SCENARIO_DICT[scenario], "", self.n_out, self.engine
                )
                if rephrased_list != []:
                    if len(rephrased_list) == 1 and rephrased_list[0] == "ERROR":
                        is_error = True
                        break
                    for r_idx, rephrased in enumerate(rephrased_list):
                        re_data_row = {}
                        re_data_row["p_idx"] = p_idx
                        re_data_row["re_idx"] = r_idx
                        re_data_row["Instruction"] = "None"
                        re_data_row["Role"] = "None"
                        re_data_row["Scenario"] = scenario
                        re_data_row["Base"] = "None"
                        re_data_row["re_question_NL"] = repr(rephrased)
                        LFTK_features = extract_LFTK_features(rephrased)
                        LingFeat_features = extract_LingFeat_features(rephrased)
                        re_data_row.update(LFTK_features)
                        re_data_row.update(LingFeat_features)
                        re_data_df = pd.concat(
                            [re_data_df, pd.DataFrame([re_data_row])]
                        )
                else:
                    status = False
                    break

            if is_error:
                print("Error! Sleeping...")
                # break
                time.sleep(60)
                is_error = False
                continue

            if status:
                self.append_to_csv(data_df, suffix="original")
                self.append_to_csv(re_data_df, suffix="rephrased")
                self.filtered_list.append(p_idx)
                self.append_filtered(p_idx)
                sample_count += 1
                pbar.update(1)

    def random_run(self) -> None:
        sample_count = 0
        pbar = tqdm(total=self.sample_num)
        is_error = False
        while sample_count < self.sample_num and not is_error:
            data_df = pd.DataFrame()
            re_data_df = pd.DataFrame()
            p_idx = np.random.randint(0, len(self.dataset))
            if p_idx in self.filtered_list:
                continue
            status = True
            row = self.dataset[p_idx]
            data_row = {}
            data_row["p_idx"] = p_idx
            question, data_features = self.extract_data_features(row)
            if question == "ERROR":
                continue
            nl_quest, eg_quest = self.preprocess_text(question)
            if nl_quest == "":
                continue
            data_row["question_NL"] = repr(nl_quest)
            data_row["question_example"] = repr(eg_quest)
            data_row.update(data_features)

            # extract original question features
            orig_LFTK_features = extract_LFTK_features(nl_quest)
            orig_LingFeat_features = extract_LingFeat_features(nl_quest)
            data_row.update(orig_LFTK_features)
            data_row.update(orig_LingFeat_features)
            data_df = pd.concat([data_df, pd.DataFrame([data_row])])

            # extract rephrased question features
            selected_insts = random.sample(list(INSTRUCTION_DICT.keys()), 2)
            for inst in selected_insts:
                if not status or is_error:
                    break
                rephrased_list = rephrase(
                    nl_quest, "", INSTRUCTION_DICT[inst], self.n_out, self.engine
                )
                if rephrased_list != []:
                    if len(rephrased_list) == 1 and rephrased_list[0] == "ERROR":
                        is_error = True
                        break
                    for r_idx, rephrased in enumerate(rephrased_list):
                        re_data_row = {}
                        re_data_row["p_idx"] = p_idx
                        re_data_row["re_idx"] = r_idx
                        re_data_row["Instruction"] = inst
                        re_data_row["Role"] = "None"
                        re_data_row["Scenario"] = "None"
                        re_data_row["Base"] = "None"
                        re_data_row["re_question_NL"] = repr(rephrased)
                        LFTK_features = extract_LFTK_features(rephrased)
                        LingFeat_features = extract_LingFeat_features(rephrased)
                        re_data_row.update(LFTK_features)
                        re_data_row.update(LingFeat_features)
                        re_data_df = pd.concat(
                            [re_data_df, pd.DataFrame([re_data_row])]
                        )
                else:
                    status = False
                    break

            selected_roles = random.sample(list(ROLE_DICT.keys()), 1)
            for role in selected_roles:
                if not status or is_error:
                    break
                rephrased_list = rephrase(
                    nl_quest, " ".join(ROLE_DICT[role]), "", self.n_out, self.engine
                )
                if rephrased_list != []:
                    if len(rephrased_list) == 1 and rephrased_list[0] == "ERROR":
                        is_error = True
                        break
                    for r_idx, rephrased in enumerate(rephrased_list):
                        re_data_row = {}
                        re_data_row["p_idx"] = p_idx
                        re_data_row["re_idx"] = r_idx
                        re_data_row["Instruction"] = "None"
                        re_data_row["Role"] = role
                        re_data_row["Scenario"] = "None"
                        re_data_row["Base"] = "None"
                        re_data_row["re_question_NL"] = repr(rephrased)
                        LFTK_features = extract_LFTK_features(rephrased)
                        LingFeat_features = extract_LingFeat_features(rephrased)
                        re_data_row.update(LFTK_features)
                        re_data_row.update(LingFeat_features)
                        re_data_df = pd.concat(
                            [re_data_df, pd.DataFrame([re_data_row])]
                        )
                else:
                    status = False
                    break
            
            selected_scenarios = random.sample(list(SCENARIO_DICT.keys()), 1)
            for scenario in selected_scenarios:
                if not status or is_error:
                    break
                rephrased_list = rephrase(
                    nl_quest, SCENARIO_DICT[scenario], "", self.n_out, self.engine
                )
                if rephrased_list != []:
                    if len(rephrased_list) == 1 and rephrased_list[0] == "ERROR":
                        is_error = True
                        break
                    for r_idx, rephrased in enumerate(rephrased_list):
                        re_data_row = {}
                        re_data_row["p_idx"] = p_idx
                        re_data_row["re_idx"] = r_idx
                        re_data_row["Instruction"] = "None"
                        re_data_row["Role"] = "None"
                        re_data_row["Scenario"] = scenario
                        re_data_row["Base"] = "None"
                        re_data_row["re_question_NL"] = repr(rephrased)
                        LFTK_features = extract_LFTK_features(rephrased)
                        LingFeat_features = extract_LingFeat_features(rephrased)
                        re_data_row.update(LFTK_features)
                        re_data_row.update(LingFeat_features)
                        re_data_df = pd.concat(
                            [re_data_df, pd.DataFrame([re_data_row])]
                        )
                else:
                    status = False
                    break

            if is_error:
                print("Error! Sleeping...")
                # break
                time.sleep(60)
                is_error = False
                continue

            if status:
                self.append_to_csv(data_df, suffix="original_random")
                self.append_to_csv(re_data_df, suffix="rephrased_random")
                self.filtered_list.append(p_idx)
                self.append_filtered(p_idx)
                sample_count += 1
                pbar.update(1)


class AppsCollector(DataCollector):
    def __init__(
        self,
        save_path: str,
        sample_num: int,
        split_name: str,
        openai_choice: int,
        n_out: int = 1,
    ) -> None:
        super().__init__(
            "apps", save_path, sample_num, split_name, openai_choice, n_out
        )

    def extract_data_features(
        self, row: pd.Series
    ) -> Tuple[str, Dict[str, Union[float, int]]]:
        if row["solutions"] == "" or row["input_output"] == "":
            return ("ERROR", {})
        question = row["question"]
        data_features = {}
        match row["difficulty"]:
            case "introductory":
                data_features["difficulty"] = 1
            case "interview":
                data_features["difficulty"] = 2
            case "competition":
                data_features["difficulty"] = 3
            case _:
                data_features["difficulty"] = 0

        return (question, data_features)


class ContestCollector(DataCollector):
    def __init__(
        self,
        save_path: str,
        sample_num: int,
        split_name: str,
        openai_choice: int,
        n_out: int = 1,
    ) -> None:
        super().__init__(
            "contests", save_path, sample_num, split_name, openai_choice, n_out
        )

    def extract_data_features(
        self, row: pd.Series
    ) -> Tuple[str, Dict[str, Union[float, int]]]:
        question = row["description"]
        data_features = {}
        difficulty = row["difficulty"]
        if difficulty == 0:
            data_features["difficulty"] = 0
        elif difficulty <= 2:
            data_features["difficulty"] = 1
        elif difficulty <= 4:
            data_features["difficulty"] = 2
        elif difficulty <= 6:
            data_features["difficulty"] = 3
        elif difficulty <= 13:
            data_features["difficulty"] = 1
        elif difficulty <= 20:
            data_features["difficulty"] = 2
        elif difficulty <= 28:
            data_features["difficulty"] = 3
        else:
            data_features["difficulty"] = 0

        return question, data_features


def main(args: Dict) -> None:
    match args.dataset:
        case "apps":
            collector = AppsCollector(
                save_path=args.save_path,
                sample_num=args.sample_num,
                split_name=args.split_name,
                openai_choice=args.openai_choice,
                n_out=args.n_out,
            )
        case "contests":
            collector = ContestCollector(
                save_path=args.save_path,
                sample_num=args.sample_num,
                split_name=args.split_name,
                openai_choice=args.openai_choice,
                n_out=args.n_out,
            )
        case _:
            raise NotImplementedError
    match args.run_choice:
        case "normal":
            print("Normal run...")
            collector.run()
        case "random":
            print("Random run...")
            collector.random_run()
        case _:
            raise NotImplementedError


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        "-d",
        type=str,
        choices=DATASETS_DICT.keys(),
        default="apps",
    )
    parser.add_argument(
        "--split_name",
        "-sn",
        type=str,
        default="train",
    )
    parser.add_argument(
        "--save_path",
        "-sp",
        type=str,
    )
    parser.add_argument(
        "--sample_num",
        "-sa",
        type=int,
        default=100,
    )
    parser.add_argument(
        "--n_out",
        "-no",
        type=int,
        default=1,
    )
    parser.add_argument(
        "--openai_choice",
        "-oc",
        type=int,
        default=2,
        choices=[0, 1, 2, 3],
    )
    parser.add_argument(
        "--run_choice",
        "-rc",
        type=str,
        default="normal",
        choices=["normal","random"],
    )

    args = parser.parse_args()
    print(args)
    main(args)
    print_time_statistic()
