# Security and responsible use

This tool edits configuration files for battery inverter systems. Misuse can damage a battery or take
a building off power. It is intended for people who are already responsible for, and authorized to
configure, the systems they apply it to.

**Scope.** The library never talks to a device. It reads and writes files that you then upload through
Victron's VRM Remote VEConfigure, which requires your own VRM login. No authentication, protection,
or credential of any kind is bypassed or handled by this project. The grid-code password that Victron
issues to dealers is out of scope by policy; setting 81 is documented for reading only.

**Reporting.** If you find a way this tool can produce a file that the device accepts but that damages
a system, or a way our guards can be fooled, please open a GitHub issue (label `incident` or `bug`).
Because this is not a service and holds no user data, we do not operate a private disclosure channel;
the fix is the same either way: a test, a guard, and a note in the docs.

**What we will not do.** Add upload capability, add anything that touches grid codes or passwords, or
remove the plausibility guards from the writer.
