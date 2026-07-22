import { describe, expect, it } from 'vitest'

import {
  hasAnyProjectPermission,
  hasPermission,
  hasPlatformRole,
  normalizeManagementUser,
  primaryPlatformRole
} from './permissions'
import type { ManagementUser } from '@/types/management'

function buildUser(overrides: Partial<ManagementUser> = {}): ManagementUser {
  return {
    id: 'user-1',
    username: 'admin',
    email: null,
    status: 'active',
    is_super_admin: false,
    platform_roles: [],
    project_roles: {},
    created_at: null,
    updated_at: null,
    ...overrides
  }
}

describe('auth permissions', () => {
  it('allows super admin project permissions without a selected project', () => {
    const user = buildUser({
      is_super_admin: true,
      platform_roles: ['platform_super_admin']
    })

    expect(hasPermission(user, 'project.runtime.read')).toBe(true)
    expect(hasAnyProjectPermission(user, 'project.runtime.read')).toBe(true)
  })

  it('treats the legacy super admin flag as the platform super admin role', () => {
    const user = buildUser({ is_super_admin: true })

    expect(hasPlatformRole(user, 'platform_super_admin')).toBe(true)
    expect(primaryPlatformRole(user)).toBe('platform_super_admin')
    expect(hasPermission(user, 'platform.config.read')).toBe(true)
    expect(hasAnyProjectPermission(user, 'project.testcase.read')).toBe(true)
  })

  it('normalizes legacy super admin payloads into the platform role list', () => {
    const user = normalizeManagementUser({
      id: 'user-1',
      username: 'admin',
      status: 'active',
      is_super_admin: true,
      platform_roles: []
    })

    expect(user.platform_roles).toContain('platform_super_admin')
    expect(hasAnyProjectPermission(user, 'project.runtime.read')).toBe(true)
  })

  it('keeps project permissions scoped for non-super-admin users', () => {
    const user = buildUser({
      project_roles: {
        'project-1': ['project_executor']
      }
    })

    expect(hasAnyProjectPermission(user, 'project.runtime.read')).toBe(true)
    expect(hasAnyProjectPermission(user, 'project.member.write')).toBe(false)
  })
})
