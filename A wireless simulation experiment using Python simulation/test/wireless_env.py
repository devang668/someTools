import gym
from gym import spaces
import numpy as np


class WirelessCommEnv(gym.Env):
    def __init__(self, max_users=50):
        super(WirelessCommEnv, self).__init__()

        # 核心参数
        self.max_users = max_users
        self.current_num_users = 10

        # 定义固定维度空间
        self.observation_space = spaces.Box(
            low=0,
            high=1,
            shape=(4 * self.max_users,),  # 固定维度：4*最大用户数
            dtype=np.float32
        )
        self.action_space = spaces.Box(
            low=0,
            high=1,
            shape=(2 * self.max_users,),  # 固定维度：2*最大用户数
            dtype=np.float32
        )

        # 无线通信参数
        self.max_power = 20  # 最大发射功率（瓦）
        self.noise_floor = 1e-9  # 噪声基底（瓦）
        self.frequency = 3.5e9  # 载波频率（Hz）

    def reset(self):
        # 生成有效状态数据
        self.user_positions = np.random.uniform(50, 500, self.current_num_users)
        self.qos_demand = np.random.randint(1, 5, self.current_num_users)

        # 生成有效状态并填充到最大维度
        valid_state = self._generate_valid_state()
        padded_state = np.zeros(4 * self.max_users)
        padded_state[:4 * self.current_num_users] = valid_state
        return padded_state

    def _generate_valid_state(self):
        """生成实际用户数对应的状态向量"""
        path_loss = 35.2 + 37.6 * np.log10(self.user_positions)
        csi = 10 ** (-path_loss / 20)  # 信道状态信息
        load = np.random.uniform(0, 1, self.current_num_users)  # 基站负载
        interference = np.random.uniform(0, 0.2, self.current_num_users)  # 干扰水平

        return np.concatenate([
            csi,
            self.qos_demand / 5.0,
            load,
            interference
        ])

    def step(self, action):
        # 截取有效动作部分
        valid_action = action[:2 * self.current_num_users]

        # 资源分配
        rb_alloc = valid_action[:self.current_num_users]
        power_alloc = valid_action[self.current_num_users:] * self.max_power

        # 物理层计算 -------------------------------
        # 信干噪比计算
        path_loss = 35.2 + 37.6 * np.log10(self.user_positions)
        channel_gain = 10 ** (-path_loss / 20)
        interference = self.noise_floor + np.mean(power_alloc) * 0.05  # 相邻小区干扰

        sinr = (power_alloc * channel_gain) / interference

        # 吞吐量计算（Mbps）
        throughput = 180e3 * np.log2(1 + sinr) / 1e6

        # QoS指标计算 -------------------------------
        # 延迟模型：基础延迟 + 队列延迟
        base_delay = np.random.uniform(1, 5, self.current_num_users)
        queue_delay = 10 / (throughput + 1e-6)  # 防止除零
        delay = base_delay + queue_delay

        # 丢包率模型：与资源块分配负相关
        packet_loss = np.clip(0.25 - (rb_alloc * 0.2), 0, 1)

        # 能效计算（Mbps/W）
        energy_efficiency = throughput / (power_alloc + 1e-6)

        # 奖励计算 -------------------------------
        throughput_reward = np.sum(throughput)
        power_penalty = 0.1 * np.sum(power_alloc)
        qos_penalty = 0.05 * np.sum(delay) + 0.2 * np.sum(packet_loss)
        reward = throughput_reward - power_penalty - qos_penalty

        # 状态更新 -------------------------------
        next_state = self.reset()  # 保持固定维度状态

        # 信息收集 -------------------------------
        info = {
            'throughput': throughput,  # 各用户吞吐量 (Mbps)
            'delay': delay,  # 各用户端到端延迟 (ms)
            'packet_loss': packet_loss,  # 各用户丢包率 (0-1)
            'power': power_alloc,  # 各用户发射功率 (W)
            'energy_efficiency': energy_efficiency  # 各用户能效
        }

        return next_state, reward, False, info

    def render(self, mode='human'):
        pass