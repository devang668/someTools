#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
@author: 'Guohan'
@file: evaluate_comparison.py
@time: 27/5/2025 上午 9:10
@functions：please note ..
"""
# !/usr/bin/env python3

# !/usr/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import numpy as np
import torch
import matplotlib.pyplot as plt
from ddpg_agent import DDPGAgent
from wireless_env import WirelessCommEnv
from traditional import TraditionalScheduler


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='性能对比评估脚本')
    parser.add_argument('--model_path', type=str, default="ddpg_actor.pth",
                        help='训练好的RL模型路径')
    parser.add_argument('--episodes', type=int, default=100,
                        help='评估轮数')
    parser.add_argument('--max_steps', type=int, default=200,
                        help='每轮最大步数')
    parser.add_argument('--max_users', type=int, default=50,
                        help='最大用户数（需与训练一致）')
    parser.add_argument('--trad_mode', type=str, default='channel_aware',
                        choices=['round_robin', 'equal_power', 'channel_aware'],
                        help='传统算法模式')
    return parser.parse_args()


def run_evaluation(agent, env, args, is_rl=True):
    """执行评估流程"""
    metrics = {
        'throughput': [],
        'delay': [],
        'packet_loss': [],
        'energy_efficiency': [],
        'fairness': [],
        'power_usage': []
    }

    for ep in range(args.episodes):
        state = env.reset()
        current_users = env.current_num_users
        ep_metrics = {k: [] for k in metrics.keys()}

        for _ in range(args.max_steps):
            # 选择动作
            if is_rl:
                action = agent.select_action(state, noise_scale=0)
            else:
                action = agent.allocate(state)

            # 与环境交互
            next_state, reward, done, info = env.step(action)

            # 收集指标（确保转换为标量）
            ep_metrics['throughput'].append(float(np.sum(info['throughput'])))
            ep_metrics['delay'].append(float(np.mean(info['delay'])))
            ep_metrics['packet_loss'].append(float(np.mean(info['packet_loss'])))
            ep_metrics['power_usage'].append(float(np.mean(info['power'])))

            # 计算能效和公平性
            valid_users = current_users
            throughputs = np.array(info['throughput'][:valid_users])
            powers = np.array(info['power'][:valid_users])
            ee = np.sum(throughputs) / (np.sum(powers) + 1e-6)
            sum_throughput = np.sum(throughputs)
            fairness = (sum_throughput ** 2) / (valid_users * np.sum(throughputs ** 2)) if sum_throughput != 0 else 0

            ep_metrics['energy_efficiency'].append(float(ee))
            ep_metrics['fairness'].append(float(fairness))

            state = next_state

        # 记录统计量
        for k in metrics.keys():
            metrics[k].append(np.mean(ep_metrics[k]))

        print(f"Ep {ep + 1}/{args.episodes} {'(RL)' if is_rl else '(Trad)'} "
              f"| Users: {current_users} | Tput: {np.mean(ep_metrics['throughput']):.1f}Mbps")

    return metrics


def generate_report(rl_metrics, trad_metrics):
    """生成性能对比报告"""
    report = {}
    for metric in rl_metrics.keys():
        # 转换为NumPy数组
        rl_data = np.array(rl_metrics[metric])
        trad_data = np.array(trad_metrics[metric])

        report[metric] = {
            'rl': rl_data,
            'trad': trad_data,
            'improvement': (np.mean(rl_data) - np.mean(trad_data)) / np.mean(trad_data)
            if metric not in ['delay', 'packet_loss']
            else (np.mean(trad_data) - np.mean(rl_data)) / np.mean(trad_data)
        }
    return report


def plot_comparison(report, args):
    """可视化对比结果"""
    plt.figure(figsize=(14, 10))

    # 1. 吞吐量对比（修正箱线图）
    plt.subplot(2, 3, 1)
    plt.boxplot([
        report['throughput']['rl'].flatten(),
        report['throughput']['trad'].flatten()
    ], labels=['DDPG', 'Traditional'])
    plt.title("Throughput Comparison")
    plt.grid(True)

    # 2. 延迟对比（修正bins）
    plt.subplot(2, 3, 2)
    max_delay = max(report['delay']['rl'].max(), report['delay']['trad'].max())
    bins = np.linspace(0, max_delay * 1.2, 20)
    plt.hist(report['delay']['rl'], bins=bins, alpha=0.5, label='DDPG', density=True)
    plt.hist(report['delay']['trad'], bins=bins, alpha=0.5, label='Traditional', density=True)
    plt.title("Delay Distribution")
    plt.legend()

    # 3. 丢包率对比（散点图尺寸调整）
    plt.subplot(2, 3, 3)
    x = range(len(report['packet_loss']['rl']))
    plt.scatter(x, report['packet_loss']['rl'], s=5, label='DDPG')
    plt.scatter(x, report['packet_loss']['trad'], s=5, label='Traditional')
    plt.title("Packet Loss Rate")
    plt.legend()

    # 4. 能效对比（趋势图）
    plt.subplot(2, 3, 4)
    plt.plot(report['energy_efficiency']['rl'], 'g-', label='DDPG', linewidth=0.8)
    plt.plot(report['energy_efficiency']['trad'], 'r--', label='Traditional', linewidth=0.8)
    plt.title("Energy Efficiency Trend")
    plt.legend()

    # 5. 公平性对比（条形图）
    plt.subplot(2, 3, 5)
    fairness_rl = np.mean(report['fairness']['rl'])
    fairness_trad = np.mean(report['fairness']['trad'])
    plt.bar([0, 1], [fairness_rl, fairness_trad],
            tick_label=['DDPG', 'Traditional'], width=0.6)
    plt.ylim(0, 1.1)
    plt.title("Fairness Index")

    # 6. 功率使用对比（KDE图）
    plt.subplot(2, 3, 6)
    import seaborn as sns
    sns.kdeplot(report['power_usage']['rl'], label='DDPG', fill=True)
    sns.kdeplot(report['power_usage']['trad'], label='Traditional', fill=True)
    plt.title("Power Distribution")

    plt.tight_layout()
    plt.savefig('performance_comparison.png', dpi=300)
    plt.close()


def main(args):
    # 初始化环境
    env = WirelessCommEnv(max_users=args.max_users)

    # 加载RL智能体
    rl_agent = DDPGAgent(
        state_dim=4 * args.max_users,
        action_dim=2 * args.max_users
    )
    rl_agent.actor.load_state_dict(torch.load(args.model_path, map_location='cpu'))
    rl_agent.actor.eval()

    # 传统算法
    trad_agent = TraditionalScheduler(
        max_users=args.max_users,
        mode=args.trad_mode
    )

    # 评估流程
    print("\n=== 评估强化学习算法 ===")
    rl_metrics = run_evaluation(rl_agent, env, args, is_rl=True)

    print("\n=== 评估传统算法 ===")
    trad_metrics = run_evaluation(trad_agent, env, args, is_rl=False)

    # 生成报告
    report = generate_report(rl_metrics, trad_metrics)

    # 打印结果
    print("\n=== 最终性能对比 ===")
    for metric in report.keys():
        data = report[metric]
        print(f"{metric.upper():<18} RL: {np.mean(data['rl']):.3f} | Trad: {np.mean(data['trad']):.3f} "
              f"| 提升: {data['improvement'] * 100:+.1f}%")

    # 可视化
    plot_comparison(report, args)


if __name__ == "__main__":
    args = parse_args()
    main(args)