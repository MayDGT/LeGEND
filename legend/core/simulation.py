import json
import os
import lgsvl
import logging
import time
import math
import numpy as np
from shapely.geometry import Point, LineString, Polygon
# from monitor import MonitorController
from llm4fuzz.utils import sim_util

logger = logging.getLogger(__name__)


class Simulation:
    def __init__(self, sim_time, sim_map, hd_map):
        self.sim = None
        self.ego = None
        self.npc_list = None
        self.sim_time = sim_time
        self.sim_map = sim_map
        self.hd_map = hd_map

        self.testcase = None
        path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        with open(path + '/configs/straight_road/road.json') as f:
            self.road = json.load(f)
        self.npc_list = None

        # record
        self.distance_to_npcs = []
        self.snapshot = []
        self.is_collision = False
        self.connect_simulator()
        self.load_map()

    def connect_simulator(self):
        try:
            sim = lgsvl.Simulator(address="127.0.0.1", port=8181)
            self.sim = sim
        except Exception as e:
            logger.error(f"simulator connection error: {e}")

    def load_map(self):
        if self.sim.current_scene == self.sim_map:
            self.sim.reset()
        else:
            self.sim.load(self.sim_map)

    def set_weather(self):
        self.sim.weather = lgsvl.WeatherState(rain=0, fog=0, wetness=0, cloudiness=0, damage=0)
        self.sim.set_time_of_day(10.4)

    def calculate_position(self, lane_id, offset):
        """convert the GPS position to a Unity position"""
        lane_start = self.sim.map_from_gps(
            northing=self.road[lane_id]["central"]["points"][0]['y'],
            easting=self.road[lane_id]["central"]["points"][0]['x']
        )
        lane_end = self.sim.map_from_gps(
            northing=self.road[lane_id]["central"]["points"][1]['y'],
            easting=self.road[lane_id]["central"]["points"][1]['x']
        )
        lane_length = np.sqrt(
            (self.road[lane_id]["central"]["points"][1]['x'] - self.road[lane_id]["central"]["points"][0]['x']) ** 2 +
            (self.road[lane_id]["central"]["points"][1]['y'] - self.road[lane_id]["central"]["points"][0]['y']) ** 2
        )

        if offset == 0:
            x = lane_start.position.x
            z = lane_start.position.z
        else:
            v_x = lane_end.position.x - lane_start.position.x
            v_z = lane_end.position.z - lane_start.position.z
            ratio = offset / (lane_length + 0.0)
            x = lane_start.position.x + ratio * v_x
            z = lane_start.position.z + ratio * v_z

        return lgsvl.Vector(x=x, y=10.2, z=z)

    def calculate_v2b_distance(self, vehicle_state):
        """calculate the distance between a vehicle and lane boundaries"""
        left_start = self.sim.map_from_gps(
            northing=self.road["lane_1"]["left_boundary"]["points"][0]['y'],
            easting=self.road["lane_1"]["left_boundary"]["points"][0]['x']
        )
        left_end = self.sim.map_from_gps(
            northing=self.road["lane_1"]["left_boundary"]["points"][1]['y'],
            easting=self.road["lane_1"]["left_boundary"]["points"][1]['x']
        )
        right_start = self.sim.map_from_gps(
            northing=self.road["lane_3"]["right_boundary"]["points"][0]['y'],
            easting=self.road["lane_3"]["right_boundary"]["points"][0]['x']
        )
        right_end = self.sim.map_from_gps(
            northing=self.road["lane_3"]["right_boundary"]["points"][1]['y'],
            easting=self.road["lane_3"]["right_boundary"]["points"][1]['x']
        )

        p0 = vehicle_state.position
        p1 = left_start.position
        p2 = left_end.position
        p3 = right_start.position
        p4 = right_end.position

        left_line = LineString([(p1.x, p1.z), (p2.x, p2.z)])
        right_line = LineString([(p3.x, p3.z), (p4.x, p4.z)])
        bottom_line = LineString([(p1.x, p1.z), (p3.x, p3.z)])
        point = Point(p0.x, p0.z)
        distance_to_left = point.distance(left_line)
        distance_to_right = point.distance(right_line)
        distance_to_bottom = point.distance(bottom_line)
        lane_width = left_line.distance(right_line)

        # the rightmost lane id is 3
        lane_id = 3 - int(distance_to_right / 3.5)
        s = distance_to_bottom
        t = 3.5 - (distance_to_right - (int(distance_to_right / 3.5)) * 3.5)

        # return lane_id, s, t

        # use the raycast function from lgsvl to get the distance to road boundaries
        layers = self.sim.layers
        layer_mask = 0
        tohitlayers = ["Default"]  # road
        for layer in tohitlayers:
            layer_mask |= 1 << layers[layer]
        right = lgsvl.utils.transform_to_right(vehicle_state.transform)
        hit = self.sim.raycast(vehicle_state.position, right, layer_mask)
        if hit is None:
            right_distance = 4 * 3.5
        else:
            right_distance = self.sim.raycast(vehicle_state.position, right, layer_mask).distance

        lane_id = 3 - int(right_distance / 3.5)

        return lane_id

    def init_ego(self):
        ego_state = lgsvl.AgentState()
        ego_statement = None
        for statement in self.testcase.constructor_statements:
            if statement.assignee == 'ego':
                ego_statement = statement
                break

        # set start position
        lane_id = 'lane_' + str(int(ego_statement.args['lane_id']))
        offset = ego_statement.args['offset']

        ego_start_position = self.calculate_position(lane_id=lane_id, offset=offset)
        ego_state.transform = self.sim.map_point_on_lane(ego_start_position)
        self.ego = self.sim.add_agent('2e966a70-4a19-44b5-a5e7-64e00a7bc5de', lgsvl.AgentType.EGO, ego_state)

        # set destination position
        offset += 200
        ego_end_position = self.calculate_position(lane_id=lane_id, offset=offset)
        ego_end_position = self.sim.map_point_on_lane(ego_end_position)

        # setup dreamview
        self.ego.connect_bridge(address='127.0.0.1', port=9090)
        while not self.ego.bridge_connected:
            time.sleep(1)
        dv = lgsvl.dreamview.Connection(self.sim, self.ego, os.environ.get("BRIDGE_HOST", "127.0.0.1"))
        dv.set_hd_map(self.hd_map)
        dv.set_vehicle('Lincoln2017MKZ')
        dv.set_setup_mode('Mkz Lgsvl')
        modules = ['Localization', 'Transform', 'Routing', 'Prediction', 'Planning', 'Control']
        dv.setup_apollo(ego_end_position.position.x, ego_end_position.position.z, modules, default_timeout=30)

    def init_npc(self):
        npc_state = lgsvl.AgentState()
        for statement in self.testcase.constructor_statements:
            if statement.assignee != 'ego':
                lane_id = 'lane_' + str(int(statement.args['lane_id']))
                offset = statement.args['offset']
                position = self.calculate_position(lane_id=lane_id, offset=offset)
                npc_state.transform = self.sim.map_point_on_lane(position)
                npc = self.sim.add_agent("Sedan", lgsvl.AgentType.NPC, npc_state)
                start_speed = statement.args['initial_speed'] * 0.44704
                npc.follow_closest_lane(True, start_speed, False)
                self.npc_list[statement.assignee] = npc

    def activate_npc_action(self, npc, action_name, args):
        # if action["action_name"] == "acceleration":
        #     current_speed = npc.state.speed
        #     target_speed = min(20.0, current_speed + action["speed_offset"])  # speed limit = 20m/s
        #     npc.follow_closest_lane(True, target_speed, False)
        # elif action["action_name"] == "deceleration":
        #     current_speed = npc.state.speed
        #     target_speed = max(0.0, current_speed - action["speed_offset"])
        #     npc.follow_closest_lane(True, target_speed, False)

        if args["target_speed"] == 0.0:
            control = lgsvl.NPCControl()
            control.e_stop = True
            npc.apply_control(control)
        else:
            npc.follow_closest_lane(True, args["target_speed"] * 0.44704, False) # mph to m/s

        if action_name == "changeLane":
            lane_id = self.calculate_v2b_distance(npc.state)
            lane_num = abs(int(args["target_lane"]) - lane_id)
            direction = int(args["target_lane"]) - lane_id
            print(f"current_lane {lane_id}, lane_num {lane_num}, direction {'left' if direction < 0 else 'right'}")
            for _ in range(lane_num):
                npc.change_lane(True if direction < 0 else False)

    def run(self, testcase):
        self.testcase = testcase
        self.npc_list = {}

        self.load_map()
        self.set_weather()
        self.init_ego()
        # self.sim.run(3)
        self.init_npc()

        self.is_collision = False
        def on_collision(agent1, agent2, contact):
            if agent1.name == "2e966a70-4a19-44b5-a5e7-64e00a7bc5de" or \
                    agent2.name == "2e966a70-4a19-44b5-a5e7-64e00a7bc5de":
                self.is_collision = True
                print("A collision occur.")

        self.ego.on_collision(on_collision)
        time_count = 0
        min_d = 999
        ego_last_speed = self.ego.state.speed
        ego_acc_list = []
        npc_traj_list = []

        # # turn off signal
        # signal1 = self.sim.get_controllable(lgsvl.Vector(480.428466796875, 15.9500017166138, 69.9847717285156), "signal")
        # signal2 = self.sim.get_controllable(lgsvl.Vector(474.140686035156, 15.9500017166138, 53.5875549316406), "signal")
        # control_policy = "green=5;loop"
        # signal1.control(control_policy)
        # signal2.control(control_policy)

        for i in range(5):  # assuming 5 time slices
            for statement in self.testcase.method_statements:
                npc_index = statement.callee
                if time_count == 5 * statement.args["trigger_sequence"]:
                    action_name = statement.method_name
                    self.activate_npc_action(self.npc_list[npc_index], action_name, statement.args)
                    print("Trigger Action: ", action_name)

            for _ in range(5):  # each slice has 5 seconds simulation for executing each action
                if self.sim.current_time > self.sim_time:
                    break
                # ego
                # ego_lane_id, ego_s, ego_t = self.calculate_v2b_distance(self.ego.state)
                ego_bbox, ego_bounds = sim_util.get_bbox(self.ego.state, self.ego.bounding_box)

                for npc in self.npc_list.values():
                    # each npc
                    # lane_id, s, t = self.calculate_v2b_distance(npc.state)
                    npc_bbox, npc_bounds = sim_util.get_bbox(npc.state, npc.bounding_box)

                    # relative position
                    long_d, lat_d = sim_util.calculate_relative_distance(ego_bounds, npc_bounds)
                    print(long_d, lat_d)
                    bbox_d = ego_bbox.distance(npc_bbox)
                    if lat_d < 1.0 and long_d < min_d:
                        min_d = long_d

                    # record the trace
                    # npc_traj_list.append((npc.state.transform.position.x, npc.state.transform.position.z))

                ego_acc_list.append(self.ego.state.speed - ego_last_speed)
                ego_last_speed = self.ego.state.speed
                self.sim.run(1)
                time_count += 1

        self.sim.stop()
        sim_util.clean_apollo_dir()
        acr = sim_util.acc_check(ego_acc_list)  # maximize the acr
        print(npc_traj_list)
        return [min_d, -1.0 * acr], self.is_collision






