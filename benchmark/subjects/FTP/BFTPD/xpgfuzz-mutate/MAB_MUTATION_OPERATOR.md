# 多臂老虎机变异算子选择算法

## 概述

本项目实现了一个基于UCB1（Upper Confidence Bound）算法的多臂老虎机（Multi-Armed Bandit, MAB）系统，用于智能选择约束变异算子。该算法能够根据历史表现动态调整变异算子的选择概率，优先选择那些更容易发现新代码覆盖的算子。

## 算法原理

### UCB1算法

UCB1算法平衡了**探索（Exploration）**和**利用（Exploitation）**：

- **利用**：优先选择平均奖励高的算子（已知表现好的）
- **探索**：给未充分尝试的算子机会（可能发现更好的）

UCB1公式：
```
UCB(i) = avg_reward_i + sqrt(2 * ln(total_pulls) / pulls_i)
```

其中：
- `avg_reward_i`: 算子i的平均奖励
- `total_pulls`: 所有算子的总选择次数
- `pulls_i`: 算子i被选择的次数

算法选择UCB值最大的算子。

## 实现细节

### 数据结构

```c
typedef struct {
    u32 pulls;          // 该算子被选择的次数
    u32 rewards;        // 总奖励（发现新覆盖的次数）
    double avg_reward;  // 平均奖励
    double ucb_value;   // UCB1上置信界值
} mab_arm_t;

typedef struct {
    mab_arm_t *arms;    // 算子数组
    u32 num_arms;       // 算子数量
    u32 total_pulls;    // 总选择次数
} multi_armed_bandit_t;
```

### 支持的约束类型

1. **CONSTRAINT_INTEGER**: 15个变异算子
   - 小幅度变化、边界值、随机值、溢出测试等

2. **CONSTRAINT_STRING**: 10个变异算子
   - 字符替换、长度变化、特殊字符注入、UTF-8测试等

3. **CONSTRAINT_ENUM**: 5个变异算子
   - 随机选择、首尾值、大小写变化、拼写错误等

## 使用方法

### 基本使用

变异函数会自动使用多臂老虎机选择算子：

```c
// 变异操作会自动使用MAB选择算子
mutate_value_by_constraint(buf, len, constraint, offset);
```

### 反馈更新

在检测到新覆盖后，调用反馈更新函数：

```c
// 在AFL的fuzz_one函数中，检测到新覆盖后：
if (has_new_bits(virgin_bits) > new_bits) {
    // 发现新覆盖，给予奖励
    mab_update_last_mutation_reward(1);
} else {
    // 未发现新覆盖
    mab_update_last_mutation_reward(0);
}
```

### 集成到AFL

在 `afl-fuzz.c` 的 `fuzz_one` 函数中，找到变异和覆盖检测的代码位置：

```c
// 执行变异（自动使用MAB选择算子）
mutate_value_by_constraint(buf, len, constraint, offset);

// 运行测试用例并检查覆盖
u8 hnb = has_new_bits(virgin_bits);
if (hnb > new_bits) {
    // 发现新覆盖，给予奖励
    mab_update_last_mutation_reward(1);
    // ... 保存测试用例等操作
} else {
    // 未发现新覆盖
    mab_update_last_mutation_reward(0);
}
```

### 完整示例

```c
// 在AFL的fuzz_one函数中
static u8 *fuzz_one(char **argv) {
    // ... 准备测试用例 ...
    
    // 对约束字段进行变异
    for (int i = 0; i < range_count; i++) {
        if (ranges[i].constraint && ranges[i].mutable) {
            // 变异操作（内部使用MAB选择算子）
            mutate_value_by_constraint(
                out_buf, 
                len, 
                ranges[i].constraint, 
                ranges[i].start
            );
        }
    }
    
    // 执行测试用例
    u8 fault = run_target(argv, exec_tmout);
    
    // 检查是否发现新覆盖
    u8 hnb = has_new_bits(virgin_bits);
    if (hnb > new_bits) {
        // 发现新覆盖，更新MAB奖励
        mab_update_last_mutation_reward(1);
        // ... 保存有趣的测试用例 ...
    } else {
        // 未发现新覆盖
        mab_update_last_mutation_reward(0);
    }
    
    return out_buf;
}
```

## 算法优势

1. **自适应学习**：根据实际效果动态调整选择策略
2. **平衡探索与利用**：既利用已知好的算子，也探索新的可能性
3. **无需手动调参**：算法自动优化，无需人工干预
4. **简单高效**：UCB1算法计算开销小，适合实时使用

## 性能考虑

- 初始化开销：首次使用时创建MAB实例（O(n)，n为算子数量）
- 选择开销：O(n)，需要遍历所有算子计算UCB值
- 更新开销：O(1)，只需更新单个算子的统计信息

对于15个算子的情况，选择操作的开销可以忽略不计。

## 未来改进方向

1. **上下文感知**：根据协议状态或字段类型使用不同的MAB实例
2. **滑动窗口**：使用时间窗口内的奖励，适应动态变化
3. **Thompson Sampling**：尝试其他MAB算法，如Thompson Sampling
4. **多目标优化**：同时考虑覆盖率、执行时间等多个目标

## 参考文献

- Auer, P., Cesa-Bianchi, N., & Fischer, P. (2002). Finite-time analysis of the multiarmed bandit problem. Machine learning, 47(2-3), 235-256.

