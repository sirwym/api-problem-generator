from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask
from pydantic import BaseModel
from fastapi import FastAPI, HTTPException, Security, Depends
from fastapi.security.api_key import APIKeyHeader
import requests
import tempfile
import os
import zipfile
import re
import shutil
import threading

app = FastAPI()
# 定义全局并发锁，最多允许 4 个任务同时进行
task_limiter = threading.Semaphore(4)

# 定义 API Key 名称
API_KEY_NAME = "X-API-Key"
# 从环境变量读取服务器密钥，如果没有配置，则默认拒绝（防止忘记配置导致裸奔）
SERVER_API_KEY = os.getenv("API_KEY", "UNCONFIGURED_KEY") 
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=True)

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != SERVER_API_KEY or SERVER_API_KEY == "UNCONFIGURED_KEY":
        raise HTTPException(status_code=401, detail="🚫 无效的 API Key 或服务器未配置密钥")
    return api_key


GO_JUDGE_URL = os.getenv("GO_JUDGE_URL", "http://localhost:5050/run")

def cleanup_resources(temp_dir, zip_file_path, fids):
    # 1. 清理 go-judge 缓存
    for fid in fids:
        if fid:
            try:
                base_url = GO_JUDGE_URL.replace("/run", "")
                requests.delete(f"{base_url}/file/{fid}", timeout=5)
            except Exception as e:
                print(f"清理 go-judge 缓存 {fid} 失败: {e}")
                
    # 2. 清理本地的 temp_dir 临时目录
    if temp_dir and os.path.exists(temp_dir):    
        shutil.rmtree(temp_dir, ignore_errors=True)
        
    # 3. 清理生成的 zip 文件
    if zip_file_path and os.path.exists(zip_file_path):
        os.remove(zip_file_path)

class ProblemRequest(BaseModel):
    gen_cpp: str
    valid_cpp: str
    std_cpp: str
    problem_md: str
    subtasks: list[int]

def call_judge_compile(src_code: str, output_name: str, testlib_code: str):
    """调用 go-judge 编译 C++ 代码"""
    payload = {
        "cmd": [{
            "args": ["/usr/bin/g++", "-O2", "-std=c++14", "source.cpp", "-o", output_name],
            "env": ["PATH=/usr/bin:/bin"],
            "files": [{"content": ""}, {"name": "stdout", "max": 10240}, {"name": "stderr", "max": 10240}],
            "cpuLimit": 10000000000, # 10秒
            "memoryLimit": 1073741824, # 给到 1GB 内存，防止引入 testlib.h 后模板展开撑爆内存
            "procLimit": 50, # 给 g++ 开放 50 个子进程权限
            "copyIn": {
                "source.cpp": {"content": src_code},
                "testlib.h": {"content": testlib_code}
            },
            "copyOutCached": [output_name]
        }]
    }
    
    resp = requests.post(GO_JUDGE_URL, json=payload).json()[0]
    
    if resp.get('status') != 'Accepted':
        err_msg = resp.get('error', '')
        stderr_str = resp.get('files', {}).get('stderr', '')
        stdout_str = resp.get('files', {}).get('stdout', '')
        raise Exception(f"编译报错 -> 状态: {resp.get('status')}, error: '{err_msg}', stderr: '{stderr_str}', stdout: '{stdout_str}'")
        
    return resp['fileIds'][output_name]


@app.post("/api/forge_problem")
def forge_problem(req: ProblemRequest, api_key: str = Depends(verify_api_key)):
    # 使用信号量进行排队控制
    with task_limiter:
        print("分配到资源！开始执行云端出题...")
        gen_fid, valid_fid, std_fid = None, None, None
        temp_dir = None
        is_success = False  # 标记是否成功走完全程
        final_zip_path = None
        
        try:
            # 读取同目录下的 testlib.h
            with open("testlib.h", "r", encoding="utf-8") as f:
                testlib_code = f.read()

            # 1. 编译三件套
            gen_fid = call_judge_compile(req.gen_cpp, "gen", testlib_code)
            valid_fid = call_judge_compile(req.valid_cpp, "valid", testlib_code)
            std_fid = call_judge_compile(req.std_cpp, "std", testlib_code)

            temp_dir = tempfile.mkdtemp()
            testdata_dir = os.path.join(temp_dir, "testdata")
            os.makedirs(testdata_dir)

            # 2. 循环生成测试数据
            idx = 1
            for subtask_id, cases_count in enumerate(req.subtasks, start=1):
                for tc in range(1, cases_count + 1):
                    # 2.1 运行 gen 生成 input
                    run_gen = {
                        "cmd": [{
                            "args": ["gen", str(subtask_id), str(tc)],
                            "env": ["PATH=/usr/bin:/bin"],
                            "files": [{"content": ""}, {"name": "stdout", "max": 1024*1024*50}, {"name": "stderr", "max": 10240}],
                            "copyIn": {"gen": {"fileId": gen_fid}},
                            "cpuLimit": 5000000000, 
                            "memoryLimit": 536870912,
                            "procLimit": 50 
                        }]
                    }
                    gen_resp = requests.post(GO_JUDGE_URL, json=run_gen, timeout=15).json()[0]

                    if gen_resp.get('status') != 'Accepted':
                        err_msg = gen_resp.get('error', '')
                        raise Exception(f"生成器崩溃 (Subtask {subtask_id} Case {tc}): 状态={gen_resp.get('status')}, err={err_msg}")
                    input_data = gen_resp['files']['stdout']

                    # 2.2 运行 valid 校验 input
                    run_valid = {
                        "cmd": [{
                            "args": ["valid"],
                            "env": ["PATH=/usr/bin:/bin"],
                            "files": [{"content": input_data}, {"name": "stdout", "max": 1024}, {"name": "stderr", "max": 10240}],
                            "copyIn": {"valid": {"fileId": valid_fid}},
                            "cpuLimit": 2000000000, 
                            "memoryLimit": 536870912,
                            "procLimit": 50 
                        }]
                    }
                    valid_resp = requests.post(GO_JUDGE_URL, json=run_valid, timeout=15).json()[0]
                    if valid_resp.get('status') != 'Accepted' and valid_resp.get('exitStatus') != 0:
                        err_msg = valid_resp.get('error', '')
                        raise Exception(f"数据校验不通过 (Subtask {subtask_id} Case {tc}): 状态={valid_resp.get('status')}, err={err_msg}")

                    # 2.3 运行 std 生成 output
                    run_std = {
                        "cmd": [{
                            "args": ["std"],
                            "env": ["PATH=/usr/bin:/bin"],
                            "files": [{"content": input_data}, {"name": "stdout", "max": 1024*1024*50}, {"name": "stderr", "max": 10240}],
                            "copyIn": {"std": {"fileId": std_fid}},
                            "cpuLimit": 5000000000,
                            "memoryLimit": 536870912,
                            "procLimit": 50 
                        }]
                    }
                    std_resp = requests.post(GO_JUDGE_URL, json=run_std, timeout=15).json()[0]
                    if std_resp.get('status') != 'Accepted':
                        err_msg = std_resp.get('error', '')
                        raise Exception(f"标程运行异常 (Subtask {subtask_id} Case {tc}): 状态={std_resp.get('status')}, err={err_msg}")
                    output_data = std_resp['files']['stdout']

                    # 写入本地临时文件
                    with open(os.path.join(testdata_dir, f"{idx}.in"), "w", encoding="utf-8") as f: f.write(input_data)
                    with open(os.path.join(testdata_dir, f"{idx}.out"), "w", encoding="utf-8") as f: f.write(output_data)
                    idx += 1

            # 3. 生成 problem.md, std.cpp 并打包
            with open(os.path.join(temp_dir, "problem.md"), "w", encoding="utf-8") as f: f.write(req.problem_md)
            with open(os.path.join(temp_dir, "std.cpp"), "w", encoding="utf-8") as f: f.write(req.std_cpp)
            
            parent_dir = os.path.dirname(temp_dir)
            zip_base_name = os.path.join(parent_dir, f"problem_package_{os.path.basename(temp_dir)}")

            # 执行打包
            shutil.make_archive(zip_base_name, 'zip', temp_dir)
            final_zip_path = zip_base_name + ".zip"

            is_success = True
            
            # FastAPI 在文件发送完毕后，再去后台执行清理函数
            cleanup_task = BackgroundTask(cleanup_resources, temp_dir=temp_dir, zip_file_path=final_zip_path, fids=[gen_fid, valid_fid, std_fid])
            return FileResponse(final_zip_path, filename="problem_package.zip", media_type="application/zip", background=cleanup_task)

        except Exception as e:
            print(f"Error: {str(e)}") 
            raise HTTPException(status_code=500, detail=str(e))

        finally:
            # 如果中间报错了，还没来得及返回 FileResponse，那就立刻执行清理，防止泄露
            if not is_success:
                cleanup_resources(temp_dir, final_zip_path, [gen_fid, valid_fid, std_fid])