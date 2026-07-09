import logging
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from memory.config import load_settings
from observability import trace_run

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {"hate", "violence", "sexual", "out_of_scope", "legitimate"}

CLASSIFIER_SYSTEM_PROMPT = """Tu es le classifieur de sécurité de l'assistant support Velmo.
Classe le message de l'utilisateur dans EXACTEMENT une catégorie :
- hate : contenu haineux, discriminatoire, harcèlement
- violence : violence, menaces, incitation à se faire du mal ou à nuire
- sexual : contenu sexuel / NSFW
- out_of_scope : hors périmètre support (conseil juridique, médical, financier)
- legitimate : demande de support légitime (commande, livraison, retour, facture...)

Réponds UNIQUEMENT par le nom de la catégorie, en minuscules, sans autre texte."""

_RETRIES = 2


class KimiClassifier:
    """Classifieur de sécurité utilisant Kimi 2.6 via AzureChatOpenAI."""

    def __init__(self, settings=None) -> None:
        self.settings = settings or load_settings()
        self.llm = ChatOpenAI(
            model=self.settings.classifier_deployment_name,
            api_key=self.settings.azure_openai_api_key,
            base_url=self.settings.azure_openai_endpoint,
            temperature=0.0,
            max_tokens=self.settings.classifier_max_tokens,
        )
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", CLASSIFIER_SYSTEM_PROMPT),
            ("user", "{message}"),
        ])
        self._chain = self.prompt | self.llm

    def classify(self, message: str) -> str:
        """Retourne une catégorie valide. Retry 2x puis lève RuntimeError."""
        last_exc = None
        for attempt in range(_RETRIES):
            try:
                with trace_run("guardrail_classifier") as run:
                    resp = self._chain.invoke({"message": message}, config=run.config)
                    category = resp.content.strip().lower()
                    if category not in VALID_CATEGORIES:
                        logger.warning(f"Catégorie inconnue '{category}', fallback out_of_scope")
                        category = "out_of_scope"
                    # legitimate -> not blocked ; anything else -> blocked
                    run.log_score(
                        "blocked",
                        0.0 if category == "legitimate" else 1.0,
                        comment=category,
                    )
                return category
            except Exception as e:  # noqa: BLE001
                last_exc = e
                logger.error(f"Classifier attempt {attempt + 1} failed: {e}")
        raise RuntimeError(f"Classifier failed after {_RETRIES} attempts: {last_exc}")
