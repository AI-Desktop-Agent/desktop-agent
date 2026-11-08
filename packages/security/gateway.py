
"""Central security gateway for authorizing and executing tools."""

import asyncio
import inspect
import uuid
from collections.abc import Mapping

from packages.security.policy import Denied, POLICIES, resolve_risk
from packages.security.registry import REGISTRY
from packages.security.limits import limiter
from packages.security.audit import audit_log


class ToolGateway:
    def __init__(
        self,
        registry=None,
        rate_limiter=None,
        audit=None,
        approval_callback=None,
        taint_callback=None,
    ):
        # Dependency injection makes the gateway easy to test.
        self.registry = registry if registry is not None else REGISTRY
        self.rate_limiter = rate_limiter if rate_limiter is not None else limiter
        self.audit = audit if audit is not None else audit_log
        self.approval_callback = approval_callback
        self.taint_callback = taint_callback

    async def _invoke_tool(self, tool, args):
        """Support both async and sync tools without blocking the event loop."""

        async_invoke = getattr(tool, "ainvoke", None)

        if callable(async_invoke):
            return await async_invoke(args)

        sync_invoke = getattr(tool, "invoke", None)

        if not callable(sync_invoke):
            raise TypeError("registered tool has no callable invoke method")

        result = await asyncio.to_thread(sync_invoke, args)

        # Also support a synchronous wrapper that returns an awaitable.
        if inspect.isawaitable(result):
            result = await result

        return result

    async def _request_approval(self, tool_name, risk, args, principal):
        """Request approval when the effective risk policy requires it."""

        if self.approval_callback is None:
            raise Denied("user approval is not configured")

        try:
            result = self.approval_callback(
                tool_name,
                risk,
                dict(args),
                principal,
            )

            if inspect.isawaitable(result):
                result = await result

        except Exception as exc:
            raise Denied("approval check failed") from exc

        if result is not True:
            raise Denied("user approval was not granted")

    async def _mark_tainted(self, context_id, tool_name):
        """Update trusted application state after a tool introduces untrusted data."""

        result = self.taint_callback(context_id, tool_name)

        if inspect.isawaitable(result):
            await result

    def _write_audit(
        self,
        *,
        call_id,
        tool_name,
        principal,
        risk,
        outcome,
        args,
        detail,
    ):
        """Keep audit writes consistent across all execution paths."""

        self.audit.write(
            call_id=call_id,
            tool=tool_name,
            principal=principal,
            risk=risk,
            outcome=outcome,
            args=args,
            detail=detail,
        )

    async def execute(
        self,
        tool_name: str,
        args: dict,
        *,
        principal: str,
        granted_scopes=(),
        tainted=False,
        context_id=None,
    ):
        """Authorize, audit and execute one registered tool."""

        # Validate trusted caller-supplied context.
        if not isinstance(tool_name, str) or not tool_name:
            raise ValueError("tool_name must be a non-empty string")

        if not isinstance(principal, str) or not principal.strip():
            raise ValueError("principal must be a non-empty string")

        if not isinstance(args, Mapping):
            raise TypeError("tool arguments must be a mapping")

        if isinstance(granted_scopes, str):
            raise TypeError("granted_scopes must be a collection, not a string")

        try:
            granted_scopes = frozenset(granted_scopes)
        except TypeError as exc:
            raise TypeError("granted_scopes must be an iterable of strings") from exc

        if any(
            not isinstance(scope, str) or not scope
            for scope in granted_scopes
        ):
            raise ValueError("every granted scope must be a non-empty string")

        if not isinstance(tainted, bool):
            raise TypeError("tainted must be a boolean from trusted application state")

        args = dict(args)
        call_id = str(uuid.uuid4())
        risk = "high"

        # Authorization phase.
        try:
            # 1. Only registered tools can execute.
            spec = self.registry.get(tool_name)

            if spec is None:
                raise Denied(f"tool '{tool_name}' is not registered")

            # 2. Resolve effective risk, including taint.
            risk = resolve_risk(
                spec.risk,
                args,
                external=spec.external,
                tainted=tainted,
            )

            policy = POLICIES[risk]

            # 3. Explicitly blocked tools can never execute.
            if policy.get("deny", False):
                raise Denied(f"tool '{tool_name}' is blocked by policy")

            # 4. Check permissions.
            missing_scopes = spec.scopes - granted_scopes

            if missing_scopes:
                raise Denied(
                    f"missing required scopes: {sorted(missing_scopes)}"
                )

            # 5. Apply rate limiting.
            limit = policy.get("rate_per_min")

            # None means unlimited. Do not call acquire() or record a hit.
            if limit is not None:
                self.rate_limiter.acquire(
                    principal,
                    tool_name,
                    limit,
                )

            # 6. Request approval if required.
            if policy.get("approval", False):
                await self._request_approval(
                    tool_name,
                    risk,
                    args,
                    principal,
                )

            # 7. Do not execute a taint-producing tool without a tracker.
            if spec.taints and self.taint_callback is None:
                raise Denied("taint tracking is not configured")

        except Denied as exc:
            # If this audit write fails, its error propagates.
            self._write_audit(
                call_id=call_id,
                tool_name=tool_name,
                principal=principal,
                risk=risk,
                outcome="blocked",
                args=args,
                detail=str(exc),
            )
            raise

        # Execution phase.
        # If this audit write fails, execution must not start.
        self._write_audit(
            call_id=call_id,
            tool_name=tool_name,
            principal=principal,
            risk=risk,
            outcome="allowed",
            args=args,
            detail="Tool authorized; execution starting",
        )

        try:
            # 8. Execute the registered tool.
            result = await self._invoke_tool(spec.tool, args)

            # 9. Update trusted taint state after receiving untrusted content.
            if spec.taints:
                trusted_context = (
                    context_id if context_id is not None else principal
                )
                await self._mark_tainted(trusted_context, tool_name)

        except Exception as exc:
            # The tool may have performed a side effect before failing.
            self._write_audit(
                call_id=call_id,
                tool_name=tool_name,
                principal=principal,
                risk=risk,
                outcome="error",
                args=args,
                detail=f"{type(exc).__name__}: {exc}",
            )
            raise

        # 10. Record successful completion.
        # If this write fails, the tool has already executed.
        self._write_audit(
            call_id=call_id,
            tool_name=tool_name,
            principal=principal,
            risk=risk,
            outcome="ok",
            args=args,
            detail="Tool executed successfully",
        )

        return result


gateway = ToolGateway()
