import logging
from langchain_openai import AzureChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from memory.config import load_settings

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
        self.llm = AzureChatOpenAI(
            azure_deployment=self.settings.azure_openai_deployment_name,
            azure_endpoint=self.settings.azure_openai_endpoint,
            api_key=self.settings.azure_openai_api_key,
            api_version=self.settings.azure_openai_api_version,
            temperature=0.0,
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
                resp = self._chain.invoke({"message": message})
                category = resp.content.strip().lower()
                if category not in VALID_CATEGORIES:
                    logger.warning(f"Catégorie inconnue '{category}', fallback out_of_scope")
                    return "out_of_scope"
                return category
            except Exception as e:  # noqa: BLE001
                last_exc = e
                logger.error(f"Classifier attempt {attempt + 1} failed: {e}")
        raise RuntimeError(f"Classifier failed after {_RETRIES} attempts: {last_exc}")
