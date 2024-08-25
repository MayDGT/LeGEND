from __future__ import annotations
from legend.core.chromosome import Chromosome, ChromosomeFactory
from legend.core.simulation import Simulation
from legend.utils import fnds
import json
import random
import numpy as np
import copy
import ast
import math
import astunparse
import logging

logger = logging.getLogger(__name__)


class Fuzzer:
    def __init__(self, config):
        self.config = config
        self.pop_size = None
        self.max_iteration = config['max_iteration']
        self.selection_num = config["selection_num"]
        self.tournament_round = config["tournament_round"]
        self.crossover_rate = config["crossover_rate"]
        self.mutation_rate = config["mutation_rate"]
        self.chrom_factory = None
        self.logical_testcase = None
        self.last_elitism = None
        self.sim = Simulation(config['sim_time'], config['sim_map'], config['hd_map'])

        self.pop = []
        self.collision = 0

    def initialize(self):
        self.pop = []
        self.chrom_factory = ChromosomeFactory(self.logical_testcase)
        for i in range(self.pop_size):
            chrom = self.chrom_factory.generate_random_chromosome()
            self.pop.append(chrom)
        self.eval_pop()
        self.pop = self.get_survivals(n_survival=self.pop_size)
        for chrom in self.pop:
            chrom.fitness.append(-1.0)
        self.last_elitism = self.pop[0].clone()


    def eval_pop(self, pop=None):
        pop = self.pop if pop is None else pop
        for chrom in pop:
            logger.info("=== Evaluate Chrom=== \n %s", self.chrom2string(chrom))
            chrom.fitness, is_collision = self.sim.run(chrom.testcase)
            if is_collision is True:
                logger.info("=== Find a collision ===")
                self.collision += 1
            logger.info("=== Evaluation Finished === \n fitness: %s", chrom.fitness)

    def eval(self, chrom=None):
        chrom.fitness = self.sim.run(chrom.testcase)

    def get_survivals(self, n_survival, pop=None):
        pop = self.pop if pop is None else pop
        F = []
        for chrom in pop:
            F.append(chrom.fitness)
        logger.info("Pop F: %s", str(F))
        F = np.array(F).astype(float, copy=False)
        logger.info("Population Fitness: %s", str(F))
        survivors = []
        fronts = fnds.fast_non_dominated_sort(F)
        logger.info("Fronts: %s", str(fronts))
        for k, front in enumerate(fronts):
            crowding_of_front = fnds.calc_crowding_distance(F[front, :])
            for j, i in enumerate(front):
                pop[i].rank = k
                pop[i].crowding = crowding_of_front[j]

            if len(survivors) + len(front) > n_survival:
                P = np.random.permutation(len(crowding_of_front))
                I = np.argsort(crowding_of_front[P], kind='quicksort')
                I = P[I]
                I = np.flip(I, axis=0)
            else:
                I = np.arange(len(front))

            survivors.extend(front[I])
        logger.info("Survivors: %s", str(survivors))
        return [pop[i] for i in survivors]

    def select(self, num, max_round, pop=None):
        pop = self.pop if pop is None else pop
        selection = []
        for _ in range(num):
            new_idx = random.randint(0, len(pop) - 1)
            winner_idx = new_idx
            round = 0
            while round < max_round:
                new_idx = random.randint(0, len(pop) - 1)
                selected = pop[new_idx]
                if selected.fitness < pop[winner_idx].fitness:
                    winner_idx = new_idx
                round += 1
            selection.append(pop[winner_idx])
        return selection

    def crossover(self, chrom1: Chromosome, chrom2: Chromosome):
        clone1 = chrom1.clone()
        clone2 = chrom2.clone()
        chrom1.crossover(clone2)
        chrom2.crossover(clone1)

    def update_fitness(self, pop):
        last_elitism_arg = []
        for statement in self.last_elitism.testcase.statements:
            last_elitism_arg.extend(list(statement.args.values()))
        for chrom in pop:
            chrom_arg = []
            for statement in chrom.testcase.statements:
                chrom_arg.extend(list(statement.args.values()))
            if len(last_elitism_arg) != len(chrom_arg):
                logger.info(self.chrom2string(self.last_elitism))
                logger.info(self.chrom2string(chrom))
                logger.error("The two param list must be of equal length")
                chrom.fitness.append(-1.0)
                continue
            squared_differences = [(a - b) ** 2 for a, b in zip(last_elitism_arg, chrom_arg)]
            sum_of_squared_differences = sum(squared_differences)
            distance = math.sqrt(sum_of_squared_differences)
            chrom.fitness.append(-1.0 * distance)  # maximize the diversity

    def evolve(self):
        new_pop = []
        # new_pop.extend(self.elitism())
        while len(new_pop) < self.pop_size:
            parent1 = self.select(num=self.selection_num, max_round=self.tournament_round)[0]
            parent2 = self.select(num=self.selection_num, max_round=self.tournament_round)[0]

            offspring1 = parent1.clone()
            offspring2 = parent2.clone()

            logger.info("parent 1: %s", self.chrom2string(parent1))
            logger.info("parent 2: %s", self.chrom2string(parent2))

            if random.random() <= self.crossover_rate:
                logger.info("====== Start Crossover ======")
                self.crossover(offspring1, offspring2)

            logger.info("offspring 1 after crossover: %s", self.chrom2string(offspring1))
            logger.info("offspring 2 after crossover: %s", self.chrom2string(offspring2))

            offspring1.mutate()
            offspring2.mutate()

            logger.info("offspring 1 after mutation: %s", self.chrom2string(offspring1))
            logger.info("offspring 2 after mutation: %s", self.chrom2string(offspring2))

            new_pop.append(offspring1)
            new_pop.append(offspring2)

        self.eval_pop(new_pop)
        self.update_fitness(new_pop)
        pop = self.pop + new_pop
        self.pop = self.get_survivals(self.pop_size, pop)
        self.last_elitism = self.pop[0].clone()
        logger.info("===Updated Population=== \n")
        for p in self.pop:
            logger.info("fitness: %s", str(p.fitness))
        # logger.info("The best individual: %s \r\n its fitness score is %s",
        #                  self.chrom2string(self.population[0]), str(self.population[0].fitness))

    def loop(self, logical_testcase):
        self.logical_testcase = logical_testcase
        self.pop_size = logical_testcase.size()
        logger.info("Pop size: %d", self.pop_size)
        self.initialize()
        iteration = 0
        is_need_to_mutate = False
        while iteration < self.max_iteration:
            logger.info("===Iteration %d===", iteration)
            self.evolve()
            iteration += 1
            # if self.collision == 0:
            #         # self.pop[0].fitness[0] > 6.0:
            #     is_need_to_mutate = True
            #     break
        logger.info("This loop has %d iterations and found %d collisions", iteration, self.collision)
        self.collision = 0
        return is_need_to_mutate

    def elitism(self):
        elite = []
        for idx in range(self.config["elite"]):
            elite.append(self.pop[idx].clone())
        return elite

    @staticmethod
    def chrom2string(chrom):
        return astunparse.unparse(ast.fix_missing_locations(chrom.testcase.update_ast_node()))



