import requests
import json
import zipfile
import shutil
import os
import tempfile
import argparse
from datetime import datetime

# ==========================================
# 使用 argparse 接收命令行参数
# ==========================================
parser = argparse.ArgumentParser(description="Cloud Judge AI 出题本地客户端")
parser.add_argument("--url", required=True, help="云端 API 的完整地址 (例如: http://IP:8000/api/forge_problem)")
parser.add_argument("--key", required=True, help="云端 API 的访问密钥 (X-API-Key)")
args = parser.parse_args()

API_URL = args.url
API_KEY = args.key
# ==========================================

print("正在读取 payload 数据...")
try:
    with open("test_payload.json", "r", encoding="utf-8") as f:
        payload = json.load(f)
except FileNotFoundError:
    print("❌ 找不到 test_payload.json，请确认 AI 是否已生成。")
    exit(1)

print(f"🚀 正在向云端引擎提交出题任务，目标: {API_URL}")
try:
    # 携带 API Key 注入请求头
    headers = {"X-API-Key": API_KEY}
    
    r = requests.post(API_URL, json=payload, headers=headers, timeout=180) 
    
    if r.status_code == 200:
        print("✅ 云端数据生成完毕，正在下载基础包...")
        
        cloud_zip = "cloud_temp.zip"
        with open(cloud_zip, "wb") as f:
            f.write(r.content)
            
        print("📦 正在本地组装元数据并进行二次打包...")
        
        with tempfile.TemporaryDirectory() as local_tmp:
            shutil.unpack_archive(cloud_zip, local_tmp)
            
            if os.path.exists("meta.json"):
                shutil.copy("meta.json", os.path.join(local_tmp, "meta.json"))
                print("   ➕ 成功注入: meta.json")
            else:
                print("   ⚠️ 警告: 未在当前目录找到 meta.json，已跳过注入步骤")
                
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_zip_name = f"problem_package_{timestamp}"
            
            shutil.make_archive(final_zip_name, 'zip', local_tmp)
            
        if os.path.exists(cloud_zip):
            os.remove(cloud_zip)
            
        print(f"🎉 组装彻底完成！最终数据包已生成: {final_zip_name}.zip")

    elif r.status_code == 401:
        print("❌ 认证失败: API Key 错误或未授权访问！")
    else:
        try:
            error_detail = r.json().get("detail", r.text)
        except Exception:
            error_detail = r.text
        print(f"❌ 失败 (状态码 {r.status_code}): {error_detail}")
        
except requests.exceptions.RequestException as e:
    print(f"❌ 网络请求发生异常: {e}")