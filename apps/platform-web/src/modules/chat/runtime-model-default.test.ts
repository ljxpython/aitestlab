import type { RuntimeModelItem, RuntimeModelPolicyItem } from '@/types/management'
import { resolveChatDefaultModelId } from './runtime-model-default'

function model(modelId: string, isDefault = false): RuntimeModelItem {
  return {
    id: modelId,
    runtime_id: 'runtime',
    model_id: modelId,
    display_name: modelId,
    is_default: isDefault,
    sync_status: 'ready',
    last_seen_at: null,
    last_synced_at: null
  }
}

function policy(
  modelId: string,
  options: { enabled?: boolean; projectDefault?: boolean } = {}
): RuntimeModelPolicyItem {
  return {
    catalog_id: modelId,
    model_id: modelId,
    display_name: modelId,
    is_default_runtime: false,
    sync_status: 'ready',
    last_synced_at: null,
    policy: {
      is_enabled: options.enabled ?? true,
      is_default_for_project: options.projectDefault ?? false,
      temperature_default: null,
      note: null
    }
  }
}

describe('resolveChatDefaultModelId', () => {
  it('优先使用已启用的项目默认模型', () => {
    expect(
      resolveChatDefaultModelId(
        [model('runtime-default', true), model('project-default')],
        [policy('project-default', { projectDefault: true })]
      )
    ).toBe('project-default')
  })

  it('忽略未启用或不可用的项目默认模型', () => {
    expect(
      resolveChatDefaultModelId(
        [model('runtime-default', true), model('disabled-default')],
        [
          policy('missing-model', { projectDefault: true }),
          policy('disabled-default', { enabled: false, projectDefault: true })
        ]
      )
    ).toBe('runtime-default')
  })

  it('没有项目默认时回退到 runtime 默认或第一项', () => {
    expect(resolveChatDefaultModelId([model('first'), model('runtime-default', true)])).toBe('runtime-default')
    expect(resolveChatDefaultModelId([model('first'), model('second')])).toBe('first')
    expect(resolveChatDefaultModelId([])).toBe('')
  })
})
