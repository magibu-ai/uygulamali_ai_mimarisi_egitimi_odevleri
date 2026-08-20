import csv
from bs4 import BeautifulSoup

data = []
with open('raw-data.csv', mode='r', encoding='utf-8', newline='') as infile:
    reader = csv.reader(infile)

    # Skip or capture the header row
    next(reader)

    for row in reader:
        question_title = BeautifulSoup(row[0], "html.parser").get_text()
        question_body = BeautifulSoup(row[1], "html.parser").get_text()
        answer = BeautifulSoup(row[2], "html.parser").get_text()
        data.append(
            question_title + " " + question_body + '\n' + answer
        )

with open('../../datasets/data.txt', mode='w', encoding='utf-8', newline='') as outfile:
    outfile.writelines(data)