from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.context.models import ActorContext
from app.modules.operations.application.ports import (
    OperationExecutionResult,
    OperationExecutorProtocol,
    StoredOperation,
)
from app.modules.runtime_gateway.application.service import RuntimeGatewayService


class RuntimeDurableRunReconciliationExecutor(OperationExecutorProtocol):
    kind = "runtime.durable_run"

    def __init__(self, *, service: RuntimeGatewayService, attempt_limit: int = 3) -> None:
        self._service = service
        self._attempt_limit = attempt_limit

    async def execute(
        self,
        *,
        operation: StoredOperation,
        actor: ActorContext,
    ) -> OperationExecutionResult:
        reconciled = await self._service.reconcile_operation(
            operation_id=operation.id,
            actor=actor,
        )
        if reconciled:
            return OperationExecutionResult(
                result_payload={"reconciled": True},
                metadata={"reconciliation": "run_associated"},
            )

        attempts = _attempts(operation.metadata)
        if attempts >= self._attempt_limit:
            await self._service.fail_reconciliation(operation_id=operation.id)
        raise RuntimeError("run_start_unknown_not_found")


def _attempts(metadata: Mapping[str, Any]) -> int:
    execution = metadata.get("_execution")
    if not isinstance(execution, Mapping):
        return 0
    value = execution.get("attempts")
    return value if isinstance(value, int) and value >= 0 else 0
