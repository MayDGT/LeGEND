import openai
import yaml
from openai import OpenAI
import os
import sys
import time
import signal

config_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + '/configs/config.yaml'
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

client = openai.OpenAI(api_key=config["api_key"])


def handler(signum, frame):
    # swallow signum and frame
    raise Exception("End of time")


def request_response(content, task_id=1):
    res = None
    while res is None:
        try:
            signal.signal(signal.SIGALRM, handler)
            signal.alarm(120)  # wait 10
            res = client.chat.completions.create(
                model=config["extraction_model"] if task_id == 1 else config["conversion_model"],
                messages=content,
                max_tokens=config["max_tokens"],
                temperature=config["temperature"]
            )
            signal.alarm(0)
        except openai._exceptions.BadRequestError as e:
            print(e)
            signal.alarm(0)
        except openai._exceptions.RateLimitError as e:
            print("Rate limit exceeded. Waiting...")
            print(e)
            signal.alarm(0)  # cancel alarm
            time.sleep(5)
        except openai._exceptions.APIConnectionError as e:
            print("API connection error. Waiting...")
            signal.alarm(0)  # cancel alarm
            time.sleep(5)
        except Exception as e:
            print(e)
            print("Unknown error. Waiting...")
            signal.alarm(0)  # cancel alarm
            time.sleep(1)
    return res


