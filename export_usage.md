# 知乎爬虫数据导出工具使用说明

## 概述

`export_to_excel.py` 是一个功能完整的数据导出工具，可以将PostgreSQL数据库中的知乎爬虫数据导出为Excel格式文件。

## 功能特性

- ✅ 支持多种导出模式
- ✅ 自动处理数据格式化（时间、JSON、长文本等）
- ✅ 自动调整Excel列宽
- ✅ 支持按任务筛选导出
- ✅ 提供详细的日志记录
- ✅ 生成统计信息

## 安装依赖

```bash
pip3 install pandas openpyxl
```

## 使用方法

### 1. 查看数据库统计信息

```bash
python3 export_to_excel.py --mode summary
```

显示各表的记录数量和任务列表。

### 2. 导出所有数据到一个Excel文件（推荐）

```bash
# 使用默认文件名
python3 export_to_excel.py --mode combined

# 指定文件名
python3 export_to_excel.py --mode combined --output "我的数据导出.xlsx"
```

将所有表的数据导出到一个Excel文件的不同工作表中：
- 任务信息
- 搜索结果
- 问题数据
- 答案数据

### 3. 导出所有数据为单独文件

```bash
python3 export_to_excel.py --mode all
```

为每个表生成单独的Excel文件。

### 4. 导出指定表

```bash
# 导出答案表
python3 export_to_excel.py --mode table --table answers

# 导出问题表
python3 export_to_excel.py --mode table --table questions

# 导出搜索结果表
python3 export_to_excel.py --mode table --table search_results

# 导出任务信息表
python3 export_to_excel.py --mode table --table task_info
```

### 5. 按任务导出数据

```bash
# 按任务ID导出
python3 export_to_excel.py --mode task --task-id "e7294913-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

# 按关键词导出
python3 export_to_excel.py --mode task --keywords "Python编程"
python3 export_to_excel.py --mode task --keywords "海归"
```

按任务导出会包含该任务相关的所有数据（任务信息、搜索结果、问题、答案）。

## 导出文件说明

### 文件位置
所有导出的文件都保存在 `exports/` 目录下。

### 文件命名规则
- 合并导出：`zhihu_data_combined_YYYYMMDD_HHMMSS.xlsx`
- 单表导出：`表名_YYYYMMDD_HHMMSS.xlsx`
- 任务导出：`zhihu_task_标识符_YYYYMMDD_HHMMSS.xlsx`

### 数据处理说明

1. **时间字段**：自动转换为标准日期时间格式
2. **JSON字段**：如tags字段会转换为逗号分隔的字符串
3. **布尔字段**：转换为中文（是/否）
4. **长文本字段**：超过500字符的内容会被截断并添加"..."
5. **列宽调整**：自动调整列宽，最大不超过50个字符宽度

## 工作表说明

### 任务信息表 (task_info)
- 任务ID、关键词、创建时间等基本信息

### 搜索结果表 (search_results)
- 搜索关键词返回的问题列表
- 包含问题ID、标题、预览内容等

### 问题表 (questions)
- 问题的详细信息
- 包含标题、内容、作者、标签、统计数据等

### 答案表 (answers)
- 问题的回答内容
- 包含答案内容、作者、点赞数、评论数等

## 示例输出

```
=== 数据库统计信息 ===
任务信息表: 9 条记录
搜索结果表: 824 条记录
问题表: 316 条记录
答案表: 815 条记录

=== 任务列表 ===
ID: e7294913... | 关键词: Python编程 | 创建时间: 2025-08-21 17:07:28
ID: 4b56850b... | 关键词: 博士 回国 | 创建时间: 2025-08-21 16:33:59
...

✓ 合并导出完成: exports/zhihu_data_combined_20250822_061246.xlsx
```

## 日志文件

导出过程的详细日志保存在 `logs/export.log` 文件中，包含：
- 导出进度信息
- 错误信息
- 数据统计

## 常见问题

### Q: 导出文件很大怎么办？
A: 可以使用按任务导出功能，分批导出数据。

### Q: 如何查看特定时间段的数据？
A: 可以先查看任务列表，然后按任务ID导出对应时间段的数据。

### Q: Excel文件打不开？
A: 确保安装了Microsoft Excel或WPS等支持.xlsx格式的软件。

### Q: 数据格式不对？
A: 脚本会自动处理常见的数据格式，如果有特殊需求可以修改 `_process_dataframe` 方法。

## 技术说明

- 使用 pandas 进行数据处理
- 使用 openpyxl 引擎生成Excel文件
- 支持中文文件名和内容
- 自动处理数据库连接和异常

## 更新日志

- v1.0: 初始版本，支持基本导出功能
- 支持多种导出模式
- 自动数据格式化
- 完整的错误处理和日志记录