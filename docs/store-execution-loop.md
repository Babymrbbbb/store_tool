# 门店执行闭环（合成参考实现）

> 方法论开源复刻，不含任何真实门店名 / 经营数据。本模块演示「作战卡下发 →
> 门店执行 → 门店验收」的门店执行闭环，对应内部业务系统同一套管控思路。

## 它解决什么

总部把标准动作（陈列 / 话术 / 订货）做成「作战卡」下发给每家门店，门店执行后由
门店验收，形成 **下发 → 执行 → 验收** 的管控闭环。难点不在"发下去"，而在：

- **全量下发**：每家店 × 每张卡都要有一条下发记录，缺一条就是覆盖漏洞；
- **状态机不可跳步**：不能从"已下发"直接变成"已验收"，必须依次走过执行；
- **试点先行**：先让少数门店跑通全闭环验证流程，其余门店先只下发。

## 合成数据设计

- 门店：演示品牌，A / B / C / D 四市共 **12 家**（与 `hunkon_rag` 真相源一致）；
- 作战卡：3 张（陈列标准 / 服务话术 / 订货节奏），均为通用动作，无真实业务细节；
- 试点：合成门店 `A01`、`D01` 跑通全闭环，其余 10 家仅下发。

## 状态机

```
dispatched ──advance(executed)──▶ executed ──advance(accepted)──▶ accepted
```

`advance()` 显式校验前置态：从 `dispatched` 直接到 `accepted` 会被 `ValueError` 拦截。

## 代码位置

- `app/store_loop.py`：`LoopStore` / `BattleCard` / `Dispatch` 三张表 + 状态机 + `seed_loop()` / `stats()`；
- `tests/test_store_loop.py`：全量下发计数、合法推进、非法跳过拦截；
- `seed_loop.py`（仓库根）：一键建库并写入合成数据，便于本地演示。

## 跑起来

```bash
pip install sqlmodel
python seed_loop.py          # 建 store_loop.db + 写入 12 家 × 3 卡 = 36 条下发
python -c "from app.store_loop import stats, seed_loop; seed_loop(); print(stats())"
pytest tests/test_store_loop.py -q
```

把"下发覆盖率"和"状态不可跳步"做成可测试的断言，闭环才不会在无人察觉时悄悄破洞。
