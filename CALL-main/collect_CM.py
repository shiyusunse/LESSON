import os
import sys
import re
import time
import json
import argparse
import logging
import tempfile
import numpy as np
import pandas as pd
import subprocess
from typing import *
from tqdm import tqdm, trange
from datasets import load_dataset
from sacrebleu import corpus_bleu
from tree_sitter import Language, Parser

sys.path.append()

import myUtils
from myUtils import time_statistic, logme, print_time_statistic, TimeoutError
from llm import INSTRUCTION_DICT, ROLE_DICT, SCENARIO_DICT
from CodeBLEU.my_calc import calc_codeBleu

DATASETS_DICT = {
    "apps": "codeparrot/apps",
    "contests": "deepmind/code_contests",
}


def proc_solution(solution):
    solution = eval(solution)
    # verify if there is a markdown python code block
    if "```" in solution:
        # remove all contents before the markdown python code block
        solution = re.sub(r"^.*?```\w*\n *", "", solution, flags=re.DOTALL)
        # remove all contents after the markdown python code block
        solution = re.sub(r"```.*$", "", solution, flags=re.DOTALL)
    return solution


def semgrep_call(code, temp_folder: tempfile.TemporaryDirectory) -> int:
    # return num of potential security bugs
    temp_file = os.path.join(temp_folder, "semgrep_call.py")
    temp_log = os.path.join(temp_folder, "semgrep_log.json")
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(code)
    result_num = 0
    try:
        cmd = f'python -m semgrep --config "p/python" {temp_file} --json -o {temp_log} > ./semgrep.log'
        result = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE)
        with open(temp_log, "r", encoding="utf-8") as f3:
            changelog = json.load(f3)
            result_num = len(changelog["results"])
            #     changed = changelog.count("@@")//2
    except subprocess.CalledProcessError as e:
        # print(e)
        pass

    return result_num


def black_call(code, temp_folder: tempfile.TemporaryDirectory) -> int:
    # return difference to PEP8 spec
    temp_file = os.path.join(temp_folder, "black_call.py")
    temp_log = os.path.join(temp_folder, "black.log")
    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(code)
    changed = 0
    try:
        cmd = f"black {temp_file} --diff > {temp_log}"
        result = subprocess.run(cmd, shell=True, check=True, stdout=subprocess.PIPE)
        with open(temp_log, "r", encoding="utf-8") as f:
            changelog = f.read()
            changed = changelog.count("@@") // 2
    except subprocess.CalledProcessError as e:
        # print(e)
        pass
    return changed


def sitter_call(
    code,
) -> bool:
    PY_LANGUAGE = Language(
        "",
        "python",
    )
    parser = Parser()
    parser.set_language(PY_LANGUAGE)
    tree = parser.parse(bytes(code, "utf8"))
    root_node = tree.root_node
    treecontent = root_node.sexp()
    has_error = False
    try:
        if root_node.has_error:
            # print('error!')
            has_error = True
    except:
        pass
    return has_error


def eval_code(
    code: str,
    function_name: str,
    test_cases: List,
    temp_folder: tempfile.TemporaryDirectory,
    time_limit: int = 3,
) -> Tuple[float, float, float]:
    if len(test_cases) == 0:
        return 0, 0, 0
    passed_count = 0
    error_count = 0
    timeout_count = 0
    # overwrite the temp file
    temp_file = os.path.join(temp_folder, "eval_code.py")
    if function_name != "":
        code = "import sys\n" + code
        code += f"\n{function_name}(*sys.argv[1:])"

    with open(temp_file, "w", encoding="utf-8") as f:
        f.write(code)

    for i in range(len(test_cases)):
        if function_name != "":
            cmds = ["python", temp_file]
            for arg in test_cases[i]["input"].split(" "):
                cmds.append(arg)
            try:
                output = subprocess.run(
                    cmds,
                    capture_output=True,
                    text=True,
                    timeout=time_limit,
                )
            except subprocess.TimeoutExpired as e:
                timeout_count += 1
                continue
            except Exception as e:
                error_count += 1
                continue
        else:
            try:
                output = subprocess.run(
                    ["python", temp_file],
                    capture_output=True,
                    text=True,
                    input=test_cases[i]["input"],
                    timeout=time_limit,
                )
            except subprocess.TimeoutExpired as e:
                timeout_count += 1
                continue
            except Exception as e:
                error_count += 1
                continue
        if output.returncode != 0:
            error_count += 1
        gold_out = test_cases[i]["output"]
        if isinstance(gold_out, str):
            if test_cases[i]["output"].strip() == output.stdout.strip():
                passed_count += 1
        else:
            if test_cases[i]["output"] == output.stdout.strip():
                passed_count += 1

    pass_rate = passed_count / len(test_cases)
    error_rate = error_count / len(test_cases)
    timeout_rate = timeout_count / len(test_cases)
    return pass_rate, error_rate, timeout_rate


class CodeMetric(object):
    def __init__(
        self,
        dataset_name: str,
        save_path: str,
        code_path: str,
        start_index: int = 0,
        split_name: str = "train",
    ) -> None:
        self.name: str = dataset_name
        assert self.name is not None and self.name in DATASETS_DICT.keys()
        origin_dataset = load_dataset(DATASETS_DICT[self.name])
        assert split_name in origin_dataset.keys()
        self.split_name = split_name
        self.dataset = origin_dataset[self.split_name]
        self.save_path: str = save_path
        self.code_path: str = code_path
        # assert type_name in ["original", "rephrased", "base"]
        # self.type_name: str = type_name
        self.code_df: pd.DataFrame = pd.read_csv(self.code_path)
        assert (
            "p_idx" in self.code_df.columns
            and "Instruction" in self.code_df.columns
            and "Role" in self.code_df.columns
            and "Scenario" in self.code_df.columns
        )
        if "Base" not in self.code_df.columns:
            self.groups = self.code_df.groupby(
                ["p_idx", "Instruction", "Role", "Scenario"], sort=False
            )
        else:
            self.groups = self.code_df.groupby(
                ["p_idx", "Instruction", "Role", "Scenario", "Base"], sort=False
            )
        assert start_index >= 0 and start_index < len(self.groups)
        self.start_index = start_index
        self.start_timestamp = time.time()

    # def extract_rows(self, p_idx: int) -> List[pd.DataFrame]:
    #     ret_rows = []
    #     if self.type_name == "original":
    #         temp_rows = self.collected_df[self.collected_df["p_idx"] == p_idx]
    #         if len(temp_rows) > 0:
    #             ret_rows = [temp_rows]
    #     else:
    #         multi_rows = self.collected_df[self.collected_df["p_idx"] == p_idx]
    #         # divide the multi_rows according to "Instruction"
    #         ret_rows = []
    #         for inst in INSTRUCTION_DICT.keys():
    #             temp_rows = multi_rows[multi_rows["Instruction"] == inst]
    #             if len(temp_rows) > 0:
    #                 ret_rows.append(temp_rows)
    #     return ret_rows

    def append_to_csv(
        self,
        add_df: pd.DataFrame,
    ) -> None:
        code_file_name = os.path.basename(self.code_path).split(".")[0]
        file_path = os.path.join(
            self.save_path,
            # self.name,
            f"{code_file_name}_cm.csv",
        )
        add_df.to_csv(
            file_path, mode="a", header=not os.path.exists(file_path), index=False
        )

    def run(self):
        raise NotImplementedError


class AppsCM(CodeMetric):
    def __init__(
        self,
        save_path: str,
        code_path: str,
        start_index: int = 0,
        split_name: str = "train",
    ) -> None:
        super().__init__("apps", save_path, code_path, start_index, split_name)

    def run(self):
        pbar = tqdm(total=len(self.groups))
        for index, (group_name, group_df) in enumerate(self.groups):
            if index < self.start_index:
                pbar.update(1)
                continue
            data_row = {}
            if "Base" not in self.code_df.columns:
                p_idx = int(group_name[0])
                inst, role, scenario = group_name[1:]
                data_row["p_idx"] = p_idx
                data_row["Instruction"] = inst
                data_row["Role"] = role
                data_row["Scenario"] = scenario
                data_row["Base"] = "None"
            else:
                p_idx = int(group_name[0])
                inst, role, scenario, base= group_name[1:]
                data_row["p_idx"] = p_idx
                data_row["Instruction"] = inst
                data_row["Role"] = role
                data_row["Scenario"] = scenario
                data_row["Base"] = base

            gen_codes = group_df["code"].tolist()
            gen_codes = [proc_solution(code) for code in gen_codes]
            code_count = len(gen_codes)
            if self.dataset[p_idx]["solutions"] == "":
                pbar.update(1)
                continue
            ground_truth = json.loads(self.dataset[p_idx]["solutions"])
            if self.dataset[p_idx]["input_output"] == "":
                pbar.update(1)
                continue
            test_cases = json.loads(self.dataset[p_idx]["input_output"])
            function_name = ""
            if "fn_name" in test_cases.keys():
                function_name = test_cases["fn_name"]
            in_outs = []
            try:
                for idx, inp in enumerate(test_cases["inputs"]):
                    # fetch the first string in the input list
                    while isinstance(inp, list):
                        if len(inp) == 0:
                            inp = ""
                            break
                        if not isinstance(inp[0], list):
                            if isinstance(inp[0], int) or isinstance(inp[0], float):
                                inp = map(str, inp)
                                inp = "\n".join(inp)
                                break
                            elif isinstance(inp[0], str):
                                inp = inp[0].strip("'\"")
                                break
                            else:
                                inp = str(inp[0])
                                break
                        else:
                            inp = inp[0]
                    gold_out = test_cases["outputs"][idx]
                    while isinstance(gold_out, list):
                        if len(gold_out) == 0:
                            gold_out = ""
                            break
                        if not isinstance(gold_out[0], list):
                            if isinstance(gold_out[0], int) or isinstance(
                                gold_out[0], float
                            ):
                                gold_out = map(str, gold_out)
                                gold_out = "\n".join(gold_out)
                                break
                            elif isinstance(gold_out[0], str):
                                gold_out = gold_out[0].strip("'\"")
                                break
                            else:
                                gold_out = str(gold_out[0])
                                break
                        else:
                            gold_out = gold_out[0]
                    temp_case = {"input": inp, "output": gold_out}
                    in_outs.append(temp_case)
            except Exception as e:
                pass

            with tempfile.TemporaryDirectory() as tmp:
                semgrep_list = []
                black_list = []
                syntaxError_list = []
                sta_codeBleu_list = []
                sta_Bleu_list = []
                sim_codeBleu_list = []
                sim_Bleu_list = []
                pass_rate_list = []
                error_rate_list = []
                timeout_rate_list = []
                for i in range(code_count):
                    semgrep_num = semgrep_call(gen_codes[i], tmp)
                    semgrep_list.append(semgrep_num)
                    black_num = black_call(gen_codes[i], tmp)
                    black_list.append(black_num)
                    syntaxError = sitter_call(gen_codes[i])
                    syntaxError_list.append(syntaxError)

                    other_codes = gen_codes[:i] + gen_codes[i + 1 :]
                    other_codes = [[x] for x in other_codes]
                    sta_codeBleu = calc_codeBleu(
                        pre_references=other_codes, hypothesis=[gen_codes[i]]
                    )
                    sta_codeBleu_list.append(sta_codeBleu)
                    sta_Bleu = corpus_bleu(
                        hypotheses=[gen_codes[i]], references=other_codes
                    )
                    # sacrebleu returns a score between 0 and 100, so we need to divide 100
                    sta_Bleu_list.append(sta_Bleu.score/100)

                    sim_codeBleu = calc_codeBleu(
                        pre_references=[[x] for x in ground_truth],
                        hypothesis=[gen_codes[i]],
                    )
                    sim_codeBleu_list.append(sim_codeBleu)
                    sim_Bleu = corpus_bleu(
                        hypotheses=[gen_codes[i]],
                        references=[[x] for x in ground_truth],
                    )
                    sim_Bleu_list.append(sim_Bleu.score/100)

                    if syntaxError:
                        pass_rate_list.append(0)
                        error_rate_list.append(0)
                        timeout_rate_list.append(0)
                        continue
                    pass_rate, error_rate, timeout_rate = eval_code(
                        code=gen_codes[i], 
                        function_name=function_name,
                        test_cases=in_outs, 
                        temp_folder=tmp
                    )
                    pass_rate_list.append(pass_rate)
                    error_rate_list.append(error_rate)
                    timeout_rate_list.append(timeout_rate)

            data_row["semgrep"] = sum(semgrep_list) / code_count
            data_row["black"] = sum(black_list) / code_count
            data_row["syntaxError_rate"] = sum(syntaxError_list) / code_count
            data_row["sta_codeBleu"] = sum(sta_codeBleu_list) / code_count
            data_row["sta_Bleu"] = sum(sta_Bleu_list) / code_count
            data_row["sim_codeBleu"] = sum(sim_codeBleu_list) / code_count
            data_row["sim_Bleu"] = sum(sim_Bleu_list) / code_count
            data_row["pass_rate"] = sum(pass_rate_list) / len(pass_rate_list)
            data_row["error_rate"] = sum(error_rate_list) / len(error_rate_list)
            data_row["timeout_rate"] = sum(timeout_rate_list) / len(timeout_rate_list)
            self.append_to_csv(pd.DataFrame(data_row, index=[0]))
            pbar.update(1)


def main(args):
    match args.dataset:
        case "apps":
            collector = AppsCM(
                save_path=args.save_path,
                code_path=args.code_path,
                start_index=args.start_index,
                split_name=args.split_name,
            )
        case _:
            raise NotImplementedError

    collector.run()


if __name__ == "__main__":
    logging.basicConfig(
        filename="",
        filemode="a",
        format="%(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
        level=logging.INFO,
    )
    logger = logging.getLogger("collect_CM")
    

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
        "--code_path",
        "-cp",
        type=str,
    )
    args = parser.parse_args()
    print(args)
    logger.info("/n/n"+"="*20)
    logger.info(args)
    logger.info("Start collecting code metrics")
    main(args)
    print_time_statistic()
    logger.info("Finish collecting code metrics")