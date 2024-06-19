from __future__ import annotations
import abc
import ast
import re
from abc import ABCMeta
from itertools import islice
from typing import TYPE_CHECKING
from llm4fuzz.core.statement import Statement, ConstructorStatement, MethodStatement


class TestCase(metaclass=ABCMeta):
    def __init__(self):
        self._statements: list[Statement] = []
        self._constructor_statements = []
        self._method_statements = []
        self._cursor: int = 0
        self._ast_node = None

        self.is_reverse = False  # judge whether we need to reverse the road structure
        self.reversed = False

    @property
    def statements(self) -> list[Statement]:
        return self._statements

    @property
    def constructor_statements(self):
        return self._constructor_statements

    @property
    def method_statements(self):
        return self._method_statements

    @property
    def cursor(self) -> int:
        return self._cursor

    @property
    def ast_node(self):
        return self._ast_node

    def size(self) -> int:
        return len(self._statements)

    def clone(self, start: int = 0, stop: int | None = None) -> TestCase:
        test_case = TestCase()
        for statement in islice(self._statements, start, stop):
            clone_statement: Statement = statement.clone(test_case)
            clone_statement.update_ast_node()
            test_case._statements.append(clone_statement)
            if isinstance(clone_statement, ConstructorStatement):
                test_case._constructor_statements.append(statement)
            elif isinstance(clone_statement, MethodStatement):
                test_case._method_statements.append(statement)
        return test_case

    def get_statement(self, position: int) -> Statement:
        assert 0 <= position < len(self._statements)
        return self._statements[position]

    def add_statement(self, statement: Statement, position: int = -1):
        self._statements.append(statement)
        if isinstance(statement, ConstructorStatement):
            self._constructor_statements.append(statement)
        elif isinstance(statement, MethodStatement):
            self._method_statements.append(statement)

    def remove_statement(self, statement):
        self._statements.remove(statement)
        if statement in self._constructor_statements:
            self._constructor_statements.remove(statement)
        if statement in self._method_statements:
            self._method_statements.remove(statement)

    def get_callees(self) -> list[str]:
        callees = []
        for statement in self._statements:
            if isinstance(statement, ConstructorStatement) and re.match('vehicle', statement.assignee) is not None:
                callees.append(statement.assignee)
        return callees

    def update_ast_node(self, with_range=False) -> ast.Module:
        function_node_body = []
        for statement in self._statements:
            if with_range:
                ast_node: ast.Assign = statement.ast_node2
            else:
                ast_node: ast.Assign = statement.ast_node
            function_node_body.append(ast_node)
        function_node = ast.FunctionDef(
                            name=f"testcase",
                            args=ast.arguments(
                                args=[ast.Name(id="self", ctx="Param")],
                                defaults=[],
                                vararg=None,
                                kwarg=None,
                                posonlyargs=[],
                                kwonlyargs=[],
                                kw_defaults=[],
                            ),
                            body=function_node_body,
                            decorator_list=[]
                            )
        self._ast_node = ast.Module(body=[function_node], type_ignores=[])
        return self._ast_node
