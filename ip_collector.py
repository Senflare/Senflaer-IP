import requests
import re
import os
import time
import socket
from urllib3.exceptions import InsecureRequestWarning
from collections import defaultdict

# 禁用SSL证书警告
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# 国家/地区代码映射表
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

# 核心配置（你的API和参数）
CONFIG = {
    "ip_sources": [
        'https://ip.164746.xyz',  
        'https://cf.hyli.xyz/'
    ],
    "test_port": 443,                # 仅检测443端口
    "timeout": 8,                    # 超时时间
    "retries": 2,                    # 重试次数
    "query_interval": 0.5,           # API查询间隔
    "ip_info_cache": {},             # 缓存IP信息
    # 你的API列表（已验证可用性）
    "ip_info_apis": [
        {
            "name": "ipinfo.io（你的token）",
            "url": "https://ipinfo.io/{ip}?token=2cb674df499388",
            "parser": lambda resp: (
                resp.json().get("country", "Unknown").upper(),
                resp.json().get("org", "未知运营商").split(' ', 1)[-1]
            )
        },
        {
            "name": "api.ip.sb",
            "url": "https://api.ip.sb/geoip/{ip}",
            "parser": lambda resp: (
                resp.json().get("country_code", "Unknown").upper(),
                resp.json().get("isp", "未知运营商")
            )
        },
        {
            "name": "iplark.com",
            "url": "https://iplark.com/{ip}",
            "parser": lambda resp: (
                re.search(r'Country Code.*?<code>([A-Z]{2})</code>', resp.text).group(1) 
                if re.search(r'Country Code.*?<code>([A-Z]{2})</code>', resp.text) else "Unknown",
                re.search(r'ISP.*?<code>(.*?)</code>', resp.text).group(1)
                if re.search(r'ISP.*?<code>(.*?)</code>', resp.text) else "未知运营商"
            )
        }
    ]
}

def delete_old_files():
    """删除历史结果文件"""
    for file in ['IPlist.txt', 'Senflare.txt']:
        if os.path.exists(file):
            try:
                os.remove(file)
                print(f"已删除旧文件: {file}")
            except Exception as e:
                print(f"删除文件失败: {str(e)}")

def validate_ipv4(ip):
    """验证IPv4格式"""
    try:
        parts = list(map(int, ip.split('.')))
        return len(parts) == 4 and all(0 <= p <= 255 for p in parts)
    except:
        return False

def get_ip_info(ip):
    """获取IP的国家代码和运营商"""
    if ip in CONFIG["ip_info_cache"]:
        return CONFIG["ip_info_cache"][ip]

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/118.0.0.0 Safari/537.36'}
    country_code, isp = "Unknown", "未知运营商"

    for api in CONFIG["ip_info_apis"]:
        try:
            resp = requests.get(
                api["url"].format(ip=ip),
                headers=headers,
                timeout=8,
                verify=False
            )
            if resp.status_code == 200:
                temp_code, temp_isp = api["parser"](resp)
                if temp_code != "Unknown" and temp_isp != "未知运营商":
                    country_code, isp = temp_code, temp_isp
                    break
        except Exception as e:
            continue
        time.sleep(0.3)

    CONFIG["ip_info_cache"][ip] = (country_code, isp)
    time.sleep(CONFIG["query_interval"])
    return country_code, isp

def test_ip(ip):
    """检测IP的443端口可用性"""
    for _ in range(CONFIG["retries"]):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(CONFIG["timeout"])
                start = time.time()
                if s.connect_ex((ip, CONFIG["test_port"])) == 0:
                    return (True, round((time.time() - start) * 1000))
        except:
            time.sleep(1)
    return (False, 0)

def main():
    start_time = time.time()
    print("===== 开始IPv4处理程序 =====")
    delete_old_files()

    # 收集IP
    all_ips = []
    print("\n1. 收集IP地址...")
    for url in CONFIG["ip_sources"]:
        try:
            print(f"处理 {url}...", end=' ')
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', resp.text)
                valid = [ip for ip in ips if validate_ipv4(ip)]
                all_ips.extend(valid)
                print(f"找到{len(valid)}个有效IP")
            else:
                print(f"失败（状态码{resp.status_code}）")
        except Exception as e:
            print(f"出错: {str(e)[:30]}")

    # 去重排序
    unique_ips = sorted(list(set(all_ips)), key=lambda x: [int(p) for p in x.split('.')])
    print(f"\n2. 去重后共{len(unique_ips)}个IPv4地址")

    # 检测可用性
    available = []
    print("\n3. 检测443端口可用性...")
    for i, ip in enumerate(unique_ips, 1):
        print(f"检测 {i}/{len(unique_ips)} {ip}...", end=' ')
        ok, delay = test_ip(ip)
        if ok:
            available.append((ip, delay))
            print(f"可用（{delay}ms）")
        else:
            print("不可用")

    # 保存可用IP
    if available:
        with open('IPlist.txt', 'w') as f:
            f.write('\n'.join([ip for ip, _ in available]))
        print(f"\n4. 已保存{len(available)}个可用IP到IPlist.txt")
    else:
        print("\n4. 未找到可用IP")

    # 获取地区和运营商并格式化
    print("\n5. 获取地区和运营商信息...")
    groups = defaultdict(list)
    for ip, delay in available:
        code, isp = get_ip_info(ip)
        country = COUNTRY_MAPPING.get(code, "未知")
        groups[f"{country}-{isp}"].append((ip, code, delay))

    # 生成最终结果
    result = []
    for group in sorted(groups.keys()):
        for idx, (ip, code, _) in enumerate(sorted(groups[group], key=lambda x: x[2]), 1):
            result.append(f"{ip}#{code} {group}节点|{idx:02d}")

    if result:
        with open('Senflare.txt', 'w') as f:
            f.write('\n'.join(result))
        print(f"\n6. 已保存{len(result)}条记录到Senflare.txt")
    else:
        print("\n6. 无有效记录可保存")

    print(f"\n总耗时: {round(time.time()-start_time, 2)}秒")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n程序被中断")
    except Exception as e:
        print(f"\n出错: {str(e)}")
