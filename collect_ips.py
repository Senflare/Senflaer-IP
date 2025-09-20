import requests
import re
import os
import time
import socket
from urllib3.exceptions import InsecureRequestWarning
from collections import defaultdict

# 禁用SSL证书警告（避免IP直连HTTPS的证书不匹配警告）
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# 国家/地区代码到中文名称的映射表（扩展更多地区）
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

# 核心配置参数（集中管理，方便调整）
CONFIG = {
    "ip_sources": [
        'https://ip.164746.xyz',  
        'https://cf.hyli.xyz/',
        # 'https://cf.090227.xyz',
        'https://api.uouin.com/cloudflare.html',
        'https://ipdb.api.030101.xyz/?type=bestproxy&country=true',
        'https://ipdb.api.030101.xyz/?type=bestcf&country=true',
        'https://stock.hostmonit.com/CloudFlareYes',
        'https://www.wetest.vip/page/cloudflare/address_v4.html'
    ],  # IP来源URL
    "test_port": 443,                        # 检测端口
    "timeout": 5,                            # 超时时间（秒）
    "retries": 2,                            # 重试次数（含首次）
    "region_cache": {}                       # 缓存IP地区信息，避免重复查询
}

def delete_file_if_exists(file_path):
    """保存文件前先删除原有文件"""
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"已删除原有文件: {file_path}")
        except Exception as e:
            print(f"删除文件 {file_path} 失败: {str(e)}")

def get_ip_region(ip):
    """获取IP的国家/地区代号（多API备份，提高成功率）"""
    # 先检查缓存，避免重复查询
    if ip in CONFIG["region_cache"]:
        return CONFIG["region_cache"][ip]
    
    # 多API查询，提高成功率
    apis = [
        f'http://ip-api.com/json/{ip}?fields=countryCode',
        f'https://ipinfo.io/{ip}/country',
        f'https://api.ip.sb/geoip/{ip}?fields=country_code'
    ]
    
    for api in apis:
        for _ in range(2):  # 每个API重试2次
            try:
                headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                resp = requests.get(api, headers=headers, timeout=5)
                
                if 'ip-api.com' in api:
                    data = resp.json()
                    if data.get('status') == 'success':
                        country_code = data.get('countryCode', 'Unknown').upper()
                        CONFIG["region_cache"][ip] = country_code
                        return country_code
                        
                elif 'ipinfo.io' in api and resp.status_code == 200:
                    country_code = resp.text.strip().upper()
                    if country_code:
                        CONFIG["region_cache"][ip] = country_code
                        return country_code
                        
                elif 'ip.sb' in api and resp.status_code == 200:
                    data = resp.json()
                    country_code = data.get('country_code', 'Unknown').upper()
                    if country_code:
                        CONFIG["region_cache"][ip] = country_code
                        return country_code
                        
            except:
                time.sleep(0.5)  # 重试间隔
    
    # 所有API都失败时返回Unknown
    CONFIG["region_cache"][ip] = 'Unknown'
    return 'Unknown'

def get_country_name(code):
    """根据国家/地区代码获取中文名称"""
    return COUNTRY_MAPPING.get(code, code)

def test_ip_availability(ip):
    """检测IP可用性（双层验证：先TCP握手，再HTTP请求）"""
    for attempt in range(CONFIG["retries"]):
        try:
            # 1. 底层TCP连接检测
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(CONFIG["timeout"])
                start_time = time.time()
                if s.connect_ex((ip, CONFIG["test_port"])) == 0:
                    tcp_delay = round((time.time() - start_time) * 1000)
                    
                    # 2. 应用层HTTP请求检测
                    try:
                        response = requests.get(
                            f'https://{ip}:{CONFIG["test_port"]}',
                            timeout=CONFIG["timeout"],
                            verify=False,
                            allow_redirects=False,
                            headers={'User-Agent': 'Mozilla/5.0'}
                        )
                        if 200 <= response.status_code < 400:
                            return (True, tcp_delay)
                    except:
                        # HTTP失败但TCP成功仍视为可用
                        return (True, tcp_delay)
        except:
            if attempt < CONFIG["retries"] - 1:
                time.sleep(1)
    
    return (False, 0)  # 不可用

def main():
    start_time = time.time()
    print("===== 开始IP收集与处理程序 =====")
    
    # 第一步：获取IP列表（提取所有IPv4地址）
    print("\n===== 第一步：收集IP地址 =====")
    all_ips = []
    for url in CONFIG["ip_sources"]:
        try:
            print(f"正在从 {url} 收集IP...", end=' ')
            resp = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code == 200:
                # 提取并验证IPv4地址
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
    # 按IP地址数字排序
    unique_ips.sort(key=lambda x: [int(p) for p in x.split('.')])
    print(f"去重后共得到 {len(unique_ips)} 个唯一IP地址")

    # 第三步：检测IP可用性并保存到IPlist.txt
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
    
    # 保存可用IP到IPlist.txt（先删除原有文件）
    delete_file_if_exists('IPlist.txt')
    with open('IPlist.txt', 'w', encoding='utf-8') as f:
        for ip, _ in available_ips:
            f.write(f"{ip}\n")
    print(f"\n已保存 {len(available_ips)} 个可用IP到 IPlist.txt")

    # 第四步：获取IP的国家/地区信息并分组
    print("\n===== 第四步：获取IP地区信息 =====")
    # 按地区分组IP
    region_groups = defaultdict(list)
    total = len(available_ips)
    
    for i, (ip, delay) in enumerate(available_ips, 1):
        print(f"获取地区信息 {i}/{total} - {ip}", end=' ')
        region_code = get_ip_region(ip)
        country_name = get_country_name(region_code)
        # 存储IP、延迟和地区信息
        region_groups[country_name].append((ip, region_code, delay))
        print(f"→ {country_name}")
    
    # 第五步：按地区排序并按自定义格式保存
    print("\n===== 第五步：按地区排序并格式化 =====")
    # 按地区名称排序（中文按拼音排序）
    sorted_regions = sorted(region_groups.items(), key=lambda x: x[0])
    
    result = []
    for region_name, ips in sorted_regions:
        # 每个地区内按延迟排序，更快的排在前面
        ips_sorted_by_delay = sorted(ips, key=lambda x: x[2])
        # 每个地区单独编号
        for idx, (ip, region_code, _) in enumerate(ips_sorted_by_delay, 1):
            # 格式化序号为两位数
            seq = f"{idx:02d}"
            # 自定义格式：IP+#+代号+" "+中文名称+"节点|"+序号
            formatted_line = f"{ip}#{region_code} {region_name}节点|{seq}"
            result.append(formatted_line)
            print(f"{formatted_line}")
    
    # 保存到Senflare.txt（先删除原有文件）
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
