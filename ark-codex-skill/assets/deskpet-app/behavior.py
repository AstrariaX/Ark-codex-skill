import random
from enum import IntEnum


class State(IntEnum):
    IDLE = 0
    SIT = 1
    SLEEP = 2
    MOVE_L = 3
    MOVE_R = 4
    INTERACT = 5


STATE_TO_ANIM = {
    State.IDLE: ("idle", 0),
    State.SIT: ("sit", 0),
    State.SLEEP: ("sleep", 0),
    State.MOVE_L: ("move", -1),
    State.MOVE_R: ("move", 1),
    State.INTERACT: ("interact", 0),
}

DEFAULT_WEIGHTS = [
    [40, 20, 10, 10, 10, 10],
    [30, 40, 20, 10, 10, 10],
    [20, 20, 60,  0,  0,  0],
    [40, 10,  0, 20, 20, 10],
    [40, 10,  0, 20, 20, 10],
    [50, 20, 10, 10, 10,  0],
]

MIN_DURATION = 0.5


class StochasticMatrix:
    def __init__(self, weights=None):
        src = weights or DEFAULT_WEIGHTS
        n = len(State)
        self.weights = [list(row[:n]) for row in src[:n]]
        self.disabled = [False] * n

    def disable(self, state):
        self.disabled[state] = True

    def enable(self, state):
        self.disabled[state] = False

    def scale(self, state, factor):
        row = self.weights[state]
        for i in range(len(row)):
            row[i] = round(row[i] * factor)

    def transition(self, current):
        row = self.weights[current]
        candidates = []
        total = 0
        for i, w in enumerate(row):
            if self.disabled[i]:
                continue
            candidates.append((i, w))
            total += w
        if total == 0:
            return current
        r = random.randint(0, total - 1)
        acc = 0
        for idx, w in candidates:
            acc += w
            if r < acc:
                return State(idx)
        return current

    def configure(self, available_states, activation=4):
        for s in State:
            anim_name, _ = STATE_TO_ANIM[s]
            if anim_name not in available_states:
                self.disable(s)
            else:
                self.enable(s)
        factor = 1 + (8 - max(0, min(16, activation))) / 8
        self.scale(State.IDLE, factor)
