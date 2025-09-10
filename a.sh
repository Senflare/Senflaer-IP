#!/bin/bash
set -e  # 脚本执行出错时立即退出

# 1. 检查是否为root用户
if [ "$(id -u)" -ne 0 ]; then
    echo "错误：请使用root用户执行此脚本（sudo -i切换到root后再运行）"
    exit 1
fi

echo "===== 开始执行Debian 13初始化脚本 ====="

# 2. 替换为华为源（先备份原源列表）
echo -e "\n1. 替换为华为源..."
BACKUP_SOURCES="/etc/apt/sources.list.bak_$(date +%Y%m%d)"
if [ ! -f "$BACKUP_SOURCES" ]; then
    cp /etc/apt/sources.list "$BACKUP_SOURCES"
    echo "已备份原源列表到：$BACKUP_SOURCES"
fi
# 写入华为源（Debian 13 codename为trixie）
cat > /etc/apt/sources.list << EOF
deb https://mirrors.huaweicloud.com/debian/ trixie main contrib non-free non-free-firmware
deb https://mirrors.huaweicloud.com/debian/ trixie-updates main contrib non-free non-free-firmware
deb https://mirrors.huaweicloud.com/debian/ trixie-backports main contrib non-free non-free-firmware
deb https://mirrors.huaweicloud.com/debian-security/ trixie-security main contrib non-free non-free-firmware
EOF
echo "华为源替换完成"

# 3. 更新软件包列表 + 配置SSH
echo -e "\n2. 配置SSH服务..."
apt update -y > /dev/null 2>&1
apt install -y openssh-server ufw > /dev/null 2>&1
systemctl enable --now ssh


# 允许root账户SSH登录
sed -i 's/^#PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config
sed -i 's/^PermitRootLogin.*/PermitRootLogin yes/' /etc/ssh/sshd_config

if sshd -t > /dev/null 2>&1; then
    systemctl restart ssh
    echo "SSH配置完成：允许root登录，服务已重启"
else
    echo "错误：SSH配置文件无效"
    exit 1
fi

# 4. 配置静态IP（使用NetworkManager）
echo -e "\n3. 配置静态IP（192.168.8.199）..."
DEFAULT_NIC=$(ip link show | grep -v "lo:" | grep -o "^\w\+" | head -n 1)
if [ -z "$DEFAULT_NIC" ]; then
    echo "错误：未检测到有效网卡，请手动指定网卡名"
    exit 1
fi
echo "检测到默认网卡：$DEFAULT_NIC（若不正确，请手动修改脚本）"

nmcli connection delete "$DEFAULT_NIC" > /dev/null 2>&1 || true
nmcli connection add \
    type ethernet \
    con-name "$DEFAULT_NIC" \
    ifname "$DEFAULT_NIC" \
    ip4 192.168.8.199/24 \
    gw4 192.168.8.1 \
    ipv4.dns 192.168.8.1 \
    autoconnect yes > /dev/null 2>&1
nmcli connection up "$DEFAULT_NIC" > /dev/null 2>&1
echo "静态IP配置完成"

# 5. 重启服务器
echo -e "\n===== 所有配置已完成 ====="
echo "重启后可通过：ssh root@192.168.8.199 连接"
read -p "是否立即重启？(y/n，默认y)：" REBOOT_CONFIRM
REBOOT_CONFIRM=${REBOOT_CONFIRM:-y}
if [ "$REBOOT_CONFIRM" = "y" ] || [ "$REBOOT_CONFIRM" = "Y" ]; then
    echo "10秒后重启..."
    sleep 10
    reboot
else
    echo "请手动执行 reboot 生效配置"
fi
