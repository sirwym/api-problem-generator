import requests
import json
import zipfile
import shutil
import os
import tempfile
from datetime import datetime  

url = "http://localhost:8000/api/forge_problem"

print("正在读取 payload 数据...")
try:
    with open("test_payload.json", "r", encoding="utf-8") as f:
        payload = json.load(f)
except FileNotFoundError:
    print("❌ 找不到 test_payload.json，请确认 AI 是否已生成。")
    exit(1)

print("🚀 正在向云端引擎提交出题任务，请稍候...")
try:
    # 延长 timeout，防止数据点多的时候超时
    r = requests.post(url, json=payload, timeout=60) 
    
    if r.status_code == 200:
        print("✅ 云端数据生成完毕，正在下载基础包...")
        
        # 1. 暂存云端返回的原始 zip
        cloud_zip = "cloud_temp.zip"
        with open(cloud_zip, "wb") as f:
            f.write(r.content)
            
        print("📦 正在本地组装元数据并进行二次打包...")
        
        # 2. 创建本地临时目录进行解压和组装
        with tempfile.TemporaryDirectory() as local_tmp:
            # 将云端的包解压到本地临时目录
            shutil.unpack_archive(cloud_zip, local_tmp)
            
            # 3. 寻找并注入 meta.json
            if os.path.exists("meta.json"):
                shutil.copy("meta.json", os.path.join(local_tmp, "meta.json"))
                print("   ➕ 成功注入: meta.json")
            else:
                print("   ⚠️ 警告: 未在当前目录找到 meta.json，已跳过注入步骤")
                
            # 4. 将加入了元数据的文件夹，重新打包为最终形态
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_zip_name = f"problem_package_{timestamp}"
            
            shutil.make_archive(final_zip_name, 'zip', local_tmp)
            
        # 5. 阅后即焚：清理云端的过渡压缩包
        if os.path.exists(cloud_zip):
            os.remove(cloud_zip)
            
        print(f"🎉 组装彻底完成！最终包含元数据的数据包已生成: {final_zip_name}.zip")

    else:
        print(f"❌ 失败 (状态码 {r.status_code}): {r.text}")
        
except Exception as e:
    print(f"❌ 请求发生异常: {e}")