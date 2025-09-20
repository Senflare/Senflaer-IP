# Senflare-IP

> 自动收集、验证Cloudflare IP并按地区格式化的工具

## 项目介绍

Senflare-IP 是一个用于**自动收集IPv4地址、验证其可用性、识别国家/地区信息**，并最终按自定义格式输出的工具。它能够帮助你筛选出可用的IP资源，并按地区分组编号，便于管理和使用（例如用于Cloudflare节点筛选等场景）。


## 功能特点

- **多源IP收集**：从多个可靠来源自动提取IPv4地址
- **智能去重验证**：自动去重，并通过**TCP握手+HTTP请求双层验证**确保IP可用性
- **精准地区识别**：获取IP的国家/地区代号，并映射为中文名称（如`US`→`美国`）
- **自定义格式输出**：按 `IP#代号 中文名称节点 | 序号` 格式分组（同一地区内按延迟排序，单独编号）
- **定时自动执行**：通过GitHub Actions配置，每3小时自动执行一次（可自定义频率）
- **结果持久化**：生成`IPlist.txt`（纯可用IP列表）和`Senflare.txt`（格式化结果）


## 使用方法

### 手动运行（本地执行）

1. 确保安装 **Python 3.9+**
2. 安装依赖库：
   ```bash
   pip install requests urllib3
   ```
3. 执行核心脚本：
   ```bash
   python ip_collector.py
   ```


### 自动运行（GitHub Actions）

项目已配置自动工作流，可实现**每3小时自动执行一次**，步骤如下：

1. 将本仓库推送到你的GitHub账号
2. 工作流会自动触发，执行“IP收集→验证→格式化→提交结果”全流程
3. 生成的`IPlist.txt`和`Senflare.txt`会自动提交到仓库，随时可查看最新结果


## 工作原理

1. **IP收集**：从配置的多个来源URL中提取IPv4地址
2. **去重处理**：通过集合（Set）结构自动去除重复IP
3. **可用性检测**：先尝试TCP连接目标端口（默认443），再发起HTTP请求验证服务可用性
4. **地区识别**：调用`ip-api.com`、`ipinfo.io`等多API备份获取IP所属国家/地区代号，再映射为中文名称
5. **格式化输出**：按地区分组，同一地区内按延迟排序，单独编号后输出到`Senflare.txt`


## 配置说明

### 核心配置（`ip_collector.py`）

可修改`CONFIG`字典调整核心行为：

```python
CONFIG = {
    "ip_sources": [
        'https://ip.164746.xyz',  
        'https://cf.hyli.xyz/',
        'https://api.uouin.com/cloudflare.html',
        # 可添加/替换为新的IP来源URL
    ],  
    "test_port": 443,    # 检测端口（默认Cloudflare HTTPS端口）
    "timeout": 5,        # 网络超时时间（秒）
    "retries": 2         # 每个IP的重试次数（含首次）
}
```

### 定时配置（`.github/workflows/ip-collection.yml`）

可修改`cron`表达式调整自动执行频率：

```yaml
on:
  schedule:
    - cron: '0 */3 * * *'  # 每3小时整点执行，格式：分 时 日 月 周
    # 示例：'0 0 * * *' 表示每天0点执行
```


## 文件说明

- `ip_collector.py`：核心脚本，实现IP收集、验证、地区识别和格式化逻辑
- `IPlist.txt`：仅包含**可用IP地址**的纯文本列表
- `Senflare.txt`：按`IP#代号 中文名称节点 | 序号`格式生成的最终结果（如`1.1.1.1#US 美国节点 | 01`）
- `.github/workflows/ip-collection.yml`：GitHub Actions工作流配置，定义自动执行规则


## 注意事项

1. 若某IP来源URL失效，可在`CONFIG["ip_sources"]`中替换为新的可靠来源
2. 地区识别依赖第三方API，若出现大量“未知”，可检查网络连通性或稍后重试
3. 自动提交功能需GitHub仓库授予写入权限，若提交失败请检查仓库权限设置
4. 若需调整检测严格度，可修改`test_ip_availability`函数的验证逻辑（如增减HTTP状态码判断）


通过以上配置和说明，你可以快速上手并根据需求定制这个IP收集工具。
