#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: 'Guohan'
@file: evaluate.py.py
@time: 27/5/2025 上午 12:22
@functions：性能评估与可视化
"""
import numpy as np
import matplotlib.pyplot as plt
from wireless_env import WirelessCommEnv
from ddpg_agent import DDPGAgent

# 加载训练好的模型
NUM_USERS = 20
env = WirelessCommEnv(num_users=NUM_USERS)
state_dim = env.observation_space.shape[0]
action_dim = env.action_space.shape[0]

agent = DDPGAgent(state_dim, action_dim)
agent.actor.load_state_dict(torch.load("ddpg_actor.pth"))


# 评估函数
def evaluate(algorithm, env, episodes=10):
    throughput_list = []
    jain_index_list = []
    energy_list = []

    for _ in range(episodes):
        state = env.reset()
        total_throughput = 0
        total_energy = 0
        user_throughputs = []

        for _ in range(100):  # 每个episode运行100步
            if algorithm == "DDPG":
                action = agent.select_action(state, noise_scale=0)  # 关闭探索噪声
            elif algorithm == "PF":
                action = proportional_fair_scheduler(state)
            elif algorithm == "Greedy":
                action = greedy_scheduler(state)

            _, reward, _, info = env.step(action)

            # 收集指标
            total_throughput += info['throughput']
            total_energy += info['energy']
            user_throughputs.append(info['user_throughputs'])

        # 计算公平性指数
        avg_throughputs = np.mean(user_throughputs, axis=0)
        jain = np.sum(avg_throughputs) ** 2 / (NUM_USERS * np.sum(avg_throughputs ** 2))

        throughput_list.append(total_throughput / 100)
        jain_index_list.append(jain)
        energy_list.append(total_energy / 100)

    return np.mean(throughput_list), np.mean(jain_index_list), np.mean(energy_list)


# 传统算法实现示例
def proportional_fair_scheduler(state):
    # 实现比例公平调度逻辑 [...]
    return np.random.rand(2 * NUM_USERS)


def greedy_scheduler(state):
    # 实现贪婪调度逻辑 [...]
    return np.random.rand(2 * NUM_USERS)


# 运行评估
ddpg_metrics = evaluate("DDPG", env)
pf_metrics = evaluate("PF", env)
greedy_metrics = evaluate("Greedy", env)

# 可视化对比
labels = ['Throughput (Mbps)', 'Jain Fairness Index', 'Energy Consumption (W)']
x = np.arange(len(labels))
width = 0.25

fig, ax = plt.subplots()
rects1 = ax.bar(x - width, ddpg_metrics, width, label='DDPG')
rects2 = ax.bar(x, pf_metrics, width, label='PF')
rects3 = ax.bar(x + width, greedy_metrics, width, label='Greedy')

ax.set_ylabel('Performance')
ax.set_title('Algorithm Comparison')
ax.set_xticks(x)
ax.set_xticklabels(labels)
ax.legend()

plt.savefig("performance_comparison.png")