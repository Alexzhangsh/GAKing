# @ai-generated
#!/bin/bash

LOG_FILE="/var/log/certbot-dftsh-renew.log"
LETSENCRYPT_DIR="/etc/letsencrypt/live"
CERT_NAME="wild_dftsh"
CDN_DOMAINS=("img.dftsh.top")

HUAWEI_CLI="/usr/local/bin/hcloud"
ENV_FILE="/etc/huawei_cloud_env"

log() {
    local level="$1"
    local message="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message" | tee -a "$LOG_FILE"
}

load_env() {
    if [ -f "$ENV_FILE" ]; then
        . "$ENV_FILE"
        log "INFO" "[OK] Environment file loaded: $ENV_FILE"
    else
        log "ERROR" "[FAIL] Environment file not found: $ENV_FILE"
        return 1
    fi

    if [ -z "$HUAWEI_AK" ] || [ -z "$HUAWEI_SK" ] || [ -z "$HUAWEI_DOMAIN_ID" ]; then
        log "ERROR" "[FAIL] HUAWEI_AK/SK/DOMAIN_ID not set"
        return 1
    fi

    HUAWEI_REGION=${HUAWEI_REGION:-cn-east-3}
    HUAWEI_SCM_REGION=${HUAWEI_SCM_REGION:-ap-southeast-1}

    return 0
}

configure_hcloud() {
    "$HUAWEI_CLI" configure set \
        --region="$HUAWEI_REGION" \
        --domain-id="$HUAWEI_DOMAIN_ID" \
        --access-key="$HUAWEI_AK" \
        --secret-key="$HUAWEI_SK" >> "$LOG_FILE" 2>&1

    if [ $? -eq 0 ]; then
        log "INFO" "[OK] hcloud configured with region: $HUAWEI_REGION"
        return 0
    else
        log "ERROR" "[FAIL] Failed to configure hcloud"
        return 1
    fi
}

sync_certificate_to_scm() {
    local cert_path="$LETSENCRYPT_DIR/$CERT_NAME/cert.pem"
    local chain_path="$LETSENCRYPT_DIR/$CERT_NAME/chain.pem"
    local privkey_path="$LETSENCRYPT_DIR/$CERT_NAME/privkey.pem"

    if [ ! -f "$cert_path" ]; then
        log "ERROR" "[FAIL] Cert file not found: $cert_path"
        return 1
    fi

    if [ ! -f "$chain_path" ]; then
        log "ERROR" "[FAIL] Chain file not found: $chain_path"
        return 1
    fi

    if [ ! -f "$privkey_path" ]; then
        log "ERROR" "[FAIL] Private key file not found: $privkey_path"
        return 1
    fi

    cert_content=$(cat "$cert_path" | sed ':a;N;$!ba;s/\n/\\n/g')
    chain_content=$(cat "$chain_path" | sed ':a;N;$!ba;s/\n/\\n/g')
    privkey_content=$(cat "$privkey_path" | sed ':a;N;$!ba;s/\n/\\n/g')

    if [ -z "$cert_content" ] || [ -z "$chain_content" ] || [ -z "$privkey_content" ]; then
        log "ERROR" "[FAIL] Certificate content is empty"
        return 1
    fi

    log "INFO" "Cert length: ${#cert_content}, Chain length: ${#chain_content}, Key length: ${#privkey_content}"

    log "INFO" "Switching to SCM region: $HUAWEI_SCM_REGION"
    "$HUAWEI_CLI" configure set --region="$HUAWEI_SCM_REGION" >> "$LOG_FILE" 2>&1

    log "INFO" "Querying certificate list for: $CERT_NAME"
    cert_list=$("$HUAWEI_CLI" SCM ListCertificates 2>&1)

    if echo "$cert_list" | grep -q "error"; then
        log "ERROR" "[FAIL] Failed to query certificates: $cert_list"
        return 1
    fi

    existing_id=$(echo "$cert_list" | python3 -c "
import sys, json
data = json.load(sys.stdin)
for cert in data.get('certificates', []):
    if cert.get('name') == 'wild_dftsh-cert':
        print(cert['id'])
        break
" 2>/dev/null)

    cert_name="wild_dftsh-cert"

    if [ -n "$existing_id" ]; then
        log "INFO" "Found existing dftsh certificate ID: $existing_id"
        log "INFO" "Updating certificate: $CERT_NAME"
    else
        log "INFO" "No existing dftsh certificate found, creating new certificate for: $CERT_NAME"
    fi

    import_result=$("$HUAWEI_CLI" SCM ImportCertificate \
        --name="$cert_name" \
        --certificate="$cert_content" \
        --certificate_chain="$chain_content" \
        --private_key="$privkey_content" \
        --duplicate_check=false \
        2>&1)

    if echo "$import_result" | grep -q "error"; then
        log "ERROR" "[FAIL] Failed to import certificate: $import_result"
        "$HUAWEI_CLI" configure set --region="$HUAWEI_REGION" >> "$LOG_FILE" 2>&1
        return 1
    else
        log "INFO" "[OK] Certificate synced successfully: $import_result"
    fi

    log "INFO" "Switching back to business region: $HUAWEI_REGION"
    "$HUAWEI_CLI" configure set --region="$HUAWEI_REGION" >> "$LOG_FILE" 2>&1

    return 0
}

update_cdn_certificates() {
    log "INFO" "Step 5: Updating CDN certificates..."

    "$HUAWEI_CLI" configure set --region="cn-north-1" >> "$LOG_FILE" 2>&1
    log "INFO" "Switched to CDN region: cn-north-1"

    for domain in "${CDN_DOMAINS[@]}"; do
        log "INFO" "--- Processing CDN domain: $domain ---"

        local domain_id
        domain_id=$("$HUAWEI_CLI" CDN ShowCertificatesHttpsInfo/v2 --domain_name="$domain" 2>&1 | python3 -c "
import sys, json
data = json.load(sys.stdin)
if data.get('https'):
    print(data['https'][0]['domain_id'])
" 2>/dev/null)

        if [ -z "$domain_id" ]; then
            log "ERROR" "[FAIL] Failed to get domain ID for: $domain"
            continue
        fi

        log "INFO" "Domain ID for $domain: $domain_id"

        local fullchain_path="$LETSENCRYPT_DIR/$CERT_NAME/fullchain.pem"
        local privkey_path="$LETSENCRYPT_DIR/$CERT_NAME/privkey.pem"

        if [ ! -f "$fullchain_path" ]; then
            log "ERROR" "[FAIL] Fullchain file not found: $fullchain_path"
            continue
        fi

        if [ ! -f "$privkey_path" ]; then
            log "ERROR" "[FAIL] Private key file not found: $privkey_path"
            continue
        fi

        local fullchain_content
        fullchain_content=$(cat "$fullchain_path" | sed ':a;N;$!ba;s/\n/\\n/g')
        local privkey_content
        privkey_content=$(cat "$privkey_path" | sed ':a;N;$!ba;s/\n/\\n/g')

        local update_result
        update_result=$("$HUAWEI_CLI" CDN UpdateHttpsInfo \
            --domain_id="$domain_id" \
            --https.cert_name="$CERT_NAME" \
            --https.https_status=3 \
            --https.certificate_type=0 \
            --https.certificate="$fullchain_content" \
            --https.private_key="$privkey_content" \
            --https.http2=1 \
            --https.force_redirect_https=1 2>&1)

        if echo "$update_result" | grep -q "error"; then
            log "ERROR" "[FAIL] Failed to update CDN certificate for $domain: $update_result"
        else
            log "INFO" "[OK] CDN certificate updated successfully for: $domain"
        fi
    done

    return 0
}

verify_cdn_certificates() {
    log "INFO" "Step 6: Verifying CDN certificates..."
    sleep 30

    for domain in "${CDN_DOMAINS[@]}"; do
        log "INFO" "--- Verifying CDN domain: $domain ---"

        local cert_info
        cert_info=$(echo | openssl s_client -connect "$domain:443" -servername "$domain" 2>/dev/null | openssl x509 -noout -subject -dates 2>/dev/null || true)

        if [ -n "$cert_info" ]; then
            log "INFO" "[OK] CDN cert verified for $domain:"
            echo "$cert_info" | while read line; do
                log "INFO" "  $line"
            done
        else
            log "WARN" "[WARN] Failed to verify CDN cert for $domain (may be caching)"
        fi
    done

    return 0
}

log "INFO" "=== Starting dftsh certificate sync process ==="

log "INFO" "Step 1: Loading environment variables..."
if ! load_env; then
    log "ERROR" "[FAIL] Failed to load environment variables, exiting"
    exit 1
fi

log "INFO" "Step 2: Configuring hcloud..."
if ! configure_hcloud; then
    log "ERROR" "[FAIL] Failed to configure hcloud, exiting"
    exit 1
fi

log "INFO" "Step 3: Reloading Nginx..."
if systemctl reload nginx; then
    log "INFO" "[OK] Nginx reloaded successfully"
else
    log "ERROR" "[FAIL] Failed to reload Nginx"
fi

log "INFO" "Step 4: Syncing dftsh certificate to Huawei Cloud SCM..."
sync_certificate_to_scm

update_cdn_certificates

verify_cdn_certificates

log "INFO" "=== dftsh certificate sync process completed ==="