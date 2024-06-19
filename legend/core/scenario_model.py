class NPC:
    def __init__(self, lane_id: int, offset: float, initial_speed: float):
        pass

    def accelerate(self, target_speed: float, trigger_sequence: int):
        pass

    def decelerate(self, target_speed: float, trigger_sequence: int):
        pass

    def changeLane(self, target_lane: int, target_speed: float, trigger_sequence: int):
        pass