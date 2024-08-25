import json
import logging
from datetime import datetime
import os
import astunparse
import ast
import yaml
import openpyxl
from legend.core.algorithm import Fuzzer
from legend.core.extractor import Extractor
from legend.core.converter import Converter
from legend.core.chromosome import Chromosome

with open("../configs/config.yaml") as f:
    config = yaml.safe_load(f)

with open("../data/accident_reports/test_report.txt", 'r') as f:
    report = f.read()


workbook = openpyxl.load_workbook('../data/accident_reports/final_straight_cases.xlsx')
sheet = workbook.active

data_rows = sheet.iter_rows(min_row=1, max_row=6, values_only=True)

extractor = Extractor()
converter = Converter()

scenario_to_mutate = {}  # id: func_scenario
mutated_scenario_dict = {}
logical_testcase_dict = {}

project_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.makedirs(project_dir + "/data/results", exist_ok=True)

for row in data_rows:
    report = row[1]
    id = row[0]
    extracted_scenario = None
    try:
        extracted_scenario = extractor.extract(report)
    except Exception as e:
        print(e)
    if extracted_scenario is None:
        continue
    logical_testcase, flag = converter.convert(extracted_scenario)
    count = 0
    while flag is False and count <= 2:
        logical_testcase, flag = converter.convert(extracted_scenario)
        count += 1
# logical_testcase = converter.parse_testcase_string(testcase_str)
# # logical_testcase = converter.replace_ego(logical_testcase, [2])
    logical_testcase_dict[row[0]] = logical_testcase

    record_path = project_dir + "/data/results/" + str(id) + '.json'
    data = {}
    data["accident_report"] = report
    data["functional_scenario"] = extracted_scenario
    data["logical_scenario"] = astunparse.unparse(ast.fix_missing_locations(logical_testcase.update_ast_node()))
    data["logical_scenario"] = data["logical_scenario"].replace("\\n", "\n")
    with open(record_path, 'w') as f:
        json.dump(data, f, indent=4)



