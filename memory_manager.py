import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Any

from config import CV_DATA, settings

logger = logging.getLogger(__name__)

# ---------- mem0 инициализация с диагностикой ----------
def _init_mem0():
    try:
        from mem0 import MemoryClient, Memory
        logger.info("✅ mem0 библиотека установлена")
    except Exception as e:
        logger.warning("❌ mem0 не установлена: %s", e)
        return {"kind": "none", "client": None}

    # 1) Пробуем Platform
    api_key = settings.MEM0_API_KEY or os.getenv("MEM0_API_KEY")
    if api_key:
        try:
            client = MemoryClient(api_key=api_key)
            logger.info("✅ mem0 Platform инициализирована с API key")
            return {"kind": "platform", "client": client}
        except Exception as e:
            logger.warning("⚠️ mem0 Platform не удалось инициализировать: %s", e)

    # 2) Пробуем OSS версию
    try:
        if settings.GEMINI_API_KEY:
            os.environ["GOOGLE_API_KEY"] = settings.GEMINI_API_KEY
            config = {
                "llm": {
                    "provider": "gemini", 
                    "config": {"model": settings.GEMINI_MODEL, "temperature": 0.3}
                },
                "embedder": {
                    "provider": "gemini", 
                    "config": {"model": "models/text-embedding-004"}
                }
            }
            client = Memory.from_config(config)
            logger.info("✅ mem0 OSS инициализирована с Gemini")
            return {"kind": "oss", "client": client}
    except Exception as e:
        logger.warning("⚠️ mem0 OSS не удалось инициализировать: %s", e)

    logger.info("ℹ️ Работаем без mem0 (только short-term память и RAG)")
    return {"kind": "none", "client": None}

@dataclass
class Retrieved:
    text: str
    score: float

class MemoryManager:
    """
    Многоуровневая память:
    - mem0: эпизодическая память диалогов
    - Chroma: векторный поиск по CV и документам
    - Short-term: последние сообщения
    """
    def __init__(self, persist_path: str = "./memory_db"):
        # На Vercel используем /tmp для персистентности между вызовами в рамках инстанса
        try:
            if "VERCEL" in os.environ or os.environ.get("VC_ENV"):
                persist_path = "/tmp/memory_db"
        except Exception:
            pass
        # Инициализация mem0 с диагностикой
        mem = _init_mem0()
        self.mem0_kind = mem["kind"]
        self.mem0 = mem["client"]
        logger.info(f"📝 Система памяти: mem0={self.mem0_kind}")

        # Short-term память
        self.dialog: Dict[str, List[Dict[str, str]]] = {}

        # Chromadb для RAG
        Path(persist_path).mkdir(parents=True, exist_ok=True)
        
        import chromadb
        from chromadb.utils import embedding_functions
        
        self.client = chromadb.PersistentClient(path=persist_path)
        self.embedder = embedding_functions.GoogleGenerativeAiEmbeddingFunction(
            api_key=settings.GEMINI_API_KEY,
            model_name="models/text-embedding-004",
        )

        # Создаем коллекции
        try:
            self.kb_col = self.client.get_collection("kb_main", embedding_function=self.embedder)
            logger.info(f"📚 Загружена KB коллекция: {self.kb_col.count()} документов")
        except:
            self.kb_col = self.client.create_collection(
                "kb_main",
                embedding_function=self.embedder,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("📚 Создана новая KB коллекция")

        try:
            self.cv_col = self.client.get_collection("cv_data", embedding_function=self.embedder)
            logger.info(f"📄 Загружена CV коллекция: {self.cv_col.count()} фрагментов")
        except:
            self.cv_col = self.client.create_collection(
                "cv_data",
                embedding_function=self.embedder,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("📄 Создана новая CV коллекция")

        # Индексация данных
        self._index_cv_thoroughly()  # Улучшенная индексация CV
        self._maybe_ingest_docs(Path("docs"))
        self._maybe_ingest_single_pdf(Path("CV.pdf"))

    def add_conversation_memory(self, user_id: str, message: str, response: str):
        """Сохраняем диалог в short-term и mem0"""
        # Short-term
        hist = self.dialog.setdefault(user_id, [])
        hist.append({"q": message, "a": response})
        if len(hist) > 15:  # Увеличил до 15 для лучшего контекста
            self.dialog[user_id] = hist[-15:]

        # mem0
        if self.mem0:
            try:
                messages = [
                    {"role": "user", "content": message},
                    {"role": "assistant", "content": response},
                ]
                if self.mem0_kind == "platform":
                    result = self.mem0.add(messages, user_id=str(user_id))
                    logger.debug(f"✅ mem0 сохранила: {result}")
                else:
                    self.mem0.add(messages, user_id=str(user_id))
                    logger.debug("✅ mem0 OSS сохранила диалог")
            except Exception as e:
                logger.warning(f"⚠️ mem0 не смогла сохранить: {e}")

    def get_relevant_context(self, query: str, user_id: str, k_ep=5, k_kb=8, k_cv=6) -> str:
        """Собираем контекст из всех источников"""
        ep = self._mem0_search(query, user_id, k_ep)
        kb = self._kb_search(query, k_kb)
        cv = self._cv_search(query, k_cv)  # Всегда ищем в CV
        
        # Последние сообщения
        tail = []
        for item in self.dialog.get(user_id, [])[-3:]:
            tail.append(f"User: {item['q']}\nAssistant: {item['a'][:200]}")

        parts = []
        
        # ВАЖНО: CV данные в приоритете
        if cv:
            parts.append("=== ДАННЫЕ ИЗ CV ФИРДАВСА ===")
            for x in cv:
                parts.append(f"• {x.text.strip()}")
        
        if kb:
            parts.append("\n=== ДОПОЛНИТЕЛЬНЫЕ ДОКУМЕНТЫ ===")
            for x in kb[:5]:  # Ограничиваем чтобы не забить контекст
                parts.append(f"• {x.text.strip()[:300]}")
        
        if ep:
            parts.append("\n=== ИСТОРИЯ ДИАЛОГА (mem0) ===")
            for x in ep:
                parts.append(f"• {x.strip()}")
        
        if tail:
            parts.append("\n=== НЕДАВНИЕ СООБЩЕНИЯ ===")
            parts.extend(tail)

        context = "\n".join(parts) if parts else "Контекст не найден."
        
        # Диагностика
        logger.info(f"📊 Контекст: CV={len(cv)}, KB={len(kb)}, mem0={len(ep)}, dialog={len(tail)}")
        
        return context

    def _mem0_search(self, query: str, user_id: str, k: int) -> List[str]:
        """Поиск в mem0 памяти"""
        if not self.mem0:
            return []
        try:
            if self.mem0_kind == "platform":
                results = self.mem0.search(query, user_id=str(user_id), limit=k)
                memories = []
                for r in results.get("results", []):
                    memories.append(r.get("memory", str(r)))
                logger.debug(f"🔍 mem0 нашла {len(memories)} воспоминаний")
                return memories[:k]
            else:
                results = self.mem0.search(query, user_id=str(user_id))
                return [r.get("memory", str(r)) for r in results[:k]]
        except Exception as e:
            logger.warning(f"⚠️ mem0 поиск failed: {e}")
            return []

    def _kb_search(self, query: str, k: int) -> List[Retrieved]:
        """Поиск в базе документов"""
        try:
            if self.kb_col.count() == 0:
                return []
            r = self.kb_col.query(query_texts=[query], n_results=min(k, self.kb_col.count()))
            docs = r.get("documents", [[]])[0]
            dists = r.get("distances", [[]])[0]
            return [Retrieved(text=d, score=1-dist) for d, dist in zip(docs, dists) if (1-dist) > 0.3]
        except Exception as e:
            logger.debug(f"KB search error: {e}")
            return []

    def _cv_search(self, query: str, k: int) -> List[Retrieved]:
        """Поиск в CV - ВСЕГДА активен"""
        try:
            if self.cv_col.count() == 0:
                logger.warning("⚠️ CV коллекция пуста!")
                return []
            r = self.cv_col.query(query_texts=[query], n_results=min(k, self.cv_col.count()))
            docs = r.get("documents", [[]])[0]
            dists = r.get("distances", [[]])[0]
            results = [Retrieved(text=d, score=1-dist) for d, dist in zip(docs, dists) if (1-dist) > 0.2]
            logger.debug(f"🔍 CV поиск: найдено {len(results)} релевантных фрагментов")
            return results
        except Exception as e:
            logger.error(f"❌ CV search error: {e}")
            return []

    def _index_cv_thoroughly(self):
        """Тщательная индексация CV с избыточностью для лучшего поиска"""
        if self.cv_col.count() > 0:
            logger.info(f"CV уже проиндексирован: {self.cv_col.count()} фрагментов")
            return
        
        docs, ids = [], []
        
        # Личная информация - несколько вариантов
        pi = CV_DATA["personal_info"]
        docs.append(f"Фирдавс Файзуллаев - {pi['title']}. Опыт: {pi['experience_years']} лет в AI/ML. "
                   f"Локация: {pi['location']}. Специализация: {pi['expertise']}.")
        ids.append("cv_personal_1")
        
        docs.append(f"Имя: Фирдавс Файзуллаев. Должность: AI/ML Engineer и архитектор LLM-систем. "
                   f"Экспертиза в {pi['expertise']}. Базируется в Москве.")
        ids.append("cv_personal_2")
        
        # Контакты - детально
        c = CV_DATA["contacts"]
        docs.append(f"Контакты Фирдавса: Email {c['email']}, Telegram {c['telegram']}. {c['availability']}")
        ids.append("cv_contacts_1")
        
        docs.append(f"Для связи с Фирдавсом Файзуллаевым: почта {c['email']} или телеграм {c['telegram']}")
        ids.append("cv_contacts_2")
        
        # Опыт - подробно по каждой компании
        for i, w in enumerate(CV_DATA["work_experience"]):
            # Полное описание
            docs.append(f"Фирдавс работал в {w['company']} на позиции {w['position']} в период {w['period']}. "
                       f"Ключевые проекты: {', '.join(w['highlights'])}.")
            ids.append(f"cv_work_{i}_full")
            
            # Отдельно компания и роль
            docs.append(f"{w['company']}: {w['position']} ({w['period']})")
            ids.append(f"cv_work_{i}_brief")
            
            # Отдельно достижения
            for j, highlight in enumerate(w['highlights']):
                docs.append(f"В {w['company']} Фирдавс работал над: {highlight}")
                ids.append(f"cv_work_{i}_hl_{j}")
        
        # Навыки - по категориям и общий список
        sk = CV_DATA["skills"]
        
        # Модели
        docs.append(f"Фирдавс работает с моделями: {', '.join(sk['models'])}. "
                   f"Особенно силен в Llama, DeepSeek, Qwen для локального деплоя.")
        ids.append("cv_skills_models")
        
        # Фреймворки
        docs.append(f"Фреймворки которыми владеет Фирдавс: {', '.join(sk['frameworks'])}. "
                   f"Эксперт в LangChain и LangGraph для построения агентских систем.")
        ids.append("cv_skills_frameworks")
        
        # Инфраструктура
        docs.append(f"Инфраструктурный стек Фирдавса: {', '.join(sk['infra'])}. "
                   f"Умеет разворачивать ML системы в Kubernetes, оптимизировать через vLLM.")
        ids.append("cv_skills_infra")
        
        # Общий список навыков
        all_skills = sk['models'] + sk['frameworks'] + sk['infra']
        docs.append(f"Полный список технологий Фирдавса: {', '.join(all_skills)}")
        ids.append("cv_skills_all")
        
        # Образование
        ed = CV_DATA["education"]
        docs.append(f"Образование Фирдавса: {ed['university']}, специальность {ed['degree']}, {ed['period']}")
        ids.append("cv_education")
        
        # Ключевые метрики и достижения (из PDF)
        achievements = [
            "Фирдавс развернул 15+ production AI-ботов для бизнеса",
            "Системы Фирдавса обрабатывают 500K+ запросов в день с latency < 2 секунд",
            "Фирдавс снижает затраты на AI на 80% через локальный деплой моделей",
            "У Фирдавса дома лаборатория с RTX 4090 и 128GB RAM для экспериментов",
            "Фирдавс достиг качества MOS 4.2/5 в voice cloning технологиях",
            "Фирдавс создал zero-shot voice cloning бота на Chatterbox",
            "Фирдавс специалист по RAG системам с персистентной памятью Mem0/Zep",
            "Фирдавс работает в Voximplant над AI-ассистентом для 15K+ бизнес-клиентов"
        ]
        
        for i, achievement in enumerate(achievements):
            docs.append(achievement)
            ids.append(f"cv_achievement_{i}")
        
        # Сохраняем в Chroma
        if docs:
            self.cv_col.add(documents=docs, ids=ids)
            logger.info(f"✅ CV проиндексирован: {len(docs)} фрагментов")
            
            # Проверка
            test_queries = ["опыт работы", "контакты", "навыки", "voice AI", "LLM"]
            for q in test_queries:
                results = self.cv_col.query(query_texts=[q], n_results=2)
                if results["documents"][0]:
                    logger.info(f"✓ Тест '{q}': найдено {len(results['documents'][0])} результатов")

    def _maybe_ingest_single_pdf(self, path: Path):
        """Индексация CV.pdf если есть"""
        if not path.exists():
            return
        if self.kb_col.count() > 20:  # Уже что-то есть
            return
            
        text = self._read_file(path)
        if text:
            chunks, ids = self._chunk_texts([text], prefix="CV_PDF", chunk_chars=800)
            if chunks:
                self.kb_col.add(documents=chunks, ids=ids)
                logger.info(f"✅ Индексирован {path.name}: {len(chunks)} чанков")

    def _maybe_ingest_docs(self, folder: Path):
        """Индексация папки docs/"""
        if not folder.exists():
            return
        files = list(folder.glob("*.pdf")) + list(folder.glob("*.txt")) + list(folder.glob("*.md"))
        if not files:
            return
        
        for file in files:
            text = self._read_file(file)
            if text:
                chunks, ids = self._chunk_texts([text], prefix=file.stem[:20])
                if chunks:
                    self.kb_col.add(documents=chunks, ids=ids)
                    logger.info(f"✅ Индексирован {file.name}: {len(chunks)} чанков")

    def _read_file(self, path: Path) -> str:
        """Чтение файлов разных форматов"""
        try:
            if path.suffix.lower() == ".pdf":
                from PyPDF2 import PdfReader
                texts = []
                with open(path, "rb") as f:
                    reader = PdfReader(f)
                    for page in reader.pages:
                        if text := page.extract_text():
                            texts.append(text)
                return "\n".join(texts)
            else:
                return path.read_text("utf-8", errors="ignore")
        except Exception as e:
            logger.warning(f"Не удалось прочитать {path}: {e}")
            return ""

    def _chunk_texts(self, texts: List[str], prefix: str, chunk_chars=800, overlap=200):
        """Разбивка текста на чанки с перекрытием"""
        docs, ids = [], []
        idx = 1
        for raw in texts:
            text = " ".join((raw or "").split())
            if not text:
                continue
            
            start = 0
            step = max(100, chunk_chars - overlap)
            while start < len(text):
                chunk = text[start:start + chunk_chars]
                if len(chunk) > 50:  # Минимальный размер чанка
                    docs.append(chunk)
                    ids.append(f"{prefix}_{idx}")
                    idx += 1
                start += step
                
        return docs, ids

    def get_diagnostics(self) -> str:
        """Диагностическая информация о состоянии памяти"""
        diag = []
        diag.append(f"🧠 mem0: {self.mem0_kind}")
        diag.append(f"📚 KB документов: {self.kb_col.count()}")
        diag.append(f"📄 CV фрагментов: {self.cv_col.count()}")
        diag.append(f"💬 Активных диалогов: {len(self.dialog)}")
        
        # Тест поиска
        test_results = self._cv_search("опыт работы Фирдавс", 3)
        diag.append(f"🔍 Тест CV поиска: {'✅ OK' if test_results else '❌ FAIL'}")
        
        return "\n".join(diag)