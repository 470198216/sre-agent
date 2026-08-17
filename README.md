# sre-agent

基于 **远程 SSH + 命令白名单** 的最小可运行 SRE 诊断 Agent（Python）。

## 文档

| 文档 | 用途 |
|------|------|
| [操作手册.md](./操作手册.md) | 配置、日常命令、排障、安全红线 |
| [代码实现逻辑说明.md](./代码实现逻辑说明.md) | 模块职责、调用链、流程图、源码阅读顺序 |

## 最快开始

```powershell
cd c:\Users\wenjin\Desktop\wwjfiles\sre-agent
.\.venv\Scripts\activate
# 编辑 .env 与 configs\hosts.yaml 后：
sre-agent ping --host test-01
sre-agent tool --host test-01 --name df_h
sre-agent diagnose --host test-01 --symptom "/ disk usage alert 95%"
```
