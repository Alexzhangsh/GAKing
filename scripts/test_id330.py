#!/usr/bin/env python3
"""生产服务器验证 ID=330 联盟版万能转链接口（临时测试脚本）"""
import sys, json, urllib.parse, urllib.request

APKEY = "45d81d4d-890f-00fa-806a-89e3d8309b8d"
TBNAME = "dft4377"

search_url = "http://api.web.ecapi.cn/taoke/getTkMaterialItem?apkey=%s&keyword=%s&pageno=1&pagesize=1&ver_code=101&tbname=%s" % (APKEY, urllib.parse.quote("手串"), TBNAME)
resp = json.loads(urllib.request.urlopen(search_url).read())
items = resp.get("data", {}).get("list", [])
if not items:
    print("NO search results")
    sys.exit(1)
item = items[0]
click_url = item.get("click_url", "")
item_id = item.get("item_id", "")
print("Search OK: item_id=%s" % item_id[:30])
print("click_url=%s" % click_url[:80])

conv_url = "http://api.web.ecapi.cn/taoke/doTbHighCommissionPromotionUrl"
enc_url = urllib.parse.quote(click_url, safe="")
full_url = "%s?apkey=%s&tbname=%s&material_list=%s&biz_scene_id=1" % (conv_url, APKEY, TBNAME, enc_url)
print("Requesting: %s" % full_url[:120])
resp2 = json.loads(urllib.request.urlopen(full_url).read())
print("code=%s msg=%s" % (resp2.get("code"), resp2.get("msg")))
data = resp2.get("data", {})
print("data keys: %s" % list(data.keys()))

iul = data.get("item_url_list", {})
if isinstance(iul, dict):
    lst = iul.get("item_url_list", [])
    if lst:
        item = lst[0]
        print("item_url_list keys: %s" % list(item.keys()))
        ld = item.get("link_info_dto", {})
        if isinstance(ld, dict):
            for k in ["cps_short_url", "cps_long_url", "cps_short_tpwd", "cps_full_tpwd", "item_id", "coupon_short_url", "coupon_long_url"]:
                v = ld.get(k, "")
                print("  %s=%s" % (k, str(v)[:80]))
        pdi = item.get("promotion_info_dto", {})
        if isinstance(pdi, dict):
            print("  promotion_info_dto keys: %s" % list(pdi.keys()))
            print("  commission_rate=%s" % pdi.get("commission_rate", ""))

mul = data.get("material_url_list", {})
if isinstance(mul, dict):
    lst = mul.get("material_url_list", [])
    if lst:
        print("material_url_list[0] keys: %s" % list(lst[0].keys()))
        ld = lst[0].get("link_info_dto", {})
        if isinstance(ld, dict):
            for k in ["cps_short_url", "cps_long_url", "cps_short_tpwd", "cps_full_tpwd", "item_id"]:
                v = ld.get(k, "")
                print("  %s=%s" % (k, str(v)[:80]))