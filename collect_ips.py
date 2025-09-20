import requests
import re
import os
import subprocess
import platform
import time

# 目标URL列表
urls = [
    'https://ip.164746.xyz'
]

# 正则表达式用于匹配IP地址
ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'

# 检查并删除原有文件
for file in ['ip.txt', 'senflare.txt']:
    if os.path.exists(file):
        os.remove(file)

# 使用集合存储IP地址实现自动去重
unique_ips = set()

print("正在从各个URL收集IP地址...")
for url in urls:
    try:
        # 发送HTTP请求获取网页内容
        response = requests.get(url, timeout=5)
        
        # 确保请求成功
        if response.status_code == 200:
            # 获取网页的文本内容
            html_content = response.text
            
            # 使用正则表达式查找IP地址
            ip_matches = re.findall(ip_pattern, html_content, re.IGNORECASE)
            
            # 将找到的IP添加到集合中（自动去重）
            unique_ips.update(ip_matches)
            print(f'从 {url} 获取到 {len(ip_matches)} 个IP地址')
    except requests.exceptions.RequestException as e:
        print(f'请求 {url} 失败: {e}')
        continue

# 获取IP的地区信息（国家代码）
def get_ip_region(ip):
    try:
        # 使用ip-api.com获取IP信息，返回国家代码
        response = requests.get(f'http://ip-api.com/json/{ip}?fields=countryCode', timeout=5)
        data = response.json()
        if data['status'] == 'success':
            return data['countryCode']
        return 'Unknown'
    except Exception as e:
        print(f"查询IP {ip} 地区信息失败: {e}")
        return 'Unknown'

# 将去重后的IP地址按数字顺序排序后写入文件
if unique_ips:
    # 按IP地址的数字顺序排序（非字符串顺序）
    sorted_ips = sorted(unique_ips, key=lambda ip: [int(part) for part in ip.split('.')])
    
    with open('ip.txt', 'w') as file:
        for ip in sorted_ips:
            file.write(ip + '\n')
    print(f'已保存 {len(sorted_ips)} 个唯一IP地址到ip.txt文件。')
    
    # 对IP进行ping测试并获取延迟
    print("正在进行ping测试并收集地区信息，筛选可用IP...")
    reachable_ips = []
    for ip in sorted_ips:
        # 获取地区信息
        region = get_ip_region(ip)
        # 为避免API请求过于频繁，添加短暂延迟
        time.sleep(0.5)
        
        # 根据操作系统设置不同的ping参数
        param = '-n 1' if platform.system().lower() == 'windows' else '-c 1'
        timeout = '-w 2000' if platform.system().lower() == 'windows' else '-W 2'
        
        try:
            # 执行ping命令
            output = subprocess.check_output(
                f'ping {param} {timeout} {ip}',
                shell=True,
                stderr=subprocess.STDOUT,
                universal_newlines=True
            )
            
            # 提取延迟时间（处理Windows和Linux不同的输出格式）
            delay = None
            if platform.system().lower() == 'windows':
                # Windows格式: 时间=32ms
                delay_match = re.search(r'时间=(\d+)ms', output)
            else:
                # Linux格式: time=32 ms
                delay_match = re.search(r'time=(\d+)', output)
                
            if delay_match:
                delay = f"{delay_match.group(1)}ms"
                reachable_ips.append(f"{ip}#{region}-{delay}")
                print(f"IP {ip} 可访问，地区: {region}，延迟: {delay}")
            else:
                print(f"IP {ip} 可访问，但无法获取延迟信息")
                
        except subprocess.CalledProcessError:
            print(f"IP {ip} 不可访问")
    
    # 保存可访问的IP到senflare.txt，格式: IP#地区-延迟
    with open('senflare.txt', 'w') as file:
        for entry in reachable_ips:
            file.write(entry + '\n')
    print(f'已保存 {len(reachable_ips)} 个可访问的IP地址到senflare.txt文件。')
else:
    print('未找到有效的IP地址。')
    
