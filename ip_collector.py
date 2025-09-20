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

# 核心配置（优化后参数）
CONFIG = {
    "ip_sources": [
        'https://ip.164746.xyz'
    ],
    "test_ports": [443, 80, 2053],  # 多端口检测提高兼容性
    "timeout": 10,                  # 延长超时时间至10秒
    "retries": 3,                   # 保留3次重试
    "tcp_ping_ports": [80, 443],    # 核心端口TCP Ping
    "region_cache": {},             # 地区缓存
    "api_timeout": 8                # API查询超时时间
}

def delete_file_if_exists(file_path):
    """删除原有文件，避免结果累积"""
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"已删除原有文件: {file_path}")
        except Exception as e:
            print(f"删除文件失败: {str(e)}")

def tcp_ping(ip):
    """
    TCP Ping检测（兼容GitHub Actions环境）
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
    1. 保留经过验证的两个可靠API
    2. 只要有一个有效结果就使用（而非必须两个一致）
    3. 优先采用出现次数多的结果
    4. 仅在所有API失败时才返回Unknown
    """
    # 检查缓存，避免重复查询
    if ip in CONFIG["region_cache"]:
        return CONFIG["region_cache"][ip]
    
    # 经过验证的可靠API列表
    apis = [
        {
            'name': 'ip-api.com',
            'url': f'http://ip-api.com/json/{ip}?fields=countryCode',
            'parser': lambda resp: resp.json().get('countryCode', '').upper() 
                                  if resp.json().get('status') == 'success' else None
        },
        {
            'name': 'ipinfo.io',
            'url': f'https://ipinfo.io/{ip}/country',
            'parser': lambda resp: resp.text.strip().upper() if resp.status_code == 200 else None
        }
    ]
    
    results = []
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/114.0.0.0 Safari/537.36'}
    
    for api in apis:
        for attempt in range(2):  # 每个API重试2次
            try:
                # 增加API查询超时时间
                resp = requests.get(api['url'], headers=headers, timeout=CONFIG["api_timeout"])
                country_code = api['parser'](resp)
                
                if country_code and country_code != '':
                    results.append(country_code)
                    break  # 成功获取后停止重试
            except Exception as e:
                # 仅在调试时显示API错误
                # print(f"  {api['name']} 尝试{attempt+1}失败: {str(e)[:30]}")
                time.sleep(0.5)  # 重试间隔
    
    # 处理结果：只要有有效结果就使用
    if results:
        # 选择出现次数最多的代码
        code_counts = Counter(results)
        most_common = code_counts.most_common(1)[0]
        CONFIG["region_cache"][ip] = most_common[0]
        return most_common[0]
    
    # 所有API都失败时才返回Unknown
    CONFIG["region_cache"][ip] = 'Unknown'
    return 'Unknown'

def get_country_name(code):
    """根据国家代码获取中文名称，默认返回代码本身"""
    return COUNTRY_MAPPING.get(code, code)

def test_ip_availability(ip):
    """
    分层可用性检测：
    1. 基础TCP Ping检测网络连通性
    2. 多端口服务检测确认服务可用性
    3. 宽松判定标准，提高可用IP识别率
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
    print("===== 开始IP处理程序 =====")
    
    # 1. 收集IP地址
    print("\n===== 收集IP地址 =====")
    all_ips = []
    for url in CONFIG["ip_sources"]:
        try:
            print(f"从 {url} 收集...", end=' ')
            resp = requests.get(url, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            if resp.status_code == 200:
                # 提取并验证IPv4地址
                ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', resp.text)
                valid_ips = [
                    ip for ip in ips 
                    if all(0 <= int(part) <= 255 for part in ip.split('.'))
                ]
                all_ips.extend(valid_ips)
                print(f"成功收集 {len(valid_ips)} 个")
            else:
                print(f"失败（状态码 {resp.status_code}）")
        except Exception as e:
            print(f"出错: {str(e)[:30]}")

    # 2. IP去重与排序
    unique_ips = sorted(list(set(all_ips)), key=lambda x: [int(p) for p in x.split('.')])
    print(f"\n去重后共 {len(unique_ips)} 个IP")

    # 3. 检测IP可用性
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
    
    # 保存可用IP列表
    delete_file_if_exists('IPlist.txt')
    with open('IPlist.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join([ip for ip, _ in available_ips]))
    print(f"\n已保存 {len(available_ips)} 个可用IP到 IPlist.txt")

    # 4. 地区识别与结果格式化
    print("\n===== 地区识别与格式化 =====")
    region_groups = defaultdict(list)
    for ip, delay in available_ips:
        region_code = get_ip_region(ip)
        country_name = get_country_name(region_code)
        region_groups[country_name].append((ip, region_code, delay))
        # 可选：显示识别结果用于调试
        # print(f"  {ip} → {region_code}({country_name})")
    
    # 按地区排序并生成最终结果
    result = []
    for region in sorted(region_groups.keys()):
        # 同一地区内按延迟排序
        sorted_ips = sorted(region_groups[region], key=lambda x: x[2])
        for idx, (ip, code, _) in enumerate(sorted_ips, 1):
            result.append(f"{ip}#{code} {region}节点|{idx:02d}")
    
    # 保存格式化结果
    delete_file_if_exists('Senflare.txt')
    with open('Senflare.txt', 'w', encoding='utf-8') as f:
        f.write('\n'.join(result))
    print(f"已保存 {len(result)} 条记录到 Senflare.txt")
    
    # 显示总耗时
    print(f"\n总耗时: {round(time.time()-start_time, 2)}秒")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序被用户中断")
    except Exception as e:
        print(f"\n运行出错: {str(e)}")
