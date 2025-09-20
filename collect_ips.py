import requests
import re
import os
import time
from urllib3.exceptions import InsecureRequestWarning

# 禁用SSL证书警告（因直接访问IP会触发证书不匹配）
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# -------------------------- 1. 核心配置 --------------------------
IP_SOURCE_URLS = ['https://ip.164746.xyz']  # IP来源URL
TEST_PORT = 443  # 测试端口（Cloudflare核心服务端口）
TEST_TIMEOUT = 3  # 延长超时到3秒（解决“响应慢被误判不通”）
TEST_RETRIES = 1  # 重试1次（提升检测准确性）
RAW_IP_FILE = 'ip.txt'
AVAILABLE_IP_FILE = 'senflare.txt'

# -------------------------- 2. 工具函数 --------------------------
def get_ip_region(ip):
    """获取IP地区代号（双API备份+重试，确保稳定性）"""
    region = 'Unknown'
    # 备选API列表（优先用国内可访问的，避免GitHub网络限制）
    apis = [
        # API1: ip-api.com（返回国家代码，如CN/US）
        f'http://ip-api.com/json/{ip}?fields=countryCode&lang=en',
        # API2: ipinfo.io（备用，返回国家代码）
        f'https://ipinfo.io/{ip}/country'
    ]
    
    for api in apis:
        for _ in range(2):  # 每个API重试2次
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
                if 'ip-api.com' in api:
                    resp = requests.get(api, headers=headers, timeout=5)
                    if resp.status_code == 200 and resp.json().get('status') == 'success':
                        region = resp.json().get('countryCode', 'Unknown').upper()
                        return region
                else:  # ipinfo.io
                    resp = requests.get(api, headers=headers, timeout=5)
                    if resp.status_code == 200:
                        region = resp.text.strip().upper()
                        return region
            except Exception as e:
                time.sleep(0.5)  # 重试前短暂延迟
                continue
    return region

def test_ip_availability(ip):
    """测试IP可用性（TCP 443连接），返回：(是否可用, 延时ms)"""
    for _ in range(TEST_RETRIES + 1):  # 包含重试
        start_time = time.time()
        try:
            # 尝试连接IP的443端口（忽略证书验证，Cloudflare IP证书不匹配正常）
            resp = requests.get(
                f'https://{ip}:{TEST_PORT}',
                timeout=TEST_TIMEOUT,
                verify=False,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            # 只要能建立连接（无论状态码200/403/502），都视为可用
            end_time = time.time()
            delay_ms = round((end_time - start_time) * 1000)  # 转换为ms
            return (True, delay_ms)
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            # 超时或连接拒绝，重试
            time.sleep(0.5)
            continue
        except Exception as e:
            # 其他异常（如SSL错误），视为不可用
            return (False, 0)
    return (False, 0)

# -------------------------- 3. 收集并去重IP --------------------------
ip_pattern = r'\b(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-5])\.(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-5])\.(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-5])\.(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-5])\b'
unique_ips = set()

print("=== 步骤1：收集IP地址 ===")
for url in IP_SOURCE_URLS:
    try:
        resp = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
        if resp.status_code == 200:
            ip_matches = re.findall(ip_pattern, resp.text)
            unique_ips.update(ip_matches)
            print(f"从 {url} 获取到 {len(ip_matches)} 个IP，去重后累计 {len(unique_ips)} 个")
    except Exception as e:
        print(f"请求 {url} 失败：{str(e)[:50]}")

# 保存原始IP（按数字排序）
if unique_ips:
    sorted_ips = sorted(unique_ips, key=lambda x: [int(part) for part in x.split('.')])
    with open(RAW_IP_FILE, 'w') as f:
        f.write('\n'.join(sorted_ips))
    print(f"\n已保存 {len(sorted_ips)} 个唯一IP到 {RAW_IP_FILE}")
else:
    print("未找到任何有效IP，退出流程")
    # 创建空文件避免后续步骤报错
    with open(RAW_IP_FILE, 'w') as f:
        pass
    with open(AVAILABLE_IP_FILE, 'w') as f:
        pass
    exit(0)

# -------------------------- 4. 测试可用性+收集地区/延时 --------------------------
print("\n=== 步骤2：测试IP可用性（TCP 443）+ 收集地区/延时 ===")
available_entries = []  # 存储格式：IP#地区-延时ms

for ip in sorted_ips:
    print(f"\n正在处理 IP: {ip}")
    # 1. 获取地区
    region = get_ip_region(ip)
    print(f"  - 地区代号：{region}")
    
    # 2. 测试可用性+延时
    is_available, delay_ms = test_ip_availability(ip)
    if is_available:
        entry = f"{ip}#{region}-{delay_ms}ms"
        available_entries.append(entry)
        print(f"  - 状态：可访问 | 延时：{delay_ms}ms | 格式：{entry}")
    else:
        print(f"  - 状态：不可访问（多次重试后仍失败）")

# -------------------------- 5. 保存结果 --------------------------
with open(AVAILABLE_IP_FILE, 'w') as f:
    f.write('\n'.join(available_entries))

print(f"\n=== 最终结果 ===")
print(f"原始IP总数：{len(sorted_ips)} 个")
print(f"可用IP总数：{len(available_entries)} 个")
print(f"可用IP已保存到 {AVAILABLE_IP_FILE}，格式：IP#地区-延时ms")
print(f"示例：{available_entries[0] if available_entries else '无可用IP'}")
