# 园区水量漏损排查

面向园区巡检的本地工作台。内置业务样例覆盖园区夜间水表异常聚类与巡检工单排序。样例采用确定性构造，适合复现实验和核查边界行为。

## 启动

```sh
docker compose up --build -d
```

打开 `http://127.0.0.1:18206/` 查看夜间巡检指令。左侧六个入口可展开运行证据。调整「巡检名额（次）」，点击「执行巡检排程」比较处置结果。结束后执行 `docker compose down --remove-orphans`。

## 独立业务模块

- 抄表校验 `meter_ingress`
- 隔离夜窗 `night_windows`
- 用水聚类 `consumption_clusters`
- 漏损筛查 `loss_screen`
- 巡检配次 `field_rounds`
- 水量追溯 `water_balance`

## 查看运行结果

- `GET /api/overview` 返回默认运行及其指纹。
- `POST /api/scenario` 接收 `{"capacity": 3}`。入口接受 1–100 的整数，应用样例时使用该业务额度。
- `GET /api/stages/water_balance` 查看该环节的独立证据，支持 `?capacity=3`。

```sh
docker compose exec -T app python -m meterloss.delivery evaluate --capacity 3
docker compose exec -T app pytest -q
```

数据和模型约定见 [业务契约](docs/SPEC.md)。模块、例外规则与验证入口见 [业务深度](docs/DEPTH.md)。
