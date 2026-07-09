"""Internal service-layer command objects, one sub-package per endpoint.

Routers build these from the validated request plus resolved dependencies
(cookie identity, path params) and pass them into the corresponding
IChatService method — the service layer never accepts loose keyword args.
"""
