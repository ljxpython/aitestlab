export type AuthTokenSet = {
  accessToken: string
  refreshToken: string
  tokenType: string
}

export type PlatformRole = 'platform_super_admin' | 'platform_operator' | 'platform_viewer'
export type ProjectRole = 'project_admin' | 'project_editor' | 'project_executor'
export type LegacyProjectRole = 'admin' | 'editor' | 'executor'
export type PermissionCode =
  | 'platform.user.read'
  | 'platform.user.write'
  | 'platform.audit.read'
  | 'platform.catalog.refresh'
  | 'platform.announcement.write'
  | 'platform.operation.read'
  | 'platform.operation.write'
  | 'platform.config.read'
  | 'platform.config.write'
  | 'platform.service_account.read'
  | 'platform.service_account.write'
  | 'project.member.read'
  | 'project.member.write'
  | 'project.audit.read'
  | 'project.announcement.read'
  | 'project.announcement.write'
  | 'project.assistant.read'
  | 'project.assistant.write'
  | 'project.runtime.read'
  | 'project.runtime.write'
  | 'project.knowledge.read'
  | 'project.knowledge.write'
  | 'project.knowledge.admin'
  | 'project.testcase.read'
  | 'project.testcase.write'
  | 'project.operation.read'
  | 'project.operation.write'

export type PaginatedResponse<T> = {
  items: T[]
  total: number
}

export type ManagementUser = {
  id: string
  username: string
  status: string
  is_super_admin: boolean
  platform_roles: PlatformRole[]
  project_roles: Record<string, ProjectRole[]>
  email?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export type ManagementUserProject = {
  project_id: string
  project_name: string
  project_description: string
  project_status: string
  role: ProjectRole
  joined_at: string
}

export type ManagementProject = {
  id: string
  name: string
  description: string
  status: string
}

export type ManagementProjectMember = {
  user_id: string
  username: string
  role: ProjectRole
}

export type ManagementAssistant = {
  id: string
  project_id: string
  name: string
  description: string
  graph_id: string
  langgraph_assistant_id: string
  runtime_base_url: string
  sync_status: string
  last_sync_error?: string | null
  last_synced_at?: string | null
  status: 'active' | 'disabled'
  config: Record<string, unknown>
  context: Record<string, unknown>
  metadata: Record<string, unknown>
  created_by?: string | null
  updated_by?: string | null
  created_at?: string | null
  updated_at?: string | null
}

export type ManagementAuditRow = {
  id: string
  request_id: string
  action: string | null
  target_type: string | null
  target_id: string | null
  method: string
  path: string
  status_code: number
  created_at: string
  user_id: string | null
}

export type OperationStatus =
  | 'submitted'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'

export type OperationArchiveScope = 'exclude' | 'include' | 'only'

export type ManagementOperation = {
  id: string
  kind: string
  status: OperationStatus
  requested_by: string
  tenant_id?: string | null
  project_id?: string | null
  idempotency_key?: string | null
  input_payload: Record<string, unknown>
  result_payload: Record<string, unknown>
  error_payload: Record<string, unknown>
  metadata: Record<string, unknown>
  cancel_requested_at?: string | null
  started_at?: string | null
  finished_at?: string | null
  archived_at?: string | null
  created_at: string
  updated_at: string
}

export type ManagementOperationPage = PaginatedResponse<ManagementOperation>

export type OperationBulkMutationResult = {
  requested_count: number
  updated_count: number
  skipped_count: number
  updated: ManagementOperation[]
  skipped_ids: string[]
}

export type OperationArtifactCleanupResult = {
  storage_backend: string
  retention_hours: number
  scanned_count: number
  removed_count: number
  missing_count: number
  bytes_reclaimed: number
}

export type RuntimeGraphPolicyValue = {
  is_enabled: boolean
  display_order?: number | null
  note?: string | null
  updated_at?: string | null
}

export type RuntimeGraphPolicyItem = {
  catalog_id: string
  graph_id: string
  display_name: string
  description: string
  source_type: string
  sync_status: string
  last_synced_at?: string | null
  policy: RuntimeGraphPolicyValue
}

export type RuntimeToolPolicyValue = {
  is_enabled: boolean
  display_order?: number | null
  note?: string | null
  updated_at?: string | null
}

export type RuntimeToolPolicyItem = {
  catalog_id: string
  tool_key: string
  name: string
  source: string
  description: string
  sync_status: string
  last_synced_at?: string | null
  policy: RuntimeToolPolicyValue
}

export type RuntimeModelPolicyValue = {
  is_enabled: boolean
  is_default_for_project: boolean
  temperature_default?: number | null
  note?: string | null
  updated_at?: string | null
}

export type RuntimeModelPolicyItem = {
  catalog_id: string
  model_id: string
  display_name: string
  is_default_runtime: boolean
  sync_status: string
  last_synced_at?: string | null
  policy: RuntimeModelPolicyValue
}

export type RuntimeGraphPolicyListResponse = PaginatedResponse<RuntimeGraphPolicyItem>
export type RuntimeToolPolicyListResponse = PaginatedResponse<RuntimeToolPolicyItem>
export type RuntimeModelPolicyListResponse = PaginatedResponse<RuntimeModelPolicyItem>

export type PlatformConfigSnapshot = {
  service: {
    name: string
    version: string
    env: string
    docs_enabled: boolean
  }
  database: {
    enabled: boolean
    auto_create: boolean
    migration_strategy: string
  }
  operations: {
    queue_backend: string
    worker_poll_interval_seconds: number
    worker_idle_sleep_seconds: number
    worker_heartbeat_interval_seconds: number
    worker_stale_after_seconds: number
    artifact_storage_backend: string
    artifact_retention_hours: number
    artifact_cleanup_batch_size: number
    queue_depth: number
    running_count: number
    succeeded_count: number
    failed_count: number
    cancelled_count: number
    archived_count: number
    avg_duration_ms: number
    max_duration_ms: number
  }
  auth: {
    required: boolean
    bootstrap_admin_enabled: boolean
  }
  runtime: {
    langgraph_upstream_url: string
    interaction_data_service_configured: boolean
  }
  observability: {
    requests: {
      total: number
      failed: number
      failure_rate: number
      avg_duration_ms: number
      max_duration_ms: number
      by_method: Record<string, number>
      by_status_family: Record<string, number>
      top_paths: Array<{
        path: string
        count: number
        failed: number
        failure_rate: number
        avg_duration_ms: number
        max_duration_ms: number
      }>
    }
    operations: {
      queue_backend: string
      worker_poll_interval_seconds: number
      worker_idle_sleep_seconds: number
      worker_heartbeat_interval_seconds: number
      worker_stale_after_seconds: number
      artifact_storage_backend: string
      artifact_retention_hours: number
      artifact_cleanup_batch_size: number
      queue_depth: number
      running_count: number
      succeeded_count: number
      failed_count: number
      cancelled_count: number
      archived_count: number
      avg_duration_ms: number
      max_duration_ms: number
    }
    workers: {
      heartbeat_interval_seconds: number
      stale_after_seconds: number
      healthy_count: number
      stale_count: number
      items: Array<{
        worker_id: string
        queue_backend: string
        hostname: string
        pid: string
        status: string
        current_operation_id: string | null
        last_error: string | null
        last_started_at: string | null
        last_completed_at: string | null
        last_heartbeat_at: string | null
        age_seconds: number
        healthy: boolean
        metadata: Record<string, unknown>
      }>
    }
    trace: {
      request_id_header: string
      trace_id_header: string
      operation_chain_source: string
    }
  }
  security: {
    oidc: {
      enabled: boolean
      issuer_url: string | null
      client_id: string | null
      mode: string
    }
    service_accounts: {
      enabled: boolean
      api_key_header: string
      default_token_ttl_days: number
      total_accounts: number
      active_accounts: number
      active_tokens: number
      revoked_tokens: number
    }
    sensitive_config: Record<
      string,
      {
        configured: boolean
        masked_value: string | null
      }
    >
  }
  environment: {
    current: string
    supported: string[]
    production_like: boolean
    auth_required: boolean
    docs_enabled: boolean
    bootstrap_admin_enabled: boolean
  }
  data_governance: {
    artifact_retention_hours: number
    artifact_cleanup_batch_size: number
    audit_storage: string
    export_mode: string
    delete_mode: string
  }
  feature_flags: Record<string, boolean>
}

export type ManagementAnnouncement = {
  id: string
  title: string
  summary: string
  body: string
  tone: 'info' | 'warning' | 'success'
  scope_type: string
  scope_project_id: string | null
  status: string
  publish_at: string | null
  expire_at: string | null
  created_at: string | null
  updated_at: string | null
  is_read: boolean
}

export type ManagementServiceAccountToken = {
  id: string
  name: string
  token_prefix: string
  status: string
  expires_at: string | null
  last_used_at: string | null
  revoked_at: string | null
  created_at: string | null
}

export type ManagementServiceAccount = {
  id: string
  name: string
  description: string | null
  status: string
  platform_roles: PlatformRole[]
  created_by: string | null
  updated_by: string | null
  last_used_at: string | null
  created_at: string | null
  updated_at: string | null
  tokens: ManagementServiceAccountToken[]
}

export type ManagementServiceAccountPage = PaginatedResponse<ManagementServiceAccount>

export type CreatedServiceAccountToken = {
  token: ManagementServiceAccountToken
  plain_text_token: string
}

export type RuntimeModelItem = {
  id: string
  runtime_id: string
  model_id: string
  display_name: string
  is_default: boolean
  sync_status: string
  last_seen_at: string | null
  last_synced_at: string | null
}

export type RuntimeModelsResponse = {
  count: number
  models: RuntimeModelItem[]
  last_synced_at: string | null
}

export type RuntimeToolItem = {
  id: string
  runtime_id: string
  tool_key: string
  name: string
  source: string
  description: string
  sync_status: string
  last_seen_at: string | null
  last_synced_at: string | null
}

export type RuntimeToolsResponse = {
  count: number
  tools: RuntimeToolItem[]
  last_synced_at: string | null
}

export type RuntimeRefreshResponse = {
  ok: boolean
  count: number
  last_synced_at: string | null
}

export type RuntimeGraphItem = {
  id: string
  runtime_id: string
  graph_id: string
  display_name: string
  description: string
  source_type: string
  sync_status: string
  last_seen_at: string | null
  last_synced_at: string | null
}

export type RuntimeGraphsResponse = {
  count: number
  graphs: RuntimeGraphItem[]
  last_synced_at: string | null
}

export type ProjectKnowledgeSpace = {
  id: string
  project_id: string
  provider: string
  display_name: string
  workspace_key: string
  status: string
  service_base_url: string
  runtime_profile_json: Record<string, unknown>
  health?: Record<string, unknown> | null
  created_at?: string | null
  updated_at?: string | null
}

export type KnowledgeMetadataFilters = {
  tags_any?: string[]
  tags_all?: string[]
  attributes?: Record<string, string | string[]>
}

export type KnowledgeMetadataBoost = {
  tags_any?: string[]
  attributes?: Record<string, string | string[]>
  weight?: number
}

export type KnowledgeUploadMetadata = {
  tags?: string[]
  attributes?: Record<string, string>
}

export type KnowledgeDocument = {
  id: string
  content_summary: string
  content_length: number
  status: string
  created_at?: string | null
  updated_at?: string | null
  track_id?: string | null
  chunks_count?: number | null
  error_msg?: string | null
  metadata?: Record<string, unknown> | null
  file_path?: string | null
}

export type KnowledgeDocumentsPage = {
  documents: KnowledgeDocument[]
  pagination: {
    page: number
    page_size: number
    total_count: number
    total_pages: number
    has_next: boolean
    has_prev: boolean
  }
  status_counts: Record<string, number>
}

export type KnowledgeTrackStatus = {
  track_id: string
  documents: KnowledgeDocument[]
  total_count: number
  status_summary: Record<string, number>
}

export type KnowledgePipelineStatus = {
  autoscanned?: boolean
  busy?: boolean
  job_name?: string
  job_start?: string | null
  docs?: number
  batchs?: number
  cur_batch?: number
  request_pending?: boolean
  latest_message?: string
  history_messages?: string[]
  update_status?: Record<string, boolean[]>
  [key: string]: unknown
}

export type KnowledgeDocumentsScanProgress = {
  is_scanning: boolean
  current_file: string
  indexed_count: number
  total_files: number
  progress: number
}

export type KnowledgeQueryReference = {
  reference_id: string
  file_path: string
  content?: string[]
}

export type KnowledgeQueryResult = {
  response: string
  references?: KnowledgeQueryReference[] | null
}

export type ManagementGraph = {
  id: string
  runtime_id: string
  graph_id: string
  display_name: string
  description?: string
  source_type: string
  sync_status: string
  last_synced_at: string | null
}

export type ManagementGraphListResponse = PaginatedResponse<ManagementGraph> & {
  last_synced_at?: string | null
}

export type ManagementThread = {
  thread_id: string
  status?: string | null
  created_at?: string | null
  updated_at?: string | null
  metadata?: Record<string, unknown> | null
  values?: Record<string, unknown> | null
  error?: Record<string, unknown> | string | null
}

export type ThreadHistoryEntry = Record<string, unknown>

export type TestcaseOverview = {
  project_id: string
  documents_total: number
  parsed_documents_total: number
  failed_documents_total: number
  test_cases_total: number
  latest_batch_id?: string | null
  latest_activity_at?: string | null
}

export type TestcaseBatchSummary = {
  batch_id: string
  documents_count: number
  test_cases_count: number
  latest_created_at?: string | null
  parse_status_summary: Record<string, number>
}

export type TestcaseBatchDetailCase = {
  id: string
  case_id?: string | null
  title: string
  status: string
  batch_id?: string | null
  module_name?: string | null
  priority?: string | null
  updated_at?: string | null
}

export type TestcaseDocument = {
  id: string
  project_id: string
  batch_id?: string | null
  filename: string
  content_type: string
  storage_path?: string | null
  source_kind: string
  parse_status: string
  summary_for_model: string
  parsed_text?: string | null
  structured_data?: Record<string, unknown> | null
  provenance: Record<string, unknown>
  confidence?: number | null
  error?: Record<string, unknown> | null
  created_at: string
}

export type TestcaseDocumentRelationCase = {
  id: string
  case_id?: string | null
  title: string
  status: string
  batch_id?: string | null
}

export type TestcaseDocumentRelations = {
  document: TestcaseDocument
  runtime_meta: Record<string, unknown>
  related_cases: TestcaseDocumentRelationCase[]
  related_cases_count: number
}

export type TestcaseCase = {
  id: string
  project_id: string
  batch_id?: string | null
  case_id?: string | null
  title: string
  description: string
  status: string
  module_name?: string | null
  priority?: string | null
  source_document_ids: string[]
  source_documents?: TestcaseDocument[]
  missing_source_document_ids?: string[]
  content_json: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type TestcaseBatchDetail = {
  batch: TestcaseBatchSummary
  documents: {
    items: TestcaseDocument[]
    total: number
  }
  test_cases: {
    items: TestcaseBatchDetailCase[]
    total: number
  }
}

export type TestcaseRole = {
  project_id: string
  role: ProjectRole
  can_write_testcase: boolean
}

export type ManagementDownload = {
  blob: Blob
  filename: string | null
  contentType: string | null
}

export type ManagementProjectListResponse = PaginatedResponse<ManagementProject>
export type ManagementUserListResponse = PaginatedResponse<ManagementUser>
export type ManagementAssistantListResponse = PaginatedResponse<ManagementAssistant>
export type ManagementAuditListResponse = PaginatedResponse<ManagementAuditRow>
