import logging
from gym.envs.registration import register

logger = logging.getLogger(__name__)

register(
    id='guidance-collision-avoidance-single-v0',
    entry_point='gym_guidance_collision_avoidance_single.envs:SingleAircraftEnv',
    timestep_limit=10000,
    reward_threshold=10.0,
    nondeterministic=False,
)