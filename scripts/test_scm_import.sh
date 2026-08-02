# @ai-generated
#!/bin/bash

HUAWEI_CLI="/usr/local/bin/hcloud"

"$HUAWEI_CLI" configure set --region=ap-southeast-1

CERT_FILE="/etc/letsencrypt/live/www.dftsh.top/cert.pem"
CHAIN_FILE="/etc/letsencrypt/live/www.dftsh.top/chain.pem"
KEY_FILE="/etc/letsencrypt/live/www.dftsh.top/privkey.pem"

CERT_CONTENT=$(cat "$CERT_FILE" | sed ':a;N;$!ba;s/\n/\\n/g')
CHAIN_CONTENT=$(cat "$CHAIN_FILE" | sed ':a;N;$!ba;s/\n/\\n/g')
KEY_CONTENT=$(cat "$KEY_FILE" | sed ':a;N;$!ba;s/\n/\\n/g')

echo "=== Testing SCM ImportCertificate with separate cert/chain ==="
echo "Cert length: ${#CERT_CONTENT}"
echo "Chain length: ${#CHAIN_CONTENT}"
echo "Key length: ${#KEY_CONTENT}"
echo ""

RESULT=$("$HUAWEI_CLI" SCM ImportCertificate \
    --name="www-dftsh-top-test" \
    --certificate="$CERT_CONTENT" \
    --certificate_chain="$CHAIN_CONTENT" \
    --private_key="$KEY_CONTENT" \
    --duplicate_check=false)

echo "Result:"
echo "$RESULT"
echo ""

echo "=== Querying certificates ==="
"$HUAWEI_CLI" SCM ListCertificates
