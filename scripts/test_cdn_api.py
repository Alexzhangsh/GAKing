#!/usr/bin/env python3
import os
import sys
from datetime import datetime

from huaweicloudsdkcore.auth.credentials import BasicCredentials, GlobalCredentials
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkiam.v3 import IamClient, KeystoneListProjectsRequest
from huaweicloudsdkcdn.v2 import CdnClient, ListDomainsRequest, ShowDomainDetailByNameRequest

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
                    log("INFO", f"[OK] Got project ID for region {region}: {project.id}")
                    return project.id
            log("INFO", f"[OK] Using first project ID: {response.projects[0].id}")
            return response.projects[0].id
        else:
            log("ERROR", "[FAIL] No projects found")
            return None
    except exceptions.ClientRequestException as e:
        log("ERROR", f"[FAIL] IAM API error: {e}")
        return None

def test_cdn_api(ak, sk, region, project_id):
    try:
        credentials = GlobalCredentials(ak, sk, project_id)
        cdn_client = CdnClient.new_builder() \
            .with_credentials(credentials) \
            .with_endpoint("https://cdn.myhuaweicloud.com") \
            .build()

        request = ListDomainsRequest()
        response = cdn_client.list_domains(request)

        domains = []
        if hasattr(response, 'domains'):
            domains = response.domains
        elif hasattr(response, 'domain_list'):
            domains = response.domain_list
        
        if domains:
            log("INFO", f"[OK] Found {len(domains)} CDN domains")
            for domain in domains[:3]:
                domain_name = getattr(domain, 'domain_name', 'unknown')
                domain_id = getattr(domain, 'id', 'unknown')
                status = getattr(domain, 'status', 'unknown')
                log("INFO", f"  - {domain_name} (ID: {domain_id}, Status: {status})")
            
            test_domain = domains[0].domain_name
            detail_request = ShowDomainDetailByNameRequest(domain_name=test_domain)
            detail_response = cdn_client.show_domain_detail_by_name(detail_request)
            log("INFO", f"[OK] Domain detail retrieved for: {test_domain}")
            
            https_info = getattr(detail_response, 'https', None)
            if https_info:
                cert_name = getattr(https_info, 'cert_name', 'unknown')
                cert_type = getattr(https_info, 'certificate_type', 'unknown')
                cert_type_map = {'0': '自有证书', '1': 'SCM托管', '2': 'CCM托管'}
                log("INFO", f"  Certificate: {cert_name} (Type: {cert_type_map.get(str(cert_type), cert_type)})")
            else:
                log("INFO", "  HTTPS not configured")
            
            return True
        else:
            log("WARN", "[WARN] No CDN domains found")
            return True
    except exceptions.ClientRequestException as e:
        log("ERROR", f"[FAIL] CDN API error: {e}")
        return False

def main():
    log("INFO", "=== Starting Huawei CDN API Test ===")
    
    env_result = load_env()
    if not env_result:
        log("ERROR", "Aborting due to environment configuration error")
        sys.exit(1)
    
    ak, sk, region = env_result
    
    log("INFO", "Step 1: Getting project ID...")
    project_id = get_project_id(ak, sk, region)
    if not project_id:
        log("ERROR", "Aborting due to project ID retrieval failure")
        sys.exit(1)
    
    log("INFO", "Step 2: Testing CDN API connectivity...")
    if test_cdn_api(ak, sk, region, project_id):
        log("INFO", "=== API Test Completed Successfully ===")
        sys.exit(0)
    else:
        log("ERROR", "=== API Test Failed ===")
        sys.exit(1)

if __name__ == "__main__":
    main()
