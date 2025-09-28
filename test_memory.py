"""Тестирование работы памяти и CV индексации"""

import logging
from memory_manager import MemoryManager

logging.basicConfig(level=logging.INFO)

def test_memory():
    print("🧪 Тестирование системы памяти...")
    
    mm = MemoryManager()
    
    # Диагностика
    print("\n📊 Диагностика:")
    print(mm.get_diagnostics())
    
    # Тесты поиска
    test_queries = [
        "опыт работы Фирдавса",
        "контакты email telegram", 
        "voice cloning Chatterbox",
        "Llama Qwen DeepSeek модели",
        "500K запросов latency"
    ]
    
    print("\n🔍 Тестирование поиска:")
    for query in test_queries:
        context = mm.get_relevant_context(query, "test_user", k_cv=3)
        print(f"\nЗапрос: '{query}'")
        print(f"Найдено: {len(context)} символов контекста")
        print(f"Превью: {context[:200]}...")
    
    print("\n✅ Тестирование завершено!")

if __name__ == "__main__":
    test_memory()