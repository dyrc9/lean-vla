# Frozen π0.5 Semantic-Subtask Pilot

## 1. 范围

2026-07-24 在 host GPU 1（RTX 6000 Ada）上加载当前冻结 checkpoint：

```text
/data0/ldx/libero_safety_models/pi05_libero_safety
config = pi05_libero
```

没有训练、没有修改权重、没有执行新动作，也没有读取 reward、success、collision 或 cost。输入来自已有
clean policy records；候选使用 PaliGemma tied language head 的长度归一化条件 log-probability 排序。

该 pilot 只为 L1 选择内部实现粒度，不改变论文的双层主线，也不评估 L1/L2 防御 efficacy。它分别探测
“冻结 selector 能否提出 skill-level `Z_t`”和“`Z_t` prompt 是否影响 action head”，不能由任一小样本
结果推出完整 Intent→ActionBlock alignment。

可复现入口：

- `scripts/probe_pi05_semantic_subtasks.py`
- `scripts/probe_pi05_subtask_action_conditioning.py`
- `experiments/pi05_semantic_subtask_probe_v0.json`
- `experiments/pi05_semantic_subtask_probe_v1.json`
- `experiments/pi05_semantic_subtask_probe_v2.json`

## 2. 粒度对照

### Motion-level 候选

四个干净初始场景均应处于 `approach the black bowl`。候选包括 approach/grasp/lift/transport/place/release。

结果：

```text
top-1 expected = 0 / 4
四个场景 top-1 均为 place the black bowl on the plate
```

说明当前 frozen language head 不适合直接承担 RT-H 风格的 motion-level selector。

### π0.5 skill-level 候选

把同一批初始场景改为 π0.5 风格：

```text
pick up the black bowl
move the black bowl to the plate
put the black bowl on the plate
release the black bowl
finish the task
```

结果：

```text
top-1 expected = 4 / 4
top-1 margin = 0.40 -- 1.06 mean log-probability
```

这支持把 `Z_t` 定义为技能级 subtask，把 approach/align/grasp/lift 留给解析式 local motion checker。
但样本只有四个、对象和任务模板相同，不能解释为 100% 泛化准确率。

## 3. 阶段切换

在一条 `black bowl on stove -> plate` clean trajectory 上，选取当前观察明确的五个帧：

```text
manual expected: pick_up, pick_up, move, move, place
model top-1:      pick_up, move,    move, move, move
```

名义 top-1 是 `3/5`。两个 disagreement 都接近阶段边界：

- step 9 已闭合夹爪，模型提前切到 move；
- step 21 仍闭合且尚未释放，模型继续判为 move，place 排第二。

因此这组数据证明了分数会随 observation/state 改变，而不是只复述固定 task；但人工 boundary label 不足以
给出可靠 accuracy。下一轮需要使用接触、抓持和 target-region predicate 生成预注册阶段标签。

运行时间：

- checkpoint load：约 7--8 s；
- 第一次 JIT/score：约 10 s；
- 同一进程后续每帧：约 0.18--0.27 s。

## 4. `Z_t` 对 action head 的影响

固定同一 observation 和 `10 x 32` flow noise，比较不同 prompt 得到的 `10 x 7` ActionBlock。

### 初始帧

`pick up bowl` 与 `put bowl on plate` 的 subtask-only prompt：

```text
mean absolute action delta = 0.000149
motion cosine similarity = 0.999665
```

### 已抓持的搬运帧

`move bowl to plate` 与冲突的 `release bowl`：

```text
mean absolute action delta = 0.000311
motion cosine similarity = 0.999177
```

即使输入 `release the black bowl`，action chunk 的 gripper command 仍约为 `+1`（保持闭合）。这可以有两种
解释：

1. flow head 根据场景前提拒绝了不合时宜的 release；
2. 当前 action-only fine-tune 并未学会把新加的 semantic prompt 当成强控制变量。

当前证据不能区分二者，所以只可声称 prompt path 有非零敏感性，不能声称 `Z_t` 已可靠、因果地控制
ActionBlock。追加 `Current semantic subtask:` 到原任务后的影响更弱。

## 5. 当前决策

零训练方案继续，但收紧 claim：

1. `Z_t` 使用 π0.5 风格的 skill-level task graph；
2. frozen PaliGemma 只提供候选 proposal/ranking，不单独授权；
3. task graph/FSM 决定合法 frontier；
4. 解析式 motion/geometry checker 判断 `Z_t -> A_t`；
5. 在 open-loop qualification 通过前，不把 `Z_t` prompt conditioning 当作安全机制；
6. 不进入 LoRA 或其他训练，除非零训练 selector/FSM 的覆盖率明确不足并另行授权。

最有价值的下一步是扩展不同 task/object/stage 的 predicate-labeled snapshot set，并加入 image/state ablation，
而不是立即跑大规模 closed-loop outcome。
