import requests
import re
import os
import time
from urllib3.exceptions import InsecureRequestWarning

# 禁用SSL证书警告
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# 配置参数
IP_SOURCE_URLS = [
     'https://cf.hyli.xyz/',
     'https://ip.164746.xyz'
]
TEST_PORT = 443
TEST_TIMEOUT = 3  # 超时时间(秒)
TEST_RETRIES = 1  # 重试次数

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

def test_ip(ip):
    """测试IP可用性并返回延迟(ms)"""
    for _ in range(TEST_RETRIES + 1):
        start = time.time()
        try:
            requests.get(
                f'https://{ip}:{TEST_PORT}',
                timeout=TEST_TIMEOUT,
                verify=False,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            return round((time.time() - start) * 1000)
        except:
            time.sleep(0.5)
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
    except Exception as e:
        print(f"获取IP失败: {str(e)}")

# 保存原始IP
sorted_ips = sorted(unique_ips, key=lambda x: [int(p) for p in x.split('.')])
with open('ip.txt', 'w') as f:
    f.write('\n'.join(sorted_ips))
print(f"已收集 {len(sorted_ips)} 个唯一IP")

# 测试并生成结果
available = []
print("测试IP可用性中...")
for ip in sorted_ips:
    region = get_ip_region(ip)
    delay = test_ip(ip)
    if delay is not None:
        available.append(f"{ip}#{region}-{delay}ms")
        print(f"{ip} 可用 - {region} {delay}ms")
    else:
        print(f"{ip} 不可用")

# 保存可用IP
with open('senflare.txt', 'w') as f:
    f.write('\n'.join(available))
print(f"已保存 {len(available)} 个可用IP到 senflare.txt")
