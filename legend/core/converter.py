import json

import yaml

from legend.utils.llm_util import request_response
import re
import ast
import os
import astunparse
from legend.core.testcase import TestCase
from legend.core.statement import ConstructorStatement, MethodStatement
import logging

logger = logging.getLogger(__name__)


class Converter:
    def __init__(self):
        self.role_prompt = ("You are an expert in Simulation-based Testing for Autonomous Driving Systems, "
                            "with the goal of generating logical test cases with suitable parameter ranges "
                            "that correspond to functional scenario descriptions. ")
        # self.role_prompt = "You are ChatGPT, a large language model trained by OpenAI. "
        self.intro_gen_testcase = "Here is the scenario model and the test case model: "
        # self.intro_gen_param_range = "Here is a functional scenario description and its corresponding test case with parameter constraints: "
        self.intro_gen_param_range = "Suppose the parameter constraints of the testcase model are listed as follows: \n"
        path = os.path.dirname(os.path.abspath(__file__))
        with open(path + '/scenario_model.py', 'r') as f:
            self.scenario_model = f.read()

        path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(path + '/configs/straight_road/basic.txt') as f:
            self.param_constraint = f.read()
        with open(path + '/configs/straight_road/basic.json') as f:
            self.param = json.load(f)
        self.testcase_example = ("def testcase(): \n"
                                 "  vehicle1 = NPC(lane_id= , offset= , initial_speed= ) \n"
                                 "  vehicle2 = NPC(lane_id= , offset= , initial_speed= ) \n"
                                 "  \n "
                                 "  vehicle1.decelerate(target_speed= , trigger_sequence= ) \n"
                                 "  vehicle2.changeLane(target_lane= , target_speed= , trigger_sequence= )"
                                 )

        self.task_gen_testcase = "Please generate the test case corresponding to the following functional scenario: "

        self.task_gen_param_range = ("Can you specify a positive range for each of the parameters in the test case, "
                                     "that can make the scenario happen like the text description?  "
                                     "Please fill in all of the [] in this test case and output the new test case.")

        self.task_fix_param_range = ("Here are some parameter ranges extracted from the original accident report, "
                                     "Please update the parameter ranges in your test case: ")

        self.attention_gen_testcase = ("Attention: \n"
                                       "1. just output the new test case in a code snippet with the format of the example test case, "
                                       "which only contain the class initialization and method calls;"
                                       "2. you can combine multiple atomic actions in the scenario model to represent a complex action from the scenario description;"
                                       "3. each method call or multiple calls should correspond to an action described in the functional scenario, and each vehicle object is named as 'vehicle{1-n}';"
                                       "4. you can add comments to describe each action in the test case;"
                                       "5. do not add other actions such as the towing action."
                                       )

        self.attention_gen_param_range = ("Attention: 1. each parameter ranges in the [] should contain two real positive numbers (>0), "
                                          "which represent a minimum value and a maximum value;"
                                          "2. notice the initial position of each vehicle and the order in which events are triggered;"
                                          "3. just fill the parameter ranges and do not change other content;"
                                          "4. do not add any notes or calls of the testcase()."
                                         )

        self.attention_fix_param_range = "Attention: just modify the parameter ranges and output the new testcase. Do not change other part of the test case."

    def create_message(self, message):
        return [
            {"role": "system", "content": self.role_prompt},
            {"role": "user", "content": message},
        ]

    @staticmethod
    def wrap_user_message(message):
        return {"role": "user", "content": message}

    @staticmethod
    def wrap_system_message(message):
        return {"role": "assistant", "content": message}

    def convert(self, extracted_data):
        dialogue_history = [{"role": "system", "content": self.role_prompt}]
        message1 = self.intro_gen_testcase + "\n\n" + \
                   self.scenario_model + "\n\n" + \
                   self.testcase_example + "\n\n" + \
                   self.task_gen_testcase + "\n\n" + \
                   extracted_data["func_scenario"] + "\n\n" + \
                   self.attention_gen_testcase
        dialogue_history.append(self.wrap_user_message(message1))
        response1 = request_response(dialogue_history, task_id=2)
        response1 = response1.choices[0].message.content
        print("response1: ", response1)
        logger.info("Model Response 1: %s \n", response1)
        testcase_str = self.get_code_block(response1)
        testcase_str = self.replace_params_with_brackets(testcase_str)
        dialogue_history.append(self.wrap_system_message(testcase_str))
        logger.info("Generated Testcase with Default Params: \n %s", testcase_str)

        # message2 = self.intro_gen_param_range + "\n" + \
        #            extracted_data["func_scenario"] + "\n" + \
        #            testcase_str + "\n" + \
        #            self.param_constraint + "\n" + \
        #            self.task_gen_param_range + "\n" + \
        #            self.attention_gen_param_range
        message2 = self.intro_gen_param_range + self.param_constraint + "\n" + self.task_gen_param_range + \
                   "\n" + self.attention_gen_param_range
        dialogue_history.append(self.wrap_user_message(message2))
        response2 = request_response(dialogue_history, task_id=2)
        response2 = response2.choices[0].message.content
        print("response2: ", response2)
        logger.info("Model Response 2: %s \n", response2)
        testcase_str = self.get_code_block(response2)
        testcase_str = self.remove_comment(testcase_str)
        print("testcase with ranges: ", testcase_str)
        logger.info("Generated Testcase with Param Ranges: \n %s", testcase_str)
        dialogue_history.append(self.wrap_system_message(testcase_str))

        # fix some ranges
        # message3 = self.task_fix_param_range + '\n' \
        #            + extracted_data["param_range_desc"] + '\n' \
        #            + self.attention_fix_param_range
        # dialogue_history.append(self.wrap_user_message(message3))
        # response3 = request_response(dialogue_history)
        # response3 = response3.choices[0].message.content
        # print("response3: ", response3)
        # logger.info("Model Response 3: %s \n", response3)
        # testcase_str = self.get_code_block(response3)
        # print("response3 testcase get code block: \n", testcase_str)
        # testcase_str = self.remove_comment(testcase_str)
        # print("response3 testcase remove comment: \n", testcase_str)
        # logger.info("Generated Testcase with Fixed Param Ranges: \n %s", testcase_str)
        # print(testcase_str)

        testcase = self.parse_testcase_string(testcase_str)
        testcase = self.replace_ego(testcase)
        if len(re.findall(r'\b\d+(?:st|nd|rd|th)\b', extracted_data["func_scenario"])) != 0:
            testcase.is_reverse = True

        return testcase, self.legality_check(testcase)

    def legality_check(self, testcase):
        has_ego = False
        for statement in testcase.constructor_statements:
            if statement.assignee == 'ego':
                has_ego = True
                break
        has_sequence = True
        for statement in testcase.method_statements:
            if "trigger_sequence" not in statement.args:
                has_sequence = False
                break
        return has_ego and has_sequence

    @staticmethod
    def get_code_block(response):
        if "```" in response:
            testcase_str = response.split("```")[1]
            testcase_str = "\n".join(testcase_str.split("\n")[1:])
        elif response.find("def") != -1:
            testcase_str = response[response.find("def"): response.rfind(")") + 1]
        else:
            testcase_str = response
        return testcase_str

    @staticmethod
    def remove_comment(testcase_str):
        comment_pattern = r'#.*$'
        testcase_str = re.sub(comment_pattern, '', testcase_str, flags=re.MULTILINE)

        note_pattern = re.search(r'(?i)Note:', testcase_str)

        # If note exists, remove it
        if note_pattern:
            # Slice the string to remove the note
            testcase_str = testcase_str[:note_pattern.start()].strip()

        non_empty_lines = list(filter(lambda line: line.strip(), testcase_str.split('\n')))
        testcase_str = '\n'.join(non_empty_lines)

        return testcase_str

    @staticmethod
    def replace_params_with_brackets(testcase_str):
        # Split the text into lines
        lines = testcase_str.split('\n')

        # Iterate through each line
        for i in range(len(lines)):
            line = lines[i]
            # Check if the line contains parameters
            if "(" in line and ")" in line:
                start_index = line.index("(") + 1
                end_index = line.index(")")
                if end_index > start_index + 1:
                    params = line[start_index:end_index].split(",")
                    # Replace each parameter value with []
                    replaced_params = [param.split("=")[0] + "=[]" for param in params]
                    replaced_line = line[:start_index] + ','.join(replaced_params) + line[end_index:]
                    lines[i] = replaced_line

        # Join the lines back together
        return '\n'.join(lines)

    @staticmethod
    def parse_testcase_string(testcase_str):
        testcase = TestCase()
        tree = ast.parse(testcase_str)
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign) and isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Name) and node.value.func.id == 'NPC':
                    assignee = node.targets[0].id
                    class_name = node.value.func.id
                    args = {}
                    arg_bounds = {}
                    for keyword in node.value.keywords:
                        if isinstance(keyword.value, ast.List):
                            try:
                                arg_bounds[keyword.arg] = [elt.n for elt in keyword.value.elts]
                                args[keyword.arg] = [elt.n for elt in keyword.value.elts]
                            except Exception as e:
                                logger.error(e)
                                arg_bounds[keyword.arg] = [1, 1]
                                args[keyword.arg] = [1, 1]
                        if isinstance(keyword.value, ast.Constant):
                            arg_bounds[keyword.arg] = keyword.value.value
                            args[keyword.arg] = keyword.value.value

                    statement = ConstructorStatement(testcase=testcase,
                                                     constructor_name=class_name,
                                                     assignee=assignee,
                                                     args=args,
                                                     arg_bounds=arg_bounds)
                    statement.update_ast_node()
                    testcase.add_statement(statement)

            elif isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
                if isinstance(node.value.func, ast.Attribute):
                    callee = node.value.func.value.id
                    method_name = node.value.func.attr
                    args = {}
                    arg_bounds = {}
                    for keyword in node.value.keywords:
                        if isinstance(keyword.value, ast.List):
                            arg_bounds[keyword.arg] = [elt.n for elt in keyword.value.elts]
                            args[keyword.arg] = [elt.n for elt in keyword.value.elts]
                        if isinstance(keyword.value, ast.Constant):
                            arg_bounds[keyword.arg] = keyword.value.value
                            args[keyword.arg] = keyword.value.value

                    statement = MethodStatement(testcase=testcase,
                                                callee=callee,
                                                method_name=method_name,
                                                args=args,
                                                arg_bounds=arg_bounds)
                    statement.update_ast_node()
                    testcase.add_statement(statement)

        print(astunparse.unparse(ast.fix_missing_locations(testcase.update_ast_node())))
        return testcase

    @staticmethod
    def replace_ego(testcase: TestCase):
        statement_list = testcase.statements
        frequency_dict = {}
        for stmt in statement_list:
            if isinstance(stmt, ConstructorStatement):
                frequency_dict[stmt.assignee] = 0
            if isinstance(stmt, MethodStatement):
                frequency_dict[stmt.callee] += 1
        min_value = min(frequency_dict.values())
        candidate_ego = [key[-1] for key, value in frequency_dict.items() if value == min_value]
        for i in reversed(range(len(statement_list))):
            statement = statement_list[i]
            if isinstance(statement, ConstructorStatement) and statement.assignee[-1] in candidate_ego:
                statement.assignee = 'ego'
                statement.update_ast_node()
                print("replace assignee")
            elif isinstance(statement, MethodStatement) and statement.callee[-1] in candidate_ego:
                testcase.remove_statement(statement)
                print("remove its action")

        print(astunparse.unparse(ast.fix_missing_locations(testcase.update_ast_node())))

        return testcase


if __name__ == "__main__":
    converter = Converter()
    extracted_data = {
        'func_scenario': """Initial actions: 
(V1, V2, V3): V1 is traveling eastbound in the right lane approaching a T-intersection, V2 is also traveling eastbound in the right lane directly in front of V1 and decelerating, and V3 is traveling eastbound in the right lane directly 3-4 car lengths in front of V2.

Interactive pattern sequence: 
(V2, V1): V2 decelerates in traffic while in the same lane in front of V1 who maintains speed.
(V3, V2): V3 stays stationary due to traffic while V2 is decelerating directly behind it.
(V1, V2): V1 brakes and swerves right after noticing V2's abrupt deceleration.
(V3, V2): V3 attempts to turn wheel to the right upon noticing V1's high speed approach towards V2.""",
        'param_range_desc': "",
        'candidate_ego': [3]}
    # converter.convert(extracted_data)
    testcase_str = """def testcase(): 
    vehicle1 = NPC(lane_id=[2, 2], offset=[45, 50], initial_speed=[30, 30]) 
    vehicle2 = NPC(lane_id=[2, 2], offset=[15, 20], initial_speed=[0, 0]) 
    vehicle3 = NPC(lane_id=[2, 2], offset=[10, 15], initial_speed=[0, 0]) 
    vehicle4 = NPC(lane_id=[2, 2], offset=[5, 10], initial_speed=[0, 0]) 
    vehicle1.decelerate(target_speed=[0, 0], trigger_sequence=[1, 1]) 
Note: 
- The offset parameter for vehicle1 is set higher so that it starts behind all other vehicles.
- The initial_speed of vehicle1 is set to approximate 48kph (30mph)"""
    # testcase_str = converter.parse_testcase_string(testcase_str)
    # converter.replace_ego(testcase_str, [3])
    print(converter.remove_comment(testcase_str))
