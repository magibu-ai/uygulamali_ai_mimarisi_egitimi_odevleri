import csv
from bs4 import BeautifulSoup
import json
import pandas as pd

data = []
with open('raw-data.csv', mode='r', encoding='utf-8', newline='') as infile:
    reader = csv.reader(infile)

    # Skip or capture the header row
    next(reader)

    i = 0
    for row in reader:
        question_title = BeautifulSoup(row[0], "html.parser").get_text()
        question_body = BeautifulSoup(row[1], "html.parser").get_text()
        answer = BeautifulSoup(row[2], "html.parser").get_text()
        data.append(
            {
                "conversation_id": i,
                "messages": [{
                    "context": question_title + " " + question_body, # Question title and body
                    "images": None,
                    "role": "user",
                    "thinking": None,
                    "tool_calls": None
                },
                {
                    "context": answer, # Question answer
                    "images": None,
                    "role": "assistant",
                    "thinking": None,
                    "tool_calls": None
                }]
            }
        )
        i += 1

#with open("data.json", "w", encoding="utf-8") as outfile:
#    json.dump(data, outfile, indent=4)
pd.DataFrame(data).to_parquet("data.parquet")