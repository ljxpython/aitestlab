from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from app.modules.agents.application.ports import StoredAssistantAggregate
from app.modules.agents.infra.sqlalchemy.models import AgentRecord, AssistantProfileRecord


def _to_aggregate(
    agent: AgentRecord,
    profile: AssistantProfileRecord | None,
) -> StoredAssistantAggregate:
    return StoredAssistantAggregate(
        id=agent.id,
        project_id=agent.project_id,
        name=agent.name,
        description=agent.description,
        graph_id=agent.graph_id,
        langgraph_assistant_id=agent.langgraph_assistant_id,
        runtime_base_url=agent.runtime_base_url,
        sync_status=agent.sync_status,
        last_sync_error=agent.last_sync_error,
        last_synced_at=agent.last_synced_at,
        status=profile.status if profile is not None else "active",
        config=dict(profile.config) if profile is not None else {},
        context=dict(profile.context) if profile is not None else {},
        metadata=dict(profile.metadata_json) if profile is not None else {},
        created_by=profile.created_by if profile is not None else None,
        updated_by=profile.updated_by if profile is not None else None,
        created_at=agent.created_at,
        updated_at=profile.updated_at if profile is not None else None,
    )


class SqlAlchemyAssistantsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def _get_agent(self, assistant_id: UUID) -> AgentRecord | None:
        return self.session.get(AgentRecord, assistant_id)

    def _get_profile(self, assistant_id: UUID) -> AssistantProfileRecord | None:
        stmt = select(AssistantProfileRecord).where(
            AssistantProfileRecord.agent_id == assistant_id
        )
        return self.session.scalar(stmt)

    def list_project_assistants(
        self,
        *,
        project_id: UUID,
        limit: int,
        offset: int,
        query: str | None,
        graph_id: str | None,
    ) -> tuple[list[StoredAssistantAggregate], int]:
        base_stmt = (
            select(AgentRecord, AssistantProfileRecord)
            .outerjoin(
                AssistantProfileRecord,
                AssistantProfileRecord.agent_id == AgentRecord.id,
            )
            .where(AgentRecord.project_id == project_id)
        )
        if query and query.strip():
            normalized = f"%{query.strip().lower()}%"
            base_stmt = base_stmt.where(
                func.lower(AgentRecord.name).like(normalized)
                | func.lower(AgentRecord.description).like(normalized)
                | func.lower(AgentRecord.graph_id).like(normalized)
                | func.lower(AgentRecord.langgraph_assistant_id).like(normalized)
            )
        if graph_id and graph_id.strip():
            base_stmt = base_stmt.where(AgentRecord.graph_id == graph_id.strip())

        stmt = (
            base_stmt.order_by(desc(AgentRecord.created_at), desc(AgentRecord.id))
            .offset(offset)
            .limit(limit)
        )
        count_stmt = select(func.count()).select_from(base_stmt.subquery())
        rows = list(self.session.execute(stmt).tuples().all())
        total = int(self.session.scalar(count_stmt) or 0)
        return [_to_aggregate(agent, profile) for agent, profile in rows], total

    def get_assistant_by_id(self, assistant_id: UUID) -> StoredAssistantAggregate | None:
        stmt = (
            select(AgentRecord, AssistantProfileRecord)
            .outerjoin(
                AssistantProfileRecord,
                AssistantProfileRecord.agent_id == AgentRecord.id,
            )
            .where(AgentRecord.id == assistant_id)
        )
        row = self.session.execute(stmt).tuples().first()
        if row is None:
            return None
        agent, profile = row
        return _to_aggregate(agent, profile)

    def get_by_project_and_graph_id(
        self,
        *,
        project_id: UUID,
        graph_id: str,
    ) -> StoredAssistantAggregate | None:
        stmt = (
            select(AgentRecord, AssistantProfileRecord)
            .outerjoin(
                AssistantProfileRecord,
                AssistantProfileRecord.agent_id == AgentRecord.id,
            )
            .where(
                AgentRecord.project_id == project_id,
                AgentRecord.graph_id == graph_id,
            )
            .limit(1)
        )
        row = self.session.execute(stmt).tuples().first()
        if row is None:
            return None
        agent, profile = row
        return _to_aggregate(agent, profile)

    def get_by_project_and_langgraph_assistant_id(
        self,
        *,
        project_id: UUID,
        langgraph_assistant_id: str,
    ) -> StoredAssistantAggregate | None:
        stmt = (
            select(AgentRecord, AssistantProfileRecord)
            .outerjoin(
                AssistantProfileRecord,
                AssistantProfileRecord.agent_id == AgentRecord.id,
            )
            .where(
                AgentRecord.project_id == project_id,
                AgentRecord.langgraph_assistant_id == langgraph_assistant_id,
            )
            .limit(1)
        )
        row = self.session.execute(stmt).tuples().first()
        if row is None:
            return None
        agent, profile = row
        return _to_aggregate(agent, profile)

    def create_assistant(
        self,
        *,
        project_id: UUID,
        name: str,
        description: str,
        graph_id: str,
        runtime_base_url: str,
        langgraph_assistant_id: str,
    ) -> StoredAssistantAggregate:
        record = AgentRecord(
            project_id=project_id,
            name=name,
            description=description,
            graph_id=graph_id,
            runtime_base_url=runtime_base_url,
            langgraph_assistant_id=langgraph_assistant_id,
            sync_status="ready",
            last_sync_error=None,
            last_synced_at=datetime.now(timezone.utc),
        )
        self.session.add(record)
        self.session.flush()
        return _to_aggregate(record, None)

    def update_assistant_runtime_fields(
        self,
        *,
        assistant_id: UUID,
        graph_id: str,
        name: str,
        description: str,
        runtime_base_url: str,
    ) -> StoredAssistantAggregate:
        record = self._get_agent(assistant_id)
        if record is None:
            raise ValueError("assistant_not_found")
        record.graph_id = graph_id
        record.name = name
        record.description = description
        record.runtime_base_url = runtime_base_url
        self.session.flush()
        return _to_aggregate(record, self._get_profile(assistant_id))

    def update_assistant_sync_state(
        self,
        *,
        assistant_id: UUID,
        sync_status: str,
        last_sync_error: str | None,
        last_synced_at: datetime | None,
    ) -> StoredAssistantAggregate:
        record = self._get_agent(assistant_id)
        if record is None:
            raise ValueError("assistant_not_found")
        record.sync_status = sync_status
        record.last_sync_error = last_sync_error
        record.last_synced_at = last_synced_at
        self.session.flush()
        return _to_aggregate(record, self._get_profile(assistant_id))

    def upsert_assistant_profile(
        self,
        *,
        assistant_id: UUID,
        status: str,
        config: dict,
        context: dict,
        metadata: dict,
        actor_user_id: UUID,
    ) -> StoredAssistantAggregate:
        profile = self._get_profile(assistant_id)
        if profile is None:
            profile = AssistantProfileRecord(
                agent_id=assistant_id,
                status=status,
                config=config,
                context=context,
                metadata_json=metadata,
                created_by=actor_user_id,
                updated_by=actor_user_id,
            )
            self.session.add(profile)
            self.session.flush()
        else:
            profile.status = status
            profile.config = config
            profile.context = context
            profile.metadata_json = metadata
            profile.updated_by = actor_user_id
            self.session.flush()
        record = self._get_agent(assistant_id)
        if record is None:
            raise ValueError("assistant_not_found")
        return _to_aggregate(record, profile)

    def delete_assistant(self, *, assistant_id: UUID) -> None:
        record = self._get_agent(assistant_id)
        if record is None:
            return
        self.session.delete(record)
        self.session.flush()
