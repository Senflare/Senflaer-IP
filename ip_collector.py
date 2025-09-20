import requests
import re
import os
import time
import socket
from urllib3.exceptions import InsecureRequestWarning
from collections import defaultdict, Counter

# 禁用SSL证书警告
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# 国家/地区代码映射表
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
    'AT': '奥地利',
    'BE': '比利时',
    'DK': '丹麦',
    'FI': '芬兰',
    'GR': '希腊',
    'IE': '爱尔兰',
    'IL': '以色列',
    'MX': '墨西哥',
    'MY': '马来西亚',
    'NZ': '新西兰',
    'NO': '挪威',
    'PT': '葡萄牙',
    'SA': '沙特阿拉伯',
    'SE': '瑞典',
    'TH': '泰国',
    'TR': '土耳其',
    'UA': '乌克兰',
    'Unknown': '未知'
}

# 核心配置（适配GitHub Actions环境）
CONFIG = {
    "ip_sources": [
        'https://ip.164746.xyz'
    ],
    "test_ports": [443, 80, 2053],  # 多端口检测，提高兼容性
    "timeout": 8,                   # 超时时间（秒）
    "retries": 3,                   # 重试次数
    "tcp_ping_ports": [80, 443],    # TCP Ping替代ICMP的端口
    "region_cache": {}
}

def delete_file_if_exists(file_path):
    """删除原有文件"""
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"已删除原有文件: {file_path}")
        except Exception as e:
            print(f"删除文件失败: {str(e)}")

def tcp_ping(ip):
    """
    用TCP连接模拟Ping检测（兼容GitHub Actions）
    尝试连接常用端口，只要有一个端口能连接就视为可达
    """
    min_delay = float('inf')
    for port in CONFIG["tcp_ping_ports"]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(CONFIG["timeout"] / 2)  # 每个端口超时时间短一些
                start_time = time.time()
                if s.connect_ex((ip, port)) == 0:
                    delay = (time.time() - start_time) * 1000
                    min_delay = min(min_delay, delay)
        except:
            continue
    
    if min_delay != float('inf'):
        return (True, round(min_delay))
    return (False, 0)

def get_ip_region(ip):
    """双重认证获取地区信息"""
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
        }
    ]
    
    results = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0 Safari/537.36'}
    
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
    
    if len(results) >= 2:
        code_counts = Counter(results)
        most_common = code_counts.most_common(1)[0]
        if most_common[1] >= 2:
            CONFIG["region_cache"][ip] = most_common[0]
            return most_common[0]
    
    CONFIG["region_cache"][ip] = 'Unknown'
    return 'Unknown'

def get_country_name(code):
    """获取中文地区名称"""
    return COUNTRY_MAPPING.get(code, code)

def test_ip_availability(ip):
    """
    兼容GitHub Actions的可用性检测：
    1. 先通过TCP Ping检测基础连通性
    2. 再检测目标服务端口（多端口尝试）
    """
    # 1. TCP Ping检测（兼容GitHub环境）
    ping_reachable, ping_delay = tcp_ping(ip)
    if not ping_reachable:
        return (False, 0)  # 基础连通性都没有，直接判定不可用
    
    # 2. 多端口服务检测
    for port in CONFIG["test_ports"]:
        for attempt in range(CONFIG["retries"]):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(CONFIG["timeout"])
                    start_time = time.time()
                    if s.connect_ex((ip, port)) == 0:
                        tcp_delay = round((time.time() - start_time) * 1000)
                        
                        # 尝试HTTP验证
                        try:
                            proto = 'https' if port == 443 else 'http'
                            response = requests.get(
                                f'{proto}://{ip}:{port}',
                                timeout=CONFIG["timeout"],
                                verify=False,
                                allow_redirects=False,
                                headers={'User-Agent': 'Mozilla/5.0'}
                            )
                            if 200 <= response.status_code < 400:
                                return (True, tcp_delay)
                        except:
                            return (True, tcp_delay)  # TCP成功即可
            except:
                if attempt < CONFIG["retries"] - 1:
                    time.sleep(1)
    
    # TCP Ping成功但服务端口不可达，仍视为弱可用
    print(f"⚠️ {ip} 服务端口不可达但基础网络连通")
    return (True, ping_delay)

def main():
    start_time = time.time()
    print("===== 开始IP处理程序 =====")
    
    # 1. 收集IP
    print("\n===== 收集IP地址 =====")
    all_ips = []
    for url in CONFIG["ip_sources"]:
        try:
            print(f"从 {url} 收集...", end=' ')
            resp = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code == 200:
                ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', resp.text)
                valid_ips = [ip for ip in ips if all(0<=int(p)<=255 for p in ip.split('.'))]
                all_ips.extend(valid_ips)
                print(f"成功收集 {len(valid_ips)} 个")
            else:
                print(f"失败（状态码 {resp.status_code}）")
        except Exception as e:
            print(f"出错: {str(e)[:30]}")

    # 2. 去重
    unique_ips = sorted(list(set(all_ips)), key=lambda x: [int(p) for p in x.split('.')])
    print(f"\n去重后共 {len(unique_ips)} 个IP")

    # 3. 检测可用性
    print("\n===== 检测可用性 =====")
    available_ips = []
    for i, ip in enumerate(unique_ips, 1):
        print(f"检测 {i}/{len(unique_ips)} - {ip}", end=' ')
        is_available, delay = test_ip_availability(ip)
        if is_available:
            available_ips.append((ip, delay))
            print(f"✅ 可用（延迟 {delay}ms）")
        else:
            print(f"❌ 不可用")
    
    # 保存可用IP
    delete_file_if_exists('IPlist.txt')
    with open('IPlist.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join([ip for ip, _ in available_ips]))
    print(f"\n已保存 {len(available_ips)} 个可用IP到 IPlist.txt")

    # 4. 地区识别与格式化
    print("\n===== 地区识别与格式化 =====")
    region_groups = defaultdict(list)
    for ip, delay in available_ips:
        region_code = get_ip_region(ip)
        region_groups[get_country_name(region_code)].append((ip, region_code, delay))
    
    # 按地区排序并生成结果
    result = []
    for region in sorted(region_groups.keys()):
        for idx, (ip, code, _) in enumerate(sorted(region_groups[region], key=lambda x: x[2]), 1):
            result.append(f"{ip}#{code} {region}节点|{idx:02d}")
    
    # 保存最终结果
    delete_file_if_exists('Senflare.txt')
    with open('Senflare.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(result))
    print(f"已保存 {len(result)} 条记录到 Senflare.txt")
    
    print(f"\n总耗时: {round(time.time()-start_time, 2)}秒")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序被中断")
    except Exception as e:
        print(f"\n出错: {str(e)}")
