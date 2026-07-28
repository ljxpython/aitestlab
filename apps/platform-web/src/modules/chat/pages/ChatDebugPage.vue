<script setup lang="ts">
import type { Message } from "@langchain/langgraph-sdk";
import { computed, reactive, ref, watch } from "vue";
import { useRoute } from "vue-router";
import BaseButton from "@/components/base/BaseButton.vue";
import EmptyState from "@/components/platform/EmptyState.vue";
import StateBanner from "@/components/platform/StateBanner.vue";
import PageHeader from "@/components/layout/PageHeader.vue";
import { useWorkspaceProjectContext } from "@/composables/useWorkspaceProjectContext";
import {
  createRuntimeDebugSession,
  streamRuntimeDebugRun,
  type RuntimeDebugBreakpointMode,
} from "@/services/runtime-gateway/debug.service";
import {
  cancelRuntimeRun,
  getRuntimeThreadSnapshot,
  normalizeRuntimeGatewayError,
} from "@/services/runtime-gateway/workspace.service";
import { getThreadStateValues, toPrettyJson } from "@/utils/threads";
import { hasPendingTaskToolCall } from "../composables/platform-chat-stream/helpers";
import type { ChatResolvedTarget, ChatRunOptions } from "../types";

type DebugEvent = {
  id: number;
  event: string;
  data: unknown;
};

const route = useRoute();
const { activeProjectId, activeProject } = useWorkspaceProjectContext();
const targetType = ref<"assistant" | "graph">(
  route.query.targetType === "graph" ? "graph" : "assistant",
);
const targetId = ref(
  (targetType.value === "graph"
    ? typeof route.query.graphId === "string" && route.query.graphId
    : typeof route.query.assistantId === "string" && route.query.assistantId) ||
    "",
);
const breakpointMode = ref<RuntimeDebugBreakpointMode>("tools");
const streamSubgraphs = ref(true);
const input = ref("");
const threadId = ref("");
const runId = ref("");
const status = ref<"idle" | "running" | "interrupted" | "error">("idle");
const error = ref("");
const info = ref("");
const values = ref<Record<string, unknown>>({});
const messages = ref<Message[]>([]);
const events = ref<DebugEvent[]>([]);
const runOptions = reactive<ChatRunOptions>({
  modelId: "",
  systemPrompt: "",
  enableTools: true,
  toolNames: [],
  temperature: "",
  maxTokens: "",
});

let eventId = 0;
let activeAbortController: AbortController | null = null;

const target = computed<ChatResolvedTarget | null>(() => {
  const resolvedTargetId = targetId.value.trim();
  if (!resolvedTargetId) {
    return null;
  }

  if (targetType.value === "graph") {
    return {
      targetType: "graph",
      graphId: resolvedTargetId,
      graphName: resolvedTargetId,
      updatedAt: "",
      resolvedTargetId,
      displayName: resolvedTargetId,
      label: `Graph · ${resolvedTargetId}`,
    };
  }

  return {
    targetType: "assistant",
    assistantId: resolvedTargetId,
    assistantName: resolvedTargetId,
    updatedAt: "",
    resolvedTargetId,
    displayName: resolvedTargetId,
    label: `Assistant · ${resolvedTargetId}`,
  };
});
const isRunning = computed(() => status.value === "running");
const canStart = computed(
  () => Boolean(activeProjectId.value && target.value) && !isRunning.value,
);
const canContinue = computed(
  () =>
    status.value === "interrupted" &&
    Boolean(threadId.value) &&
    !isRunning.value,
);
const eventText = computed(() =>
  events.value
    .map((item) => `${item.id}. ${item.event}\n${toPrettyJson(item.data)}`)
    .join("\n\n"),
);

function appendEvent(event: string, data: unknown) {
  eventId += 1;
  events.value = [...events.value.slice(-199), { id: eventId, event, data }];
}

function resetSession() {
  activeAbortController?.abort();
  activeAbortController = null;
  threadId.value = "";
  runId.value = "";
  status.value = "idle";
  error.value = "";
  info.value = "";
  values.value = {};
  messages.value = [];
  events.value = [];
  eventId = 0;
}

async function ensureSession() {
  const projectId = activeProjectId.value?.trim() || "";
  const currentTarget = target.value;
  if (!projectId || !currentTarget) {
    throw new Error("缺少项目或调试目标");
  }
  if (threadId.value) {
    return threadId.value;
  }

  const session = await createRuntimeDebugSession(projectId, currentTarget);
  threadId.value = session.thread_id;
  appendEvent("debug.session.created", { thread_id: session.thread_id });
  return session.thread_id;
}

async function refreshSession() {
  const projectId = activeProjectId.value?.trim() || "";
  if (!projectId || !threadId.value) {
    return "idle" as const;
  }

  const snapshot = await getRuntimeThreadSnapshot(projectId, threadId.value, {
    historyLimit: 1,
  });
  const nextValues =
    getThreadStateValues(snapshot.state || snapshot.detail) || {};
  values.value = nextValues;
  messages.value = Array.isArray(nextValues.messages)
    ? (nextValues.messages as Message[])
    : [];
  const nextStatus =
    snapshot.detail.status === "interrupted" ? "interrupted" : "idle";
  status.value = nextStatus;
  return nextStatus;
}

async function executeRun(
  nextInput: Record<string, unknown> | null,
  continueFromInterrupt = false,
) {
  const projectId = activeProjectId.value?.trim() || "";
  const currentTarget = target.value;
  if (!projectId || !currentTarget || isRunning.value) {
    return false;
  }

  const controller = new AbortController();
  activeAbortController = controller;
  status.value = "running";
  error.value = "";
  info.value = "";

  try {
    const sessionThreadId = await ensureSession();
    const stream = streamRuntimeDebugRun({
      projectId,
      threadId: sessionThreadId,
      target: currentTarget,
      request: {
        input: nextInput,
        runOptions,
        breakpointMode: breakpointMode.value,
        streamSubgraphs: streamSubgraphs.value,
        continueFromInterrupt,
        hasPendingTaskToolCall: hasPendingTaskToolCall(messages.value),
      },
      signal: controller.signal,
      onRunCreated: (createdRunId) => {
        runId.value = createdRunId;
      },
    });

    for await (const event of stream) {
      appendEvent(event.event, event.data);
      if (
        event.event === "metadata" &&
        event.data &&
        typeof event.data === "object"
      ) {
        const createdRunId = (event.data as { run_id?: unknown }).run_id;
        if (typeof createdRunId === "string") {
          runId.value = createdRunId;
        }
      }
      if (
        event.event.split("|")[0] === "values" &&
        event.data &&
        typeof event.data === "object"
      ) {
        values.value = event.data as Record<string, unknown>;
        messages.value = Array.isArray(values.value.messages)
          ? (values.value.messages as Message[])
          : messages.value;
      }
      if (event.event.split("|")[0] === "error") {
        throw new Error(toPrettyJson(event.data));
      }
    }

    const nextStatus = await refreshSession();
    info.value =
      nextStatus === "interrupted" ? "运行已在静态断点暂停。" : "运行已完成。";
    return true;
  } catch (runError) {
    if (controller.signal.aborted) {
      status.value = "idle";
      info.value = "运行已取消。";
      return true;
    }

    status.value = "error";
    error.value = normalizeRuntimeGatewayError(
      runError,
      "调试运行失败",
    ).message;
    return false;
  } finally {
    if (activeAbortController === controller) {
      activeAbortController = null;
    }
  }
}

async function startRun() {
  const content = input.value.trim();
  if (!content) {
    return;
  }

  const humanMessage: Message = {
    id: crypto.randomUUID(),
    type: "human",
    content,
  } as Message;
  const started = await executeRun({ messages: [humanMessage] });
  if (started) {
    input.value = "";
  }
}

async function continueRun() {
  await executeRun(null, true);
}

async function cancelRun() {
  if (!isRunning.value) {
    return;
  }

  const projectId = activeProjectId.value?.trim() || "";
  activeAbortController?.abort();
  if (projectId && threadId.value && runId.value) {
    await cancelRuntimeRun(projectId, threadId.value, runId.value).catch(
      () => undefined,
    );
  }
  status.value = "idle";
  info.value = "运行已取消。";
}

watch([activeProjectId, targetType, targetId], resetSession);
</script>

<template>
  <section class="pw-page-shell flex min-h-0 flex-1 flex-col">
    <PageHeader
      title="Runtime Debug"
      eyebrow="Legacy Debug"
      description=""
    />

    <EmptyState
      v-if="!activeProject"
      icon="project"
      title="请先选择项目"
      description=""
    />

    <template v-else>
      <StateBanner
        v-if="error"
        title="调试运行失败"
        :description="error"
        variant="danger"
      />
      <StateBanner
        v-else-if="info"
        title="调试状态"
        :description="info"
        variant="info"
      />

      <div class="grid min-h-0 flex-1 gap-4 xl:grid-cols-[360px_minmax(0,1fr)]">
        <aside class="min-w-0 space-y-4 overflow-y-auto">
          <section class="pw-panel space-y-4 p-4">
            <div class="text-sm font-semibold text-gray-900 dark:text-white">
              Session
            </div>
            <div class="flex gap-2">
              <button
                v-for="item in ['assistant', 'graph'] as const"
                :key="item"
                type="button"
                class="pw-chip-toggle"
                :class="targetType === item ? 'pw-chip-toggle-active' : ''"
                :disabled="isRunning"
                @click="targetType = item"
              >
                {{ item === "assistant" ? "Assistant" : "Graph" }}
              </button>
            </div>
            <label class="block">
              <span class="pw-input-label">Target ID</span>
              <input
                v-model="targetId"
                class="pw-input"
                :disabled="isRunning"
              >
            </label>
            <dl class="space-y-2 text-xs text-gray-500 dark:text-dark-300">
              <div class="flex justify-between gap-3">
                <dt>Thread</dt>
                <dd class="break-all text-right">
                  {{ threadId || "--" }}
                </dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt>Run</dt>
                <dd class="break-all text-right">
                  {{ runId || "--" }}
                </dd>
              </div>
              <div class="flex justify-between gap-3">
                <dt>Status</dt>
                <dd>{{ status }}</dd>
              </div>
            </dl>
            <BaseButton
              variant="secondary"
              :disabled="isRunning"
              @click="resetSession"
            >
              新建 Debug Session
            </BaseButton>
          </section>

          <section class="pw-panel space-y-4 p-4">
            <div class="text-sm font-semibold text-gray-900 dark:text-white">
              Breakpoints
            </div>
            <div class="flex gap-2">
              <button
                v-for="item in [
                  { value: 'tools', label: 'Tools' },
                  { value: 'none', label: '关闭' },
                ] as const"
                :key="item.value"
                type="button"
                class="pw-chip-toggle"
                :class="
                  breakpointMode === item.value ? 'pw-chip-toggle-active' : ''
                "
                :disabled="isRunning"
                @click="breakpointMode = item.value"
              >
                {{ item.label }}
              </button>
            </div>
            <label class="flex items-center justify-between gap-3 text-sm">
              <span>Subgraph Stream</span>
              <input
                v-model="streamSubgraphs"
                type="checkbox"
                class="pw-table-checkbox"
                :disabled="isRunning"
              >
            </label>
          </section>

          <section class="pw-panel space-y-4 p-4">
            <div class="text-sm font-semibold text-gray-900 dark:text-white">
              Runtime
            </div>
            <label class="block"><span class="pw-input-label">Model ID</span><input
              v-model="runOptions.modelId"
              class="pw-input"
              :disabled="isRunning"
            ></label>
            <label class="block"><span class="pw-input-label">System Prompt</span><textarea
              v-model="runOptions.systemPrompt"
              rows="4"
              class="pw-input resize-y"
              :disabled="isRunning"
            />
            </label>
            <label class="flex items-center justify-between gap-3 text-sm"><span>Tools</span><input
              v-model="runOptions.enableTools"
              type="checkbox"
              class="pw-table-checkbox"
              :disabled="isRunning"
            ></label>
            <label class="block"><span class="pw-input-label">Tool Names</span><input
              :value="runOptions.toolNames.join(', ')"
              class="pw-input"
              :disabled="isRunning"
              @input="
                runOptions.toolNames = (
                  ($event.target as HTMLInputElement).value || ''
                )
                  .split(',')
                  .map((item) => item.trim())
                  .filter(Boolean)
              "
            ></label>
            <div class="grid grid-cols-2 gap-3">
              <label><span class="pw-input-label">Temperature</span><input
                v-model="runOptions.temperature"
                class="pw-input"
                :disabled="isRunning"
              ></label>
              <label><span class="pw-input-label">Max Tokens</span><input
                v-model="runOptions.maxTokens"
                class="pw-input"
                :disabled="isRunning"
              ></label>
            </div>
          </section>
        </aside>

        <main class="flex min-h-0 min-w-0 flex-col gap-4">
          <section class="pw-panel flex min-h-[280px] flex-1 flex-col p-4">
            <div class="mb-3 flex items-center justify-between gap-3">
              <div class="text-sm font-semibold text-gray-900 dark:text-white">
                Event Stream
              </div>
              <span class="pw-pill-soft pw-pill-soft-neutral">{{
                events.length
              }}</span>
            </div>
            <pre
              class="min-h-0 flex-1 overflow-auto whitespace-pre-wrap break-words text-xs leading-6 text-gray-600 dark:text-dark-100"
            >{{ eventText || "No events" }}</pre>
          </section>

          <section class="pw-panel p-4">
            <div
              class="mb-3 text-sm font-semibold text-gray-900 dark:text-white"
            >
              State
            </div>
            <pre
              class="max-h-64 overflow-auto whitespace-pre-wrap break-words text-xs leading-6 text-gray-600 dark:text-dark-100"
            >{{ toPrettyJson(values) }}</pre>
          </section>

          <section class="pw-panel p-3">
            <textarea
              v-model="input"
              rows="3"
              class="pw-input resize-y"
              :disabled="isRunning"
            />
            <div class="mt-3 flex flex-wrap justify-end gap-2">
              <BaseButton
                v-if="canContinue"
                variant="secondary"
                @click="continueRun"
              >
                Continue
              </BaseButton>
              <BaseButton
                v-if="isRunning"
                variant="danger"
                @click="cancelRun"
              >
                Cancel
              </BaseButton>
              <BaseButton
                v-else
                :disabled="!canStart || !input.trim()"
                @click="startRun"
              >
                Run
              </BaseButton>
            </div>
          </section>
        </main>
      </div>
    </template>
  </section>
</template>
