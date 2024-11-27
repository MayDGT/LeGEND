import random

from legend.utils.llm_util import request_response
import re
import os
import ast
import logging
import openpyxl
import astunparse
from legend.core.testcase import TestCase
from legend.core.statement import ConstructorStatement, MethodStatement

logger = logging.getLogger(__name__)


class Generator:
    def __init__(self):
        self.role_prompt = ("You are an expert in Simulation-based Testing for Autonomous Driving Systems, "
                            "with the goal of generating test cases from public accident reports. "
                            "Here is a description of an accident report: ")

        path = os.path.dirname(os.path.abspath(__file__))
        with open(path + '/scenario_model.py', 'r') as f:
            self.scenario_model = f.read()

        self.testcase_example = ("Here is the scenario model and test case model: \n"
                                 + self.scenario_model + "\n"
                                 "def testcase(): \n"
                                 "  vehicle1 = NPC(lane_id= , offset= , initial_speed= ) \n"
                                 "  vehicle2 = NPC(lane_id= , offset= , initial_speed= ) \n"
                                 "  \n "
                                 "  vehicle1.decelerate(target_speed= , trigger_sequence= ) \n"
                                 "  vehicle2.changeLane(target_lane= , target_speed= , trigger_sequence= )"
                                 )
        self.task_gen_testcase = "Please generate the test case corresponding to the original accident report and " \
                                 "specify a positive range for each of the parameters in the test case."

        path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(path + '/configs/straight_road/basic.txt') as f:
            self.param_constraint = f.read()

        self.attention_prompt = (
            "Attention: \n"
            "1. just output the new test case in a code snippet with the format of the example test case, "
                "which only contain the class initialization and method calls;"
            "2. each parameter range should be filled in the test case, and each [] should contain two real positive numbers ( > 0), "
                "which represent a minimum value and a maximum value;"
           )

    @staticmethod
    def wrap_user_message(message):
        return {"role": "user", "content": message}

    @staticmethod
    def wrap_system_message(message):
        return {"role": "assistant", "content": message}

    def generate(self, report):
        dialogue_history = [{"role": "system", "content": self.role_prompt}]
        message1 = report + "\n\n" + \
                   self.testcase_example + "\n\n" + \
                   self.task_gen_testcase + "\n\n" + \
                   self.param_constraint + "\n\n" +\
                   self.attention_prompt
        dialogue_history.append(self.wrap_user_message(message1))
        response1 = request_response(dialogue_history, task_id=2)
        response1 = response1.choices[0].message.content
        print("response1: ", response1)
        logger.info("Model Response 1: %s \n", response1)
        testcase_str = self.get_code_block(response1)
        dialogue_history.append(self.wrap_system_message(testcase_str))
        testcase = self.parse_testcase_string(testcase_str)

        candidate_ego = []
        frequency_dict = {}
        for stmt in testcase.constructor_statements:
            frequency_dict[stmt.assignee[-1]] = 0
        for stmt in testcase.statements:
            if isinstance(stmt, MethodStatement):
                frequency_dict[stmt.callee[-1]] += 1

        min_value = min(frequency_dict.values())
        candidate_ego = [key[-1] for key, value in frequency_dict.items() if value == min_value]
        testcase = self.replace_ego(testcase, [random.choice(candidate_ego)])

        if len(re.findall(r'\b\d+(?:st|nd|rd|th)\b', report)) != 0:
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
    def replace_ego(testcase: TestCase, candidate_ego: list):
        statement_list = testcase.statements
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
    pass
