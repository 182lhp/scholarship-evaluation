# 🎓 Scholarship Evaluation

高校综合奖学金自动化评定系统 —— 从成绩 Excel 一键生成排名、等级分配与获奖名单。

## 功能概览

| 步骤 | 说明 |
|------|------|
| 1. 数据清理 | 删除成绩作废记录 |
| 2. 无资格识别 | 低分 / 旷考 / 取消考试资格 / 缓考超限 |
| 3. 合并成绩 | 正考 + 缓考合并，剔除网络平台课程 |
| 4. 筛选参评 | 按年级过滤，剔除留学生，应用课程白名单 |
| 5. 按专业拆分 | 输出各专业成绩数据 Excel |
| 6. 绩点计算 | 学分加权裸绩点 |
| 7. 裸绩排名 | 按专业分配特等/一等/二等/三等/单项名额 |
| 8. 综合排名 | 加载加分表 → 综合绩点 → 综合等级（含升降档约束） |
| 预算验证 | 统计各等级人数 × 金额，与总预算对比 |
| 附件5 | 输出获奖名单 Excel（按学校模板格式） |

## 项目结构

```
scholarship-evaluation/
├── environment.yaml          # Conda 环境定义
├── data/
│   ├── input/                # ⚠️ 原始数据（含学生隐私，不提交）
│   └── output/               # 输出结果（不提交）
├── docs/                     # 参考文档 / 模板
└── src/
    ├── run.py                # 入口脚本
    ├── config.py             # 所有可调常量
    ├── pipeline.py           # 流水线协调层
    ├── processing/           # 纯数据处理
    │   ├── cleaning.py       #   清洗 / 无资格 / 合并
    │   ├── filtering.py      #   年级过滤 / 白名单
    │   ├── gpa.py            #   绩点计算
    │   ├── ranking.py        #   等级分配 / 综合排名
    │   └── bonus.py          #   加分表加载
    ├── reporting/            # 报告生成
    │   ├── budget.py         #   预算验证
    │   ├── major_report.py   #   各专业汇总
    │   └── award_list.py     #   附件5 获奖名单 Excel
    └── utils/                # 公共工具
        ├── md.py             #   Markdown 打印
        └── excel.py          #   Excel 染色 / 保存
```

## 快速开始

### 1. 创建环境

```bash
conda env create -f environment.yaml
conda activate scholarship
```

### 2. 准备数据

将以下文件放入 `data/input/`：

| 文件 | 说明 |
|------|------|
| `XX级裸绩点正考.xlsx` | 正考成绩表（必须） |
| `XX级裸绩点缓考.xlsx` | 缓考成绩表（必须） |
| `综合加分绩点.xlsx` | 加分简表（可选） |
| `综合奖学金加分表单.xlsx` | 加分表单（可选） |

> 正考/缓考文件需包含列：`成绩, 学号, 姓名, 专业, 学院, 课程名称, 学分, 学分绩点, 年级, 学期` 等。

### 3. 配置参数

编辑 `src/config.py`，主要关注：

- `SEMESTER_LABEL` — 学期标识（影响输出文件名前缀）
- `LEVELS` / `RATIOS` — 奖学金等级及比例
- `MAJOR_COURSE_WHITELIST` — 各专业计分课程白名单
- `BUDGET_STUDENT_COUNT` / `BUDGET_PER_STUDENT` — 预算参数
- `AWARD_AMOUNTS` — 各等级奖学金金额

### 4. 运行

```bash
cd src
python run.py
```

输出：

- `data/output/排名/` — 各专业排名 Excel（自动染色）
- `data/output/成绩数据/` — 各专业成绩数据
- `data/output/logs/` — Markdown 运行日志
- `data/output/附件5：….xlsx` — 获奖名单
- `data/output/无资格名单.xlsx` — 无资格学生名单

## 等级分配规则

- **名额**：按专业人数 × 比例，进一法（`math.ceil`）取整
- **特等**：前 N 名中全科 ≥ 85 分者
- **综合等级**：在裸绩等级基础上，最多升一档（不可升至特等），后 50% 上限为单项
- **预算**：特等单独核算，不占总预算池

## 数据安全

`data/input/` 和 `data/output/` 已加入 `.gitignore`，**不会被提交到仓库**。请确保不要手动添加含学生个人信息的文件。

## License

MIT
