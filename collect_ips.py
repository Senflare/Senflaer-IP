import requests
from bs4 import BeautifulSoup
import re
import os

# -------------------------- 1. 配置参数 --------------------------
# 目标URL列表（收集IP的来源）
IP_SOURCE_URLS = ['https://ip.164746.xyz']
# 可用性测试：尝试连接IP的443端口（HTTPS），超时时间2秒（避免卡慢）
TEST_PORT = 443
TEST_TIMEOUT = 2
# 输出文件
RAW_IP_FILE = 'ip.txt'       # 去重后的原始IP
AVAILABLE_IP_FILE = 'senflare.txt'  # 可用IP

# -------------------------- 2. 收集并去重IP --------------------------
# 正则匹配IP（排除0.0.0.0、255.255.255.255等无效IP）
ip_pattern = r'\b(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-5])\.(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-5])\.(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-5])\.(?:[1-9]\d?|1\d\d|2[0-4]\d|25[0-5])\b'
unique_ips = set()

print("正在从各个URL收集IP地址...")
for url in IP_SOURCE_URLS:
    try:
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            ip_matches = re.findall(ip_pattern, response.text)
            unique_ips.update(ip_matches)
            print(f"从 {url} 获取到 {len(ip_matches)} 个IP地址")
    except Exception as e:
        print(f"请求 {url} 失败: {str(e)}")

# 保存去重后的原始IP到ip.txt
if unique_ips:
    sorted_ips = sorted(unique_ips, key=lambda ip: [int(part) for part in ip.split('.')])
    with open(RAW_IP_FILE, 'w') as f:
        f.write('\n'.join(sorted_ips))
    print(f"已保存 {len(sorted_ips)} 个唯一IP地址到 {RAW_IP_FILE}。")
else:
    print("未找到有效的IP地址，退出流程。")
    exit(0)

# -------------------------- 3. 可用性测试（替换为TCP 443端口检测） --------------------------
# 核心逻辑：尝试用HTTPS连接IP的443端口，能建立连接则视为“可用”
available_ips = []
print("\n正在进行TCP 443端口测试（替代Ping），筛选可用IP...")

for ip in sorted_ips:
    try:
        # 尝试连接IP的443端口（添加https://避免requests报错，忽略证书验证）
        test_url = f"https://{ip}:{TEST_PORT}"
        # 关键参数：超时2秒，不验证SSL证书（CDN节点证书可能与IP不匹配）
        response = requests.get(test_url, timeout=TEST_TIMEOUT, verify=False)
        # 只要不抛异常（状态码200/403/502等都算“可连接”）
        available_ips.append(ip)
        print(f"IP {ip} 可访问（状态码：{response.status_code}）")
    except Exception as e:
        # 捕获超时、连接拒绝等异常，视为“不可访问”
        print(f"IP {ip} 不可访问（原因：{str(e)[:30]}...）")

# -------------------------- 4. 保存可用IP到senflare.txt --------------------------
with open(AVAILABLE_IP_FILE, 'w') as f:
    f.write('\n'.join(available_ips))
print(f"\n已保存 {len(available_ips)} 个可访问的IP地址到 {AVAILABLE_IP_FILE}。")
