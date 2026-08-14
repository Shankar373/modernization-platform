import pytest
import json
from app.config import Settings
from app.core.application.llm_service import LLMService

def test_llm_config_validation_success():
    # 1. No provider set -> passes validation
    settings = Settings(llm_provider="", groq_api_key="")
    assert settings.llm_provider == ""
    
    # 2. Groq provider with key -> passes validation
    settings = Settings(llm_provider="groq", groq_api_key="gsk_123")
    assert settings.llm_provider == "groq"
    assert settings.groq_api_key == "gsk_123"

def test_llm_config_validation_failures():
    # Groq provider missing key -> ValueError
    with pytest.raises(ValueError) as exc:
        Settings(llm_provider="groq", groq_api_key="")
    assert "GROQ_API_KEY is not configured" in str(exc.value)

def test_llm_service_initialization_mapping(monkeypatch):
    # Mock settings values using monkeypatch
    import app.config
    monkeypatch.setattr(app.config.settings, "llm_provider", "groq")
    monkeypatch.setattr(app.config.settings, "groq_api_key", "gsk_test")
    monkeypatch.setattr(app.config.settings, "groq_model", "llama-3.3-70b-versatile")
    
    # Init service
    service = LLMService()
    assert service.provider == "groq"

def test_llm_service_success_recommendations(monkeypatch):
    service = LLMService()
    service._available = True
    
    class FakeChoice:
        def __init__(self, content):
            self.message = type('Message', (), {'content': content})()
            
    class FakeResponse:
        def __init__(self, content):
            self.choices = [FakeChoice(content)]
            
    class FakeChatCompletions:
        def create(self, **kwargs):
            return FakeResponse(json.dumps([
                {
                    "recipe_id": "cs-var-modernization",
                    "name": "Use implicit var type",
                    "category": "upgrade",
                    "priority": "HIGH",
                    "reason": "Uses var.",
                    "risk": "LOW"
                }
            ]))
            
    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type('Chat', (), {'completions': FakeChatCompletions()})()
            
    service._openai_client = FakeOpenAI()
    service._groq_model = "llama-3.3-70b-versatile"
    
    profile = {"languages": ["csharp"]}
    recipes = [{"id": "cs-var-modernization", "name": "Use implicit var", "language": "csharp"}]
    executable_ids = ["cs-var-modernization"]
    
    recs = service.recommend_recipes(profile, recipes, executable_ids)
    assert len(recs) == 1
    assert recs[0]["recipe_id"] == "cs-var-modernization"
    assert recs[0]["executable"] is True

def test_llm_service_failure_recommendations(monkeypatch):
    service = LLMService()
    service._available = True
    
    class FakeChatCompletions:
        def create(self, **kwargs):
            raise Exception("API Limit reached")
            
    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type('Chat', (), {'completions': FakeChatCompletions()})()
            
    service._openai_client = FakeOpenAI()
    
    profile = {"languages": ["csharp"]}
    recipes = [{"id": "cs-var-modernization", "name": "Use implicit var", "language": "csharp"}]
    executable_ids = ["cs-var-modernization"]
    
    recs = service.recommend_recipes(profile, recipes, executable_ids)
    assert recs == []

def test_llm_service_malformed_response(monkeypatch):
    service = LLMService()
    service._available = True
    
    class FakeChoice:
        def __init__(self, content):
            self.message = type('Message', (), {'content': content})()
            
    class FakeResponse:
        def __init__(self, content):
            self.choices = [FakeChoice(content)]
            
    class FakeChatCompletions:
        def create(self, **kwargs):
            return FakeResponse("This is not JSON at all!")
            
    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type('Chat', (), {'completions': FakeChatCompletions()})()
            
    service._openai_client = FakeOpenAI()
    
    profile = {"languages": ["csharp"]}
    recipes = [{"id": "cs-var-modernization", "name": "Use implicit var", "language": "csharp"}]
    executable_ids = ["cs-var-modernization"]
    
    recs = service.recommend_recipes(profile, recipes, executable_ids)
    assert recs == []

def test_llm_service_recipe_filtering(monkeypatch):
    service = LLMService()
    service._available = True
    
    class FakeChoice:
        def __init__(self, content):
            self.message = type('Message', (), {'content': content})()
            
    class FakeResponse:
        def __init__(self, content):
            self.choices = [FakeChoice(content)]
            
    class FakeChatCompletions:
        def create(self, **kwargs):
            return FakeResponse(json.dumps([
                {
                    "recipe_id": "cs-var-modernization", # Valid
                    "name": "Use implicit var type",
                    "category": "upgrade",
                    "priority": "HIGH",
                    "reason": "Uses var.",
                },
                {
                    "recipe_id": "non-existent-recipe", # Unavailable, should be filtered out
                    "name": "Unimplemented",
                    "category": "upgrade",
                    "priority": "LOW",
                    "reason": "Fake.",
                },
                {
                    "recipe_id": "py-type-hint-injector", # Language incompatible (python recipe, csharp project)
                    "name": "Inject type hints",
                    "category": "style",
                    "priority": "MEDIUM",
                    "reason": "Injecting python hints."
                }
            ]))
            
    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = type('Chat', (), {'completions': FakeChatCompletions()})()
            
    service._openai_client = FakeOpenAI()
    service._groq_model = "llama-3.3-70b-versatile"
    
    profile = {"languages": ["csharp"]}
    recipes = [
        {"id": "cs-var-modernization", "name": "Use implicit var", "language": "csharp"},
        {"id": "py-type-hint-injector", "name": "Inject type hints", "language": "python"}
    ]
    executable_ids = ["cs-var-modernization", "py-type-hint-injector"]
    
    recs = service.recommend_recipes(profile, recipes, executable_ids)
    assert len(recs) == 1
    assert recs[0]["recipe_id"] == "cs-var-modernization"
