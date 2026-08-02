# @ai-generated
#!/bin/bash

LOG_FILE="/var/log/certbot-transinfo-renew.log"
LETSENCRYPT_DIR="/etc/letsencrypt/live"
DOMAINS=("wild_transinfo")

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

sync_certificate() {
    local domain="$1"
    local cert_path="$LETSENCRYPT_DIR/$domain/cert.pem"
    local chain_path="$LETSENCRYPT_DIR/$domain/chain.pem"
    local privkey_path="$LETSENCRYPT_DIR/$domain/privkey.pem"
    
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
    
    log "INFO" "Querying certificate list for domain: $domain"
    cert_list=$("$HUAWEI_CLI" SCM ListCertificates 2>&1)
    
    if echo "$cert_list" | grep -q "error"; then
        log "ERROR" "[FAIL] Failed to query certificates: $cert_list"
        return 1
    fi
    
    existing_id=$(echo "$cert_list" | grep -o "\"id\": *\"[^\"]*\"" | head -1 | cut -d'"' -f4)
    
    cert_name="${domain//./-}-cert"
    
    if [ -n "$existing_id" ]; then
        log "INFO" "Found existing certificate ID: $existing_id"
        log "INFO" "Updating certificate: $domain"
    else
        log "INFO" "No existing certificate found, creating new certificate for: $domain"
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

log "INFO" "=== Starting certificate sync process ==="

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

log "INFO" "Step 4: Syncing certificates to Huawei Cloud SCM..."

for domain in "${DOMAINS[@]}"; do
    log "INFO" "Processing domain: $domain"
    sync_certificate "$domain"
done

log "INFO" "=== Certificate sync process completed ==="
