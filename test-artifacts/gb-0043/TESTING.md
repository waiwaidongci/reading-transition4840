# gb-0043 测试说明（分层文集对照特性）

特性：两个互不重叠阅读文集的分层接续对照。受理即冻结两组会话与分层；每条接续在同一会话只计有无；
仅用两组都有人数的可比层；合并表做双侧 Fisher 精确检验（固定各层组别人数与命中总数），
再对全部在可比层出现过的接续做 Holm 校正；页面只发布合并方向与每个可比层方向都相反的全层反转接续。

本目录不混入应用源码，全部脚本仅依赖 Python 3.11 标准库（运行加 `-I`），无需数据库或网络。

## 1. 独立统计 oracle

```bash
python3 -I test-artifacts/gb-0043/oracle_comparison.py
```

与产品代码完全独立的第二份实现（手工整数枚举超几何表、独立 Holm），共 31 项断言：

- 双侧 Fisher 精确概率与独立枚举逐表交叉验证，含手算表 `[[0,4],[4,2]]`、最小概率点 p=1 等边界；
- Holm 校正单调性、`m*p1` 下界、全 1 输入；
- 端到端口径：经典辛普森构造下每层 A 更高、合并 B 反超并正确标记全层反转；
- 同一会话重复经过同一接续只计 1 次；
- 单章会话层（无任何边）方向持平，会阻止“全层反转”标记；
- 仅一组有人数的层整体剔除；
- 空文集、无可比层、重复会话编号等退化输入被拒绝。

## 2. 服务/Worker/导出集成测试

```bash
python3 -I test-artifacts/gb-0043/integration/integration_test.py
```

环境内无 pip/外部依赖，因此 `integration/site_shim/` 提供仅供测试使用的内存版
SQLAlchemy / Redis / FastAPI / PyJWT 最小垫片（不在应用导入路径内），被测的仍是真实的
`src/services/*`、`src/worker.py`、`src/services/export.py` 代码。9 个用例：

1. 受理时冻结两组快照并入队，写 `comparison.queued` 审计；
2. 受理后向来源并发追加样本，已锁定任务快照不混入（22 条保持不变），来源实时数据为 23 条；
3. worker 消费后 completed、结果可 JSON 序列化（无 NaN）、反转行/人数/命中/方向正确、写出 BOM CSV、
   `GET /comparisons/{id}/export` 内容与工件一致、写 `comparison.completed` 审计；
4. 非 queued 状态的任务不会被重复处理；
5. 算法异常进入 failed 态并保留错误消息、写 `comparison.failed` 审计；
6. 同来源 422、来源不存在 404、空文集 422、队列中断 503 且任务落 failed；
7. 列表剔除快照/结果大字段、未知 id 404、未完成导出 409；
8. worker 落库结果与直接对同一冻结快照调用算法完全一致（含 SHA256 校验和）；
9. 双队列 `BLPOP` 经 `worker.main` 正确路由到 `comparison:queue` 并完成。

## 3. 前端

所有 ES Module 通过 `node --check` 语法校验；新增页面 `frontend/src/pages/comparison.js`，
路由 `#comparison`，导航顺序：业务总览 / 阅读文集 / 分析配置 / 完整结果 / 文集对照 / 编辑衔接建议 / 审计。
前端不做任何统计计算，只渲染后端 `result.reversed_rows` 与各层人数、命中数、校正概率。

## 4. 建议的容器内手工复核

```bash
docker compose up -d --build
docker compose exec -T backend python -m scripts.seed_demo
# 浏览器登录 analyst 账号 → 文集对照 → 选择 SY-202611-01 与 SY-202611-02 → 执行
# 预期：任务经独立 worker 完成；全层反转卡片展示各可比层人数/命中/比例与 Holm 校正 p；
#       下载 CSV 含全部受检接续（不止反转行）；审计页出现 comparison.queued/completed。
```
