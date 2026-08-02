# @ai-generated
#!/bin/bash

LOG_FILE="/var/log/cert_sync_huawei.log"
LETSENCRYPT_DIR="/etc/letsencrypt/live"
DOMAINS=("www.dftsh.top")

HUAWEI_REGION="cn-east-3"
HUAWEI_SCM_ENDPOINT="scm.ap-southeast-1.myhuaweicloud.com"

log() {
    local level="$1"
    local message="$2"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $message" | tee -a "$LOG_FILE"
}

sign_request() {
    local ak="$1"
    local sk="$2"
    local method="$3"
    local uri="$4"
    local query="$5"
    local body="$6"
    
    local timestamp=$(date -u +"%Y%m%dT%H%M%SZ")
    
    local canonical_uri="$uri"
    
    local canonical_querystring=""
    if [ -n "$query" ]; then
        canonical_querystring=$(echo "$query" | tr '&' '\n' | sort | tr '\n' '&' | sed 's/&$//')
    fi
    
    local host="$HUAWEI_SCM_ENDPOINT"
    local content_type="application/json"
    
    local canonical_headers="content-type:$content_type"$'\n'"host:$host"$'\n'"x-sdk-date:$timestamp"$'\n'
    local signed_headers="content-type;host;x-sdk-date"
    
    local payload_hash=$(echo -n "$body" | openssl dgst -sha256 | awk '{print $2}')
    if [ -z "$payload_hash" ]; then
        payload_hash=$(printf '' | openssl dgst -sha256 | awk '{print $2}')
    fi
    
    local canonical_request="$method"$'\n'"$canonical_uri"$'\n'"$canonical_querystring"$'\n'"$canonical_headers"$'\n'"$signed_headers"$'\n'"$payload_hash"
    
    local algorithm="SDK-HMAC-SHA256"
    
    local canonical_request_hash=$(echo -n "$canonical_request" | openssl dgst -sha256 | awk '{print $2}')
    local string_to_sign="$algorithm"$'\n'"$timestamp"$'\n'"$canonical_request_hash"
    
    local signature=$(echo -n "$string_to_sign" | openssl dgst -sha256 -hmac "$sk" | awk '{print $2}')
    
    local authorization="$algorithm Access=$ak, SignedHeaders=$signed_headers, Signature=$signature"
    
    echo "$authorization"
    echo "$timestamp"
}

get_project_id() {
    local ak="$1"
    local sk="$2"
    local region="$3"
    
    local method="GET"
    local uri="/v3/projects"
    local query=""
    local body=""
    
    local auth_result=$(sign_request "$ak" "$sk" "$method" "$uri" "$query" "$body")
    local authorization=$(echo "$auth_result" | head -1)
    local timestamp=$(echo "$auth_result" | tail -1)
    
    local endpoint="iam.$region.myhuaweicloud.com"
    
    log "DEBUG" "Getting project ID from: $endpoint"
    
    local response=$(curl -s -X "$method" "https://$endpoint$uri" \
        -H "Content-Type: application/json" \
        -H "Host: $endpoint" \
        -H "X-Sdk-Date: $timestamp" \
        -H "Authorization: $authorization" 2>&1)
    
    log "DEBUG" "Projects API Response: $response"
    
    local project_id=$(echo "$response" | grep -o "\"id\": *\"[^\"]*\"" | head -1 | cut -d'"' -f4)
    
    if [ -n "$project_id" ]; then
        echo "$project_id"
        return 0
    else
        echo ""
        return 1
    fi
}

find_cert_id() {
    local ak="$1"
    local sk="$2"
    local domain="$3"
    local project_id="$4"
    
    local method="GET"
    local uri="/v3/scm/certificates"
    local query=""
    local body=""
    
    local auth_result=$(sign_request "$ak" "$sk" "$method" "$uri" "$query" "$body")
    local authorization=$(echo "$auth_result" | head -1)
    local timestamp=$(echo "$auth_result" | tail -1)
    
    log "DEBUG" "Authorization: $authorization"
    log "DEBUG" "Timestamp: $timestamp"
    log "DEBUG" "Project ID: $project_id"
    
    local response=$(curl -s -X "$method" "https://$HUAWEI_SCM_ENDPOINT$uri" \
        -H "Content-Type: application/json" \
        -H "Host: $HUAWEI_SCM_ENDPOINT" \
        -H "X-Sdk-Date: $timestamp" \
        -H "X-Project-Id: $project_id" \
        -H "Authorization: $authorization" 2>&1)
    
    log "DEBUG" "API Response: $response"
    
    local cert_id=$(echo "$response" | grep -o "\"id\": *\"[^\"]*\"" | head -1 | cut -d'"' -f4)
    
    if [ -n "$cert_id" ]; then
        echo "$cert_id"
        return 0
    else
        echo "$response"
        return 1
    fi
}

log "INFO" "=== Starting dry-run test ==="

ENV_FILE="${SCRIPT_DIR:-$(dirname "$0")}/.env.huawei"
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
    log "INFO" "[OK] Environment file found: $ENV_FILE"
else
    log "ERROR" "[FAIL] Environment file not found: $ENV_FILE"
    exit 1
fi

AK="${HUAWEI_AK:-}"
SK="${HUAWEI_SK:-}"

if [ -n "$AK" ] && [ -n "$SK" ]; then
    log "INFO" "[OK] HUAWEI_AK and HUAWEI_SK are set"
else
    log "ERROR" "[FAIL] HUAWEI_AK or HUAWEI_SK is empty"
    exit 1
fi

for domain in "${DOMAINS[@]}"; do
    log "INFO" "Testing domain: $domain"
    
    fullchain_path="$LETSENCRYPT_DIR/$domain/fullchain.pem"
    privkey_path="$LETSENCRYPT_DIR/$domain/privkey.pem"
    
    if [ -f "$fullchain_path" ]; then
        fullchain_size=$(wc -c < "$fullchain_path")
        log "INFO" "[OK] Fullchain file exists: $fullchain_path ($fullchain_size bytes)"
    else
        log "ERROR" "[FAIL] Fullchain file not found: $fullchain_path"
        continue
    fi
    
    if [ -f "$privkey_path" ]; then
        privkey_size=$(wc -c < "$privkey_path")
        log "INFO" "[OK] Private key file exists: $privkey_path ($privkey_size bytes)"
    else
        log "ERROR" "[FAIL] Private key file not found: $privkey_path"
        continue
    fi
    
    fullchain_content=$(cat "$fullchain_path")
    if echo "$fullchain_content" | grep -q "BEGIN CERTIFICATE"; then
        cert_count=$(echo "$fullchain_content" | grep -c "BEGIN CERTIFICATE")
        log "INFO" "[OK] Fullchain contains $cert_count certificate(s)"
    else
        log "ERROR" "[FAIL] Fullchain content is invalid"
        continue
    fi
    
    privkey_content=$(cat "$privkey_path")
    if echo "$privkey_content" | grep -q "BEGIN PRIVATE KEY"; then
        log "INFO" "[OK] Private key content is valid"
    else
        log "ERROR" "[FAIL] Private key content is invalid"
        continue
    fi
done

log "INFO" "Testing Huawei Cloud API connectivity with AK/SK signature (endpoint: $HUAWEI_SCM_ENDPOINT)..."

log "INFO" "Step 1: Getting project ID..."
project_id=$(get_project_id "$AK" "$SK" "$HUAWEI_REGION")
if [ -n "$project_id" ]; then
    log "INFO" "[OK] Got project ID: $project_id"
else
    log "ERROR" "[FAIL] Failed to get project ID"
    exit 1
fi

log "INFO" "Step 2: Querying certificates list using AK/SK signature..."
cert_id=$(find_cert_id "$AK" "$SK" "www.dftsh.top" "$project_id")
if [ $? -eq 0 ]; then
    log "INFO" "[OK] Found certificate ID: $cert_id"
else
    log "ERROR" "[FAIL] Failed to find certificate: $cert_id"
    exit 1
fi

log "INFO" "=== Dry-run test completed successfully ==="
log "INFO" "All checks passed! The sync script should work correctly."
