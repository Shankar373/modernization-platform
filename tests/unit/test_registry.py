from backend.app.capabilities.registry import registry
from backend.app.core.domain.models import CapabilityStatus

def test_registry_loads_capabilities():
    all_caps = registry.get_all()
    assert len(all_caps) > 0
    
    # Check that Java OpenRewrite capabilities exist
    java_caps = registry.get_for_language("java")
    assert len(java_caps) > 0
    assert any(c.provider == "openrewrite" for c in java_caps)

def test_registry_contains_unsupported_stubs():
    # Stubs like typescript should be present as NOT_AVAILABLE
    ts_caps = registry.get_for_language("typescript")
    assert len(ts_caps) > 0
    assert ts_caps[0].status == CapabilityStatus.NOT_AVAILABLE
