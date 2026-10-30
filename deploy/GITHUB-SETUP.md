# GitHub 仓库设置清单

仓库：https://github.com/verifly-team/activity-collecetion-backend

按顺序做完下面 4 步，`git push` 就能自动部署。

---

## 步骤 0：把代码推上去

远端仓库现在是**空的**，先在本机执行：

```bash
cd ~/Documents/mvp/verifly/verifly-activity/server
git push -u origin main
```

> 如果提示要账号密码：密码处填 **Personal Access Token**（不是 GitHub 登录密码）。
> 生成地址：GitHub → Settings → Developer settings → Personal access tokens → Tokens (classic)
> 勾选 `repo` + `workflow`（`workflow` 必须有，否则推不上去 workflow 文件）。

---

## 步骤 1：建 Environment

`Settings → Environments → New environment`

- 名字：**`acr`**（必须一字不差，workflow 里写死了）
- 建议勾选 **Required reviewers → 选自己**
  - 勾了之后每次部署前要点一下 Approve，防误触发

---

## 步骤 2：配 Secrets

`Settings → Secrets and variables → Actions → Secrets 标签 → New repository secret`

### 主流程（源码构建）只需要这 3 个

| Name | Value |
|---|---|
| `SSH_HOST` | 服务器公网 IP |
| `SSH_USER` | `deploy` |
| `SSH_PRIVATE_KEY` | 部署私钥全文，含 `-----BEGIN` / `-----END` 两行 |
| `SSH_PORT` | 端口，默认 22，可不配 |

### 备用流程（推镜像到 ACR）另外需要

| Name | Value |
|---|---|
| `ACR_USERNAME` | ACR「访问凭证」里显示的**登录用户名** |
| `ACR_PASSWORD` | ACR「访问凭证」里的**固定密码**（不是阿里云登录密码） |

> ⚠️ 一定要建在 **Repository secrets**（这个页面），
> 不要建在 Environment 里 —— 主流程的 build job 没声明 environment，读不到。

生成部署私钥（本机执行，不要在服务器上生成）：

```bash
ssh-keygen -t ed25519 -N "" -C "github-actions@verifly" -f ~/.ssh/id_deploy_gh
ssh-copy-id -i ~/.ssh/id_deploy_gh.pub deploy@<服务器IP>
ssh -i ~/.ssh/id_deploy_gh deploy@<服务器IP> 'docker ps && echo OK'   # 必须先看到 OK
pbcopy < ~/.ssh/id_deploy_gh                                          # 复制粘贴到 SSH_PRIVATE_KEY
```

---

## 步骤 3：配 Variables（可选）

`Settings → Secrets and variables → Actions → Variables 标签`

| Name | Value | 作用 |
|---|---|---|
| `AUTO_DEPLOY` | `true` | 给**镜像仓库版**用。主流程不需要，它是 push 就部署 |

---

## 步骤 4：验证

推一次代码：

```bash
git commit --allow-empty -m "test: 触发部署"
git push
```

去 `Actions` 页面看 **「部署（源码构建·主流程）」**：

```
✅ 测试         ruff + pytest
✅ 准备 SSH
✅ 服务器环境自检    ← 第一次最容易卡在这
✅ 打包源码
✅ 上传源码
✅ 构建并重启
```

---

## 两条流水线

| 文件 | 触发 | 说明 |
|---|---|---|
| `deploy-source.yml` | **push main 自动** | 主流程，不碰镜像仓库 |
| `ci-cd.yml` | 仅手动 | 备用，构建镜像推 ACR |

---

## 服务器准备（root，一次性）

```bash
# 目录
mkdir -p /verifly/activity/{uploads,src}
chown -R 10001:10001 /verifly/activity/uploads
chown -R deploy:deploy /verifly/activity

# 配置文件
cp .env.example /verifly/activity/.env
vi /verifly/activity/.env              # 改 DATABASE_URL 的密码
chown deploy:deploy /verifly/activity/.env
chmod 600 /verifly/activity/.env
```

`/verifly/activity/.env` 里 **`UPLOAD_DIR` 必须是 `/data/uploads`**（容器内路径），
宿主机路径只出现在 `-v /verifly/activity/uploads:/data/uploads` 里。

---

## 常见失败

| 现象 | 原因 | 处理 |
|---|---|---|
| `mkdir: cannot create directory '/verifly/activity'` | deploy 用户对 `/verifly` 无写权限 | root 执行上面的 mkdir + chown |
| `Permission denied (publickey)` | 私钥不对 | 本机 `ssh -i ~/.ssh/id_deploy_gh deploy@IP` 先试通 |
| 测试过、部署失败 | 服务器环境没配好 | 看「服务器环境自检」那步的日志，会直接给出要执行的命令 |
| 上传返回成功但宿主机没文件 | `UPLOAD_DIR` 写成了宿主机路径 | 改成 `/data/uploads`，重建容器 |
| 推送镜像 `denied` | ACR 里没建这个镜像仓库 | 去 ACR 控制台创建 |
