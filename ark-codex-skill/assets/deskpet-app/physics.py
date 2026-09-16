import math


class Plane:
    def __init__(self):
        self.x = 0.0
        self.y = 0.0
        self.vx = 0.0
        self.vy = 0.0
        self.obj_w = 0.0
        self.obj_h = 0.0
        self.gravity = 800.0
        self.air_friction = 100.0
        self.static_friction = 500.0
        self.speed_limit_x = 1000.0
        self.speed_limit_y = 1000.0
        self.barriers = []
        self.world = []
        self.point_charges = []
        self._dropped = False
        self._dropped_height = 0.0

    DROPPED_Y_THRESHOLD = 10.0

    def set_obj_size(self, w, h):
        self.obj_w = w
        self.obj_h = h

    def set_world(self, areas):
        self.world = list(areas)

    def change_position(self, x, y, dt=0):
        if dt > 0:
            self.vx = (x - self.x) / dt
            self.vy = (y - self.y) / dt
        self.x = self._limit_x(x)
        self.y = self._limit_y(y)

    def update(self, dt):
        self._update_velocity(dt)
        dx = self.vx * dt
        dy = self.vy * dt
        bottom = self.border_bottom()
        self._dropped_height = max(self.y - bottom, self._dropped_height)
        if self.y != bottom and self._limit_y(dy + self.y) == bottom:
            if self.y - bottom > 0:
                self._dropped = True
            self.vy = 0
        self.x = self._limit_x(dx + self.x)
        self.y = self._limit_y(dy + self.y)

    @property
    def is_dropping(self):
        return abs(self.y - self.border_bottom()) > self.DROPPED_Y_THRESHOLD

    @property
    def is_dropped(self):
        if self._dropped:
            self._dropped = False
            if self._dropped_height >= self.DROPPED_Y_THRESHOLD:
                self._dropped_height = 0
                return True
        return False

    def border_top(self):
        area = self._active_area()
        return area[3] if area else 100000.0

    def border_bottom(self):
        ceiling = self.border_top()
        for by, bx, bw in self.barriers:
            if bx <= self.x + self.obj_w and self.x <= bx + bw:
                if self.y + self.obj_h > by and ceiling - self.obj_h > by:
                    return by
        area = self._active_area()
        return area[2] if area else 0.0

    def border_left(self):
        run = self._horizontal_run()
        return run[0] if run else 0.0

    def border_right(self):
        run = self._horizontal_run()
        return run[1] if run else 100000.0

    def _active_area(self):
        if not self.world:
            return None
        anchor_x = self.x + self.obj_w / 2
        anchor_y = self.y
        best = None
        for left, right, bottom, top in self.world:
            if left <= anchor_x <= right and bottom <= anchor_y <= top:
                if best is None or bottom > best[2]:
                    best = (left, right, bottom, top)
        if best:
            return best
        nearest = self.world[0]
        min_dist = float("inf")
        for area in self.world:
            left, right, bottom, top = area
            cx = max(left, min(anchor_x, right))
            cy = max(bottom, min(anchor_y, top))
            d = math.hypot(anchor_x - cx, anchor_y - cy)
            if d < min_dist:
                min_dist = d
                nearest = area
        return nearest

    def _horizontal_run(self):
        active = self._active_area()
        if not active:
            return None
        run = [active]
        changed = True
        while changed:
            changed = False
            for area in self.world:
                if area in run:
                    continue
                for m in run:
                    if self._is_x_contiguous(m, area):
                        run.append(area)
                        changed = True
                        break
        left = min(a[0] for a in run)
        right = max(a[1] for a in run)
        return (left, right)

    def _is_x_contiguous(self, a, b):
        edge_eps = 1.0
        edge_touch = abs(a[1] - b[0]) <= edge_eps or abs(a[0] - b[1]) <= edge_eps
        overlap = min(a[3], b[3]) - max(a[2], b[2])
        return edge_touch and overlap >= self.obj_h

    def set_point_charge(self, y, x, quantity):
        self.point_charges.append((y, x, quantity))

    def _update_velocity(self, dt):
        bottom = self.border_bottom()
        top = self.border_top()
        self.vy -= self.gravity * dt
        if self.y == bottom or (self.y + self.obj_h >= top and self.vy > 0):
            self.vy = 0
        if self.y == bottom:
            self.vx = self._apply_friction(self.vx, self.static_friction, dt)
        self.vx = self._apply_friction(self.vx, self.air_friction, dt)
        self.vy = self._apply_friction(self.vy, self.air_friction, dt)
        cx = self.x + self.obj_w / 2
        for cy, cxx, q in self.point_charges:
            dx = cx - cxx
            dist_sq = max(dx * dx, 2500.0)
            force = q / dist_sq * math.copysign(1, dx)
            self.vx += force * dt
        self.vx = self._apply_friction(self.vx, self.air_friction, dt)
        self.vy = self._apply_friction(self.vy, self.air_friction, dt)
        if self.speed_limit_x and abs(self.vx) > self.speed_limit_x:
            self.vx = math.copysign(self.speed_limit_x, self.vx)
        if self.speed_limit_y and abs(self.vy) > self.speed_limit_y:
            self.vy = math.copysign(self.speed_limit_y, self.vy)

    @staticmethod
    def _apply_friction(speed, friction, dt):
        delta = math.copysign(friction * dt, speed)
        estimated = speed - delta
        if delta * estimated < 0:
            return 0.0
        return estimated

    def _limit_x(self, x):
        return max(self.border_left(), min(x, self.border_right() - self.obj_w))

    def _limit_y(self, y):
        return max(self.border_bottom(), min(y, self.border_top() - self.obj_h))
