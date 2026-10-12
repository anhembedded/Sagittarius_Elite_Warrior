"""When a pre-flight check boots, relative to the extensions that do the work.

The Engine boots a higher `priority` first and breaks ties by registration order
(`ExtensionManager._build_and_sort`). A pre-flight check exists to stop a boot
that cannot succeed *before* anything starts: a module that restores bots,
subscribes to streams and starts watches must not run to completion and then
meet a `sys.exit(1)` from a check that happened to be registered after it.

`create_app` registered its checks first, so they booted first by order alone.
`EPIC-038A` moved the UI-only checks to the GUI wiring, which registers after
the modules, so they now say it explicitly. Default-priority extensions are 0.
"""

PREFLIGHT_BOOT_PRIORITY = 100
