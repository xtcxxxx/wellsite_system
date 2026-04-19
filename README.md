# 井场物资调度管理系统

基于 Python + SQLite + PySide6 的桌面物资调度系统，支持：

- 仓库管理
- 物料管理
- 调度记录管理
- Excel 导出
- 拓扑可视化

## 启动步骤

1. 安装依赖:

```bash
pip install -r requirements.txt
```

2. 运行应用:

```bash
python main.py
```

## 功能说明

- 左侧面板支持创建仓库、添加物料、
- 右侧拓扑图展示仓库节点及仓库间调度连线
- 下方表格展示调度历史记录，可按时间过滤
- 导出按钮将调度记录导出到 Excel 文件
