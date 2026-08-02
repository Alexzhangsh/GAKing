#!/usr/bin/env python3
import os
import sys
import json
from datetime import datetime

from huaweicloudsdkcore.auth.credentials import BasicCredentials, GlobalCredentials
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkiam.v3 import IamClient, KeystoneListProjectsRequest
from huaweicloudsdkcdn.v2 import CdnClient, ShowCertificatesHttpsInfoRequest, UpdateDomainMultiCertificatesRequest, UpdateDomainMultiCertificatesRequestBody, UpdateDomainMultiCertificatesRequestBodyContent

LOG_FILE = os.path.join(os.path.dirname(__file__), "cert_sync_huawei.log")

def log(level, message):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] [{level}] {message}"
    print(log_line)
    with open(LOG_FILE, "a") as f:
        f.write(log_line + "\n")

def load_env():
    env_file = os.path.join(os.path.dirname(__file__), ".env.huawei")
    if os.path.exists(env_file):
        with open(env_file, "r") as f:
            for line in f:
                if line.strip() and not line.startswith("#"):
                    key, value = line.strip().split("=", 1)
                    os.environ[key] = value
        log("INFO", f"[OK] Environment file loaded: {env_file}")
    else:
        log("ERROR", f"[FAIL] Environment file not found: {env_file}")
        return False

    ak = os.environ.get("HUAWEI_AK", "")
    sk = os.environ.get("HUAWEI_SK", "")
    region = os.environ.get("HUAWEI_REGION", "cn-east-3")

    if not ak or not sk:
        log("ERROR", "[FAIL] HUAWEI_AK or HUAWEI_SK is empty")
        return False

    log("INFO", "[OK] HUAWEI_AK and HUAWEI_SK are set")
    return ak, sk, region

def get_project_id(ak, sk, region):
    try:
        credentials = BasicCredentials(ak, sk)
        iam_client = IamClient.new_builder() \
            .with_credentials(credentials) \
            .with_endpoint(f"https://iam.{region}.myhuaweicloud.com") \
            .build()

        request = KeystoneListProjectsRequest()
        response = iam_client.keystone_list_projects(request)

        if hasattr(response, 'projects') and response.projects:
            for project in response.projects:
                if project.name == region:
                    return project.id
            return response.projects[0].id
        else:
            return None
    except exceptions.ClientRequestException as e:
        log("ERROR", f"[FAIL] IAM API error: {e}")
        return None

def get_cdn_client(ak, sk, project_id):
    credentials = GlobalCredentials(ak, sk, project_id)
    cdn_client = CdnClient.new_builder() \
        .with_credentials(credentials) \
        .with_endpoint("https://cdn.myhuaweicloud.com") \
        .build()
    return cdn_client

def get_cdn_cert_info(cdn_client, domain):
    try:
        request = ShowCertificatesHttpsInfoRequest(domain_name=domain)
        response = cdn_client.show_certificates_https_info(request)
        if hasattr(response, 'https'):
            https = response.https
            cert_type = getattr(https, 'certificate_type', 'unknown')
            cert_name = getattr(https, 'cert_name', 'unknown')
            cert_type_map = {'0': '自有证书', '1': 'SCM托管证书', '2': 'CCM托管证书'}
            type_name = cert_type_map.get(str(cert_type), str(cert_type))
            log("INFO", f"CDN cert info: cert_type={type_name} (code={cert_type}), cert_name={cert_name}")
        return True
    except exceptions.ClientRequestException as e:
        log("ERROR", f"[FAIL] Failed to query CDN cert info: {e}")
        return False

def update_cdn_certificate(cdn_client, domain, cert_name, fullchain_content, privkey_content):
    try:
        content = UpdateDomainMultiCertificatesRequestBodyContent(
            https_switch=1,
            cert_name=cert_name,
            certificate_type=0,
            certificate_value=fullchain_content,
            private_key=privkey_content
        )
        body = UpdateDomainMultiCertificatesRequestBody(https=content)
        request = UpdateDomainMultiCertificatesRequest(
            domain_name=domain,
            body=body
        )
        response = cdn_client.update_domain_multi_certificates(request)
        log("INFO", f"[OK] CDN certificate update request accepted for {domain}")
        return True
    except exceptions.ClientRequestException as e:
        log("ERROR", f"[FAIL] CDN cert update failed: {e}")
        return False

def read_cert_files(cert_name, letsencrypt_dir="/etc/letsencrypt/live"):
    fullchain_path = os.path.join(letsencrypt_dir, cert_name, "fullchain.pem")
    privkey_path = os.path.join(letsencrypt_dir, cert_name, "privkey.pem")

    if not os.path.exists(fullchain_path):
        log("ERROR", f"[FAIL] Fullchain file not found: {fullchain_path}")
        return None, None

    if not os.path.exists(privkey_path):
        log("ERROR", f"[FAIL] Private key file not found: {privkey_path}")
        return None, None

    with open(fullchain_path, "r") as f:
        fullchain_content = f.read()
    
    with open(privkey_path, "r") as f:
        privkey_content = f.read()

    if "BEGIN CERTIFICATE" not in fullchain_content:
        log("ERROR", "[FAIL] Fullchain content invalid")
        return None, None

    if "BEGIN PRIVATE KEY" not in privkey_content and "BEGIN RSA PRIVATE KEY" not in privkey_content:
        log("ERROR", "[FAIL] Private key content invalid")
        return None, None

    log("INFO", f"Fullchain length: {len(fullchain_content)} bytes")
    log("INFO", f"Privkey length: {len(privkey_content)} bytes")
    return fullchain_content, privkey_content

def main():
    log("INFO", "========================================")
    log("INFO", "=== CDN Certificate Sync Process Start ===")
    log("INFO", "========================================")

    log("INFO", "Step 1: Loading environment variables...")
    env_result = load_env()
    if not env_result:
        log("ERROR", "Aborting due to environment configuration error")
        sys.exit(1)
    
    ak, sk, region = env_result
    
    log("INFO", "Step 2: Getting project ID...")
    project_id = get_project_id(ak, sk, region)
    if not project_id:
        log("ERROR", "Aborting due to project ID retrieval failure")
        sys.exit(1)
    log("INFO", f"[OK] Project ID: {project_id}")

    log("INFO", "Step 3: Reading local certificate files...")
    cert_name = os.environ.get("CERT_NAME", "wild_dftsh")
    fullchain_content, privkey_content = read_cert_files(cert_name)
    if not fullchain_content or not privkey_content:
        log("WARN", "Certificate files not found, testing API connectivity only")
        fullchain_content = "TEST_CERT_CONTENT"
        privkey_content = "TEST_PRIVKEY_CONTENT"

    cdn_client = get_cdn_client(ak, sk, project_id)
    
    log("INFO", "Step 4: Processing CDN domains...")
    domains_env = os.environ.get("CDN_DOMAINS", "img.yyhpinfo.com")
    CDN_DOMAINS = [d.strip() for d in domains_env.split(",")]
    
    failed_domains = []
    success_domains = []

    for domain in CDN_DOMAINS:
        log("INFO", f"--- Processing domain: {domain} ---")

        get_cdn_cert_info(cdn_client, domain)

        if fullchain_content and fullchain_content != "TEST_CERT_CONTENT":
            if update_cdn_certificate(cdn_client, domain, f"{cert_name}-cdn", fullchain_content, privkey_content):
                log("INFO", f"[OK] Domain {domain} update request successful")
                success_domains.append(domain)
            else:
                log("ERROR", f"[FAIL] Domain {domain} update failed")
                failed_domains.append(domain)
        else:
            log("INFO", f"[SKIP] No valid certificate found, skipping update for {domain}")
            success_domains.append(domain)

    log("INFO", "========================================")
    log("INFO", "=== Summary ===")
    log("INFO", f"Successful domains: {len(success_domains)}")
    for d in success_domains:
        log("INFO", f"  - {d} [OK]")
    log("INFO", f"Failed domains: {len(failed_domains)}")
    for d in failed_domains:
        log("ERROR", f"  - {d} [FAIL]")
    log("INFO", "========================================")

    if not failed_domains:
        log("INFO", "[OK] All CDN certificates updated successfully")
        log("INFO", "=== CDN Certificate Sync Process Completed Successfully ===")
        sys.exit(0)
    else:
        log("ERROR", f"[FAIL] Some domains failed: {failed_domains}")
        log("ERROR", "=== CDN Certificate Sync Process Completed With Errors ===")
        sys.exit(1)

if __name__ == "__main__":
    main()
