import { describe, expect, it } from 'vitest'

import {
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
    must_change_password: false,
    created_at: null,
    updated_at: null,
    ...overrides
  }
}

describe('auth permissions', () => {
  it('does not infer project content permissions from super admin', () => {
    const user = buildUser({
      is_super_admin: true,
      platform_roles: ['platform_super_admin']
    })

    expect(hasPermission(user, 'project.runtime.read')).toBe(false)
    expect(hasPermission(user, 'platform.project.takeover')).toBe(true)
  })

  it('treats the legacy super admin flag as the platform super admin role', () => {
    const user = buildUser({ is_super_admin: true })

    expect(hasPlatformRole(user, 'platform_super_admin')).toBe(true)
    expect(primaryPlatformRole(user)).toBe('platform_super_admin')
    expect(hasPermission(user, 'platform.config.read')).toBe(true)
    expect(hasPermission(user, 'project.testcase.read')).toBe(false)
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
    expect(user.must_change_password).toBe(false)
  })

  it('keeps project permissions out of the identity profile', () => {
    const user = buildUser()

    expect(hasPermission(user, 'project.runtime.read')).toBe(false)
    expect(hasPermission(user, 'project.member.write')).toBe(false)
  })

  it('keeps operator and super-admin governance capabilities distinct', () => {
    const operator = buildUser({ platform_roles: ['platform_operator'] })
    const superAdmin = buildUser({ platform_roles: ['platform_super_admin'] })

    expect(hasPermission(operator, 'platform.user.create')).toBe(true)
    expect(hasPermission(operator, 'platform.user.credential.reset')).toBe(false)
    expect(hasPermission(operator, 'platform.service_account.grant.write')).toBe(false)
    expect(hasPermission(superAdmin, 'platform.user.credential.reset')).toBe(true)
    expect(hasPermission(superAdmin, 'platform.service_account.grant.write')).toBe(true)
  })
})
