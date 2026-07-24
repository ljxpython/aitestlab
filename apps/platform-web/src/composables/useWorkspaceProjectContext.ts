import { computed } from 'vue'
import { useWorkspaceStore } from '@/stores/workspace'

export function useWorkspaceProjectContext() {
  const workspaceStore = useWorkspaceStore()

  const activeProjectId = computed(() => workspaceStore.currentProjectId)
  const activeProject = computed(() => workspaceStore.currentProject)
  const activeProjects = computed(() => workspaceStore.projects)

  async function setActiveProjectId(projectId: string) {
    await workspaceStore.setProjectId(projectId)
  }

  return {
    workspaceStore,
    activeProjectId,
    activeProject,
    activeProjects,
    setActiveProjectId
  }
}
