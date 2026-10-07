"""PostgreSQL-backed Casbin adapter (implements casbin.persist.Adapter).

Kept deliberately small: load/persist policy rows through the RevenueOS
session factory. Policy truth lives in revenueos_core alongside all other
durable business state (PostgreSQL = durable business state).
"""

import uuid

from casbin.persist import Adapter
from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DbSession

from revenueos_authorization.models import CasbinRule


def _rule_values(rule) -> list[str | None]:
    values = list(rule) + [None] * 4
    return [str(v) if v is not None else None for v in values[:4]]


class SQLAlchemyAdapter(Adapter):
    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

    def _session(self) -> DbSession:
        return self._session_factory()

    def load_policy(self, model) -> None:
        db = self._session()
        try:
            rows = db.execute(select(CasbinRule)).scalars().all()
            for row in rows:
                values = [row.v0, row.v1, row.v2, row.v3]
                while values and (values[-1] is None or values[-1] == ""):
                    values.pop()
                sec = "p" if row.ptype == "p" else "g"
                model.add_policy(sec, row.ptype, values)
        finally:
            db.close()

    def save_policy(self, model) -> None:
        db = self._session()
        try:
            db.execute(delete(CasbinRule))
            for sec in ("p", "g"):
                for ptype, rules in model[sec].items():
                    for rule in rules:
                        v0, v1, v2, v3 = _rule_values(rule)
                        db.add(
                            CasbinRule(
                                id=str(uuid.uuid4()), ptype=ptype, v0=v0, v1=v1, v2=v2, v3=v3
                            )
                        )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def add_policy(self, sec: str, ptype: str, rule) -> None:
        db = self._session()
        try:
            v0, v1, v2, v3 = _rule_values(rule)
            db.add(CasbinRule(id=str(uuid.uuid4()), ptype=ptype, v0=v0, v1=v1, v2=v2, v3=v3))
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def remove_policy(self, sec: str, ptype: str, rule) -> None:
        v0, v1, v2, v3 = _rule_values(rule)
        db = self._session()
        try:
            stmt = delete(CasbinRule).where(
                CasbinRule.ptype == ptype,
                CasbinRule.v0 == v0,
                CasbinRule.v1 == v1,
            )
            if v2 is None:
                stmt = stmt.where((CasbinRule.v2.is_(None)) | (CasbinRule.v2 == ""))
            else:
                stmt = stmt.where(CasbinRule.v2 == v2)
            if v3 is None:
                stmt = stmt.where((CasbinRule.v3.is_(None)) | (CasbinRule.v3 == ""))
            else:
                stmt = stmt.where(CasbinRule.v3 == v3)
            db.execute(stmt)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def remove_filtered_policy(self, sec: str, ptype: str, field_index: int, *field_values) -> None:
        db = self._session()
        try:
            stmt = delete(CasbinRule).where(CasbinRule.ptype == ptype)
            columns = ["v0", "v1", "v2", "v3"]
            for offset, value in enumerate(field_values):
                col = getattr(CasbinRule, columns[field_index + offset])
                if value is None or value == "":
                    stmt = stmt.where((col.is_(None)) | (col == ""))
                else:
                    stmt = stmt.where(col == value)
            db.execute(stmt)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()
