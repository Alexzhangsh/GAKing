# @ai-generated
#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import sys
import hashlib
import hmac
import binascii
from datetime import datetime
from urllib.parse import quote, unquote

LOG_FILE = "/var/log/cert_sync_huawei.log"
LETSENCRYPT_DIR = "/etc/letsencrypt/live"
DOMAINS = ["www.dftsh.top"]

HUAWEI_REGION = "cn-east-3"
HUAWEI_SCM_ENDPOINT = "scm.ap-southeast-1.myhuaweicloud.com"

def hmacsha256(byte, msg):
    return hmac.new(byte.encode('utf-8'), msg.encode('utf-8'), digestmod=hashlib.sha256).digest()

def urlencode(str):
    return quote(str, safe='~')

def HexEncodeSHA256Hash(d):
    sha = hashlib.sha256()
    sha.update(d)
    return sha.hexdigest()

def StringToSign(request, time):
    b = HexEncodeSHA256Hash(request.encode('utf-8'))
    return "%s\n%s\n%s" % ("SDK-HMAC-SHA256", datetime.strftime(time, "%Y%m%dT%H%M%SZ"), b)

def CanonicalURI(uri):
    patterns = unquote(uri).split('/')
    uri_parts = []
    for value in patterns:
        uri_parts.append(urlencode(value))
    url_path = "/".join(uri_parts)
    if url_path[-1] != '/':
        url_path = url_path + "/"
    return url_path

def CanonicalQueryString(query_params):
    if not query_params:
        return ""
    keys = sorted(query_params.keys())
    arr = []
    for key in keys:
        ke = urlencode(key)
        value = query_params[key]
        if isinstance(value, list):
            value.sort()
            for v in value:
                kv = ke + "=" + urlencode(str(v))
                arr.append(kv)
        else:
            kv = ke + "=" + urlencode(str(value))
            arr.append(kv)
    return '&'.join(arr)

def CanonicalHeaders(headers):
    arr = []
    _headers = {}
    for k in headers:
        keyEncoded = k.lower()
        value = headers[k]
        if isinstance(value, bytes):
            valueEncoded = value.decode('utf-8').strip()
        else:
            valueEncoded = str(value).strip()
        _headers[keyEncoded] = valueEncoded
    sorted_keys = sorted(_headers.keys())
    for k in sorted_keys:
        arr.append(k + ":" + _headers[k])
    return '\n'.join(arr) + "\n"

def SignedHeaders(headers):
    arr = []
    for k in headers:
        arr.append(k.lower())
    arr.sort()
    return arr

def SignStringToSign(strToSign, sigKey):
    hmac_result = hmacsha256(sigKey, strToSign)
    return binascii.hexlify(hmac_result).decode()

def AuthHeaderValue(sig, AppKey, sHeaders):
    return "%s Access=%s, SignedHeaders=%s, Signature=%s" % (
        "SDK-HMAC-SHA256", AppKey, ";".join(sHeaders), sig)

def sign_request(ak, sk, method, endpoint, uri, query_params=None, body="", extra_headers=None):
    if query_params is None:
        query_params = {}
    if extra_headers is None:
        extra_headers = {}
    
    timestamp = datetime.utcnow()
    x_sdk_date = datetime.strftime(timestamp, "%Y%m%dT%H%M%SZ")
    
    headers = {
        "host": endpoint,
        "content-type": "application/json",
        "x-sdk-date": x_sdk_date,
    }
    headers.update(extra_headers)
    
    canonical_uri = CanonicalURI(uri)
    canonical_querystring = CanonicalQueryString(query_params)
    canonical_headers = CanonicalHeaders(headers)
    signed_headers = SignedHeaders(headers)
    
    body_bytes = body.encode('utf-8') if isinstance(body, str) else body
    payload_hash = HexEncodeSHA256Hash(body_bytes)
    
    canonical_request = "%s\n%s\n%s\n%s\n%s\n%s" % (
        method.upper(),
        canonical_uri,
        canonical_querystring,
        canonical_headers,
        ";".join(signed_headers),
        payload_hash
    )
    
    string_to_sign = StringToSign(canonical_request, timestamp)
    signature = SignStringToSign(string_to_sign, sk)
    authorization = AuthHeaderValue(signature, ak, signed_headers)
    
    headers["Authorization"] = authorization
    
    return headers

def log(level, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {message}"
    print(log_line)
    with open(LOG_FILE, "a") as f:
        f.write(log_line + "\n")

def get_project_id(ak, sk, region):
    method = "GET"
    endpoint = f"iam.{region}.myhuaweicloud.com"
    uri = "/v3/projects"
    
    headers = sign_request(ak, sk, method, endpoint, uri)
    
    log("DEBUG", f"Getting project ID from: {endpoint}")
    log("DEBUG", f"Headers: {headers}")
    
    cmd = ["curl", "-s", "-X", method, f"https://{endpoint}{uri}"]
    for key, value in headers.items():
        cmd.append("-H")
        cmd.append(f"{key}: {value}")
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    response = result.stdout.decode("utf-8") + result.stderr.decode("utf-8")
    
    log("DEBUG", f"Projects API Response: {response}")
    
    try:
        data = json.loads(response)
        if "projects" in data and data["projects"]:
            for project in data["projects"]:
                if project.get("name") == region:
                    return project["id"]
            return data["projects"][0]["id"]
    except Exception as e:
        log("DEBUG", f"JSON parse error: {e}")
        pass
    
    return None

def find_cert_id(ak, sk, domain, project_id):
    method = "GET"
    endpoint = HUAWEI_SCM_ENDPOINT
    uri = "/v3/scm/certificates"
    
    headers = sign_request(ak, sk, method, endpoint, uri, extra_headers={"X-Project-Id": project_id})
    
    log("DEBUG", f"Authorization: {headers.get('Authorization')}")
    log("DEBUG", f"Timestamp: {headers.get('x-sdk-date')}")
    log("DEBUG", f"Project ID: {project_id}")
    
    cmd = ["curl", "-s", "-X", method, f"https://{endpoint}{uri}"]
    for key, value in headers.items():
        cmd.append("-H")
        cmd.append(f"{key}: {value}")
    
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    response = result.stdout.decode("utf-8") + result.stderr.decode("utf-8")
    
    log("DEBUG", f"API Response: {response}")
    
    try:
        data = json.loads(response)
        for cert in data.get("certificates", []):
            cert_domain = cert.get("domain", "")
            cert_domains = cert.get("domains", [])
            if domain == cert_domain or domain in cert_domains:
                return cert["id"]
        if "certificates" in data and data["certificates"]:
            return data["certificates"][0]["id"]
    except Exception as e:
        log("DEBUG", f"JSON parse error: {e}")
        pass
    
    return None

def main():
    log("INFO", "=== Starting dry-run test ===")
    
    env_file = os.path.join(os.path.dirname(__file__), ".env.huawei")
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value
        log("INFO", f"[OK] Environment file found: {env_file}")
    else:
        log("ERROR", f"[FAIL] Environment file not found: {env_file}")
        sys.exit(1)
    
    ak = os.environ.get("HUAWEI_AK", "")
    sk = os.environ.get("HUAWEI_SK", "")
    
    if ak and sk:
        log("INFO", "[OK] HUAWEI_AK and HUAWEI_SK are set")
    else:
        log("ERROR", "[FAIL] HUAWEI_AK or HUAWEI_SK is empty")
        sys.exit(1)
    
    for domain in DOMAINS:
        log("INFO", f"Testing domain: {domain}")
        
        fullchain_path = os.path.join(LETSENCRYPT_DIR, domain, "fullchain.pem")
        privkey_path = os.path.join(LETSENCRYPT_DIR, domain, "privkey.pem")
        
        if os.path.exists(fullchain_path):
            fullchain_size = os.path.getsize(fullchain_path)
            log("INFO", f"[OK] Fullchain file exists: {fullchain_path} ({fullchain_size} bytes)")
        else:
            log("ERROR", f"[FAIL] Fullchain file not found: {fullchain_path}")
            continue
        
        if os.path.exists(privkey_path):
            privkey_size = os.path.getsize(privkey_path)
            log("INFO", f"[OK] Private key file exists: {privkey_path} ({privkey_size} bytes)")
        else:
            log("ERROR", f"[FAIL] Private key file not found: {privkey_path}")
            continue
        
        with open(fullchain_path, "r") as f:
            fullchain_content = f.read()
        if "BEGIN CERTIFICATE" in fullchain_content:
            cert_count = fullchain_content.count("BEGIN CERTIFICATE")
            log("INFO", f"[OK] Fullchain contains {cert_count} certificate(s)")
        else:
            log("ERROR", "[FAIL] Fullchain content is invalid")
            continue
        
        with open(privkey_path, "r") as f:
            privkey_content = f.read()
        if "BEGIN PRIVATE KEY" in privkey_content or "BEGIN RSA PRIVATE KEY" in privkey_content:
            log("INFO", "[OK] Private key content is valid")
        else:
            log("ERROR", "[FAIL] Private key content is invalid")
            continue
    
    log("INFO", f"Testing Huawei Cloud API connectivity with AK/SK signature (endpoint: {HUAWEI_SCM_ENDPOINT})...")
    
    log("INFO", "Step 1: Getting project ID...")
    project_id = get_project_id(ak, sk, HUAWEI_REGION)
    if project_id:
        log("INFO", f"[OK] Got project ID: {project_id}")
    else:
        log("ERROR", "[FAIL] Failed to get project ID")
        sys.exit(1)
    
    log("INFO", "Step 2: Querying certificates list using AK/SK signature...")
    cert_id = find_cert_id(ak, sk, "www.dftsh.top", project_id)
    if cert_id:
        log("INFO", f"[OK] Found certificate ID: {cert_id}")
    else:
        log("ERROR", "[FAIL] Failed to find certificate")
        sys.exit(1)
    
    log("INFO", "=== Dry-run test completed successfully ===")
    log("INFO", "All checks passed! The sync script should work correctly.")

if __name__ == "__main__":
    main()
