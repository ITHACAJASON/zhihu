# 知乎人机验证手动处理指南

由于自动化验证脚本遇到了技术问题，请按照以下步骤手动完成验证：

## 步骤1：手动访问验证页面

1. 打开浏览器，访问以下验证URL：
   ```
   https://www.zhihu.com/account/unhuman?type=Q8J2L3&need_login=false&session=5ce0198591dfdc49c36534d1aa80cecb&next=%2Fquestion%2F1912780463006782640
   ```

2. 完成人机验证（点击验证按钮、拖动滑块等）

3. 验证成功后，确保能正常访问知乎页面

## 步骤2：获取新的cookies

### 方法1：使用浏览器开发者工具

1. 在验证完成后的知乎页面，按F12打开开发者工具
2. 切换到"Application"或"应用程序"标签
3. 在左侧找到"Cookies" -> "https://www.zhihu.com"
4. 复制所有cookies信息

### 方法2：使用简单的Python脚本

运行以下命令获取当前浏览器的cookies：

```bash
python3 -c "
import requests
import json

# 手动输入重要的cookies值
print('请从浏览器开发者工具中复制以下cookies的值：')
print('1. z_c0 (用户认证token)')
print('2. d_c0 (设备标识)')
print('3. _zap (会话标识)')

z_c0 = input('请输入z_c0的值: ')
d_c0 = input('请输入d_c0的值: ')
_zap = input('请输入_zap的值: ')

# 构建cookies
cookies = [
    {'name': 'z_c0', 'value': z_c0, 'domain': '.zhihu.com', 'path': '/', 'secure': True},
    {'name': 'd_c0', 'value': d_c0, 'domain': '.zhihu.com', 'path': '/', 'secure': True},
    {'name': '_zap', 'value': _zap, 'domain': '.zhihu.com', 'path': '/', 'secure': True}
]

# 保存cookies
import pickle
with open('cache/zhihu_cookies.pkl', 'wb') as f:
    pickle.dump(cookies, f)

with open('cookies/zhihu_cookies.json', 'w', encoding='utf-8') as f:
    json.dump(cookies, f, ensure_ascii=False, indent=2)

print('Cookies已保存到 cache/zhihu_cookies.pkl 和 cookies/zhihu_cookies.json')
"
```

## 步骤3：测试API

完成cookies更新后，运行以下命令测试API：

```bash
python3 postgres_main.py test-api
```

如果仍然出现403错误，可能需要：

1. 确保在同一个浏览器会话中完成验证
2. 检查cookies是否正确复制
3. 等待几分钟后重试

## 步骤4：开始正常爬取

验证成功后，可以运行正常的爬取命令：

```bash
python3 postgres_main.py batch-crawl --keywords "博士回国,海归就业" --no-batch-mode
```

## 注意事项

- 知乎的反爬机制会定期要求重新验证
- 建议在验证完成后尽快进行数据爬取
- 如果频繁遇到验证，可以适当降低爬取频率
- 保持cookies的安全性，不要泄露给他人