import os
import re
import time
import json
import argparse
import numpy as np
import pandas as pd
from typing import *
from tqdm import tqdm, trange
import openai
from datasets import load_dataset

import transformers
import torch

import myUtils
from myUtils import time_statistic, logme, print_time_statistic, TimeoutError
from llm import openai_set, openai_codeGen, INSTRUCTION_DICT

DATASETS_DICT = {
    "apps": "codeparrot/apps",
    "contests": "deepmind/code_contests",
}


def generate_prompt(
    args, test_case_path, prompt_path, solutions_path, tokenizer, starter_path=None
):
    _input = "\nQUESTION:\n"
    with open(prompt_path, "r") as f:
        data = f.readlines()
        data = "".join(data)
    _input += data
    if starter_path != None:
        with open(starter_path, "r") as f:
            data = f.readlines()
            data = "".join(data)
            data = "\n" + data  # + "\n"
        _input += data
    else:
        # _input += "\n\n"
        pass

    with open(test_case_path, "r") as f:
        data = json.load(f)
    if not data.get("fn_name"):
        _input += "\nUse Standard Input format"  # \n"
    else:
        _input += "\nUse Call-Based format"  # \n"

    _input += "\nANSWER:\n"

    return _input


class DataCollector(object):
    def __init__(
        self,
        dataset_name: str,
        save_path: str,
        text_path: str,
        start_index: int = 0,
        split_name: str = "train",
        n_out: int = 3,
        openai_choice: int = 0,
        model_name: str = "35",
    ) -> None:
        self.name: str = dataset_name
        self.n_out: int = n_out
        assert self.name is not None and self.name in DATASETS_DICT.keys()
        origin_dataset = load_dataset(DATASETS_DICT[self.name])
        assert split_name in origin_dataset.keys()
        self.split_name = split_name
        self.dataset = origin_dataset[self.split_name]
        self.save_path = save_path
        self.collected_df = pd.DataFrame()
        self.re_collected_df = pd.DataFrame()
        self.text_path = text_path
        self.text_df = pd.read_csv(text_path)
        assert start_index >= 0 and start_index < len(self.text_df)
        print(f"{text_path} shape: {self.text_df.shape}")
        self.start_index = start_index
        self.start_timestamp = time.time()
        self.init_model(openai_choice, model_name)

    def init_model(self, openai_choice: int, model_name: str) -> None:
        self.engine = openai_set(openai_choice)
        self.model_name = model_name

    @time_statistic
    def extract_data_features(self) -> Tuple[str, Dict[str, Union[float, int]]]:
        raise NotImplementedError

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
    def codeGen(self, text: str, starter_code: str) -> List[str]:
        try:
            ret_list = openai_codeGen(
                question=text,
                starter_code=starter_code,
                n_out=self.n_out,
                engine=self.engine,
            )
            return ret_list
        except TimeoutError:
            return []

    def save_to_csv(self) -> None:
        text_file_name = os.path.basename(self.text_path).split(".")[0]
        file_path = os.path.join(
            self.save_path,
            self.name,
            f"{text_file_name}_code.csv",
        )
        self.collected_df.to_csv(file_path, index=False)

    def append_to_csv(self, add_df: pd.DataFrame) -> None:
        text_file_name = os.path.basename(self.text_path).split(".")[0]
        file_path = os.path.join(
            self.save_path,
            self.name,
            self.model_name,
            f"{text_file_name}_code.csv",
        )
        add_df.to_csv(
            file_path, mode="a", header=not os.path.exists(file_path), index=False
        )

    # def original_run(self) -> None:
    #     data_row = {}
    #     for p_idx in trange(self.start_idx, self.end_idx):
    #         row = self.dataset[p_idx]
    #         data_row["p_idx"] = p_idx
    #         question = self.extract_data_features(row)
    #         if question is None:
    #             continue

    #         code_list = self.codeGen(question)
    #         if code_list != []:
    #             for r_idx, code in enumerate(code_list):
    #                 temp_data_row = data_row.copy()
    #                 temp_data_row["re_idx"] = r_idx
    #                 temp_data_row["code"] = repr(code)
    #                 re_data_df = pd.DataFrame([temp_data_row])
    #                 self.append_to_csv(re_data_df, suffix="original")
    #         else:
    #             print(f"code generation failed for data: {p_idx}")

    def run(self) -> None:
        for index, text_row in tqdm(
            self.text_df.iterrows(), total=self.text_df.shape[0]
        ):
            if index < self.start_index:
                continue

            # text_row = self.text_df.loc[index]
            p_idx = int(text_row["p_idx"])
            data_row = {}
            data_row["p_idx"] = p_idx
            if "re_question_NL" in text_row.keys():
                nl_question = eval(text_row["re_question_NL"])
            elif "question_NL" in text_row.keys():
                nl_question = eval(text_row["question_NL"])
            else:
                raise ValueError("question_NL not found")
            row = self.dataset[p_idx]
            extracted = self.extract_data_features(row)
            if extracted is None:
                continue
            question, starter_code = extracted
            _, eg_question = self.preprocess_text(question)
            re_question = nl_question + "\n" + eg_question

            retry_count = 0
            while retry_count < 5:
                code_list = self.codeGen(re_question, starter_code)
                if code_list != [] and code_list[0] != "ERROR":
                    for r_idx, code in enumerate(code_list):
                        temp_data_row = data_row.copy()
                        if "Instruction" in text_row.keys():
                            temp_data_row["Instruction"] = text_row["Instruction"]
                        else:
                            temp_data_row["Instruction"] = "None"
                        if "Role" in text_row.keys():
                            temp_data_row["Role"] = text_row["Role"]
                        else:
                            temp_data_row["Role"] = "None"
                        if "Scenario" in text_row.keys():
                            temp_data_row["Scenario"] = text_row["Scenario"]
                        else:
                            temp_data_row["Scenario"] = "None"
                        if "Base" in text_row.keys():
                            temp_data_row["Base"] = text_row["Base"]
                        else:
                            temp_data_row["Base"] = "None"
                        temp_data_row["re_idx"] = r_idx
                        temp_data_row["code"] = repr(code)
                        re_data_df = pd.DataFrame([temp_data_row])
                        self.append_to_csv(re_data_df)
                    retry_count = 0
                    break
                else:
                    print(f"code generation failed for data: {p_idx}")
                    retry_count += 1
                    time.sleep(15 * retry_count)


class AppsCollectorGPT(DataCollector):
    def __init__(
        self,
        save_path: str,
        text_path: str,
        start_index: int = 0,
        split_name: str = "train",
        n_out: int = 3,
    ) -> None:
        super().__init__(
            "apps",
            save_path,
            text_path,
            start_index,
            split_name,
            n_out,
            openai_choice=0,
            model_name="neo",
        )
        print("Running GPT-Neo")

    def init_model(self, openai_choice: int, model_name: str) -> None:
        self.tokenizer = transformers.GPT2Tokenizer.from_pretrained("gpt2")
        # Set up model
        print("Loading model...")
        self.model = transformers.GPTNeoForCausalLM.from_pretrained(
        )
        self.model.cuda()
        print(f"Loaded.")
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
        self.model_name = model_name

    def extract_data_features(self, row: pd.Series):
        question: str = row["question"]
        starter_code: str = row["starter_code"]
        test_cases = json.loads(row["input_output"])
        if row["solutions"] == "" or row["input_output"] == "":
            return None
        return question, starter_code, test_cases

    def run(self) -> None:
        for index, text_row in tqdm(
            self.text_df.iterrows(), total=self.text_df.shape[0]
        ):
            if index < self.start_index:
                continue

            # text_row = self.text_df.loc[index]
            p_idx = int(text_row["p_idx"])
            data_row = {}
            data_row["p_idx"] = p_idx
            if "re_question_NL" in text_row.keys():
                nl_question = eval(text_row["re_question_NL"])
            elif "question_NL" in text_row.keys():
                nl_question = eval(text_row["question_NL"])
            else:
                raise ValueError("question_NL not found")
            row = self.dataset[p_idx]
            extracted = self.extract_data_features(row)
            if extracted is None:
                continue
            question, starter_code, test_cases = extracted
            _, eg_question = self.preprocess_text(question)
            re_question = nl_question + "\n" + eg_question
            re_question = "\nQUESTION:\n" + re_question + "\n" + starter_code
            quest_suffix = ""
            if "fn_name" in test_cases.keys():
                quest_suffix += "\nUse Call-Based format"
            else:
                quest_suffix += "\nUse Standard Input format"
            quest_suffix += "\nANSWER:\n"

            code_list = []
            try:
                with torch.no_grad():
                    quest_ids = (
                        torch.LongTensor(
                            self.tokenizer.encode(re_question, verbose=False)
                        )
                        .unsqueeze(0)
                        .cuda()
                    )
                    if quest_ids.shape[1] > 896:
                        quest_ids = quest_ids[:, :896]
                    suffix_ids = (
                        torch.LongTensor(
                            self.tokenizer.encode(quest_suffix, verbose=False)
                        )
                        .unsqueeze(0)
                        .cuda()
                    )
                    input_ids = torch.cat([quest_ids, suffix_ids], dim=1)
                    output_ids = self.model.generate(
                        input_ids,
                        num_beams=5,
                        pad_token_id=self.tokenizer.pad_token_id,
                        early_stopping=True,
                        # max_length=1024 - len(input_ids),
                        max_length=1024,
                        num_return_sequences=3,
                    )

                    for i in range(max(3, output_ids.shape[0])):
                        # out_list.append(self.tokenizer.decode(output_ids[i]))
                        temp_code = self.tokenizer.decode(output_ids[i])
                        if len(temp_code.split("ANSWER:\n")) >= 2:
                            temp_code = temp_code.split("ANSWER:\n")[1].replace(
                                "<|endoftext|>", ""
                            )
                            code_list.append(temp_code)
            except Exception as e:
                if (
                    isinstance(e, UnboundLocalError)
                    and str(e)
                    == "local variable 'next_tokens' referenced before assignment"
                ):
                    # See https://github.com/huggingface/transformers/issues/5118
                    if args.debug:
                        print("Problem text was > 1024 tokens, so cannot do generation")
                        print(e)
                else:
                    print("Unexpected exception in generating solution")
                    print(e)
                # Default to empty string on errors

            # code_list = self.codeGen(re_question, starter_code)

            if code_list != []:
                for r_idx, code in enumerate(code_list):
                    temp_data_row = data_row.copy()
                    if "Instruction" in text_row.keys():
                        temp_data_row["Instruction"] = text_row["Instruction"]
                    else:
                        temp_data_row["Instruction"] = "None"
                    if "Role" in text_row.keys():
                        temp_data_row["Role"] = text_row["Role"]
                    else:
                        temp_data_row["Role"] = "None"
                    if "Scenario" in text_row.keys():
                        temp_data_row["Scenario"] = text_row["Scenario"]
                    else:
                        temp_data_row["Scenario"] = "None"
                    if "Base" in text_row.keys():
                        temp_data_row["Base"] = text_row["Base"]
                    else:
                        temp_data_row["Base"] = "None"
                    temp_data_row["re_idx"] = r_idx
                    temp_data_row["code"] = repr(code)
                    re_data_df = pd.DataFrame([temp_data_row])
                    self.append_to_csv(re_data_df)
            else:
                print(f"code generation failed for data: {p_idx}")


class AppsCollector(DataCollector):
    def __init__(
        self,
        save_path: str,
        text_path: str,
        start_index: int = 0,
        split_name: str = "train",
        n_out: int = 3,
        openai_choice: int = 0,
        model_name: str = "35",
    ) -> None:
        super().__init__(
            "apps",
            save_path,
            text_path,
            start_index,
            split_name,
            n_out,
            openai_choice,
            model_name,
        )

    def extract_data_features(self, row: pd.Series) -> Optional[Tuple[str, str]]:
        question: str = row["question"]
        starter_code: str = row["starter_code"]
        if row["solutions"] == "" or row["input_output"] == "":
            return None
        return question, starter_code


class ContestsCollector(DataCollector):
    def __init__(
        self,
        save_path: str,
        text_path: str,
        start_index: int = 0,
        split_name: str = "train",
        n_out: int = 3,
        openai_choice: int = 0,
        model_name: str = "35",
    ) -> None:
        super().__init__(
            "contests",
            save_path,
            text_path,
            start_index,
            split_name,
            n_out,
            openai_choice,
            model_name,
        )

    def extract_data_features(self, row: pd.Series) -> Optional[Tuple[str, str]]:
        question: str = row["description"]
        py3_count: int = sum(
            map(lambda x: 1 if x == 3 else 0, row["solutions"]["language"])
        )
        if py3_count <= 0:
            return None
        return question, ""


def main(args: Dict) -> None:
    if args.model_name == "neo":
        assert args.dataset == "apps"
        collector = AppsCollectorGPT(
            save_path=args.save_path,
            text_path=args.text_path,
            start_index=args.start_index,
            split_name=args.split_name,
            n_out=args.n_out,
        )
    else:
        match args.dataset:
            case "contests":
                collector = ContestsCollector(
                    save_path=args.save_path,
                    text_path=args.text_path,
                    start_index=args.start_index,
                    split_name=args.split_name,
                    n_out=args.n_out,
                    openai_choice=args.openai_choice,
                    model_name=args.model_name,
                )
            case "apps":
                collector = AppsCollector(
                    save_path=args.save_path,
                    text_path=args.text_path,
                    start_index=args.start_index,
                    split_name=args.split_name,
                    n_out=args.n_out,
                    openai_choice=args.openai_choice,
                    model_name=args.model_name,
                )

    collector.run()


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
        "--start_index",
        "-si",
        type=int,
        default=0,
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
        "--text_path",
        "-tp",
        type=str,
    )
    parser.add_argument(
        "--n_out",
        "-no",
        type=int,
        default=3,
    )
    parser.add_argument(
        "--openai_choice",
        "-oc",
        type=int,
        default=2,
        choices=[0, 1, 2, 3, 4, 5, 6],
    )
    parser.add_argument(
        "--model_name",
        "-mn",
        type=str,
        default="35",
        choices=["35", "4", "neo"],
    )
    args = parser.parse_args()
    print(args)
    main(args)
    print_time_statistic()
