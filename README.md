# 火山灰喷发端元混合审计

火山灰层可能由多个喷发端元混合而成。本系统用**精确有理数**寻找解释目标示踪值的
**最小端元凸组合**，避免把落在凸包内部的混合误判为单一来源：

1. **最少化正权端元数**（最小支撑，R³ 中至多 4 个端元）；
2. 再**最小化所选端元的复核代价和**；
3. 同优时按**标识序列字典序**确定唯一规范解；
4. 并把每个端元归类为在前两级（最少端元数 ∧ 最小代价）同优解中
   **所有（always）/ 部分（partial）/ 从不（never）** 出现。

- `api/` — FastAPI 后端，`fractions.Fraction` 精确算术（Bareiss/RREF，无浮点）
- `web/` — React + TypeScript + Vite 前端，nginx 提供静态文件与 API 反代
- `verify/` — Compose 中的一次性校验服务
- `docker-compose.yml` — 三服务协同

## 快速开始

```bash
cp .env.example .env        # 可选：修改宿主机端口 API_PORT / WEB_PORT
docker compose up --build
# Web:  http://localhost:${WEB_PORT:-8080}
# API:  http://localhost:${API_PORT:-8000}/health
```

宿主机端口均可通过环境变量配置（`.env` 或 shell）：

| 变量 | 默认 | 说明 |
| --- | --- | --- |
| `API_PORT` | 8000 | API 发布到宿主机的端口（容器内固定 8000） |
| `WEB_PORT` | 8080 | Web 发布到宿主机的端口（容器内固定 80） |

两个容器均带 Docker `HEALTHCHECK`（API 检 `/health`，Web 检 `/healthz`）。

## 一次性校验（verify）

```bash
docker compose build verify
docker compose run --rm verify
```

`verify` 是一次性服务，依次检查并**按结果退出码**（0 全通过 / 1 有失败）：

1. 后端代码测试（容器内运行 pytest）；
2. 规范分数权重（四面体内点 → 四个 `1/4`；四位小数目标 `0.125` → `7/8 + 1/8`）；
3. 凸包外目标 `feasible=false` 且无解；
4. 同优归类（等代价两条对角线 → 四个端元皆 partial；唯一解 → always/never）；
5. 构建产物（Web 容器返回构建后的 `index.html` 且 JS bundle 可访问）；
6. API 冒烟（直连与经 Web 代理的 `/health`、`POST /api/audit`）。

## HTTP 接口

- `GET /health` → `{"status":"ok"}`
- `POST /api/audit`

```json
{
  "endmembers": [
    {"id": "A", "t0": "0", "t1": "0", "t2": "0", "cost": "1"}
  ],
  "target": ["1", "1", "1"]
}
```

输入以原始文本提交，错误按字段定位（如 `endmembers[2].t1`、`target[0]`），
非法输入或凸包外无解时前端**保留全部编辑内容**并就地高亮反馈。

### 输入规则

- 每批 3–30 个端元，标识为唯一 ASCII 非空字符串；
- 三个示踪值为整数，绝对值 ≤ 1,000,000；
- 复核代价为正整数；
- 目标三值为至多四位小数的数值（允许负数）。

### 求解正确性要点

- 权重恒为既约分数（`numerator/denominator`，附规范字符串 `fraction`）；
- 枚举 1–4 元子集，对仿射无关列解齐次线性方程组，严格正权才接受；
  零权情形归入更小的子集，因此“最少化正权端元数”语义精确；
- 30 端元最坏规模（枚举 C(30,4)）秒级完成。

## 本地开发（不经 Docker）

```bash
# API
python3 -m venv .venv && . .venv/bin/activate
pip install -r api/requirements-dev.txt
(cd api && uvicorn app.main:app --reload --port 8000)

# Web（Vite 把 /api 与 /health 代理到 8000）
(cd web && npm install && npm run dev)
```

## 测试

```bash
(cd api && pytest -q)
```
