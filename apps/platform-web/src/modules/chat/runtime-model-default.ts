import type { RuntimeModelItem, RuntimeModelPolicyItem } from '@/types/management'

export function resolveChatDefaultModelId(
  models: RuntimeModelItem[],
  modelPolicies: RuntimeModelPolicyItem[] = []
): string {
  const availableModelIds = new Set(models.map((item) => item.model_id.trim()).filter(Boolean))
  const projectDefaultModelId =
    modelPolicies
      .find((item) => {
        const modelId = item.model_id.trim()
        return Boolean(
          modelId &&
            availableModelIds.has(modelId) &&
            item.policy.is_enabled &&
            item.policy.is_default_for_project
        )
      })
      ?.model_id.trim() || ''

  if (projectDefaultModelId) {
    return projectDefaultModelId
  }

  return models.find((item) => item.is_default)?.model_id || models[0]?.model_id || ''
}
