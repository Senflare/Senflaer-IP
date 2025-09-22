import requests
import re
import os
import time
import socket
from urllib3.exceptions import InsecureRequestWarning
from collections import defaultdict, Counter

# 禁用SSL证书警告
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# 完整的国家/地区代码映射表（保留所有需要的地区）
COUNTRY_MAPPING = {
    'US': '美国', 'CN': '中国', 'JP': '日本', 'KR': '韩国',
    'SG': '新加坡', 'DE': '德国', 'UK': '英国', 'FR': '法国',
    'CA': '加拿大', 'AU': '澳大利亚', 'IN': '印度', 'NL': '荷兰',
    'HK': '中国香港', 'TW': '中国台湾', 'RU': '俄罗斯', 'BR': '巴西',
    'IT': '意大利', 'ES': '西班牙', 'CH': '瑞士', 'AT': '奥地利',
    'BE': '比利时', 'DK': '丹麦', 'FI': '芬兰', 'GR': '希腊',
    'IE': '爱尔兰', 'IL': '以色列', 'MX': '墨西哥', 'MY': '马来西亚',
    'NZ': '新西兰', 'NO': '挪威', 'PT': '葡萄牙', 'SA': '沙特阿拉伯',
    'SE': '瑞典', 'TH': '泰国', 'TR': '土耳其', 'UA': '乌克兰',
    'Unknown': '未知'
}

# 核心配置（整合优化参数）
CONFIG = {
    "ip_sources": [
        'https://ip.164746.xyz',
        'https://cf.hyli.xyz/'
         # 'https://cf.090227.xyz',
        'https://raw.githubusercontent.com/ymyuuu/IPDB/main/BestCF/bestcfv4.txt'
        'https://api.uouin.com/cloudflare.html',
         # 'https://ipdb.api.030101.xyz/?type=bestproxy&country=true', # IP太多会导致无法处理
        'https://ipdb.api.030101.xyz/?type=bestcf&country=true',
        'https://addressesapi.090227.xyz/CloudFlareYes',
         # 'https://stock.hostmonit.com/CloudFlareYes',
        'https://www.wetest.vip/page/cloudflare/address_v4.html'
    ],
    "test_ports": [443, 2053, 2083, 2087, 2096, 8443],  # 多端口检测提高兼容性
    "timeout": 10,                  # 延长超时时间至10秒
    "retries": 3,                   # 保留3次重试
    "tcp_ping_ports": [443],    # 核心端口TCP Ping
    "region_cache": {},             # 地区缓存
    "api_timeout": 8,               # API查询超时时间
    "query_interval": 0.5           # API查询间隔（防限流）
}

def delete_file_if_exists(file_path):
    """删除原有文件，避免结果累积"""
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"🗑️ 已删除原有文件: {file_path}")
        except Exception as e:
            print(f"⚠️ 删除文件失败: {str(e)}")

def tcp_ping(ip):
    """
    TCP Ping检测（兼容多环境）
    通过尝试连接常用端口判断网络连通性
    """
    min_delay = float('inf')
    for port in CONFIG["tcp_ping_ports"]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(CONFIG["timeout"] / 2)  # 单个端口超时
                start_time = time.time()
                if s.connect_ex((ip, port)) == 0:
                    # 计算延迟并保留最小值
                    delay = (time.time() - start_time) * 1000
                    min_delay = min(min_delay, delay)
        except Exception as e:
            continue  # 忽略单个端口错误
    
    return (True, round(min_delay)) if min_delay != float('inf') else (False, 0)

def get_ip_region(ip):
    """
    优化的IP地区识别逻辑：
    1. 使用你提供的token调用ipinfo.io（高优先级）
    2. 辅以ip-api.com作为备用
    3. 采用出现次数多的结果提高准确性
    """
    # 检查缓存，避免重复查询
    if ip in CONFIG["region_cache"]:
        return CONFIG["region_cache"][ip]
    
    # 可靠API列表（含你的token）
    apis = [
        {
            'name': 'ipinfo.io（你的token）',
            'url': f'https://ipinfo.io/{ip}?token=2cb674df499388',
            'parser': lambda resp: resp.json().get('country', '').upper() 
                                  if resp.status_code == 200 else None
        },
        {
            'name': 'ip-api.com',
            'url': f'http://ip-api.com/json/{ip}?fields=countryCode',
            'parser': lambda resp: resp.json().get('countryCode', '').upper() 
                                  if resp.json().get('status') == 'success' else None
        }
    ]
    
    results = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0 Safari/537.36'}
    
    for api in apis:
        for attempt in range(2):  # 每个API重试2次
            try:
                resp = requests.get(api['url'], headers=headers, timeout=CONFIG["api_timeout"])
                country_code = api['parser'](resp)
                
                if country_code and country_code != '':
                    results.append(country_code)
                    break  # 成功获取后停止重试
            except Exception as e:
                time.sleep(0.5)  # 重试间隔
    
    # 处理结果：选择出现次数最多的代码
    if results:
        code_counts = Counter(results)
        most_common = code_counts.most_common(1)[0]
        CONFIG["region_cache"][ip] = most_common[0]
        return most_common[0]
    
    # 所有API都失败时返回Unknown
    CONFIG["region_cache"][ip] = 'Unknown'
    return 'Unknown'

def get_country_name(code):
    """根据国家代码获取中文名称"""
    return COUNTRY_MAPPING.get(code, code)

def test_ip_availability(ip):
    """
    分层可用性检测：
    1. 基础TCP Ping检测网络连通性
    2. 多端口服务检测确认服务可用性
    """
    # 1. 基础TCP Ping检测
    ping_reachable, ping_delay = tcp_ping(ip)
    if not ping_reachable:
        return (False, 0)  # 基础网络不通
    
    # 2. 多端口服务检测
    for port in CONFIG["test_ports"]:
        for attempt in range(CONFIG["retries"]):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(CONFIG["timeout"])
                    start_time = time.time()
                    if s.connect_ex((ip, port)) == 0:
                        tcp_delay = round((time.time() - start_time) * 1000)
                        
                        # 尝试HTTP验证（非必须）
                        try:
                            proto = 'https' if port == 443 else 'http'
                            response = requests.get(
                                f'{proto}://{ip}:{port}',
                                timeout=CONFIG["timeout"],
                                verify=False,
                                allow_redirects=False,
                                headers={'User-Agent': 'Mozilla/5.0'}
                            )
                            # 200-399状态码均视为有效
                            if 200 <= response.status_code < 400:
                                return (True, tcp_delay)
                        except:
                            # HTTP失败但TCP成功仍视为可用
                            return (True, tcp_delay)
            except Exception as e:
                if attempt < CONFIG["retries"] - 1:
                    time.sleep(1)  # 重试间隔
    
    # 3. 弱可用状态（基础连通但服务端口不可达）
    print(f"⚠️ {ip} 服务端口不可达但网络连通")
    return (True, ping_delay)

def main():
    start_time = time.time()
    print("🚀 ===== 开始IP处理程序 =====")
    
    # 1. 预处理：删除旧文件
    delete_file_if_exists('IPlist.txt')
    delete_file_if_exists('Senflare.txt')

    # 2. 收集IP地址
    print("\n📥 ===== 收集IP地址 =====")
    all_ips = []
    for url in CONFIG["ip_sources"]:
        try:
            print(f"🔍 从 {url} 收集...", end=' ')
            resp = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code == 200:
                # 提取并验证IPv4地址
                ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', resp.text)
                valid_ips = [
                    ip for ip in ips 
                    if all(0 <= int(part) <= 255 for part in ip.split('.'))
                ]
                all_ips.extend(valid_ips)
                print(f"✅ 成功收集 {len(valid_ips)} 个有效IP地址")
            else:
                print(f"❌ 失败（状态码 {resp.status_code}）")
        except Exception as e:
            print(f"❌ 出错: {str(e)[:30]}")

    # 3. IP去重与排序
    unique_ips = sorted(list(set(all_ips)), key=lambda x: [int(p) for p in x.split('.')])
    print(f"\n🔢 去重后共 {len(unique_ips)} 个唯一IP地址")

    # 4. 检测IP可用性
    print("\n📡 ===== 检测IP可用性 =====")
    available_ips = []
    total = len(unique_ips)
    for i, ip in enumerate(unique_ips, 1):
        print(f"[{i}/{total}] 检测 {ip}", end=' ')
        is_available, delay = test_ip_availability(ip)
        if is_available:
            available_ips.append((ip, delay))
            print(f"✅ 可用（延迟 {delay}ms）")
        else:
            print(f"❌ 不可用")
    
    # 5. 保存可用IP列表
    if available_ips:
        with open('IPlist.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join([ip for ip, _ in available_ips]))
        print(f"\n📄 已保存 {len(available_ips)} 个可用IP到 IPlist.txt")
    else:
        print(f"\n⚠️ 未检测到可用IP")

    # 6. 地区识别与结果格式化
    print("\n🌍 ===== 地区识别与结果格式化 =====")
    region_groups = defaultdict(list)
    total = len(available_ips)
    for i, (ip, delay) in enumerate(available_ips, 1):
        print(f"[{i}/{total}] 识别 {ip} 地区...", end=' ')
        region_code = get_ip_region(ip)
        country_name = get_country_name(region_code)
        region_groups[country_name].append((ip, region_code, delay))
        print(f"→ {country_name}({region_code})")
        time.sleep(CONFIG["query_interval"])  # 防API限流
    
    # 7. 生成并保存最终结果
    result = []
    for region in sorted(region_groups.keys()):
        # 同一地区内按延迟排序（更快的在前）
        sorted_ips = sorted(region_groups[region], key=lambda x: x[2])
        for idx, (ip, code, _) in enumerate(sorted_ips, 1):
            result.append(f"{ip}#{code} {region}节点|{idx:02d}")
    
    if result:
        with open('Senflare.txt', 'w', encoding='utf-8') as f:
            f.write('\n'.join(result))
        print(f"\n📊 已保存 {len(result)} 条格式化记录到 Senflare.txt")
    else:
        print(f"\n⚠️ 无有效记录可保存")
    
    # 显示总耗时
    run_time = round(time.time() - start_time, 2)
    print(f"\n⏱️ 总耗时: {run_time}秒")
    print("🏁 ===== 程序完成 =====")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ 程序被用户中断")
    except Exception as e:
        print(f"\n❌ 运行出错: {str(e)}")
