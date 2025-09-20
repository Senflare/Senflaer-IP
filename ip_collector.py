import requests
import re
import os
import time
import socket
import platform
import subprocess
from urllib3.exceptions import InsecureRequestWarning
from collections import defaultdict, Counter

# 禁用SSL证书警告（避免IP直连HTTPS的证书不匹配警告）
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# 国家/地区代码到中文名称的映射表
COUNTRY_MAPPING = {
    'US': '美国',
    'CN': '中国',
    'JP': '日本',
    'KR': '韩国',
    'SG': '新加坡',
    'DE': '德国',
    'UK': '英国',
    'FR': '法国',
    'CA': '加拿大',
    'AU': '澳大利亚',
    'IN': '印度',
    'NL': '荷兰',
    'HK': '中国香港',
    'TW': '中国台湾',
    'RU': '俄罗斯',
    'BR': '巴西',
    'IT': '意大利',
    'ES': '西班牙',
    'CH': '瑞士',
    'Unknown': '未知'
}

# 核心配置参数（集中管理，方便调整）
CONFIG = {
    "ip_sources": [
        'https://ip.164746.xyz'
    ],  # IP来源URL
    "test_port": 443,                        # 检测端口
    "timeout": 8,                            # 超时时间延长至8秒（原5秒）
    "retries": 3,                            # 重试次数增加到3次（原2次）
    "ping_count": 2,                         # Ping检测次数
    "region_cache": {}                       # 缓存IP地区信息
}

def delete_file_if_exists(file_path):
    """保存文件前先删除原有文件"""
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"已删除原有文件: {file_path}")
        except Exception as e:
            print(f"删除文件 {file_path} 失败: {str(e)}")

def ping_ip(ip):
    """
    执行ICMP Ping检测（模仿itdog的检测方式）
    返回: (是否可达, 平均延迟ms)
    """
    # 根据操作系统设置ping命令参数
    param = '-n' if platform.system().lower() == 'windows' else '-c'
    count = CONFIG["ping_count"]
    timeout = CONFIG["timeout"]
    
    # 构建ping命令
    command = ['ping', param, str(count), '-W', str(timeout), ip]
    
    try:
        # 执行ping命令并捕获输出
        output = subprocess.run(
            command, 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE, 
            text=True,
            timeout=timeout + 2
        )
        
        # 检查返回码和输出判断是否可达
        if output.returncode == 0:
            # 尝试提取平均延迟（跨平台适配）
            if platform.system().lower() == 'windows':
                # Windows格式: 平均 = 38ms
                avg_match = re.search(r'平均 = (\d+)ms', output.stdout)
            else:
                # Linux格式: rtt min/avg/max/mdev = 5.623/5.623/5.623/0.000 ms
                avg_match = re.search(r'/(\d+\.\d+)/', output.stdout)
            
            avg_delay = 0
            if avg_match:
                avg_delay = round(float(avg_match.group(1)))
            
            return (True, avg_delay)
    except:
        pass
    
    return (False, 0)

def get_ip_region(ip):
    """获取IP的国家/地区代号（双重认证机制）"""
    if ip in CONFIG["region_cache"]:
        return CONFIG["region_cache"][ip]
    
    apis = [
        {
            'url': f'http://ip-api.com/json/{ip}?fields=countryCode',
            'parser': lambda resp: resp.json().get('countryCode', '').upper() 
                                  if resp.json().get('status') == 'success' else None
        },
        {
            'url': f'https://ipinfo.io/{ip}/country',
            'parser': lambda resp: resp.text.strip().upper() if resp.status_code == 200 else None
        },
        {
            'url': f'https://api.ip.sb/geoip/{ip}',
            'parser': lambda resp: resp.json().get('country_code', '').upper() if resp.status_code == 200 else None
        },
        {
            'url': f'https://ipapi.co/{ip}/country/',
            'parser': lambda resp: resp.text.strip().upper() if resp.status_code == 200 else None
        }
    ]
    
    results = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'}
    
    for api in apis:
        for _ in range(2):
            try:
                resp = requests.get(api['url'], headers=headers, timeout=5)
                country_code = api['parser'](resp)
                
                if country_code and country_code != '':
                    results.append(country_code)
                    break
            except:
                time.sleep(0.5)
    
    # 双重认证逻辑
    if len(results) >= 2:
        code_counts = Counter(results)
        most_common = code_counts.most_common(1)[0]
        if most_common[1] >= 2:
            CONFIG["region_cache"][ip] = most_common[0]
            return most_common[0]
        else:
            print(f"⚠️ IP {ip} 地区识别不一致: {results}")
    
    CONFIG["region_cache"][ip] = 'Unknown'
    return 'Unknown'

def get_country_name(code):
    """根据国家/地区代码获取中文名称"""
    return COUNTRY_MAPPING.get(code, code)

def test_ip_availability(ip):
    """
    增强版IP可用性检测（多维度验证）
    1. 先进行ICMP Ping检测（模仿itdog的检测方式）
    2. 再进行TCP端口检测
    3. 最后进行HTTP请求检测
    任一检测通过即视为可用，提高检测准确性
    """
    # 1. 先尝试Ping检测（很多节点Ping通但端口可能封闭）
    ping_reachable, ping_delay = ping_ip(ip)
    if ping_reachable:
        # 记录Ping延迟作为参考
        base_delay = ping_delay
    else:
        base_delay = 9999  # Ping不通时给一个大延迟值
    
    # 2. 尝试TCP端口连接（主要检测目标端口）
    for attempt in range(CONFIG["retries"]):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(CONFIG["timeout"])
                start_time = time.time()
                if s.connect_ex((ip, CONFIG["test_port"])) == 0:
                    tcp_delay = round((time.time() - start_time) * 1000)
                    
                    # 3. 尝试HTTP请求检测
                    try:
                        response = requests.get(
                            f'https://{ip}:{CONFIG["test_port"]}',
                            timeout=CONFIG["timeout"],
                            verify=False,
                            allow_redirects=False,
                            headers={'User-Agent': 'Mozilla/5.0'}
                        )
                        if 200 <= response.status_code < 400:
                            return (True, tcp_delay)  # HTTP成功
                    except:
                        return (True, tcp_delay)  # TCP成功但HTTP失败
        except:
            if attempt < CONFIG["retries"] - 1:
                time.sleep(1)
    
    # 如果TCP/HTTP都失败但Ping成功，也视为可用（放宽检测标准）
    if ping_reachable:
        print(f"⚠️ {ip} TCP/HTTP检测失败但Ping可达")
        return (True, base_delay)
    
    return (False, 0)  # 所有检测都失败

def main():
    start_time = time.time()
    print("===== 开始IP收集与处理程序 =====")
    
    # 第一步：获取IP列表
    print("\n===== 第一步：收集IP地址 =====")
    all_ips = []
    for url in CONFIG["ip_sources"]:
        try:
            print(f"正在从 {url} 收集IP...", end=' ')
            resp = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code == 200:
                ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', resp.text)
                valid_ips = []
                for ip in ips:
                    parts = ip.split('.')
                    if len(parts) == 4 and all(0 <= int(part) <= 255 for part in parts):
                        valid_ips.append(ip)
                all_ips.extend(valid_ips)
                print(f"成功收集到 {len(valid_ips)} 个有效IP")
            else:
                print(f"失败，状态码: {resp.status_code}")
        except Exception as e:
            print(f"出错: {str(e)[:50]}")

    # 第二步：去重IP
    print("\n===== 第二步：去重IP =====")
    unique_ips = list(set(all_ips))
    unique_ips.sort(key=lambda x: [int(p) for p in x.split('.')])
    print(f"去重后共得到 {len(unique_ips)} 个唯一IP地址")

    # 第三步：检测IP可用性（增强版多维度检测）
    print("\n===== 第三步：检测IP可用性 =====")
    available_ips = []
    total = len(unique_ips)
    
    for i, ip in enumerate(unique_ips, 1):
        print(f"检测中 {i}/{total} - {ip}", end=' ')
        is_available, delay = test_ip_availability(ip)
        
        if is_available:
            available_ips.append((ip, delay))
            print(f"✅ 可用 (延迟: {delay}ms)")
        else:
            print(f"❌ 不可用")
    
    # 保存可用IP到IPlist.txt
    delete_file_if_exists('IPlist.txt')
    with open('IPlist.txt', 'w', encoding='utf-8') as f:
        for ip, _ in available_ips:
            f.write(f"{ip}\n")
    print(f"\n已保存 {len(available_ips)} 个可用IP到 IPlist.txt")

    # 第四步：获取IP地区信息（双重认证）
    print("\n===== 第四步：获取IP地区信息 =====")
    region_groups = defaultdict(list)
    total = len(available_ips)
    
    for i, (ip, delay) in enumerate(available_ips, 1):
        print(f"获取地区信息 {i}/{total} - {ip}", end=' ')
        region_code = get_ip_region(ip)
        country_name = get_country_name(region_code)
        region_groups[country_name].append((ip, region_code, delay))
        print(f"→ {country_name}")
    
    # 第五步：按地区排序并格式化
    print("\n===== 第五步：按地区排序并格式化 =====")
    sorted_regions = sorted(region_groups.items(), key=lambda x: x[0])
    
    result = []
    for region_name, ips in sorted_regions:
        ips_sorted_by_delay = sorted(ips, key=lambda x: x[2])
        for idx, (ip, region_code, _) in enumerate(ips_sorted_by_delay, 1):
            seq = f"{idx:02d}"
            formatted_line = f"{ip}#{region_code} {region_name}节点|{seq}"
            result.append(formatted_line)
            print(f"{formatted_line}")
    
    # 保存到Senflare.txt
    delete_file_if_exists('Senflare.txt')
    with open('Senflare.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(result))
    print(f"\n已按自定义格式保存 {len(result)} 条记录到 Senflare.txt")
    
    # 显示程序运行时间
    end_time = time.time()
    run_time = round(end_time - start_time, 2)
    print(f"\n===== 程序完成，总运行时间: {run_time}秒 =====")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"\n程序运行出错: {str(e)}")
