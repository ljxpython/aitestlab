import {
  createRuntimeThread,
  normalizeRuntimeGatewayError
} from '@/services/runtime-gateway/workspace.service'
import { buildChatRunSubmitOptions } from '@/services/runtime/runtime-contract'
import type { PlatformChatStreamActionDeps } from './types'
import {
  buildOptimisticMessage,
  getMetadataCheckpointId,
  toOptimisticBaseMessage
} from './helpers'

export function createPlatformChatStreamActions(deps: PlatformChatStreamActionDeps) {
  async function reportRunError(error: unknown, fallbackMessage: string) {
    const normalized = normalizeRuntimeGatewayError(error, fallbackMessage)
    if (normalized.status === 409) {
      const threadId = deps.options.activeThreadId.value.trim()
      if (threadId) {
        await deps.options.onRefreshThread(threadId, { preserveInfo: true }).catch(() => undefined)
      }
      if (deps.interruptPayload.value !== undefined) {
        deps.detailInfo.value = '线程中已有待处理事项，已同步最新状态，请先完成确认。'
      }
    }
    deps.detailError.value = normalized.message
  }

  function clearDetailFeedback(controlOptions: { preserveInfo?: boolean } = {}) {
    deps.detailError.value = ''

    if (!controlOptions.preserveInfo) {
      deps.detailInfo.value = ''
    }
  }

  function resetStreamView(controlOptions: { preserveInfo?: boolean } = {}) {
    deps.options.historyItems.value = []
    deps.options.selectedBranch.value = ''
    clearDetailFeedback(controlOptions)
    deps.commandPending.value = false
    deps.cancelling.value = false
    deps.lastRunId.value = ''
    deps.lastEventAt.value = ''
  }

  async function sendMessage(content: string, attachments: Parameters<typeof buildOptimisticMessage>[1] = []) {
    const projectId = deps.options.projectId.value.trim()
    const target = deps.options.target.value
    const normalizedContent = content.trim()
    const normalizedAttachments = attachments.filter((item) => item && typeof item === 'object')

    if (!projectId || !target || deps.isBusy.value || (!normalizedContent && normalizedAttachments.length === 0)) {
      return false
    }

    deps.commandPending.value = true
    deps.cancelling.value = false
    clearDetailFeedback()
    deps.lastRunId.value = ''

    const humanMessage = buildOptimisticMessage(content, normalizedAttachments)
    const checkpointId =
      deps.options.selectedBranch.value
        ? getMetadataCheckpointId(deps.messageMetadataById.value[deps.messages.value[deps.messages.value.length - 1]?.id || ''])
        : ''
    const runtimeSubmitOptions = buildChatRunSubmitOptions(deps.options.runOptions)

    try {
      let threadId = deps.options.activeThreadId.value.trim()
      let createdThread = false
      if (!threadId) {
        const created = await createRuntimeThread(projectId, target)
        threadId = created.thread_id
        createdThread = true
      }

      const submission = deps.stream.submit(
        {
          messages: [humanMessage]
        },
        {
          threadId,
          forkFrom: checkpointId || undefined,
          ...runtimeSubmitOptions,
          onError: (submitError: unknown) => {
            deps.detailError.value = normalizeRuntimeGatewayError(submitError, '对话发送失败').message
          }
        }
      )
      if (createdThread) {
        deps.options.activeThreadId.value = threadId
      }
      await submission
      deps.commandPending.value = false
      return true
    } catch (runError) {
      await reportRunError(runError, '对话发送失败')
      deps.commandPending.value = false
      deps.cancelling.value = false
      return false
    }
  }

  async function cancelActiveRun() {
    const projectId = deps.options.projectId.value.trim()
    const threadId = deps.options.activeThreadId.value.trim()

    if (!deps.isBusy.value || !projectId || !threadId) {
      return false
    }

    deps.cancelling.value = true

    try {
      await deps.stream.stop()
      deps.detailInfo.value = '已请求停止，正在同步运行状态。'
    } catch (stopError) {
      await deps.stream.stop({ cancel: false }).catch(() => undefined)
      deps.detailError.value = normalizeRuntimeGatewayError(stopError, '停止运行失败').message
    } finally {
      deps.commandPending.value = false
      deps.cancelling.value = false
    }

    return true
  }

  async function resumeInterruptedRun(resumePayload: unknown, interruptId?: string) {
    const threadId = deps.options.activeThreadId.value.trim()
    if (!threadId || deps.interruptPayload.value === undefined || deps.isBusy.value) {
      return false
    }

    deps.commandPending.value = true
    deps.cancelling.value = false
    clearDetailFeedback()
    const runtimeSubmitOptions = buildChatRunSubmitOptions(deps.options.runOptions)

    try {
      await deps.stream.respond(resumePayload, {
        ...runtimeSubmitOptions,
        interruptId: interruptId?.trim() || undefined
      })
      deps.commandPending.value = false
      return true
    } catch (runError) {
      await reportRunError(runError, '恢复中断失败')
      deps.commandPending.value = false
      deps.cancelling.value = false
      return false
    }
  }

  async function resumeAllInterruptedRuns(responsesById: Record<string, unknown>) {
    const threadId = deps.options.activeThreadId.value.trim()
    if (!threadId || Object.keys(responsesById).length === 0 || deps.isBusy.value) {
      return false
    }

    deps.commandPending.value = true
    deps.cancelling.value = false
    clearDetailFeedback()

    try {
      await deps.stream.respondAll(responsesById, buildChatRunSubmitOptions(deps.options.runOptions))
      deps.commandPending.value = false
      return true
    } catch (runError) {
      await reportRunError(runError, '批量恢复中断失败')
      deps.commandPending.value = false
      deps.cancelling.value = false
      return false
    }
  }

  function selectBranch(branch: string) {
    deps.options.selectedBranch.value = branch.trim()
    deps.detailError.value = ''
  }

  async function retryMessage(messageId: string, forkFrom?: string) {
    const threadId = deps.options.activeThreadId.value.trim()
    const checkpointId =
      forkFrom?.trim() ||
      deps.messageMetadataById.value[messageId]?.parentCheckpoint?.checkpoint_id?.trim() ||
      ''

    if (!threadId || !checkpointId || deps.isBusy.value) {
      return false
    }

    deps.commandPending.value = true
    deps.cancelling.value = false
    clearDetailFeedback()
    deps.lastRunId.value = ''
    const runtimeSubmitOptions = buildChatRunSubmitOptions(deps.options.runOptions)

    try {
      await deps.stream.submit(undefined, {
        forkFrom: checkpointId,
        ...runtimeSubmitOptions,
      })
      deps.commandPending.value = false
      return true
    } catch (runError) {
      await reportRunError(runError, '重新执行失败')
      deps.commandPending.value = false
      deps.cancelling.value = false
      return false
    }
  }

  async function editHumanMessage(
    messageId: string,
    content: Parameters<typeof toOptimisticBaseMessage>[0],
    forkFrom?: string
  ) {
    const threadId = deps.options.activeThreadId.value.trim()
    const metadata = deps.messageMetadataById.value[messageId]
    const checkpointId = forkFrom?.trim() || metadata?.parentCheckpoint?.checkpoint_id?.trim() || ''

    if (!threadId || !checkpointId || deps.isBusy.value) {
      return false
    }

    const optimisticMessage = toOptimisticBaseMessage(content)

    deps.commandPending.value = true
    deps.cancelling.value = false
    clearDetailFeedback()
    deps.lastRunId.value = ''
    const runtimeSubmitOptions = buildChatRunSubmitOptions(deps.options.runOptions)

    try {
      await deps.stream.submit(
        {
          messages: [optimisticMessage]
        },
        {
          forkFrom: checkpointId,
          ...runtimeSubmitOptions,
        }
      )
      deps.commandPending.value = false
      return true
    } catch (runError) {
      await reportRunError(runError, '编辑重发失败')
      deps.commandPending.value = false
      deps.cancelling.value = false
      return false
    }
  }

  return {
    cancelActiveRun,
    clearDetailFeedback,
    editHumanMessage,
    resetStreamView,
    resumeAllInterruptedRuns,
    resumeInterruptedRun,
    retryMessage,
    selectBranch,
    sendMessage
  }
}
