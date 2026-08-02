# @ai-generated
#!/bin/bash
set -euo pipefail

LOG_FILE="/var/log/certbot-cdn-sync.log"
MAX_LOG_SIZE=10485760

LETSENCRYPT_DIR="/etc/letsencrypt/live"
CERT_NAME="wild_dftsh"
CDN_DOMAINS=("img.yyhpinfo.com")

HUAWEI_CLI="/usr/local/bin/hcloud"
ENV_FILE="${SCRIPT_DIR:-$(dirname "$0")}/.env.huawei"

MAX_RETRIES=3
RETRY_DELAY=10
CDN_PROPAGATION_DELAY=60

WECOM_WEBHOOK=""
DINGTALK_WEBHOOK=""

log() {
    local level="$1"
    local message="$2"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    echo "[${timestamp}] [${level}] ${message}" | tee -a "${LOG_FILE}"
}

log_rotate() {
    if [ -f "${LOG_FILE}" ]; then
        local size
        size=$(stat -f%z "${LOG_FILE}" 2>/dev/null || stat -c%s "${LOG_FILE}" 2>/dev/null || echo 0)
        if [ "${size}" -gt "${MAX_LOG_SIZE}" ]; then
            mv "${LOG_FILE}" "${LOG_FILE}.old"
            log "INFO" "Log rotated: old log moved to ${LOG_FILE}.old"
        fi
    fi
}

load_env() {
    if [ -f "${ENV_FILE}" ]; then
        set -a
        . "${ENV_FILE}"
        set +a
        log "INFO" "[OK] Environment file loaded: ${ENV_FILE}"
    else
        log "ERROR" "[FAIL] Environment file not found: ${ENV_FILE}"
        return 1
    fi

    if [ -z "${HUAWEI_AK:-}" ] || [ -z "${HUAWEI_SK:-}" ] || [ -z "${HUAWEI_DOMAIN_ID:-}" ]; then
        log "ERROR" "[FAIL] HUAWEI_AK/SK/DOMAIN_ID not set in environment"
        return 1
    fi

    HUAWEI_REGION="${HUAWEI_REGION:-cn-east-3}"
    return 0
}

configure_hcloud() {
    "${HUAWEI_CLI}" configure set \
        --region="${HUAWEI_REGION}" \
        --domain-id="${HUAWEI_DOMAIN_ID}" \
        --access-key="${HUAWEI_AK}" \
        --secret-key="${HUAWEI_SK}" >> "${LOG_FILE}" 2>&1

    if [ $? -eq 0 ]; then
        log "INFO" "[OK] hcloud configured with region: ${HUAWEI_REGION}"
        return 0
    else
        log "ERROR" "[FAIL] Failed to configure hcloud"
        return 1
    fi
}

read_cert_files() {
    local fullchain_path="${LETSENCRYPT_DIR}/${CERT_NAME}/fullchain.pem"
    local privkey_path="${LETSENCRYPT_DIR}/${CERT_NAME}/privkey.pem"

    if [ ! -f "${fullchain_path}" ]; then
        log "ERROR" "[FAIL] Fullchain file not found: ${fullchain_path}"
        return 1
    fi

    if [ ! -f "${privkey_path}" ]; then
        log "ERROR" "[FAIL] Private key file not found: ${privkey_path}"
        return 1
    fi

    local fullchain_raw
    fullchain_raw=$(cat "${fullchain_path}")
    local cert_count
    cert_count=$(echo "${fullchain_raw}" | grep -c "BEGIN CERTIFICATE" || true)
    log "INFO" "Fullchain contains ${cert_count} certificate(s)"

    if ! echo "${fullchain_raw}" | grep -q "BEGIN CERTIFICATE"; then
        log "ERROR" "[FAIL] Fullchain content invalid: no BEGIN CERTIFICATE found"
        return 1
    fi

    local privkey_raw
    privkey_raw=$(cat "${privkey_path}")
    if ! echo "${privkey_raw}" | grep -qE "BEGIN (RSA )?PRIVATE KEY"; then
        log "ERROR" "[FAIL] Private key content invalid"
        return 1
    fi

    FULLCHAIN_CONTENT=$(python3 -c "
import sys
with open('${fullchain_path}', 'r') as f:
    content = f.read()
print(content.replace('\\n', '\\\\n'), end='')
")
    PRIVKEY_CONTENT=$(python3 -c "
import sys
with open('${privkey_path}', 'r') as f:
    content = f.read()
print(content.replace('\\n', '\\\\n'), end='')
")

    if [ -z "${FULLCHAIN_CONTENT}" ] || [ -z "${PRIVKEY_CONTENT}" ]; then
        log "ERROR" "[FAIL] Certificate content is empty after escaping"
        return 1
    fi

    log "INFO" "Fullchain escaped length: ${#FULLCHAIN_CONTENT}"
    log "INFO" "Privkey escaped length: ${#PRIVKEY_CONTENT}"
    return 0
}

get_local_cert_dates() {
    local cert_path="${LETSENCRYPT_DIR}/${CERT_NAME}/cert.pem"
    if [ ! -f "${cert_path}" ]; then
        echo "N/A"
        return 1
    fi

    local not_before not_after
    not_before=$(openssl x509 -in "${cert_path}" -noout -startdate 2>/dev/null | cut -d= -f2 || echo "unknown")
    not_after=$(openssl x509 -in "${cert_path}" -noout -enddate 2>/dev/null | cut -d= -f2 || echo "unknown")
    echo "notBefore=${not_before}, notAfter=${not_after}"
}

get_cdn_cert_info() {
    local domain="$1"
    log "INFO" "Querying CDN certificate info for: ${domain}"

    local result
    result=$("${HUAWEI_CLI}" CDN ShowCertificatesHttpsInfo/v2 \
        --domain_name="${domain}" 2>&1) || true

    if echo "${result}" | grep -qi "error"; then
        log "ERROR" "[FAIL] Failed to query CDN cert info: ${result}"
        return 1
    fi

    local parsed
    parsed=$(echo "${result}" | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    https = data.get('https', {})
    cert_type = https.get('certificate_type', 'unknown')
    cert_name = https.get('cert_name', 'unknown')
    cert_type_map = {'0': '自有证书', '1': 'SCM托管证书', '2': 'CCM托管证书'}
    type_name = cert_type_map.get(str(cert_type), str(cert_type))
    print(f'cert_type={type_name} (code={cert_type}), cert_name={cert_name}')
except Exception as e:
    print(f'parse_error: {e}')
" 2>/dev/null || echo "parse_failed")

    log "INFO" "CDN cert info: ${parsed}"
    return 0
}

update_cdn_certificate() {
    local domain="$1"
    local attempt=0

    while [ ${attempt} -lt ${MAX_RETRIES} ]; do
        attempt=$((attempt + 1))
        log "INFO" "Updating CDN certificate for ${domain} (attempt ${attempt}/${MAX_RETRIES})..."

        local result
        result=$("${HUAWEI_CLI}" CDN UpdateDomainMultiCertificates \
            --domain_name="${domain}" \
            --https.https_switch=1 \
            --https.cert_name="${CERT_NAME}-cdn" \
            --https.certificate_type=0 \
            --https.certificate_value="${FULLCHAIN_CONTENT}" \
            --https.private_key="${PRIVKEY_CONTENT}" 2>&1) || true

        if echo "${result}" | grep -qi "error"; then
            log "ERROR" "[FAIL] CDN cert update failed (attempt ${attempt}): ${result}"
            if [ ${attempt} -lt ${MAX_RETRIES} ]; then
                log "INFO" "Retrying in ${RETRY_DELAY} seconds..."
                sleep ${RETRY_DELAY}
            else
                log "ERROR" "[FAIL] All ${MAX_RETRIES} attempts failed for ${domain}"
                return 1
            fi
        else
            log "INFO" "[OK] CDN certificate update request accepted for ${domain}"
            log "DEBUG" "Response: ${result}"
            return 0
        fi
    done

    return 1
}

verify_cdn_cert() {
    local domain="$1"
    log "INFO" "Waiting ${CDN_PROPAGATION_DELAY}s for CDN propagation..."
    sleep ${CDN_PROPAGATION_DELAY}

    log "INFO" "Verifying CDN certificate for: ${domain}"

    local cert_dates
    cert_dates=$(echo | openssl s_client -connect "${domain}:443" -servername "${domain}" 2>/dev/null | \
        openssl x509 -noout -dates 2>/dev/null || true)

    if [ -z "${cert_dates}" ]; then
        log "WARN" "[WARN] Failed to verify via openssl (may be cached)"
        return 0
    fi

    log "INFO" "CDN node cert: ${cert_dates}"
    return 0
}

send_alert() {
    local level="$1"
    local title="$2"
    local message="$3"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')

    log "${level}" "ALERT: ${title} - ${message}"

    if [ -n "${WECOM_WEBHOOK}" ]; then
        local wecom_msg
        wecom_msg=$(cat <<EOF
{
    "msgtype": "markdown",
    "markdown": {
        "content": "### [${level}] ${title}\n> ${message}\n> 时间: ${timestamp}\n> 主机: $(hostname)"
    }
}
EOF
)
        curl -s -X POST "${WECOM_WEBHOOK}" \
            -H "Content-Type: application/json" \
            -d "${wecom_msg}" >> "${LOG_FILE}" 2>&1 || true
    fi

    if [ -n "${DINGTALK_WEBHOOK}" ]; then
        local dingtalk_msg
        dingtalk_msg=$(cat <<EOF
{
    "msgtype": "markdown",
    "markdown": {
        "title": "${title}",
        "text": "### [${level}] ${title}\n\n${message}\n\n时间: ${timestamp}\n\n主机: $(hostname)"
    }
}
EOF
)
        curl -s -X POST "${DINGTALK_WEBHOOK}" \
            -H "Content-Type: application/json" \
            -d "${dingtalk_msg}" >> "${LOG_FILE}" 2>&1 || true
    fi
}

main() {
    log_rotate

    log "INFO" "========================================"
    log "INFO" "=== CDN Certificate Sync Process Start ==="
    log "INFO" "========================================"

    log "INFO" "Step 1: Loading environment variables..."
    if ! load_env; then
        send_alert "ERROR" "CDN证书同步失败" "环境变量加载失败，请检查 ${ENV_FILE}"
        exit 1
    fi

    log "INFO" "Step 2: Configuring hcloud CLI..."
    if ! configure_hcloud; then
        send_alert "ERROR" "CDN证书同步失败" "hcloud配置失败"
        exit 1
    fi

    log "INFO" "Step 3: Reading local certificate files..."
    if ! read_cert_files; then
        send_alert "ERROR" "CDN证书同步失败" "证书文件读取失败"
        exit 1
    fi

    local local_dates
    local_dates=$(get_local_cert_dates)
    log "INFO" "Local certificate: ${local_dates}"

    log "INFO" "Step 4: Processing CDN domains..."
    FAILED_DOMAINS=()
    SUCCESS_DOMAINS=()

    for domain in "${CDN_DOMAINS[@]}"; do
        log "INFO" "--- Processing domain: ${domain} ---"

        get_cdn_cert_info "${domain}" || true

        if update_cdn_certificate "${domain}"; then
            log "INFO" "[OK] Domain ${domain} update request successful"
            SUCCESS_DOMAINS+=("${domain}")
            verify_cdn_cert "${domain}" || true
        else
            log "ERROR" "[FAIL] Domain ${domain} update failed"
            FAILED_DOMAINS+=("${domain}")
        fi
    done

    log "INFO" "========================================"
    log "INFO" "=== Summary ==="
    log "INFO" "Successful domains: ${#SUCCESS_DOMAINS[@]}"
    for d in "${SUCCESS_DOMAINS[@]}"; do
        log "INFO" "  - ${d} [OK]"
    done
    log "INFO" "Failed domains: ${#FAILED_DOMAINS[@]}"
    for d in "${FAILED_DOMAINS[@]}"; do
        log "ERROR" "  - ${d} [FAIL]"
    done
    log "INFO" "========================================"

    if [ ${#FAILED_DOMAINS[@]} -eq 0 ]; then
        log "INFO" "[OK] All CDN certificates updated successfully"
        send_alert "INFO" "CDN证书同步成功" "所有域名证书更新完成: ${SUCCESS_DOMAINS[*]}"
        log "INFO" "=== CDN Certificate Sync Process Completed Successfully ==="
        exit 0
    else
        log "ERROR" "[FAIL] Some domains failed: ${FAILED_DOMAINS[*]}"
        send_alert "ERROR" "CDN证书同步部分失败" "失败域名: ${FAILED_DOMAINS[*]}"
        log "ERROR" "=== CDN Certificate Sync Process Completed With Errors ==="
        exit 1
    fi
}

main "$@"
