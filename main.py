import logging
from datetime import datetime

import yaml
import openpyxl
from legend.core.algorithm import Fuzzer
from legend.core.extractor import Extractor
from legend.core.converter import Converter
from legend.core.chromosome import Chromosome

start_time = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
log_file_path = f'data/logs/{start_time}.log'
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s  %(filename)s : %(levelname)s  %(message)s',
                    datefmt='%Y-%m-%d %A %H:%M:%S',
                    filename=log_file_path,
                    filemode='w')
logger = logging.getLogger(__name__)

with open("configs/config.yaml") as f:
    config = yaml.safe_load(f)

with open("data/accident_reports/test_report.txt", 'r') as f:
    report = f.read()

test_list = [''' def testcase():
    vehicle1 = NPC(lane_id=[3, 3], offset=[35, 40], initial_speed=[20, 25]) 
    vehicle2 = NPC(lane_id=[3, 3], offset=[20, 30], initial_speed=[10, 15]) 
    vehicle3 = NPC(lane_id=[3, 3], offset=[0, 15], initial_speed=[10, 15]) 
    vehicle1.decelerate(target_speed=[10, 15], trigger_sequence=[1, 1]) 
    vehicle1.changeLane(target_lane=[3, 3], target_speed=[10, 15], trigger_sequence=[2, 2]) 
    vehicle2.accelerate(target_speed=[15, 20], trigger_sequence=[3, 3]) 
    vehicle1.accelerate(target_speed=[20, 25], trigger_sequence=[4, 4])
    ''']


workbook = openpyxl.load_workbook('data/accident_reports/final_curve_cases.xlsx')
sheet = workbook.active

data_rows = sheet.iter_rows(min_row=5, max_row=10, values_only=True)
logger.info("caseid %s to %s", 5, 10)
extractor = Extractor()
converter = Converter()
mutator = Mutator()

concerete_testcase_str = """def testcase(self):
    vehicle1 = NPC(lane_id=2, offset=0.131228103185137, initial_speed=38.531054805837044)
    vehicle2 = NPC(lane_id=3, offset=11.793838237315796, initial_speed=28.176327565703392)
    ego = NPC(lane_id=1, offset=30.0, initial_speed=45.54335320560515)
    vehicle1.changeLane(trigger_sequence=1, target_lane=3, target_speed=12.200676954270545)
    vehicle1.decelerate(trigger_sequence=2, target_speed=10.052463178108173)
    vehicle1.decelerate(trigger_sequence=3, target_speed=0.6957226121292823)
    vehicle2.changeLane(trigger_sequence=2, target_lane=1, target_speed=29.44636536456697)
    vehicle2.decelerate(trigger_sequence=3, target_speed=0.33210673749139596)"""

testcase = converter.parse_testcase_string(concerete_testcase_str)
chrom = Chromosome(concrete_testcase=testcase)
fuzzer = Fuzzer(config=config)
fuzzer.eval(chrom)

scenario_to_mutate = {}  # id: func_scenario
mutated_scenario_dict = {}
logical_testcase_dict = {}

for row in data_rows:
    report = row[1]
    logger.info("========New accident report======== \n id: %s", row[0])
    extracted_scenario = None
    try:
        extracted_scenario = extractor.extract(report)
    except Exception as e:
        logger.error(e)
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
    flag = fuzzer.loop(logical_testcase)
    if flag is True:
        scenario_to_mutate[row[0]] = extracted_scenario

for caseid, extracted_data in scenario_to_mutate.items():
    mutated_scenario = None
    try:
        if logical_testcase_dict[caseid].method_statements[-1].args["trigger_sequence"][-1] < 3:
            mutated_scenario = mutator.mutate(extracted_data, insert=True)
        else:
            mutated_scenario = mutator.mutate(extracted_data, insert=False)
    except Exception as e:
        logger.error(e)
    if mutated_scenario is None:
        continue

    logical_testcase, flag = converter.convert(mutated_scenario)
    count = 0
    while flag is False and count <= 2:
        logical_testcase, flag = converter.convert(mutated_scenario)
        count += 1
    logical_testcase_dict[caseid] = logical_testcase
    flag = fuzzer.loop(logical_testcase)

# for logical_testcase in logical_testcase_list:

