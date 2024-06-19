from __future__ import annotations
import json
import logging
from llm4fuzz.core.testcase import TestCase
from llm4fuzz.core.statement import Statement, ConstructorStatement, MethodStatement

import random
import astunparse
import ast
import os

logger = logging.getLogger(__name__)


class Chromosome:
    def __init__(self, concrete_testcase, fitness=None):
        self.testcase = concrete_testcase
        self.fitness = fitness

    @property
    def test_case(self):
        return self.testcase

    def clone(self):
        return Chromosome(self.testcase.clone(), self.fitness)

    def crossover(self, other_chrom: Chromosome):
        """Exchange two vehicles, including their initial position and actions"""
        candidate_idx = []
        for statement in self.testcase.constructor_statements:
            if statement.assignee != 'ego':
                candidate_idx.append(statement.assignee[-1])

        idx = random.choice(candidate_idx)
        logger.info("crossover vehicle%s", idx)

        size = min(self.testcase.size(), other_chrom.testcase.size())
        for i in range(size):
            if (isinstance(self.testcase.statements[i], ConstructorStatement) and self.testcase.statements[i].assignee[-1] == idx) or \
                (isinstance(self.testcase.statements[i], MethodStatement) and self.testcase.statements[i].callee[
                    -1] == idx):
                self.testcase.statements[i].args = other_chrom.testcase.statements[i].args
                self.testcase.statements[i].arg_bounds = other_chrom.testcase.statements[i].arg_bounds
                self.testcase.statements[i].update_ast_node()

    def mutate(self):
        prob = 1.0 / self.testcase.size()
        for i in range(self.testcase.size()):
            if random.random() < prob:
                logger.info("start mutate statement %d", i)
                logger.info("its args: %s", self.testcase.statements[i].args)
                self.testcase.statements[i].mutate()


class ChromosomeFactory:
    def __init__(self, logical_testcase: TestCase, scenario_type="straight_road"):
        self.logical_testcase = logical_testcase
        self.scenario_type = scenario_type
        path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(path + '/configs/' + scenario_type + '/basic.json') as f:
            self.basic_config = json.load(f)

        self.update_param_range()

    def update_param_range(self):
        """for the npc in different lane with the ego, spawn it in the back of its lane"""
        lane_vehicle_dict = {}  # {"1": [{"name": vehicle1, "statement": statement, "offset": offset}
        for idx in self.basic_config["lane_id"]:
            lane_vehicle_dict[idx] = []

        ego_lane = None
        ego_offset = None
        ego_s = 30 if self.scenario_type == "straight_road" else 50  # straight_road 30, curve_road 50
        for statement in self.logical_testcase.constructor_statements:
            statement.arg_bounds["initial_speed"] = self.basic_config["initial_speed"]
            if statement.assignee == 'ego':
                statement.arg_bounds["offset"] = ego_s
                ego_lane = statement.args['lane_id'] if isinstance(statement.args['lane_id'], int) \
                            else random.choice(statement.args['lane_id'])
                if ego_lane > self.basic_config["lane_id"][-1]:
                    ego_lane = self.basic_config["lane_id"][-1]
                elif ego_lane < self.basic_config["lane_id"][0]:
                    ego_lane = self.basic_config["lane_id"][0]
                ego_offset = statement.args['offset'] if isinstance(statement.args['offset'], int) \
                            else random.uniform(statement.args['offset'][0], statement.args['offset'][1])
                statement.update_ast_node()

                vehicle_dict = {"name": "ego", "statement": statement, "offset": ego_offset}
                lane_vehicle_dict[ego_lane].append(vehicle_dict)

            else:
                npc_lane = statement.args['lane_id'] if isinstance(statement.args['lane_id'], int) \
                    else random.choice(statement.args['lane_id'])
                # ensure in the range
                if npc_lane > self.basic_config["lane_id"][-1]:
                    npc_lane = self.basic_config["lane_id"][-1]
                elif npc_lane < self.basic_config["lane_id"][0]:
                    npc_lane = self.basic_config["lane_id"][0]
                npc_offset = statement.args['offset'] if isinstance(statement.args['offset'], int) \
                    else random.uniform(statement.args['offset'][0], statement.args['offset'][1])

                vehicle_dict = {"name": statement.assignee, "statement": statement, "offset": npc_offset}
                lane_vehicle_dict[npc_lane].append(vehicle_dict)

        for lane_id, vehicle_list in lane_vehicle_dict.items():
            if lane_id == ego_lane:
                sorted_vehicle_list = sorted(vehicle_list, key=lambda d: d.get("offset"))
                ego_order_index = 0
                for i in range(len(sorted_vehicle_list)):
                    if sorted_vehicle_list[i]["name"] == "ego":
                        ego_order_index = i
                        break
                new_offset = 0
                for i in range(len(sorted_vehicle_list)):
                    if i != ego_order_index:  # npc
                        if sorted_vehicle_list[i]["offset"] < ego_offset:
                            new_offset = ego_s - (ego_order_index - i) * 10
                        elif sorted_vehicle_list[i]["offset"] > ego_offset:
                            new_offset = ego_s + (i - ego_order_index) * 15
                        sorted_vehicle_list[i]["statement"].arg_bounds["offset"] = [new_offset, new_offset]
                        sorted_vehicle_list[i]["statement"].update_ast_node()
            else:
                sorted_vehicle_list = sorted(vehicle_list, key=lambda d: d.get("offset"), reverse=True)
                for i in range(len(sorted_vehicle_list)):
                    new_offset = ego_s - (i + 1) * 10
                    sorted_vehicle_list[i]["statement"].arg_bounds["offset"] = [new_offset, new_offset + 1]
                    sorted_vehicle_list[i]["statement"].update_ast_node()

        for statement in self.logical_testcase.statements:
            if isinstance(statement, MethodStatement):
                if statement.method_name == "decelerate":
                    statement.arg_bounds["target_speed"] = self.basic_config["dc_target_speed"]
                if statement.method_name == "accelerate":
                    statement.arg_bounds["target_speed"] = self.basic_config["ac_target_speed"]
                if statement.method_name == "changeLane":
                    statement.arg_bounds["target_speed"] = self.basic_config["target_speed"]
                statement.update_ast_node()


        logger.info("=== Update param ranges for the logical testcase === \n %s",
                    astunparse.unparse(ast.fix_missing_locations(self.logical_testcase.update_ast_node(True))))

    def generate_random_chromosome(self):
        concrete_testcase = TestCase()

        for statement in self.logical_testcase.statements:
            clone_statement = statement.clone(concrete_testcase)

            for arg_name, arg_bound in statement.arg_bounds.items():

                if isinstance(arg_bound, int):
                    statement.arg_bounds[arg_name] = [arg_bound, arg_bound]
                    value = arg_bound
                elif len(arg_bound) == 0:
                    # LLM does not fill param ranges, so use the default bounds
                    default_bound = self.basic_config[arg_name]
                    statement.arg_bounds[arg_name] = default_bound
                    value = random.uniform(default_bound[0], default_bound[1])
                elif len(arg_bound) == 1:
                    statement.arg_bounds[arg_name] = [arg_bound[0], arg_bound[0]]
                    value = arg_bound[0]
                else:
                    if arg_name == "lane_id" or arg_name == "trigger_sequence" or arg_name == "target_lane":
                        value = random.choice(arg_bound)
                    else:
                        value = random.uniform(arg_bound[0], arg_bound[1])

                # reverse the lane, since police tend to mark the right lane as the first lane, which is opposite to that in simulator.
                if (arg_name == "lane_id" or arg_name == "target_lane") and self.logical_testcase.is_reverse is True and self.logical_testcase.reversed is False:
                    n = self.basic_config[arg_name][0] + self.basic_config[arg_name][-1]
                    value = abs(n - value)
                    statement.arg_bounds[arg_name][0] = abs(n - statement.arg_bounds[arg_name][0])
                    statement.arg_bounds[arg_name][1] = abs(n - statement.arg_bounds[arg_name][1])
                    if statement.arg_bounds[arg_name][0] > statement.arg_bounds[arg_name][1]:
                        statement.arg_bounds[arg_name] = [statement.arg_bounds[arg_name][1], statement.arg_bounds[arg_name][0]]


                clone_statement.args[arg_name] = value

            clone_statement.arg_bounds = statement.arg_bounds
            statement.update_ast_node()
            clone_statement.update_ast_node()

            print("Updated bounds: ", statement.arg_bounds)
            logger.info("Updated bounds: %s", statement.arg_bounds)

            concrete_testcase.add_statement(clone_statement)

        if self.logical_testcase.is_reverse:
            self.logical_testcase.reversed = True

        # add a brake action for each vehicle as their ending action
        last_action_dict = {}  # vehicle_name: last trigger sequence
        for statement in concrete_testcase.constructor_statements:
            if statement.assignee != 'ego':
                last_action_dict[statement.assignee] = 0

        for statement in concrete_testcase.statements:
            if isinstance(statement, MethodStatement) and statement.args['trigger_sequence'] >= last_action_dict[statement.callee]:
                last_action_dict[statement.callee] = statement.args['trigger_sequence']

        for statement in concrete_testcase.statements:
            if isinstance(statement, MethodStatement) and statement.args['trigger_sequence'] == last_action_dict[statement.callee]:
                if statement.method_name == 'decelerate':  # the vehicle already has a decelerate action
                    statement.arg_bounds['target_speed'] = [0, 1]
                    statement.args['target_speed'] = random.uniform(0, 1)
                    last_action_dict[statement.callee] = -1

        for key, value in last_action_dict.items():
            if value != -1:
                args = {"target_speed": random.uniform(0, 1), "trigger_sequence": value + 1}
                arg_bounds = {"target_speed": [0, 1], "trigger_sequence": [value + 1, value + 1]}
                statement = MethodStatement(testcase=concrete_testcase,
                                            callee=key,
                                            method_name='decelerate',
                                            args=args,
                                            arg_bounds=arg_bounds)
                statement.update_ast_node()
                concrete_testcase.add_statement(statement)

        chrom = Chromosome(concrete_testcase)
        logger.info("=== Logical Testcase with correct bounds === \n %s",
                    astunparse.unparse(ast.fix_missing_locations(self.logical_testcase.update_ast_node(True))))
        logger.info("=== Randomly Generating Concrete Scenario === \n %s",
                    astunparse.unparse(ast.fix_missing_locations(concrete_testcase.update_ast_node(True))))
        return chrom

