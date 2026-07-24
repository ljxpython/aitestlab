import { defineStore } from 'pinia'
import { getProjectAccess, listProjects } from '@/services/projects/projects.service'
import type { ManagementProject, ProjectAccess } from '@/types/management'

const PROJECT_STORAGE_KEY = 'pw:workspace:project-id'

function readProjectPreference(storageKey: string) {
  if (typeof window === 'undefined') {
    return ''
  }

  return window.localStorage.getItem(storageKey)?.trim() || ''
}

function writeProjectPreference(storageKey: string, projectId: string) {
  if (typeof window === 'undefined') {
    return
  }

  if (projectId) {
    window.localStorage.setItem(storageKey, projectId)
    return
  }

  window.localStorage.removeItem(storageKey)
}

export const useWorkspaceStore = defineStore('workspace', {
  state: () => ({
    currentProjectId: '',
    projects: [] as ManagementProject[],
    currentProjectAccess: null as ProjectAccess | null,
    loading: false
  }),
  getters: {
    currentProject(state) {
      return state.projects.find((project) => project.id === state.currentProjectId) ?? null
    }
  },
  actions: {
    hydrateProjectPreference() {
      this.currentProjectId = readProjectPreference(PROJECT_STORAGE_KEY)
    },
    async setProjectId(projectId: string) {
      this.currentProjectId = projectId
      writeProjectPreference(PROJECT_STORAGE_KEY, projectId.trim())
      this.currentProjectAccess = projectId ? await getProjectAccess(projectId) : null
    },
    async hydrateContext() {
      this.loading = true

      try {
        this.hydrateProjectPreference()
        const rows = await listProjects()
        this.projects = rows

        const nextProjectId =
          rows.find((project) => project.id === this.currentProjectId)?.id ||
          rows[0]?.id ||
          ''

        await this.setProjectId(nextProjectId)
      } catch {
        this.projects = []
        await this.setProjectId('')
      } finally {
        this.loading = false
      }
    },
    reset() {
      this.projects = []
      void this.setProjectId('')
      this.loading = false
    }
  }
})
