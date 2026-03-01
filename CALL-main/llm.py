import openai
from typing import *
from myUtils import TimeoutError, timeout
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
)  # for exponential backoff
import random
import time


INSTRUCTION_DICT = {
    "long": "Expand the problem in a more detailed and thorough manner. Make the explanation longer and clearer.",
    "short": "Condense the problem in a more concise and clear manner. Make the explanation shorter while maintaining clarity.",
    # "easy": "Simplify the problem in a more straightforward and easy-to-understand manner. Ensure the explanation is clear and accessible.",
    "formal": "Rewrite the problem in a more formal and clear manner.",
    "fluent": "Rewrite the problem in a more fluent and clear manner.",
    "technical": "Rewrite the problem in a more technical and detailed manner.",
    # "creative": "Rewrite the problem in a more creative and engaging manner, while ensuring clarity of the question.",
    # "precise": "Rewrite the problem with more precision and clarity.",
    "logical": "Rewrite the problem to make it more logical and clear.",
    # "objective": "Rewrite the problem to make it more objective and clear.",
}


ROLE_DICT = {
    "student": [
        "You are a student majoring in software engineering.",
    ],
    # "teacher": [
    #     "You are a teacher teaching python programming.",
    #     "You need to rephrase a question from an online programming practice platform to test your student whether they can still solve the question after rephrasing.",
    # ],
    "programmer": [
        "You are a senior python programmer.",
    ],
    # "researcher": [
    #     "You are a researcher in the field of large language model.",
    #     "You need to rephrase programming questions to extend your dataset for language model training.",
    # ],
    # "engineer": [
    #     "You are a software engineer.",
    # ],
    "competitor": [
        "You are a competitor in a programming competition.",
    ],
}

SCENARIO_DICT = {
    # "yourself": "Rephrase questions from an online programming practice platform to help you better understand the question.",
    # "partner": "You need to rephrase a programming question to explain it to your partner.",
    "clearer": "The following programming question is not clear enough, so you need to rephrase it.",
    "improve": "Someone wrote the following programming question, and asked you to improve it to make it clearer.",
    "specify": "You need to rephrase programming questions to make them more suitable for python3.",
}



@timeout(180)
def openai_rephrase(
    text: str,
    context: str,
    instruction: str,
    n_out: int = 1,
    engine: str = "llm-testing",
) -> List[str]:
    if len(text) > 12972:
        text = text[:12972]
    prompt = f"{context} Please rephrase the programming problem in XML tags while keeping its original meaning and structure, to help enhance the understanding of the problem's intent and facilitate better code generation. {instruction} You should keep all mathematical symbols in latex format. Here's the original problem:\n\n<text>\n{text}\n</text>"

    status = True
    ret_list = []
    timeout_count = 0
    while status and timeout_count < 3:
        # try catch all exceptions
        try:
            response = openai.ChatCompletion.create(
                engine=engine,
                messages=[
                    # {
                    #     "role": "system",
                    #     "content": system_prompt,
                    # },
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                # temperature=1,
                n=n_out,  # max 10
                max_tokens=2000,  # max char len: 16972
                # top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
                stop=None,
            )
        except (
            openai.error.Timeout,
            openai.error.APIError,
            openai.error.ServiceUnavailableError,
        ) as e:
            timeout_count += 1
            # sleep random time
            sleep_time = random.randint(1, 20)
            time.sleep(sleep_time)
            response = None
        except openai.error.RateLimitError as e:
            timeout_count += 1
            # sleep random time
            sleep_time = random.randint(20, 40)
            time.sleep(sleep_time)
            response = None
        except openai.error.InvalidRequestError as e:
            return ret_list
        except Exception as e:
            print(e)
            return ["ERROR"]
        else:
            status = False
    if response is None:
        return ret_list
    if "choices" not in response.keys():
        return ret_list
    for choice in response["choices"]:
        if "message" not in choice.keys():
            continue
        if "content" not in choice["message"].keys():
            continue
        if choice["message"]["content"] != "":
            # try to remove XML tags in the output
            ret_list.append(
                choice["message"]["content"]
                .replace("<text>", "")
                .replace("</text>", "")
            )

    return ret_list


@timeout(240)
def openai_codeGen(
    question: str, starter_code: str, n_out: int = 3, engine: str = "llm-testing"
) -> List[str]:
    if len(question) > 12972:
        question = question[:12972]
    prompt = f"Please write python3 code for the following programming question in XML tags. Your output should only contain the python3 code (in Markdown format). Here's the question:\n\n <question>\n{question}\n</question>"
    # if starter_code != "":
    #     prompt += "\nYour code should start with the following starter code:\n\n<starter_code>\n{starter_code}\n</starter_code>"
    # try catch all exceptions

    status = True
    ret_list = []
    timeout_count = 0
    while status and timeout_count < 3:
        try:
            response = openai.ChatCompletion.create(
                engine=engine,
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    },
                ],
                # temperature=1,
                n=n_out,  # max 10
                max_tokens=2000,  # max char len: 16972
                # top_p=1,
                frequency_penalty=0,
                presence_penalty=0,
                stop=None,
            )
        except (
            openai.error.Timeout,
            openai.error.APIError,
            openai.error.ServiceUnavailableError,
        ) as e:
            timeout_count += 1
            # sleep random time
            sleep_time = random.randint(1, 20)
            time.sleep(sleep_time)
            response = None
        except openai.error.RateLimitError as e:
            timeout_count += 1
            # sleep random time
            sleep_time = random.randint(20, 40)
            time.sleep(sleep_time)
            response = None
        except openai.error.InvalidRequestError as e:
            return ret_list
        except Exception as e:
            print(e)
            return ["ERROR"]
        else:
            status = False
    if response is None:
        return ret_list
    if "choices" not in response.keys():
        return ret_list
    for choice in response["choices"]:
        if "message" not in choice.keys():
            continue
        if "content" not in choice["message"].keys():
            continue
        if choice["message"]["content"] != "":
            # remove the first line and the last line
            genCode = choice["message"]["content"].split("\n")
            # genCode = genCode[:-1]
            # ret_list.append(starter_code + "\n".join(genCode))
            genCode = genCode[1:-1]
            ret_list.append("\n".join(genCode))

    return ret_list
