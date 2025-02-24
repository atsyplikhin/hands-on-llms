from typing import Any, Dict, List

import qdrant_client
from langchain.chains.base import Chain
from langchain.llms import HuggingFacePipeline

from financial_bot.embeddings import EmbeddingModelSingleton
from financial_bot.template import PromptTemplate


class ContextExtractorChain(Chain):
    """
    Encode the question, search the vector store for top-k articles and return
    context news from documents collection of Alpaca news.
    """

    top_k: int = 1
    embedding_model: EmbeddingModelSingleton
    vector_store: qdrant_client.QdrantClient
    vector_collection: str
    output_key: str = "context"

    @property
    def input_keys(self) -> List[str]:
        return ["about_me", "question"]

    @property
    def output_keys(self) -> List[str]:
        return [self.output_key]

    def _call(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        _, quest_key = self.input_keys
        question_str = inputs[quest_key]

        # TODO: maybe async embed?
        embeddings = self.embedding_model(question_str)

        # TODO: Using the metadata filter the news from the latest week (or other timeline).
        matches = self.vector_store.search(
            query_vector=embeddings,
            k=self.top_k,
            collection_name=self.vector_collection,
        )

        context = ""
        for match in matches:
            context += match.payload["summary"] + "\n"

        return {
            self.output_key: context,
        }


class FinancialBotQAChain(Chain):
    """This custom chain handles LLM generation upon given prompt"""

    hf_pipeline: HuggingFacePipeline
    template: PromptTemplate
    output_key: str = "answer"

    @property
    def input_keys(self) -> List[str]:
        return ["context"]

    @property
    def output_keys(self) -> List[str]:
        return [self.output_key]

    def _call(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        prompt = self.template.format_infer(
            {
                "user_context": inputs["about_me"],
                "news_context": inputs["question"],
                "chat_history": inputs["chat_history"],
                "question": inputs.get("context"),
            }
        )["prompt"]
        response = self.hf_pipeline(prompt)

        import logging

        logger = logging.getLogger(__name__)
        logger.info("HISTORY")
        logger.info(inputs["chat_history"])

        return {self.output_key: response}
