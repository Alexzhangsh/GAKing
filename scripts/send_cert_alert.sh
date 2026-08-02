# @ai-generated
#!/bin/bash
set -euo pipefail

CONFIG_FILE="/etc/cdn_cert_alert_config"

load_config() {
    if [ -f "${CONFIG_FILE}" ]; then
        set -a
        . "${CONFIG_FILE}"
        set +a
    fi
}

send_wecom_alert() {
    local level="$1"
    local title="$2"
    local message="$3"

    if [ -z "${WECOM_WEBHOOK:-}" ]; then
        return 0
    fi

    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local hostname
    hostname=$(hostname)

    local payload
    payload=$(cat <<EOF
{
    "msgtype": "markdown",
    "markdown": {
        "content": "### [${level}] ${title}\n\n> ${message}\n\n> **时间**: ${timestamp}\n> **主机**: ${hostname}"
    }
}
EOF
)

    curl -s -X POST "${WECOM_WEBHOOK}" \
        -H "Content-Type: application/json" \
        -d "${payload}" > /dev/null 2>&1 || true
}

send_dingtalk_alert() {
    local level="$1"
    local title="$2"
    local message="$3"

    if [ -z "${DINGTALK_WEBHOOK:-}" ]; then
        return 0
    fi

    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    local hostname
    hostname=$(hostname)

    local payload
    payload=$(cat <<EOF
{
    "msgtype": "markdown",
    "markdown": {
        "title": "${title}",
        "text": "### [${level}] ${title}\n\n${message}\n\n**时间**: ${timestamp}\n\n**主机**: ${hostname}"
    }
}
EOF
)

    curl -s -X POST "${DINGTALK_WEBHOOK}" \
        -H "Content-Type: application/json" \
        -d "${payload}" > /dev/null 2>&1 || true
}

send_alert() {
    local level="$1"
    local title="$2"
    local message="$3"

    load_config
    send_wecom_alert "${level}" "${title}" "${message}"
    send_dingtalk_alert "${level}" "${title}" "${message}"
}

if [ $# -lt 2 ]; then
    echo "Usage: $0 <level> <title> [message]"
    echo "Example: $0 ERROR \"CDN证书同步失败\" \"img.dftsh.top 更新失败\""
    exit 1
fi

LEVEL="$1"
TITLE="$2"
MESSAGE="${3:-}"

send_alert "${LEVEL}" "${TITLE}" "${MESSAGE}"
echo "Alert sent: [${LEVEL}] ${TITLE}"
