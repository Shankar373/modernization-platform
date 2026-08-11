# Language Support Matrix

| Language   | Tool           | Status           | Phase |
|------------|----------------|------------------|-------|
| Java       | OpenRewrite    | ✅ AVAILABLE     | 1-2   |
| Python     | Ruff           | ✅ AVAILABLE     | 1-2   |
| C          | clang-tidy     | 🔲 NOT_AVAILABLE | 6+    |
| C++        | clang-tidy     | 🔲 NOT_AVAILABLE | 6+    |
| C#         | Roslyn         | 🔲 NOT_AVAILABLE | 6+    |
| .NET       | .NET Upgrade   | 🔲 NOT_AVAILABLE | 6+    |
| JavaScript | jscodeshift    | 🔲 NOT_AVAILABLE | 6+    |
| TypeScript | ts-morph       | 🔲 NOT_AVAILABLE | 6+    |
| Go         | go fix         | 🔲 NOT_AVAILABLE | 6+    |
| PHP        | Rector         | 🔲 NOT_AVAILABLE | 6+    |
| Kotlin     | —              | 🔲 NOT_AVAILABLE | 6+    |
| Ruby       | —              | 🔲 NOT_AVAILABLE | 6+    |
| COBOL      | —              | 📋 ASSESSMENT_ONLY | 6+  |
| HTML       | —              | 🔲 NOT_AVAILABLE | 6+    |
| CSS        | —              | 🔲 NOT_AVAILABLE | 6+    |

## Notes

- **AVAILABLE**: Real migration implemented and validated
- **NOT_AVAILABLE**: Connector architecture defined, no real migration
- **ASSESSMENT_ONLY**: Technology detected and assessed, no automated migration

All NOT_AVAILABLE languages return an honest assessment report.
The platform never fakes migration results.
