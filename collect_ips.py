import requests
import re
import os
import subprocess
import time

# 目标URL列表
urls = [
    'https://ip.164746.xyz'
]

# 正则表达式用于匹配IP地址
ip_pattern = r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'

# 清理历史文件
for file in ['ip.txt', 'senflare.txt']:
    if os.path.exists(file):
        os.remove(file)

# 存储唯一IP
unique_ips = set()

print("正在从各个URL收集IP地址...")
for url in urls:
    try:
        # GitHub环境可能需要代理，添加超时和重试机制
        headers = {
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.0.0 Safari/537.36'
        }
        response = requests.get(
            url, 
            headers=headers,
            timeout=15,  # 延长超时（GitHub网络可能较慢）
            allow_redirects=True
        )
        
        if response.status_code == 200:
            ip_matches = re.findall(ip_pattern, response.text, re.IGNORECASE)
            unique_ips.update(ip_matches)
            print(f'从 {url} 获取到 {len(ip_matches)} 个IP地址')
    except requests.exceptions.RequestException as e:
        print(f'请求 {url} 失败: {str(e)[:50]}')
        continue

# 获取IP地区信息（适配GitHub环境的API）
def get_ip_region(ip):
    try:
        # 使用GitHub环境可访问的API
        # 备选1: ipinfo.io（国际通用）
        # 备选2: ip-api.com（添加备用）
        apis = [
            f'https://ipinfo.io/{ip}/country',
            f'http://ip-api.com/line/{ip}?fields=countryCode'
        ]
        
        for api in apis:
            try:
                response = requests.get(
                    api,
                    headers={'User-Agent': 'GitHub-Actions-Bot/1.0'},
                    timeout=10
                )
                if response.status_code == 200:
                    return response.text.strip().upper()
            except:
                continue
        
        return 'Unknown'
    except Exception as e:
        print(f"查询IP {ip} 地区信息失败: {str(e)[:30]}")
        return 'Unknown'

if unique_ips:
    sorted_ips = sorted(unique_ips, key=lambda ip: [int(part) for part in ip.split('.')])
    
    with open('ip.txt', 'w') as file:
        for ip in sorted_ips:
            file.write(ip + '\n')
    print(f'已保存 {len(sorted_ips)} 个唯一IP地址到ip.txt文件。')
    
    # 对IP进行ping测试（GitHub运行在Linux环境）
    print("正在进行ping测试并收集地区信息...")
    reachable_ips = []
    for ip in sorted_ips:
        # 获取地区信息
        region = get_ip_region(ip)
        time.sleep(0.8)  # 控制API请求频率
        
        try:
            # GitHub使用Linux，直接使用Linux的ping参数
            # 增加发包数量提高成功率，设置超时
            output = subprocess.check_output(
                f'ping -c 3 -W 2 {ip}',  # 3个包，超时2秒
                shell=True,
                stderr=subprocess.STDOUT,
                universal_newlines=True,
                timeout=10  # 整体超时
            )
            
            # 提取延迟时间
            delay_matches = re.findall(r'time=(\d+\.?\d*)', output)
            if delay_matches:
                delays = [float(d) for d in delay_matches]
                avg_delay = round(sum(delays) / len(delays))
                delay = f"{avg_delay}ms"
                reachable_ips.append(f"{ip}#{region}-{delay}")
                print(f"IP {ip} 可访问，地区: {region}，延迟: {delay}")
            else:
                print(f"IP {ip} 可访问，但无法获取延迟信息")
                
        except subprocess.CalledProcessError:
            print(f"IP {ip} 不可访问")
        except subprocess.TimeoutExpired:
            print(f"IP {ip} 测试超时")
        except Exception as e:
            print(f"测试IP {ip} 时出错: {e}")
    
    # 保存结果
    with open('senflare.txt', 'w') as file:
        for entry in reachable_ips:
            file.write(entry + '\n')
    print(f'已保存 {len(reachable_ips)} 个可访问的IP地址到senflare.txt文件。')
else:
    print('未找到有效的IP地址。')
