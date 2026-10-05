# Python Tool Chart 模块需求

## 1. 模块定位

`tool_chart` 负责把分析结果转换为前端可直接渲染的图表配置。

## 2. 当前代码现状

当前除兼容示例函数 `build_line_chart(title)` 外，还实现
`ChartSpecBuilderTool`：从 `QueryResult` 的 columns/rows 构建前端无关的 chart spec，
支持 `bar`、`line`、`pie`、`table` 类型、字段映射推断和 `max_points` 截断警告。
该工具不会直接生成 ECharts option，也不证明具体业务图表选择已通过评估。

## 3. 核心职责

1. 将查询结果转换为前端无关的图表描述。
2. 返回图表类型、标题、字段映射、数据、编码信息及截断警告。
3. 由前端或后续适配器负责转换为具体图表库配置。

## 4. MVP 功能需求

1. 支持折线图
2. 支持柱状图
3. 支持饼图
4. 支持空结果集降级处理
5. 支持对图表标题进行业务语义化命名

## 5. 输入输出要求

输入至少包括：

1. 问题文本
2. 查询结果
3. 推荐图表类型

输出至少包括：

1. `title`
2. `xAxis`
3. `yAxis`
4. `series`

## 6. 验收标准

1. 输出遵守 `ChartSpecBuilderTool` 的结构。
2. 行数超过 `max_points` 时有截断标记与警告。
3. 当前类型推断属于简单默认规则，不据此宣称图表与问题语义一致。
