import math
import numpy as np
import subprocess
import glob
import os
import yaml
from shapely.geometry import Polygon, LineString, Point

path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
with open(path + "/configs/config.yaml") as f:
    config = yaml.safe_load(f)


def calculate_v2v_distance(ego_state, npc_state):
    """calculate the distance between the center points of two vehicles"""
    ego_position = np.array([ego_state.position.x, ego_state.position.y, ego_state.position.z])
    npc_position = np.array([npc_state.position.x, npc_state.position.y, npc_state.position.z])
    distance = np.linalg.norm(ego_position - npc_position)
    return distance


def calc_abc_from_line_2d(x0, y0, x1, y1):
    a = y0 - y1
    b = x1 - x0
    c = x0 * y1 - x1 * y0
    return a, b, c


def get_line_cross_point(line1, line2):
    a0, b0, c0 = calc_abc_from_line_2d(*line1)
    a1, b1, c1 = calc_abc_from_line_2d(*line2)
    D = a0 * b1 - a1 * b0
    if D == 0:
        return None
    x = (b0 * c1 - b1 * c0) / D
    y = (a1 * c0 - a0 * c1) / D
    return x, y


def right_rotation(coord, theta):
    """
    theta : degree
    """
    theta = math.radians(theta)
    x = coord[1]
    y = coord[0]
    x1 = x * math.cos(theta) - y * math.sin(theta)
    y1 = x * math.sin(theta) + y * math.cos(theta)
    return [y1, x1]


def calc_perpendicular_distance(point: Point, line: LineString):
    x1, y1 = line.coords[0]
    x2, y2 = line.coords[1]

    A = y2 - y1
    B = x1 - x2
    C = (x2 * y1) - (x1 * y2)

    distance = np.abs((A * point.x + B * point.y + C) / np.sqrt(A ** 2 + B ** 2))

    return distance

def get_bbox(agent_state, agent_bbox):
    agent_theta = agent_state.transform.rotation.y
    #agent_bbox min max (x_min, y_min, z_min) (x_max, y_max, z_max)

    global_x = agent_state.transform.position.x
    global_z = agent_state.transform.position.z
    x_min = agent_bbox.min.x + 0.1
    x_max = agent_bbox.max.x - 0.1
    z_min = agent_bbox.min.z + 0.1
    z_max = agent_bbox.max.z - 0.1

    line1 = [x_min, z_min, x_max, z_max]
    line2 = [x_min, z_max, x_max, z_min]
    x_center, z_center = get_line_cross_point(line1, line2)

    coords = [[x_min, z_min], [x_max, z_min], [x_max, z_max], [x_min, z_max]]
    new_coords = []

    for i in range(len(coords)):
        coord_i = coords[i]
        coord_i[0] = coord_i[0] - x_center
        coord_i[1] = coord_i[1] - z_center
        new_coord_i = right_rotation(coord_i, agent_theta)
        new_coord_i[0] += global_x
        new_coord_i[1] += global_z
        new_coords.append(new_coord_i)
    p1, p2, p3, p4 = new_coords[0], new_coords[1], new_coords[2], new_coords[3]

    agent_poly = Polygon((p1, p2, p3, p4))
    return agent_poly, [p1, p2, p3, p4]


def is_in_same_lane(bounds1, bounds2):
    p1 = bounds1[0]
    p2 = bounds1[1]
    p3 = bounds1[2]
    p4 = bounds1[3]
    left_line = LineString([(p1[0], p1[1]), (p4[0], p4[1])])
    right_line = LineString([(p3[0], p3[1]), (p2[0], p2[1])])
    width = left_line.distance(right_line)

    flag = False
    threshold = 0.5

    for p in bounds2:
        p = Point(p[0], p[1])
        dist_left = calc_perpendicular_distance(p, left_line)
        dist_right = calc_perpendicular_distance(p, right_line)
        if dist_left <= width + threshold and dist_right <= width + threshold:
            flag = True
            break
    print(flag)
    return flag


def get_relative_description(lane_id, s, t, ego_lane_id, ego_s, ego_t):
    lat_position = None
    lat_distance = None
    long_position = None
    if lane_id == ego_lane_id:
        if t <= ego_t:
            lat_position = "left"
        else:
            lat_position = "right"
        lat_distance = round(abs(t - ego_t), 2)
    elif lane_id < ego_lane_id:
        lat_position = "left"
        lat_distance = round(3.5 - t + ego_t, 2)
    elif lane_id > ego_lane_id:
        lat_position = "right"
        lat_distance = round(3.5 - ego_t + t, 2)

    if s >= ego_s:
        long_position = "front"
    else:
        long_position = "behind"
    long_distance = round(abs(ego_s - s), 2)

    return [long_position, lat_position]


def calculate_relative_distance(bounds1, bounds2):
    """Get the relative lateral & longitudinal distance of agent2 to agent1.
    Lateral: the distance between the longitudinal center axes of two agents.
    Longitudinal: the distance between the front lines of two agents, which is similar to the THW (time headway) metric.
    """
    p1 = bounds1[0]
    p2 = bounds1[1]
    p3 = bounds1[2]
    p4 = bounds1[3]
    left_line = LineString([(p1[0], p1[1]), (p4[0], p4[1])])
    right_line = LineString([(p3[0], p3[1]), (p2[0], p2[1])])
    up_line1 = LineString([(p1[0], p1[1]), (p2[0], p2[1])])
    bottom_line = LineString([(p3[0], p3[1]), (p4[0], p4[1])])
    middle_line1 = LineString([((p1[0] + p2[0])/2, (p1[1] + p2[1])/2), ((p3[0] + p4[0])/2, (p3[1] + p4[1])/2)])

    point1 = Point(bounds2[0][0], bounds2[0][1])
    point2 = Point(bounds2[1][0], bounds2[1][1])
    point3 = Point(bounds2[2][0], bounds2[2][1])
    point4 = Point(bounds2[3][0], bounds2[3][1])
    up_line2 = LineString([(bounds2[0][0], bounds2[0][1]), (bounds2[1][0], bounds2[1][1])])

    long_d = up_line1.distance(up_line2)
    lat_d = min(calc_perpendicular_distance(point1, middle_line1),
                calc_perpendicular_distance(point2, middle_line1),
                calc_perpendicular_distance(point3, middle_line1),
                calc_perpendicular_distance(point4, middle_line1)
                )
    # dist_left = calc_perpendicular_distance(point1, left_line)
    # dist_right = calc_perpendicular_distance(point1, right_line)
    # if dist_left >= dist_right:
    #     # right side
    #     lat_d = min(dist_right, calc_perpendicular_distance(point4, right_line))
    # else:
    #     # left side
    #     lat_d = -1.0 * min(calc_perpendicular_distance(point2, left_line), calc_perpendicular_distance(point3, left_line))
    #
    # dist_front = min(calc_perpendicular_distance(point1, up_line), calc_perpendicular_distance(point2, up_line))
    # dist_back = min(calc_perpendicular_distance(point1, bottom_line), calc_perpendicular_distance(point2, bottom_line))
    # if dist_front <= dist_back:
    #     # front side
    #     long_d = dist_front
    # else:
    #     long_d = -1.0 * dist_back

    return long_d, lat_d


def clean_apollo_dir():
    APOLLO_ROOT = config["apollo_root"]
    subprocess.run(f"rm -rf {APOLLO_ROOT}/data".split())

    # remove records dir
    subprocess.run(f"rm -rf {APOLLO_ROOT}/records".split())

    # remove logs
    fileList = glob.glob(f'{APOLLO_ROOT}/*.log.*')
    for filePath in fileList:
        os.remove(filePath)

    # create data dir
    subprocess.run(f"mkdir {APOLLO_ROOT}/data".split())
    subprocess.run(f"mkdir {APOLLO_ROOT}/data/bag".split())
    subprocess.run(f"mkdir {APOLLO_ROOT}/data/log".split())
    subprocess.run(f"mkdir {APOLLO_ROOT}/data/core".split())
    subprocess.run(f"mkdir {APOLLO_ROOT}/records".split())


def acc_check(acc_list):
    timestamps = len(acc_list)

    alpha = 1.0
    upwards_reversals = calculate_reversals(acc_list, alpha)

    for i in range(timestamps):
        acc_list[i] = -1 * acc_list[i]

    downwards_reversals = calculate_reversals(acc_list, alpha)

    acr = (upwards_reversals + downwards_reversals) / timestamps

    return acr

def calculate_reversals(acc_list, alpha):
    d_angle = []
    timestamps = len(acc_list)
    for i in range(timestamps):
        if i == 0:
            d_angle.append(0)
        d_angle.append(acc_list[i] - acc_list[i - 1])

    stationary_points = []
    for i in range(timestamps - 1):
        if d_angle == 0 or abs(np.sign(d_angle[i]) - np.sign(d_angle[i + 1])) == 2:
            stationary_points.append(i)

    count = 0
    k = 0
    if len(stationary_points) > 1:
        for i in range(1, len(stationary_points)):
            if acc_list[stationary_points[i]] - acc_list[stationary_points[k]] >= alpha:
                count += 1
                k = i
            elif acc_list[stationary_points[i]] < acc_list[stationary_points[k]]:
                k = i

    return count

def euclidean_distance(point1, point2):
    return np.sqrt(np.sum((np.array(point1) - np.array(point2)) ** 2))

def trajectory_distance(traj1, traj2):
    # Ensure the trajectories are of the same length
    assert len(traj1) == len(traj2), "Trajectories must have the same length"
    return sum(euclidean_distance(p1, p2) for p1, p2 in zip(traj1, traj2))

def scenario_distance(scenario1, scenario2):
    # Ensure both scenarios have the same number of trajectories
    assert len(scenario1) == len(scenario2), "Scenarios must have the same number of trajectories"
    return sum(trajectory_distance(traj1, traj2) for traj1, traj2 in zip(scenario1, scenario2))

if __name__ == "__main__":
    s1 = [(101.772277832031, 970.248474121094), (97.8386077880859, 974.178283691406), (89.6416778564453, 982.199584960938), (80.5742721557617, 990.782104492188), (71.1117858886719, 999.024047851563), (61.9100494384766, 1006.26000976563), (60.0896530151367, 1006.99053955078), (53.6463813781738, 1008.70812988281), (49.8683319091797, 1009.73657226563), (49.8426704406738, 1009.74377441406), (49.8427505493164, 1009.74328613281), (49.7411727905273, 1009.78662109375), (49.4845199584961, 1009.90277099609), (49.1990280151367, 1010.03094482422), (48.9117851257324, 1010.15899658203), (48.6245384216309, 1010.28717041016), (48.3372955322266, 1010.41528320313), (48.050048828125, 1010.54345703125), (47.7628021240234, 1010.67163085938), (47.4755554199219, 1010.7998046875), (47.1883010864258, 1010.92791748047), (46.9010543823242, 1011.05609130859), (46.6138038635254, 1011.18426513672), (46.3265571594238, 1011.31231689453)]

    s2 = [(101.772277832031, 970.248474121094), (97.8386077880859, 974.178283691406), (89.6416778564453, 982.199584960938), (80.5742721557617, 990.782104492188), (71.1117858886719, 999.024047851563), (61.9100494384766, 1006.26000976563), (60.0896530151367, 1006.99053955078), (53.6463813781738, 1008.70812988281), (48.1581954956055, 1010.40307617188), (42.1553077697754, 1013.13549804688), (36.2684173583984, 1015.7255859375), (36.1126861572266, 1015.77648925781), (35.8201866149902, 1015.87109375), (35.5102615356445, 1015.97235107422), (35.1995811462402, 1016.07611083984), (34.888801574707, 1016.17852783203), (34.5779075622559, 1016.27923583984), (34.2670364379883, 1016.37994384766), (33.9561653137207, 1016.48065185547), (33.6452789306641, 1016.58135986328), (33.334400177002, 1016.68200683594), (33.0235137939453, 1016.78271484375), (32.7126388549805, 1016.88348388672), (32.4017448425293, 1016.98419189453)]

    s3 = [(101.772277832031, 970.248474121094), (97.8386077880859, 974.178283691406), (89.6416778564453, 982.199584960938), (80.5742721557617, 990.782104492188), (71.1117858886719, 999.024047851563), (61.9100494384766, 1006.26000976563), (60.0896530151367, 1006.99053955078), (53.6463813781738, 1008.70812988281), (48.1581954956055, 1010.40307617188), (42.1553077697754, 1013.13549804688), (36.2684173583984, 1015.7255859375), (36.123462677002, 1015.77294921875), (35.8511543273926, 1015.86126708984), (35.5626335144043, 1015.95281982422), (35.2734832763672, 1016.04437255859), (34.9843597412109, 1016.13598632813), (34.6952133178711, 1016.2275390625), (34.406063079834, 1016.31909179688), (34.1169128417969, 1016.41070556641), (33.8277587890625, 1016.50225830078), (33.5386009216309, 1016.59368896484), (33.2494506835938, 1016.68579101563), (32.9602966308594, 1016.78039550781), (32.6711463928223, 1016.875)]

    s4 = [(101.772277832031, 970.248474121094), (97.8386077880859, 974.178283691406), (89.6416778564453, 982.199584960938), (80.5742721557617, 990.782104492188), (71.1117858886719, 999.024047851563), (61.9100494384766, 1006.26000976563), (59.1284675598145, 1007.36505126953), (49.8411521911621, 1009.75286865234), (42.7173309326172, 1012.68957519531), (34.7558631896973, 1016.34735107422), (25.5188808441162, 1019.21533203125), (25.3945732116699, 1019.23699951172), (25.1123561859131, 1019.28198242188), (24.8026733398438, 1019.33081054688), (24.4912700653076, 1019.37963867188), (24.1798114776611, 1019.42846679688), (23.8683738708496, 1019.47735595703), (23.556921005249, 1019.52618408203), (23.2454586029053, 1019.57501220703), (22.933988571167, 1019.62384033203), (22.622537612915, 1019.67266845703), (22.3110752105713, 1019.72155761719), (21.9996242523193, 1019.77038574219), (21.6881942749023, 1019.81921386719)]

    # s5 = [(99.3335876464844, 967.262756347656), (97.9452056884766, 968.562683105469), (96.1386566162109, 970.255493164063), (93.1020812988281, 973.16552734375), (88.9639282226563, 977.329650878906), (84.3013000488281, 982.021911621094), (85.3219604492188, 990.865417480469), (80.0996856689453, 1001.43969726563), (67.9100570678711, 1005.21752929688), (56.1361083984375, 1014.59100341797), (41.5191116333008, 1022.39416503906), (32.6470260620117, 1025.15637207031), (18.9160995483398, 1028.51293945313), (3.38131427764893, 1029.10778808594), (-14.5569858551025, 1027.67858886719), (-31.5119686126709, 1024.23449707031), (-33.729866027832, 1022.30163574219), (-37.7216339111328, 1016.14538574219), (-38.4522666931152, 1015.55859375), (-38.4622573852539, 1015.56512451172), (-38.4634323120117, 1015.56549072266), (-38.5133361816406, 1015.52972412109), (-38.6800842285156, 1015.48541259766), (-38.9568748474121, 1015.40447998047)]

    total = []
    total.append(s1)
    total.append(s2)
    total.append(s3)
    total.append(s4)
    # total.append(s5)

    avg_distance = 0
    count = 0
    for i in range(len(total)):
        for j in range(i, len(total)):
            avg_distance += scenario_distance(total[i], total[j]) / len(total[i])
            count += 1
    print(avg_distance / count)
