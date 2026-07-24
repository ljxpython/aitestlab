import type { RouteRecordRaw } from 'vue-router'
import { h } from 'vue'
import { RouterView } from 'vue-router'

const workspaceChildren: RouteRecordRaw[] = [
  {
    path: '',
    redirect: '/workspace/overview'
  },
  {
    path: 'overview',
    name: 'workspace-overview',
    component: () => import('@/modules/overview/pages/OverviewPage.vue'),
    meta: { title: '总览', eyebrow: 'Overview' }
  },
  {
    path: 'projects',
    name: 'workspace-projects',
    component: () => import('@/modules/projects/pages/ProjectsPage.vue'),
    meta: { title: '项目', eyebrow: 'Projects' }
  },
  {
    path: 'projects/new',
    name: 'workspace-project-create',
    component: () => import('@/modules/projects/pages/ProjectCreatePage.vue'),
    meta: { title: '新建项目', eyebrow: 'Projects', requiredPermissions: ['platform.project.create'] }
  },
  {
    path: 'projects/:projectId',
    name: 'workspace-project-detail',
    component: () => import('@/modules/projects/pages/ProjectDetailPage.vue'),
    meta: {
      title: '项目详情',
      eyebrow: 'Projects',
      requiredPermissions: ['platform.project.read', 'project.member.read'],
      permissionMode: 'any',
      permissionProjectSource: 'route'
    }
  },
  {
    path: 'projects/:projectId/members',
    name: 'workspace-project-members',
    component: () => import('@/modules/projects/pages/ProjectMembersPage.vue'),
    meta: {
      title: '项目成员',
      eyebrow: 'Projects',
      requiredPermissions: ['project.member.read'],
      permissionProjectSource: 'route'
    }
  },
  {
    path: 'projects/:projectId/knowledge',
    component: { render: () => h(RouterView) },
    children: [
      {
        path: '',
        name: 'workspace-project-knowledge',
        redirect: (to) => `/workspace/projects/${String(to.params.projectId || '').trim()}/knowledge/documents`,
        meta: {
          title: '知识库',
          eyebrow: 'Knowledge',
          requiredPermissions: ['project.knowledge.read'],
          permissionProjectSource: 'route'
        }
      },
      {
        path: 'documents',
        name: 'workspace-project-knowledge-documents',
        component: () => import('@/modules/knowledge/pages/KnowledgeDocumentsPage.vue'),
        meta: {
          title: '知识文档',
          eyebrow: 'Knowledge',
          requiredPermissions: ['project.knowledge.read'],
          permissionProjectSource: 'route'
        }
      },
      {
        path: 'retrieval',
        name: 'workspace-project-knowledge-retrieval',
        component: () => import('@/modules/knowledge/pages/KnowledgeRetrievalPage.vue'),
        meta: {
          title: '知识检索',
          eyebrow: 'Knowledge',
          requiredPermissions: ['project.knowledge.read'],
          permissionProjectSource: 'route'
        }
      },
      {
        path: 'graph',
        name: 'workspace-project-knowledge-graph',
        component: () => import('@/modules/knowledge/pages/KnowledgeGraphPage.vue'),
        meta: {
          title: '知识图谱',
          eyebrow: 'Knowledge',
          requiredPermissions: ['project.knowledge.read'],
          permissionProjectSource: 'route'
        }
      },
      {
        path: 'settings',
        name: 'workspace-project-knowledge-settings',
        component: () => import('@/modules/knowledge/pages/KnowledgeSettingsPage.vue'),
        meta: {
          title: '知识设置',
          eyebrow: 'Knowledge',
          requiredPermissions: ['project.knowledge.read'],
          permissionProjectSource: 'route'
        }
      }
    ]
  },
  {
    path: 'users',
    name: 'workspace-users',
    component: () => import('@/modules/users/pages/UsersPage.vue'),
    meta: { title: '用户', eyebrow: 'Users', requiredPermissions: ['platform.user.read'] }
  },
  {
    path: 'users/new',
    name: 'workspace-user-create',
    component: () => import('@/modules/users/pages/UserCreatePage.vue'),
    meta: { title: '新建用户', eyebrow: 'Users', requiredPermissions: ['platform.user.create'] }
  },
  {
    path: 'users/:userId',
    name: 'workspace-user-detail',
    component: () => import('@/modules/users/pages/UserDetailPage.vue'),
    meta: { title: '用户详情', eyebrow: 'Users', requiredPermissions: ['platform.user.read'] }
  },
  {
    path: 'assistants',
    name: 'workspace-assistants',
    component: () => import('@/modules/assistants/pages/AssistantsPage.vue'),
    meta: {
      title: '助手',
      eyebrow: 'Assistants',
      requiredPermissions: ['project.assistant.read'],
      permissionProjectSource: 'workspace',
      allowWithoutProject: true
    }
  },
  {
    path: 'assistants/new',
    name: 'workspace-assistant-create',
    component: () => import('@/modules/assistants/pages/AssistantCreatePage.vue'),
    meta: {
      title: '新建助手',
      eyebrow: 'Assistants',
      requiredPermissions: ['project.assistant.write'],
      permissionProjectSource: 'workspace',
      allowWithoutProject: true
    }
  },
  {
    path: 'assistants/:assistantId',
    name: 'workspace-assistant-detail',
    component: () => import('@/modules/assistants/pages/AssistantDetailPage.vue'),
    meta: {
      title: '助手详情',
      eyebrow: 'Assistants',
      requiredPermissions: ['project.assistant.read'],
      permissionProjectSource: 'workspace',
      allowWithoutProject: true
    }
  },
  {
    path: 'runtime',
    component: { render: () => h(RouterView) },
    children: [
      {
        path: '',
        name: 'workspace-runtime',
        component: () => import('@/modules/runtime/pages/RuntimePage.vue'),
        meta: {
          title: 'Runtime',
          eyebrow: 'Runtime',
          requiredPermissions: ['project.runtime.read'],
          permissionProjectSource: 'workspace',
          allowWithoutProject: true
        }
      },
      {
        path: 'models',
        name: 'workspace-runtime-models',
        component: () => import('@/modules/runtime/pages/RuntimeModelsPage.vue'),
        meta: {
          title: 'Runtime Models',
          eyebrow: 'Runtime',
          requiredPermissions: ['project.runtime.read'],
          permissionProjectSource: 'workspace',
          allowWithoutProject: true
        }
      },
      {
        path: 'tools',
        name: 'workspace-runtime-tools',
        component: () => import('@/modules/runtime/pages/RuntimeToolsPage.vue'),
        meta: {
          title: 'Runtime Tools',
          eyebrow: 'Runtime',
          requiredPermissions: ['project.runtime.read'],
          permissionProjectSource: 'workspace',
          allowWithoutProject: true
        }
      },
      {
        path: 'policies',
        name: 'workspace-runtime-policies',
        component: () => import('@/modules/runtime/pages/RuntimePoliciesPage.vue'),
        meta: {
          title: 'Runtime Policies',
          eyebrow: 'Runtime',
          requiredPermissions: ['project.runtime.read'],
          permissionProjectSource: 'workspace',
          allowWithoutProject: true
        }
      }
    ]
  },
  {
    path: 'control-plane',
    name: 'workspace-control-plane',
    component: () => import('@/modules/control-plane/pages/ControlPlanePage.vue'),
    meta: {
      title: 'Control Plane',
      eyebrow: 'Governance',
      requiredPermissions: ['platform.config.read'],
      permissionMode: 'any'
    }
  },
  {
    path: 'operations',
    name: 'workspace-operations',
    component: () => import('@/modules/operations/pages/OperationsPage.vue'),
    meta: {
      title: 'Operations',
      eyebrow: 'Governance',
      requiredPermissions: ['platform.operation.read', 'project.operation.read'],
      permissionMode: 'any',
      permissionProjectSource: 'workspace',
      allowWithoutProject: true
    }
  },
  {
    path: 'graphs',
    name: 'workspace-graphs',
    component: () => import('@/modules/graphs/pages/GraphsPage.vue'),
    meta: {
      title: 'Graphs',
      eyebrow: 'Graphs',
      requiredPermissions: ['project.runtime.read'],
      permissionProjectSource: 'workspace',
      allowWithoutProject: true
    }
  },
  {
    path: 'sql-agent',
    name: 'workspace-sql-agent',
    component: () => import('@/modules/sql-agent/pages/SqlAgentPage.vue'),
    meta: {
      title: 'SQL Agent',
      eyebrow: 'Agent',
      requiredPermissions: ['project.runtime.read'],
      permissionProjectSource: 'workspace',
      allowWithoutProject: true
    }
  },
  {
    path: 'threads',
    name: 'workspace-threads',
    component: () => import('@/modules/threads/pages/ThreadsPage.vue'),
    meta: {
      title: 'Threads',
      eyebrow: 'Threads',
      requiredPermissions: ['project.runtime.read'],
      permissionProjectSource: 'workspace',
      allowWithoutProject: true
    }
  },
  {
    path: 'chat',
    name: 'workspace-chat',
    component: () => import('@/modules/chat/pages/ChatPage.vue'),
    meta: {
      title: 'Chat',
      eyebrow: 'Chat',
      requiredPermissions: ['project.runtime.read'],
      permissionProjectSource: 'workspace',
      allowWithoutProject: true
    }
  },
  {
    path: 'resources',
    component: { render: () => h(RouterView) },
    children: [
      {
        path: '',
        name: 'workspace-resources-overview',
        component: () => import('@/modules/examples/pages/UiAssetsPage.vue'),
        meta: { title: '资源总览', eyebrow: 'Resources' }
      },
      {
        path: 'playbook',
        name: 'workspace-resources-playbook',
        component: () => import('@/modules/examples/pages/ResourcePlaybookPage.vue'),
        meta: { title: '前端开发范式', eyebrow: 'Resources' }
      },
      {
        path: 'pages',
        name: 'workspace-resources-pages',
        component: () => import('@/modules/examples/pages/ResourcePageTemplatesPage.vue'),
        meta: { title: '页面模板', eyebrow: 'Resources' }
      },
      {
        path: 'components',
        name: 'workspace-resources-components',
        component: () => import('@/modules/examples/pages/ResourceComponentTemplatesPage.vue'),
        meta: { title: '组件模板', eyebrow: 'Resources' }
      },
      {
        path: 'engineering',
        name: 'workspace-resources-engineering',
        component: () => import('@/modules/examples/pages/ResourceEngineeringTemplatesPage.vue'),
        meta: { title: '工程模板', eyebrow: 'Resources' }
      },
      {
        path: 'top-picks',
        name: 'workspace-resources-top-picks',
        component: () => import('@/modules/examples/pages/ResourceTopPicksPage.vue'),
        meta: { title: '团队推荐 Top 10', eyebrow: 'Resources' }
      }
    ]
  },
  {
    path: 'ui-assets',
    redirect: '/workspace/resources',
    meta: { title: '资源总览', eyebrow: 'Resources' }
  },
  {
    path: 'testcase',
    component: { render: () => h(RouterView) },
    children: [
      {
        path: '',
        name: 'workspace-testcase',
        redirect: '/workspace/testcase/generate',
        meta: {
          title: 'Testcase Agent',
          eyebrow: 'Testcase Agent',
          requiredPermissions: ['project.testcase.read'],
          permissionProjectSource: 'workspace',
          allowWithoutProject: true
        }
      },
      {
        path: 'generate',
        name: 'workspace-testcase-generate',
        component: () => import('@/modules/testcase/pages/TestcaseGeneratePage.vue'),
        meta: {
          title: '用例生成',
          eyebrow: 'Testcase Agent',
          requiredPermissions: ['project.testcase.read'],
          permissionProjectSource: 'workspace',
          allowWithoutProject: true
        }
      },
      {
        path: 'cases',
        name: 'workspace-testcase-cases',
        component: () => import('@/modules/testcase/pages/TestcaseCasesPage.vue'),
        meta: {
          title: '用例管理',
          eyebrow: 'Testcase Agent',
          requiredPermissions: ['project.testcase.read'],
          permissionProjectSource: 'workspace',
          allowWithoutProject: true
        }
      },
      {
        path: 'documents',
        name: 'workspace-testcase-documents',
        component: () => import('@/modules/testcase/pages/TestcaseDocumentsPage.vue'),
        meta: {
          title: '文档管理',
          eyebrow: 'Testcase Agent',
          requiredPermissions: ['project.testcase.read'],
          permissionProjectSource: 'workspace',
          allowWithoutProject: true
        }
      }
    ]
  },
  {
    path: 'testcase-v2',
    component: { render: () => h(RouterView) },
    children: [
      {
        path: '',
        name: 'workspace-testcase-v2',
        redirect: '/workspace/testcase-v2/generate',
        meta: {
          title: 'Testcase Agent V2',
          eyebrow: 'Testcase Agent V2',
          requiredPermissions: ['project.testcase.read'],
          permissionProjectSource: 'workspace',
          allowWithoutProject: true
        }
      },
      {
        path: 'generate',
        name: 'workspace-testcase-v2-generate',
        component: () => import('@/modules/testcase/pages/TestcaseV2GeneratePage.vue'),
        meta: {
          title: '用例生成',
          eyebrow: 'Testcase Agent V2',
          requiredPermissions: ['project.testcase.read'],
          permissionProjectSource: 'workspace',
          allowWithoutProject: true
        }
      },
      {
        path: 'cases',
        name: 'workspace-testcase-v2-cases',
        component: () => import('@/modules/testcase/pages/TestcaseV2CasesPage.vue'),
        meta: {
          title: '用例管理',
          eyebrow: 'Testcase Agent V2',
          requiredPermissions: ['project.testcase.read'],
          permissionProjectSource: 'workspace',
          allowWithoutProject: true
        }
      },
      {
        path: 'documents',
        name: 'workspace-testcase-v2-documents',
        component: () => import('@/modules/testcase/pages/TestcaseV2DocumentsPage.vue'),
        meta: {
          title: '文档管理',
          eyebrow: 'Testcase Agent V2',
          requiredPermissions: ['project.testcase.read'],
          permissionProjectSource: 'workspace',
          allowWithoutProject: true
        }
      }
    ]
  },
  {
    path: 'announcements',
    name: 'workspace-announcements',
    component: () => import('@/modules/announcements/pages/AnnouncementsPage.vue'),
    meta: {
      title: '公告管理',
      eyebrow: 'Announcements',
      requiredPermissions: ['platform.announcement.write', 'project.announcement.write'],
      permissionMode: 'any',
      permissionProjectSource: 'workspace',
      allowWithoutProject: true
    }
  },
  {
    path: 'me',
    name: 'workspace-me',
    component: () => import('@/modules/account/pages/ProfilePage.vue'),
    meta: { title: '我的信息', eyebrow: 'Account' }
  },
  {
    path: 'security',
    name: 'workspace-security',
    component: () => import('@/modules/account/pages/SecurityPage.vue'),
    meta: { title: '安全设置', eyebrow: 'Account' }
  },
  {
    path: 'audit',
    name: 'workspace-audit',
    component: () => import('@/modules/audit/pages/AuditPage.vue'),
    meta: {
      title: '审计日志',
      eyebrow: 'Audit',
      requiredPermissions: ['platform.audit.read', 'project.audit.read'],
      permissionMode: 'any',
      permissionProjectSource: 'workspace',
      allowWithoutProject: true
    }
  },
  {
    path: 'platform-config',
    name: 'workspace-platform-config',
    component: () => import('@/modules/platform-config/pages/PlatformConfigPage.vue'),
    meta: { title: '平台配置', eyebrow: 'Governance', requiredPermissions: ['platform.config.read'] }
  },
  {
    path: 'service-accounts',
    name: 'workspace-service-accounts',
    component: () => import('@/modules/service-accounts/pages/ServiceAccountsPage.vue'),
    meta: {
      title: 'Service Accounts',
      eyebrow: 'Governance',
      requiredPermissions: ['platform.service_account.read']
    }
  },
  {
    path: 'system-governance',
    name: 'workspace-system-governance',
    component: () => import('@/modules/system-governance/pages/SystemGovernancePage.vue'),
    meta: { title: 'System Probes', eyebrow: 'Governance', requiredPermissions: ['platform.config.read'] }
  }
]

export const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/workspace'
  },
  {
    path: '/auth',
    component: () => import('@/layouts/AuthLayout.vue'),
    children: [
      {
        path: 'login',
        name: 'auth-login',
        component: () => import('@/views/auth/LoginView.vue')
      },
      {
        path: 'callback',
        name: 'auth-callback',
        component: () => import('@/views/auth/AuthCallbackView.vue')
      }
    ]
  },
  {
    path: '/workspace',
    component: () => import('@/layouts/WorkspaceLayout.vue'),
    children: workspaceChildren
  }
]
