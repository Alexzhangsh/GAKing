# @ai-generated
#!/bin/bash
set -euo pipefail

LETSENCRYPT_DIR="/etc/letsencrypt/live"
CERT_NAME="wild_dftsh"
CDN_DOMAINS=("img.dftsh.top")

WARN_DAYS=30
CRIT_DAYS=7

COLOR_RED='\033[0;31m'
COLOR_GREEN='\033[0;32m'
COLOR_YELLOW='\033[1;33m'
COLOR_BLUE='\033[0;34m'
COLOR_NC='\033[0m'

print_header() {
    echo -e "${COLOR_BLUE}============================================${COLOR_NC}"
    echo -e "${COLOR_BLUE}  CDN 证书有效期验证工具${COLOR_NC}"
    echo -e "${COLOR_BLUE}============================================${COLOR_NC}"
    echo ""
}

print_section() {
    echo -e "${COLOR_BLUE}--- $1 ---${COLOR_NC}"
}

get_days_until_expiry() {
    local end_date_str="$1"
    local end_date_epoch
    end_date_epoch=$(date -d "${end_date_str}" +%s 2>/dev/null || date -j -f "%b %d %H:%M:%S %Y %Z" "${end_date_str}" +%s 2>/dev/null || echo 0)

    if [ "${end_date_epoch}" -eq 0 ]; then
        echo "-1"
        return 1
    fi

    local now_epoch
    now_epoch=$(date +%s)
    local diff_days=$(( (end_date_epoch - now_epoch) / 86400 ))
    echo "${diff_days}"
}

check_local_cert() {
    print_section "本地证书 (${CERT_NAME})"

    local cert_path="${LETSENCRYPT_DIR}/${CERT_NAME}/cert.pem"
    local fullchain_path="${LETSENCRYPT_DIR}/${CERT_NAME}/fullchain.pem"
    local privkey_path="${LETSENCRYPT_DIR}/${CERT_NAME}/privkey.pem"

    if [ ! -f "${cert_path}" ]; then
        echo -e "${COLOR_RED}✗ 证书文件不存在: ${cert_path}${COLOR_NC}"
        return 1
    fi

    local not_before not_after subject issuer
    not_before=$(openssl x509 -in "${cert_path}" -noout -startdate 2>/dev/null | cut -d= -f2 || echo "unknown")
    not_after=$(openssl x509 -in "${cert_path}" -noout -enddate 2>/dev/null | cut -d= -f2 || echo "unknown")
    subject=$(openssl x509 -in "${cert_path}" -noout -subject 2>/dev/null | sed 's/subject=//' || echo "unknown")
    issuer=$(openssl x509 -in "${cert_path}" -noout -issuer 2>/dev/null | sed 's/issuer=//' || echo "unknown")

    local cert_count=0
    if [ -f "${fullchain_path}" ]; then
        cert_count=$(grep -c "BEGIN CERTIFICATE" "${fullchain_path}" 2>/dev/null || echo 0)
    fi

    local days_left
    days_left=$(get_days_until_expiry "${not_after}")

    echo "  证书路径: ${cert_path}"
    echo "  主题: ${subject}"
    echo "  签发者: ${issuer}"
    echo "  生效时间: ${not_before}"
    echo "  到期时间: ${not_after}"
    echo "  证书链长度: ${cert_count}"

    if [ "${days_left}" -le 0 ]; then
        echo -e "  剩余天数: ${COLOR_RED}已过期${COLOR_NC}"
    elif [ "${days_left}" -le "${CRIT_DAYS}" ]; then
        echo -e "  剩余天数: ${COLOR_RED}${days_left} 天 (严重)${COLOR_NC}"
    elif [ "${days_left}" -le "${WARN_DAYS}" ]; then
        echo -e "  剩余天数: ${COLOR_YELLOW}${days_left} 天 (警告)${COLOR_NC}"
    else
        echo -e "  剩余天数: ${COLOR_GREEN}${days_left} 天${COLOR_NC}"
    fi

    echo ""
}

check_cdn_cert() {
    local domain="$1"
    print_section "CDN节点证书 (${domain})"

    local cert_output
    cert_output=$(echo | openssl s_client -connect "${domain}:443" -servername "${domain}" 2>/dev/null) || true

    if [ -z "${cert_output}" ]; then
        echo -e "${COLOR_RED}✗ 无法连接到 ${domain}:443${COLOR_NC}"
        echo ""
        return 1
    fi

    local not_before not_after subject issuer
    not_before=$(echo "${cert_output}" | openssl x509 -noout -startdate 2>/dev/null | cut -d= -f2 || echo "unknown")
    not_after=$(echo "${cert_output}" | openssl x509 -noout -enddate 2>/dev/null | cut -d= -f2 || echo "unknown")
    subject=$(echo "${cert_output}" | openssl x509 -noout -subject 2>/dev/null | sed 's/subject=//' || echo "unknown")
    issuer=$(echo "${cert_output}" | openssl x509 -noout -issuer 2>/dev/null | sed 's/issuer=//' || echo "unknown")

    local days_left
    days_left=$(get_days_until_expiry "${not_after}")

    echo "  域名: ${domain}"
    echo "  主题: ${subject}"
    echo "  签发者: ${issuer}"
    echo "  生效时间: ${not_before}"
    echo "  到期时间: ${not_after}"

    if [ "${days_left}" -le 0 ]; then
        echo -e "  剩余天数: ${COLOR_RED}已过期${COLOR_NC}"
    elif [ "${days_left}" -le "${CRIT_DAYS}" ]; then
        echo -e "  剩余天数: ${COLOR_RED}${days_left} 天 (严重)${COLOR_NC}"
    elif [ "${days_left}" -le "${WARN_DAYS}" ]; then
        echo -e "  剩余天数: ${COLOR_YELLOW}${days_left} 天 (警告)${COLOR_NC}"
    else
        echo -e "  剩余天数: ${COLOR_GREEN}${days_left} 天${COLOR_NC}"
    fi

    echo ""
}

compare_certs() {
    local domain="$1"
    print_section "本地 vs CDN 证书对比"

    local cert_path="${LETSENCRYPT_DIR}/${CERT_NAME}/cert.pem"

    if [ ! -f "${cert_path}" ]; then
        echo -e "${COLOR_YELLOW}⚠ 本地证书不存在，跳过对比${COLOR_NC}"
        echo ""
        return 0
    fi

    local local_fingerprint cdn_fingerprint
    local_fingerprint=$(openssl x509 -in "${cert_path}" -noout -fingerprint -sha256 2>/dev/null || echo "")

    local cert_output
    cert_output=$(echo | openssl s_client -connect "${domain}:443" -servername "${domain}" 2>/dev/null) || true

    if [ -z "${cert_output}" ]; then
        echo -e "${COLOR_YELLOW}⚠ 无法获取CDN证书，跳过对比${COLOR_NC}"
        echo ""
        return 0
    fi

    cdn_fingerprint=$(echo "${cert_output}" | openssl x509 -noout -fingerprint -sha256 2>/dev/null || echo "")

    echo "  本地证书指纹: ${local_fingerprint}"
    echo "  CDN证书指纹:  ${cdn_fingerprint}"

    if [ -n "${local_fingerprint}" ] && [ -n "${cdn_fingerprint}" ]; then
        if [ "${local_fingerprint}" = "${cdn_fingerprint}" ]; then
            echo -e "  对比结果: ${COLOR_GREEN}✓ 一致${COLOR_NC}"
        else
            echo -e "  对比结果: ${COLOR_YELLOW}⚠ 不一致 (CDN可能尚未同步最新证书)${COLOR_NC}"
        fi
    fi

    echo ""
}

check_sync_log() {
    local log_file="/var/log/certbot-cdn-sync.log"
    print_section "最近同步日志"

    if [ ! -f "${log_file}" ]; then
        echo -e "${COLOR_YELLOW}⚠ 日志文件不存在: ${log_file}${COLOR_NC}"
        echo ""
        return 0
    fi

    echo "  日志文件: ${log_file}"
    echo "  最近20行:"
    echo ""
    tail -20 "${log_file}" | sed 's/^/    /'
    echo ""
}

print_footer() {
    echo -e "${COLOR_BLUE}============================================${COLOR_NC}"
    echo -e "验证完成。使用方法:"
    echo "  直接运行: bash $0"
    echo "  指定告警阈值: WARN_DAYS=15 CRIT_DAYS=3 bash $0"
    echo -e "${COLOR_BLUE}============================================${COLOR_NC}"
}

main() {
    print_header

    check_local_cert

    for domain in "${CDN_DOMAINS[@]}"; do
        check_cdn_cert "${domain}"
        compare_certs "${domain}"
    done

    check_sync_log

    print_footer
}

main "$@"
