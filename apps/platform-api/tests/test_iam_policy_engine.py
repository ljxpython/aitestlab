from __future__ import annotations

import unittest

from app.core.context.models import ActorContext
from app.core.errors import BadRequestError, ForbiddenError, NotAuthenticatedError, PlatformApiError
from app.modules.iam.application import AuthorizationRequest, IamPolicyEngine, PermissionCode, PolicyReason


class IamPolicyEngineTest(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = IamPolicyEngine()

    def test_evaluate_returns_explicit_reason_for_unauthenticated_actor(self) -> None:
        decision = self.engine.evaluate(
            actor=ActorContext(),
            authorization=AuthorizationRequest(permission=PermissionCode.PLATFORM_USER_READ),
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, PolicyReason.NOT_AUTHENTICATED)

    def test_require_raises_project_scope_required(self) -> None:
        actor = ActorContext(
            user_id="user-1",
            platform_roles=("platform_operator",),
        )

        with self.assertRaises(BadRequestError) as ctx:
            self.engine.require(
                actor=actor,
                authorization=AuthorizationRequest(permission=PermissionCode.PROJECT_MEMBER_READ),
            )

        self.assertEqual(ctx.exception.code, "project_scope_required")

    def test_require_raises_platform_role_missing(self) -> None:
        actor = ActorContext(
            user_id="user-1",
            project_roles={"p-1": ("project_admin",)},
        )

        with self.assertRaises(ForbiddenError) as ctx:
            self.engine.require(
                actor=actor,
                authorization=AuthorizationRequest(permission=PermissionCode.PLATFORM_USER_READ),
            )

        self.assertEqual(ctx.exception.code, "platform_role_missing")

    def test_require_raises_project_role_missing(self) -> None:
        actor = ActorContext(
            user_id="user-1",
            platform_roles=("platform_viewer",),
            project_roles={"p-1": ("project_executor",)},
        )

        with self.assertRaises(ForbiddenError) as ctx:
            self.engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_MEMBER_WRITE,
                    project_id="p-1",
                ),
            )

        self.assertEqual(ctx.exception.code, "project_role_missing")

    def test_super_admin_still_requires_project_role(self) -> None:
        actor = ActorContext(
            user_id="user-1",
            platform_roles=("platform_super_admin",),
        )

        with self.assertRaises(ForbiddenError) as ctx:
            self.engine.require(
                actor=actor,
                authorization=AuthorizationRequest(
                    permission=PermissionCode.PROJECT_MEMBER_READ,
                    project_id="p-1",
                ),
            )

        self.assertEqual(ctx.exception.code, "project_role_missing")

    def test_require_raises_not_authenticated(self) -> None:
        with self.assertRaises(NotAuthenticatedError):
            self.engine.require(
                actor=ActorContext(),
                authorization=AuthorizationRequest(permission=PermissionCode.PLATFORM_AUDIT_READ),
            )

    def test_require_raises_for_unregistered_permission(self) -> None:
        actor = ActorContext(
            user_id="user-1",
            platform_roles=("platform_operator",),
        )

        decision = self.engine.evaluate(
            actor=actor,
            authorization=AuthorizationRequest(permission="custom.permission"),  # type: ignore[arg-type]
        )
        self.assertFalse(decision.allowed)
        self.assertEqual(decision.reason, PolicyReason.PERMISSION_NOT_REGISTERED)

        with self.assertRaises(PlatformApiError) as ctx:
            self.engine.require(
                actor=actor,
                authorization=AuthorizationRequest(permission="custom.permission"),  # type: ignore[arg-type]
            )

        self.assertEqual(ctx.exception.code, "permission_not_registered")
        self.assertEqual(ctx.exception.status_code, 500)


if __name__ == "__main__":
    unittest.main()
