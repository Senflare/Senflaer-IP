import requests
import re
import os
import time
import socket
from urllib3.exceptions import InsecureRequestWarning

# 禁用SSL证书警告（避免IP直连HTTPS的证书不匹配警告）
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# 核心配置参数（集中管理，方便调整）
CONFIG = {
    "ip_sources": [
    'https://ip.164746.xyz', 
  # 'https://cf.090227.xyz',  # 这里使用#进行注释
    'https://stock.hostmonit.com/CloudFlareYes',
    'https://api.uouin.com/cloudflare.html',
    'https://ipdb.api.030101.xyz/?type=bestproxy&country=true',
    'https://cf.hyli.xyz/',
    'https://api.uouin.com/cloudflare.html',
    'https://www.wetest.vip/page/cloudflare/address_v4.html'
    ],  # IP来源URL
    "test_port": 443,                        # 检测端口（Cloudflare默认HTTPS端口）
    "timeout": 5,                            # 超时时间（秒）
    "retries": 2                             # 重试次数（含首次）
}

def get_ip_region(ip):
    """获取IP的国家/地区代号（双API备份，提高成功率）"""
    # 优先用ip-api.com（返回格式规范），失败则用ipinfo.io（备用）
    for api in [
        f'http://ip-api.com/json/{ip}?fields=countryCode',
        f'https://ipinfo.io/{ip}/country'
    ]:
        for _ in range(2):  # 每个API重试2次
            try:
                resp = requests.get(api, headers={'User-Agent': 'Mozilla/5.0'}, timeout=5)
                if 'ip-api.com' in api and resp.json().get('status') == 'success':
                    return resp.json().get('countryCode', 'Unknown').upper()
                if 'ipinfo.io' in api and resp.status_code == 200:
                    return resp.text.strip().upper()
            except:
                time.sleep(0.5)  # 重试间隔，避免请求过于密集
    return 'Unknown'

def test_ip_availability(ip):
    """检测IP可用性（双层验证：先TCP握手，再HTTP请求）"""
    for _ in range(CONFIG["retries"]):
        try:
            # 1. 底层TCP连接检测（最基础的连通性）
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(CONFIG["timeout"])
                start = time.time()
                if s.connect_ex((ip, CONFIG["test_port"])) == 0:  # 0表示连接成功
                    tcp_delay = round((time.time() - start) * 1000)
                    
                    # 2. 应用层HTTP请求检测（确认服务可用）
                    try:
                        requests.get(
                            f'https://{ip}:{CONFIG["test_port"]}',
                            timeout=CONFIG["timeout"],
                            verify=False,  # 忽略证书不匹配（IP直连常见）
                            allow_redirects=False
                        )
                    except:
                        pass  # HTTP失败但TCP成功仍视为可用（部分CDN限制IP访问）
                    
                    return tcp_delay  # 返回TCP层延迟
        except:
            time.sleep(1)  # 重试间隔，适应网络波动
    return None  # 多次重试失败则标记为不可用

# 主逻辑执行
if __name__ == "__main__":
    # 1. 收集并去重IP
    unique_ips = set()
    print("收集IP地址中...")
    for url in CONFIG["ip_sources"]:
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                # 提取所有IPv4地址（正则匹配）
                ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', resp.text)
                unique_ips.update(ips)
                print(f"从 {url} 收集到 {len(ips)} 个IP")
        except Exception as e:
            print(f"获取IP失败: {str(e)[:50]}")  # 仅显示部分错误信息，避免冗余

    # 2. 保存原始IP（按数字排序）
    sorted_ips = sorted(unique_ips, key=lambda x: [int(p) for p in x.split('.')])
    with open('ip.txt', 'w') as f:
        f.write('\n'.join(sorted_ips))
    print(f"共收集 {len(sorted_ips)} 个唯一IP")

    # 3. 检测可用IP并生成结果
    available_ips = []
    print("\n开始测试IP可用性（TCP+HTTP双层检测）...")
    for ip in sorted_ips:
        region = get_ip_region(ip)
        delay = test_ip_availability(ip)
        
        if delay is not None:
            entry = f"{ip}#{region}-{delay}ms"
            available_ips.append(entry)
            print(f"✅ {entry}（检测通过）")
        else:
            print(f"❌ {ip} 不可用")

    # 4. 保存可用IP结果
    with open('senflare.txt', 'w') as f:
        f.write('\n'.join(available_ips))
    print(f"\n已保存 {len(available_ips)} 个可用IP到 senflare.txt")
