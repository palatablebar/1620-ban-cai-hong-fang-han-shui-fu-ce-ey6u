# 板材烘房含水复测

板材厂质检与烘房班长每日核对烘房层位单。按堆层、蒸汽、厚度和取样序列拟合含水率，给高风险层保留翻层和复测窗口。同窑同层视为一个工位，补测要留见证点且不能跨冷却窗口。
内置数据是模拟业务单据，带历史结果、迟到回报、失校与缺测等情况，供本地复盘。

## 启动与跑一班

```sh
docker compose up --build -d --wait
curl -fsS http://127.0.0.1:19289/health
docker compose exec -T app python -m kilnboard.cli validate
docker compose exec -T app python -m kilnboard.cli preview --budget 16 --reserve 1
docker compose exec -T app python -m kilnboard.cli replay
docker compose exec -T app pytest -q -p no:cacheprovider
```

打开 [工作台](http://127.0.0.1:19289/)，可以调预算、选片区、看单据与近窗回放。 [接口说明](http://127.0.0.1:19289/docs)由 OpenAPI 生成，可离线获取 `/openapi.json`。
查询 `/api/decisions?limit=5` 可快速查看当班处置，`/api/replay` 返回近窗实测对照，`/api/compare` 同时回看两个方案的处置变化和预计暴露。
`POST /api/scenario` 接收 `budget`、`reserve`、`region`、`start`、`stop`。在 `POST /api/compare` 中将两份参数分别放进 `baseline`、`proposal`。发布时把预览的摘要、版号与当时参数交给 `/api/publish`。

通过 `SOURCE_FILE` 指定自备 CSV，在隔离环境中使用 `DISPATCH_STORE` 指向独立归档目录。
`docker compose down` 停止服务，已发布记录保存在 Compose 的归档卷中。

[数据和模型契约](docs/SPEC.md) · [操作与处置流程](docs/OPERATIONS.md) · [回归索引](docs/DEPTH.md)
