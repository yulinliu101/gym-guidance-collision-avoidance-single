import math
import numpy as np
import gym
from gym import spaces
from gym.utils import seeding

from .config import Config

__author__ = "Xuxi Yang <xuxiyang@iastate.edu>"


class SingleAircraft2Env(gym.Env):
    """
    This is the airspace simulator where we can control single aircraft (yellow aircraft)
    to reach the goal position (green star) while avoiding conflicts with other intruder aircraft (red aircraft).
    **STATE:**
    The state consists all the information needed for the ownship to choose an optimal action:
    position, velocity of intruder aircraft
    position, velocity, speed, heading angle, bank angle
    position of the goal
    In the beginning of each episode, the ownship starts in the bottom right corner of the map and the heading angle is
    pointing directly to the center of the map.
    **ACTIONS:**
    The action is either applying +1, 0 or -1 for the change of bank angle and +1, 0, -1 for the change of acceleration
    """

    def __init__(self):
        self.load_config()
        self.state = None
        self.viewer = None

        # build observation space and action space
        state_dimension = self.intruder_size * 4 + 8
        self.observation_space = spaces.Box(low=-1000, high=1000, shape=(state_dimension,), dtype=np.float32)
        self.action_space = spaces.Box(low=-1, high=1, shape=(2,), dtype=np.float)
        self.position_range = spaces.Box(
            low=np.array([0, 0]),
            high=np.array([self.window_width, self.window_height]),
            dtype=np.float32)

        self.seed(2)

    def seed(self, seed=None):
        self.np_random, seed = seeding.np_random(seed)
        return [seed]

    def load_config(self):
        # input dim
        self.window_width = Config.window_width
        self.window_height = Config.window_height
        self.intruder_size = Config.intruder_size
        self.EPISODES = Config.EPISODES
        self.G = Config.G
        self.tick = Config.tick
        self.scale = Config.scale
        self.minimum_separation = Config.minimum_separation
        self.NMAC_dist = Config.NMAC_dist
        self.horizon_dist = Config.horizon_dist
        self.initial_min_dist = Config.initial_min_dist
        self.goal_radius = Config.goal_radius
        self.min_speed = Config.min_speed
        self.max_speed = Config.max_speed

    def reset(self):
        # ownship = recordtype('ownship', ['position', 'velocity', 'speed', 'heading', 'bank'])
        # intruder = recordtype('intruder', ['id', 'position', 'velocity'])
        # goal = recordtype('goal', ['position'])

        self.drone = Ownship(
            position=(50, 50),
            speed=self.min_speed,
            heading=math.pi/4
        )

        self.intruder_list = []
        for _ in range(self.intruder_size):
            intruder = Aircraft(
                position=self.random_pos(),
                speed=self.random_speed(),
                heading=self.random_heading(),
            )
            while dist(self.drone, intruder) < self.initial_min_dist:
                intruder.position = self.random_pos()

            self.intruder_list.append(intruder)

        self.goal = Goal(position=self.random_pos())

        self.no_conflict = 0

        return self._get_ob()

    def _get_ob(self):
        s = []
        for i in range(self.intruder_size):
            # (x, y, vx, vy)
            s.append(self.intruder_list[i].position[0])
            s.append(self.intruder_list[i].position[1])
            s.append(self.intruder_list[i].velocity[0])
            s.append(self.intruder_list[i].velocity[1])
        for i in range(1):
            # (x, y, vx, vy, speed, heading)
            s.append(self.drone.position[0])
            s.append(self.drone.position[1])
            s.append(self.drone.velocity[0])
            s.append(self.drone.velocity[1])
            s.append(self.drone.speed)
            s.append(self.drone.heading)
        s.append(self.goal.position[0])
        s.append(self.goal.position[1])

        return np.array(s)

    def step(self, action):
        assert self.action_space.contains(action), 'given action is in incorrect shape'

        self.drone.step(action)

        reward, terminal, info = self._terminal_reward()

        return self._get_ob(), reward, terminal, info

    def _terminal_reward(self):

        # step the intruder aircraft
        conflict = False
        for idx in range(self.intruder_size):
            intruder = self.intruder_list[idx]
            intruder.position += intruder.velocity
            dist_intruder = dist(self.drone, intruder)
            if not self.position_range.contains(intruder.position):
                self.intruder_list[idx] = self.reset_intruder()

            if dist_intruder < self.minimum_separation:
                conflict = True
                if intruder.conflict == False:
                    self.no_conflict += 1
                    intruder.conflict = True
                else:
                    if not dist_intruder < self.minimum_separation:
                        intruder.conflict = False

                if dist_intruder < self.NMAC_dist:
                    return -5, True, 'n'  # NMAC

        if conflict:
            return -1, False, 'c'  # conflict

        if not self.position_range.contains(self.drone.position):
            return -1, True, 'w'  # out-of-map

        if dist(self.drone, self.goal) < self.goal_radius:
            return 1, True, 'g'  # goal
        return -dist(self.drone, self.goal)/1200, False, ''
        return 0, False, ''

    def render(self, mode='human'):
        from gym.envs.classic_control import rendering

        if self.viewer is None:
            self.viewer = rendering.Viewer(self.window_width, self.window_height)
            self.viewer.set_bounds(0, self.window_width, 0, self.window_height)

        if self.drone is None:
            return None

        import os
        __location__ = os.path.realpath(os.path.join(os.getcwd(), os.path.dirname(__file__)))

        ownship_img = rendering.Image(os.path.join(__location__, 'images/aircraft.png'), 32, 32)
        jtransform = rendering.Transform(rotation=self.drone.heading - math.pi/2, translation=self.drone.position)
        ownship_img.add_attr(jtransform)
        ownship_img.set_color(255, 241, 4)  # set it to yellow
        self.viewer.onetime_geoms.append(ownship_img)

        goal_img = rendering.Image(os.path.join(__location__, 'images/goal.png'), 32, 32)
        jtransform = rendering.Transform(rotation=0, translation=self.goal.position)
        goal_img.add_attr(jtransform)
        goal_img.set_color(15, 210, 81)  # green
        self.viewer.onetime_geoms.append(goal_img)

        for aircraft in self.intruder_list:
            intruder_img = rendering.Image(os.path.join(__location__, 'images/intruder.png'), 32, 32)
            jtransform = rendering.Transform(rotation=aircraft.heading - math.pi/2, translation=aircraft.position)
            intruder_img.add_attr(jtransform)
            intruder_img.set_color(237, 26, 32)  # red color
            self.viewer.onetime_geoms.append(intruder_img)

        return self.viewer.render(return_rgb_array=False)

    def close(self):
        if self.viewer:
            self.viewer.close()
            self.viewer = None

    def reset_intruder(self):
        intruder = Aircraft(
            position=self.random_pos(),
            speed=self.random_speed(),
            heading=self.random_heading(),
        )
        while dist(self.drone, intruder) < self.initial_min_dist:
            intruder.position = self.random_pos()

        return intruder

    def random_pos(self):
        return np.random.uniform(
            low=np.array([0, 0]),
            high=np.array([self.window_width, self.window_height])
        )

    def random_speed(self):
        return np.random.uniform(low=self.min_speed, high=self.max_speed)

    def random_heading(self):
        return np.random.uniform(low=0, high=2*math.pi)

    def build_observation_space(self):
        s = spaces.Dict({
            'own_x': spaces.Box(low=0, high=self.window_width, dtype=np.float32),
            'own_y': spaces.Box(low=0, high=self.window_height, dtype=np.float32),
            'pos_x': spaces.Box(low=0, high=self.window_width, dtype=np.float32),
            'pos_y': spaces.Box(low=0, high=self.window_height, dtype=np.float32),
            'heading': spaces.Box(low=0, high=2*math.pi, dtype=np.float32),
            'speed': spaces.Box(low=self.min_speed, high=self.max_speed, dtype=np.float32),
        })
        return s


class Goal:
    def __init__(self, position):
        self.position = position


class Aircraft:
    def __init__(self, position, speed, heading):
        self.position = np.array(position, dtype=np.float32)
        self.speed = speed
        self.heading = heading  # rad
        vx = self.speed * math.cos(self.heading)
        vy = self.speed * math.sin(self.heading)
        self.velocity = np.array([vx, vy], dtype=np.float32)

        self.conflict = False  # track if this aircraft is in conflict with ownship


class Ownship(Aircraft):
    def __init__(self, position, speed, heading):
        Aircraft.__init__(self, position, speed, heading)
        self.load_config()

    def load_config(self):

        self.G = Config.G
        self.scale = Config.scale
        self.min_speed = Config.min_speed
        self.max_speed = Config.max_speed
        self.d_speed = Config.d_speed
        self.speed_sigma = Config.speed_sigma
        self.position_sigma = Config.position_sigma

        self.d_heading = Config.d_heading
        self.heading_sigma = Config.heading_sigma

    def step(self, a):
        self.heading += self.d_heading * a[0]
        self.heading += np.random.normal(0, self.heading_sigma)
        self.speed += self.d_speed * a[1]
        self.speed = max(self.min_speed, min(self.speed, self.max_speed))  # project to range
        self.speed += np.random.normal(0, self.speed_sigma)

        vx = self.speed * math.cos(self.heading)
        vy = self.speed * math.sin(self.heading)
        self.velocity = np.array([vx, vy])
        self.position += self.velocity


def dist(object1, object2):
    return np.linalg.norm(object1.position - object2.position)
