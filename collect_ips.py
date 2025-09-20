import requests
import re
import os
import time
import socket
from urllib3.exceptions import InsecureRequestWarning

# 禁用SSL证书警告
requests.packages.urllib3.disable_warnings(category=InsecuresecureRequestWarning)

# 配置参数
IP_SOURCE_URLS = ['https://ip.164746.xyz']
TEST_PORT = 443  # 检测443端口连通性
TEST_TIMEOUT = 5  # 超时时间(秒)
TEST_RETRIES = 1  # 重试1次（应对临时网络波动）

def get_ip_region(ip):
    """获取IP地区代号（双API备份）"""
    apis = [
        f'http://ip-api.com/json/{ip}?fields=countryCode',
        f'https://ipinfo.io/{ip}/country'
    ]
    for api in apis:
        for _ in range(2):  # 每个API重试2次
            try:
                resp = requests.get(api, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                if 'ip-api.com' in api and resp.json().get('status') == 'success':
                    return resp.json().get('countryCode', 'Unknown').upper()
                if 'ipinfo.io' in api and resp.status_code == 200:
                    return resp.text.strip().upper()
            except:
                time.sleep(0.5)
    return 'Unknown'

def test_ip_availability(ip):
    """检测IP是否可连接（TCP握手），返回：(是否可用, 延迟ms)"""
    for _ in range(TEST_RETRIES + 1):  # 包含重试
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(TEST_TIMEOUT)
                start_time = time.time()
                # 尝试建立TCP连接
                result = s.connect_ex((ip, TEST_PORT))
                delay_ms = round((time.time() - start_time) * 1000)
                if result == 0:  # 0表示连接成功
                    return (True, delay_ms)
        except:
            pass
        time.sleep(0.5)  # 重试间隔
    return (False, 0)

# 1. 收集并去重IP
unique_ips = set()
print("收集IP地址中...")
for url in IP_SOURCE_URLS:
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', resp.text)
            unique_ips.update(ips)
            print(f"从 {url} 收集到 {len(ips)} 个IP")
    except Exception as e:
        print(f"收集IP失败: {str(e)}")

# 2. 保存原始IP（去重排序后）
sorted_ips = sorted(unique_ips, key=lambda x: [int(p) for p in x.split('.')])
with open('ip.txt', 'w') as f:
    f.write('\n'.join(sorted_ips))
print(f"共收集 {len(sorted_ips)} 个唯一IP\n")

# 3. 检测可用性，保留可用IP
available_ips = []
print("检测IP可用性（仅保留可连接的）...")
for ip in sorted_ips:
    region = get_ip_region(ip)
    is_available, delay = test_ip_availability(ip)
    
    if is_available:
        entry = f"{ip}#{region}-{delay}ms"
        available_ips.append(entry)
        print(f"✅ {entry}（可用）")
    else:
        print(f"❌ {ip}（不可用，已剔除）")

# 4. 保存结果
with open('senflare.txt', 'w') as f:
    f.write('\n'.join(available_ips))
print(f"\n已保存 {len(available_ips)} 个可用IP到 senflare.txt")
