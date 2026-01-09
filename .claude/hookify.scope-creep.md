---
name: scope-creep
enabled: true
event: stop
pattern: .*
---

🎯 **Before stopping - verify scope alignment**

The CodeWeaver project follows strict YAGNI (You Aren't Gonna Need It) principles and scope discipline. Please verify you've only implemented what was explicitly requested.

**Scope checklist:**
- ✅ Did I build ONLY what was asked for?
- ✅ Did I avoid "nice-to-have" features not in the requirements?
- ✅ Did I prevent adding auth, deployment, monitoring unless explicitly requested?
- ✅ Did I follow "MVP first, iterate based on feedback"?
- ✅ Did I avoid over-engineering with complex abstractions?

**Things NOT to add without explicit requests:**
- ❌ Authentication/authorization systems (unless asked)
- ❌ Deployment infrastructure (unless asked)
- ❌ Monitoring/observability (unless asked)
- ❌ Configuration system enhancements (unless asked)
- ❌ Error handling beyond what's necessary
- ❌ Helper functions for "future use"

**Constitutional Rule**: Build ONLY what's asked, avoid speculative features. Simple solutions that can evolve beat premature abstractions.

If you've added features beyond the explicit request, please review and remove them before completing.
