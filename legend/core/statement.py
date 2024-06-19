import ast
import copy
import random
import logging
import numpy as np
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

def polynomial_mutate(ori_var: list, lb: list, ub: list, distribution=5, prob=0.5):
    var = np.array(ori_var)
    mut_var = var
    lb = np.array(lb)
    ub = np.array(ub)
    prob = np.ones(var.shape) * prob
    choose_index = np.random.random(var.shape) < prob
    # if choose_index are all false, we should choose at least one var for mutation
    if ~np.any(choose_index):
        choose_index[np.random.randint(var.shape[0])] = True

    choose_var = var[choose_index]
    lb = lb[choose_index]
    ub = ub[choose_index]
    delta_1 = (choose_var - lb) / (ub - lb)
    delta_2 = (ub - choose_var) / (ub - lb)
    rand = np.random.random(choose_var.shape)
    mask = rand <= 0.5
    mask_not = np.logical_not(mask)
    delta_q = np.zeros(choose_var.shape)

    # rand <= 0.5
    q = 2 * rand + (1 - 2 * rand) * np.power(1 - delta_1, distribution + 1)
    Q = np.power(q, 1 / (distribution + 1)) - 1
    delta_q[mask] = Q[mask]

    # rand > 0.5
    q = 2 * (1 - rand) + 2 * (rand - 0.5) * (np.power(1 - delta_2, distribution + 1))
    Q = 1 - np.power(q, 1 / (distribution + 1))
    delta_q[mask_not] = Q[mask_not]

    choose_var = choose_var + delta_q * (ub - lb)

    mut_var[choose_index] = choose_var
    return mut_var.tolist()


class Statement(metaclass=ABCMeta):
    def __init__(self, testcase):
        self._testcase = testcase
        self._ast_node = None
        self._ast_node2 = None  # with param ranges
        self._args = None
        self._arg_bounds = None
        self._default_arg_bounds = None
        self._assignee = None
        self._callee = None
        self._class_name = None

    @property
    def test_case(self):
        return self._testcase

    @property
    def class_name(self):
        return self._class_name

    @property
    def assignee(self):
        return self._assignee

    @assignee.setter
    def assignee(self, val):
        self._assignee = val

    @property
    def args(self):
        return self._args

    @args.setter
    def args(self, arg_name, arg_value):
        self._args[arg_name] = arg_value

    @args.setter
    def args(self, args):
        self._args = args

    @property
    def arg_bounds(self):
        return self._arg_bounds

    @arg_bounds.setter
    def arg_bounds(self, arg_name, arg_bound):
        self._arg_bounds[arg_name] = arg_bound

    @arg_bounds.setter
    def arg_bounds(self, arg_bounds):
        self._arg_bounds = arg_bounds

    @property
    def default_arg_bounds(self):
        return self._default_arg_bounds

    @default_arg_bounds.setter
    def default_arg_bounds(self, arg_name, default_arg_bound):
        self._default_arg_bounds[arg_name] = default_arg_bound

    @default_arg_bounds.setter
    def default_arg_bounds(self, default_arg_bounds):
        self._default_arg_bounds = default_arg_bounds

    @property
    def callee(self):
        return self._callee

    @callee.setter
    def callee(self, val):
        self._callee = val

    @property
    def ast_node(self):
        return self._ast_node

    @property
    def ast_node2(self):
        return self._ast_node2

    @abstractmethod
    def clone(self, test_case):
        """Deep clone a statement"""

    @abstractmethod
    def update_ast_node(self):
        """Translate this statement to an AST node."""

    @abstractmethod
    def mutate(self):
        """Mutate this statement"""


class ConstructorStatement(Statement):

    def __init__(self, testcase, assignee: str, constructor_name: str, args: dict, arg_bounds: dict):
        super().__init__(testcase)
        self._assignee = assignee
        self._constructor_name = constructor_name
        self._args = args
        self._arg_bounds = arg_bounds
        self._default_arg_bounds = None
        self._ast_node = None
        self._ast_node2 = None
        self.callee = constructor_name

    def clone(self, test_case):
        clone_args = {}
        clone_arg_bounds = {}
        for arg_name, arg_value in self._args.items():
            clone_args[arg_name] = arg_value
        for arg_name, arg_bound in self._arg_bounds.items():
            clone_arg_bounds[arg_name] = arg_bound
        return ConstructorStatement(test_case, copy.deepcopy(self._assignee), self._constructor_name, clone_args, clone_arg_bounds)

    def update_ast_node(self):
        arg_bounds = [
                ast.keyword(arg=key, value=ast.Constant(value=value))
                for key, value in self._arg_bounds.items()
            ]
        if len(self._args) == 0:
            args = [
                ast.keyword(arg=key, value=ast.Constant(value=value))
                for key, value in self._arg_bounds.items()
            ]
        else:
            args = [
                ast.keyword(arg=key, value=ast.Constant(value=value))
                for key, value in self._args.items()
            ]

        call = ast.Call(
            func=ast.Name(id=self._constructor_name, ctx=ast.Load()),
            args=args,
            keywords=[],
        )
        call2 = ast.Call(
            func=ast.Name(id=self._constructor_name, ctx=ast.Load()),
            args=arg_bounds,
            keywords=[],
        )

        self._ast_node = ast.Assign(
                targets=[ast.Name(id=self._assignee, ctx=ast.Load())],
                value=call,
            )
        self._ast_node2 = ast.Assign(
            targets=[ast.Name(id=self._assignee, ctx=ast.Load())],
            value=call2,
        )

    def mutate(self):
        if self.assignee == 'ego':
            return
        var = []
        lb = []
        ub = []
        for arg_name, arg_bound in self._arg_bounds.items():
            if arg_name != 'lane_id' and arg_bound[0] != arg_bound[1]:
                var.append(self._args[arg_name])
                lb.append(arg_bound[0])
                ub.append(arg_bound[1])

        mut_var = polynomial_mutate(var, lb, ub)

        for arg_name, arg_bound in self._arg_bounds.items():
            if arg_name == 'lane_id' or arg_bound[0] == arg_bound[1]:
                self._args[arg_name] = random.choice(arg_bound)
            else:
                self._args[arg_name] = mut_var.pop(0)

        self.update_ast_node()

    def default_mutate(self):
        var = []
        lb = []
        ub = []
        for arg_name, default_arg_bound in self._default_arg_bounds.items():
            if arg_name != 'lane_id' and default_arg_bound[0] != default_arg_bound[1]:
                var.append(self._args[arg_name])
                lb.append(default_arg_bound[0])
                ub.append(default_arg_bound[1])

        mut_var = polynomial_mutate(var, lb, ub)

        for arg_name, default_arg_bound in self._default_arg_bounds.items():
            if arg_name == 'lane_id' or default_arg_bound[0] == default_arg_bound[1]:
                self._args[arg_name] = random.choice(default_arg_bound)
            else:
                self._args[arg_name] = mut_var.pop(0)

        self.update_ast_node()


class MethodStatement(Statement):

    def __init__(self, testcase, callee: str, method_name: str, args: dict, arg_bounds: dict):
        super().__init__(testcase)
        self._callee = callee
        self._method_name = method_name
        self._args = args
        self._arg_bounds = arg_bounds
        self._default_arg_bounds = None
        self._ast_node = None
        self._ast_node2 = None

    @property
    def method_name(self):
        return self._method_name

    def clone(self, test_case):
        clone_args = {}
        clone_arg_bounds = {}
        for arg_name, arg_value in self._args.items():
            clone_args[arg_name] = arg_value

        for arg_name, arg_bound in self._arg_bounds.items():
            clone_arg_bounds[arg_name] = arg_bound

        return MethodStatement(test_case, copy.deepcopy(self.callee), copy.deepcopy(self.method_name), clone_args, clone_arg_bounds)

    def update_ast_node(self):
        arg_bounds = [
            ast.keyword(arg=key, value=ast.Constant(value=value))
            for key, value in self._arg_bounds.items()
        ]
        if len(self._args) == 0:
            args = [
                ast.keyword(arg=key, value=ast.Constant(value=value))
                for key, value in self._arg_bounds.items()
            ]
        else:
            args = [
                ast.keyword(arg=key, value=ast.Constant(value=value))
                for key, value in self._args.items()
            ]
        call = ast.Call(
            func=ast.Attribute(attr=self._method_name,
                               ctx=ast.Load(),
                               value=ast.Name(id=self._callee, ctx=ast.Load())),
            args=args,
            keywords=[],
        )
        call2 = ast.Call(
            func=ast.Attribute(attr=self._method_name,
                               ctx=ast.Load(),
                               value=ast.Name(id=self._callee, ctx=ast.Load())),
            args=arg_bounds,
            keywords=[],
        )
        self._ast_node = ast.Expr(value=call)
        self._ast_node2 = ast.Expr(value=call2)

    def mutate(self):
        var = []
        lb = []
        ub = []
        logger.info("arg bounds: %s", str(self._arg_bounds))
        for arg_name, arg_bound in self._arg_bounds.items():
            if arg_name == "target_speed":
                var.append(self._args[arg_name])
                lb.append(arg_bound[0])
                ub.append(arg_bound[1])

        mut_var = polynomial_mutate(var, lb, ub)

        for arg_name, arg_bound in self._arg_bounds.items():
            if arg_name == "target_speed":
                self._args[arg_name] = mut_var.pop(0)
            else:
                self._args[arg_name] = random.choice(arg_bound)

        self.update_ast_node()

    def default_mutate(self):
        var = []
        lb = []
        ub = []
        for arg_name, default_arg_bound in self._default_arg_bounds.items():
            if arg_name != 'direction' and arg_name != 'lane_num' and default_arg_bound[0] != default_arg_bound[1]:
                var.append(self._args[arg_name])
                lb.append(default_arg_bound[0])
                ub.append(default_arg_bound[1])

        mut_var = polynomial_mutate(var, lb, ub)

        for arg_name, default_arg_bound in self._arg_bounds.items():
            if arg_name == 'direction' or arg_name == 'lane_num' or default_arg_bound[0] == default_arg_bound[1]:
                self._args[arg_name] = random.choice(default_arg_bound)
            else:
                self._args[arg_name] = mut_var.pop(0)
                if arg_name == "trigger_time":
                    self._args[arg_name] = int(self._args[arg_name])

        self.update_ast_node()


if __name__ == '__main__':
    var = [1.5, 20.2]
    lb = [0, 20]
    ub = [10, 30]
    mut_var = polynomial_mutate(var, lb, ub)
    print(mut_var.pop(0))