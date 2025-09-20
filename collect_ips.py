import requests
import re
import os
import time
import socket
from urllib3.exceptions import InsecureRequestWarning

# 禁用SSL证书警告
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# 配置参数（关键优化：延长超时、增加重试）
IP_SOURCE_URLS = ['https://ip.164746.xyz']
TEST_PORT = 443
TEST_TIMEOUT = 5  # 延长超时到5秒（关键优化）
TEST_RETRIES = 2  # 增加重试次数到2次（关键优化）

def get_ip_region(ip):
    """获取IP地区代号"""
    apis = [
        f'http://ip-api.com/json/{ip}?fields=countryCode',
        f'https://ipinfo.io/{ip}/country'
    ]
    
    for api in apis:
        for _ in range(2):
            try:
                headers = {'User-Agent': 'Mozilla/5.0'}
                resp = requests.get(api, headers=headers, timeout=5)
                if 'ip-api.com' in api:
                    data = resp.json()
                    if data.get('status') == 'success':
                        return data.get('countryCode', 'Unknown').upper()
                else:
                    if resp.status_code == 200:
                        return resp.text.strip().upper()
            except:
                time.sleep(0.5)
                continue
    return 'Unknown'

def test_ip_advanced(ip):
    """高级检测：先尝试TCP握手，再尝试HTTP请求（更接近itdog的检测方式）"""
    # 1. 先尝试底层TCP连接（最基础的连通性检测）
    for _ in range(TEST_RETRIES + 1):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(TEST_TIMEOUT)
                start_time = time.time()
                result = s.connect_ex((ip, TEST_PORT))
                if result == 0:  # TCP连接成功
                    tcp_delay = round((time.time() - start_time) * 1000)
                    # 2. 再尝试HTTP请求（确认应用层可用）
                    try:
                        requests.get(
                            f'https://{ip}:{TEST_PORT}',
                            timeout=TEST_TIMEOUT,
                            verify=False,
                            headers={'User-Agent': 'Mozilla/5.0'},
                            allow_redirects=False
                        )
                        return tcp_delay  # 两层检测都通过
                    except:
                        # HTTP失败但TCP成功，仍视为可用（部分CDN节点限制直接IP访问）
                        return tcp_delay
        except Exception as e:
            time.sleep(1)  # 重试间隔延长
            continue
    return None

# 收集IP
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
        print(f"获取IP失败: {str(e)}")

# 保存原始IP
sorted_ips = sorted(unique_ips, key=lambda x: [int(p) for p in x.split('.')])
with open('ip.txt', 'w') as f:
    f.write('\n'.join(sorted_ips))
print(f"共收集 {len(sorted_ips)} 个唯一IP")

# 测试并生成结果
available = []
print("\n开始测试IP可用性（包含TCP握手检测）...")
for ip in sorted_ips:
    region = get_ip_region(ip)
    delay = test_ip_advanced(ip)
    
    if delay is not None:
        entry = f"{ip}#{region}-{delay}ms"
        available.append(entry)
        print(f"✅ {entry}（检测通过）")
    else:
        print(f"❌ {ip} 不可用（多次重试后仍失败）")

# 保存可用IP
with open('senflare.txt', 'w') as f:
    f.write('\n'.join(available))
print(f"\n已保存 {len(available)} 个可用IP到 senflare.txt")
