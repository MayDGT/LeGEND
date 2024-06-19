from llm4fuzz.core.converter import Converter
from llm4fuzz.core.algorithm import Fuzzer
from llm4fuzz.core.chromosome import Chromosome
import yaml

with open("../../configs/config.yaml") as f:
    config = yaml.safe_load(f)
converter = Converter()

concerete_testcase_str = """def testcase(self):
    vehicle1 = NPC(lane_id=2, offset=20.69043823808877, initial_speed=27.951103767043612)
    vehicle2 = NPC(lane_id=1, offset=20.129366981482235, initial_speed=14.237237098567167)
    ego = NPC(lane_id=3, offset=30.0, initial_speed=18.71514939424827)
    vehicle1.changeLane(target_lane=1, target_speed=1.4334722855773752, trigger_sequence=1)
    vehicle2.changeLane(target_lane=3, target_speed=57.6121826123792, trigger_sequence=2)
    vehicle1.decelerate(target_speed=0.24893257393196966, trigger_sequence=2)
    vehicle2.decelerate(target_speed=0.7459237096970232, trigger_sequence=3)
    """

testcase = converter.parse_testcase_string(concerete_testcase_str)
chrom = Chromosome(concrete_testcase=testcase)
fuzzer = Fuzzer(config=config)
fuzzer.eval(chrom)