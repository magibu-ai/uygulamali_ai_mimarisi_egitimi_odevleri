from __future__ import annotations

import json
import os
import re
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any


class ModelClient(ABC):
    @abstractmethod
    def generate(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
        raise NotImplementedError


class TransformersModelClient(ModelClient):
    def __init__(self, model_id: str, max_new_tokens: int = 350, temperature: float = 0.1):
        try:
            import torch
            from transformers import AutoModelForMultimodalLM, AutoProcessor
        except ImportError as exc:
            raise RuntimeError(
                "Transformers backend requires torch, transformers, accelerate and pillow."
            ) from exc

        self.torch = torch
        self.max_new_tokens = max_new_tokens
        self.temperature = temperature
        self.debug_output = os.getenv("DEBUG_MODEL_OUTPUT", "0").strip() == "1"

        self.processor = AutoProcessor.from_pretrained(model_id)
        template_path = Path(__file__).resolve().parents[1] / "chat_template" / "chat_template.jinja"
        custom_template = template_path.read_text(encoding="utf-8")
        self.processor.chat_template = custom_template
        if hasattr(self.processor, "tokenizer"):
            self.processor.tokenizer.chat_template = custom_template

        dtype = torch.float16 if torch.cuda.is_available() else torch.float32
        self.model = AutoModelForMultimodalLM.from_pretrained(
            model_id,
            dtype=dtype,
            device_map="auto" if torch.cuda.is_available() else None,
            low_cpu_mem_usage=True,
        )
        if not torch.cuda.is_available():
            self.model.to("cpu")
        self.model.eval()

    def generate(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
        inputs = self.processor.apply_chat_template(
            messages,
            tools=tools,
            tokenize=True,
            add_generation_prompt=True,
            return_dict=True,
            return_tensors="pt",
            enable_thinking=False,
        )

        device = next(self.model.parameters()).device
        inputs = {
            key: value.to(device) if hasattr(value, "to") else value
            for key, value in inputs.items()
        }

        tokenizer = getattr(self.processor, "tokenizer", self.processor)
        generation_kwargs: dict[str, Any] = {
            "max_new_tokens": self.max_new_tokens,
            "pad_token_id": tokenizer.eos_token_id,
            "eos_token_id": tokenizer.eos_token_id,
        }
        if self.temperature > 0:
            generation_kwargs.update(
                do_sample=True,
                temperature=self.temperature,
                top_p=float(os.getenv("TOP_P", "0.8")),
                top_k=int(os.getenv("TOP_K", "20")),
            )
        else:
            generation_kwargs["do_sample"] = False

        with self.torch.inference_mode():
            output = self.model.generate(**inputs, **generation_kwargs)

        generated = output[0][inputs["input_ids"].shape[-1] :]
        text = self.processor.decode(generated, skip_special_tokens=True).strip()

        if self.debug_output:
            print("\n[MODEL RAW OUTPUT]\n" + text + "\n[/MODEL RAW OUTPUT]\n")
        return text


class RuleBasedDevelopmentClient(ModelClient):
    """Offline development fallback. Not intended as the final assignment model."""

    BARCODE_PATTERN = re.compile(r"\b\d{8,14}\b")

    def generate(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
        last = messages[-1]
        if last.get("role") == "tool":
            payload = json.loads(last.get("content", "{}"))
            return self._summarize_tool_result(payload)

        tool_names = {
            tool.get("function", {}).get("name")
            for tool in tools
            if isinstance(tool, dict)
        }
        if "plan_user_action" in tool_names:
            return self._plan_user_action(str(last.get("content", "")))

        text = str(last.get("content", "")).lower()
        barcode_match = self.BARCODE_PATTERN.search(text)
        barcode = barcode_match.group(0) if barcode_match else None

        if "alışveriş list" in text and any(word in text for word in ["göster", "getir", "ne var"]):
            return self._tool_call("get_shopping_list", {})
        if barcode and any(word in text for word in ["ekle", "listeye koy"]):
            quantity_match = re.search(r"\b(\d+)\s*(adet|tane)?\b", text)
            quantity = int(quantity_match.group(1)) if quantity_match else 1
            return self._tool_call(
                "add_to_shopping_list", {"barcode": barcode, "quantity": quantity}
            )
        if barcode:
            return self._tool_call("get_product_details", {"barcode": barcode})

        query = text
        for phrase in ["bul", "ara", "göster", "istiyorum", "öner"]:
            query = query.replace(phrase, " ")
        query = " ".join(query.split()).strip() or text.strip()
        return self._tool_call("search_products", {"query": query, "limit": 5})


    @classmethod
    def _plan_user_action(cls, raw_content: str) -> str:
        try:
            payload = json.loads(raw_content)
            message = str(payload.get("user_message", ""))
        except (json.JSONDecodeError, AttributeError):
            message = raw_content

        text = message.casefold()
        barcodes = cls.BARCODE_PATTERN.findall(message)
        quantity_match = re.search(r"\b(\d{1,2})\s*(?:adet|tane)\b", text)
        quantity = int(quantity_match.group(1)) if quantity_match else 1

        if ("kaç" in text or "toplam" in text) and ("sepet" in text or "alışveriş list" in text):
            arguments = {"action": "count_shopping_list", "response_mode": "count"}
        elif ("sepet" in text or "alışveriş list" in text) and any(
            token in text for token in ("göster", "görüntüle", "listele", "ne var")
        ):
            arguments = {"action": "get_shopping_list"}
        elif any(token in text for token in ("sil", "çıkar", "azalt", "kaldır")):
            arguments = {
                "action": "remove_from_shopping_list",
                "barcodes": barcodes,
                "quantity": quantity,
                "remove_all": any(token in text for token in ("tamamen", "hepsini", "kaldır")),
            }
            if not barcodes:
                arguments["selection"] = "named"
                arguments["product_reference"] = message
        elif any(token in text for token in ("olsun", "miktarı", "adetini")) and any(
            token in text for token in ("tane", "adet", "olsun", "yap")
        ):
            arguments = {
                "action": "set_shopping_list_quantity",
                "barcodes": barcodes,
                "quantity": quantity,
            }
            if not barcodes:
                arguments["selection"] = "named"
                arguments["product_reference"] = message
        elif any(token in text for token in ("ekle", "koy", "sepete at", "listemde olsun")):
            action = "ensure_in_shopping_list" if "listemde olsun" in text else "add_to_shopping_list"
            arguments = {"action": action, "barcodes": barcodes, "quantity": quantity}
            if not barcodes:
                if any(token in text for token in ("bunları", "bu ürün", "onları", "hepsini")):
                    arguments["selection"] = "last_selected"
                else:
                    arguments["selection"] = "named"
                    arguments["product_reference"] = message
        elif barcodes:
            arguments = {"action": "get_product_details", "barcodes": barcodes}
        else:
            max_sugars = 10.0 if any(
                token in text for token in ("fit", "sağlıklı", "şekeri düşük", "en fazla 10")
            ) else None
            arguments = {
                "action": "search_products",
                "query": "kahvaltılık gevrek" if "kahvalt" in text else message,
                "limit": 5,
            }
            if max_sugars is not None:
                arguments["max_sugars_100g"] = max_sugars

        return cls._tool_call("plan_user_action", arguments)

    @staticmethod
    def _tool_call(name: str, arguments: dict[str, Any]) -> str:
        parameter_blocks = []
        for argument_name, argument_value in arguments.items():
            if isinstance(argument_value, (dict, list, bool, int, float)) or argument_value is None:
                rendered_value = json.dumps(argument_value, ensure_ascii=False)
            else:
                rendered_value = str(argument_value)
            parameter_blocks.append(
                f"<parameter={argument_name}>\n{rendered_value}\n</parameter>"
            )
        parameters = "\n".join(parameter_blocks)
        return f"<tool_call>\n<function={name}>\n{parameters}\n</function>\n</tool_call>"

    @staticmethod
    def _summarize_tool_result(payload: dict[str, Any]) -> str:
        if not payload.get("success"):
            return f"İşlem tamamlanamadı: {payload.get('error', 'Bilinmeyen hata')}"

        if "products" in payload:
            products = payload.get("products", [])
            if not products:
                return "Arama kriterlerine uygun ürün bulunamadı."
            lines = []
            for product in products:
                grade = product.get("nutrition_grade") or "bilinmiyor"
                lines.append(
                    f"- {product.get('name', 'İsimsiz ürün')} | "
                    f"Barkod: {product.get('barcode')} | Nutri-Score: {grade}"
                )
            return "Bulduğum ürünler:\n" + "\n".join(lines)

        if "items" in payload:
            items = payload.get("items", [])
            if not items:
                return "Alışveriş listen şu anda boş."
            lines = [
                f"- {item['product_name']} — {item['quantity']} adet (Barkod: {item['barcode']})"
                for item in items
            ]
            return "Alışveriş listen:\n" + "\n".join(lines)

        if payload.get("action") == "shopping_list_updated":
            return (
                f"{payload['product']['name']} alışveriş listene eklendi. "
                f"Toplam miktar: {payload['quantity']}."
            )

        product = payload.get("product")
        if product:
            return (
                f"{product.get('name')} ({product.get('brand') or 'marka bilinmiyor'}), "
                f"barkod {product.get('barcode')}. Nutri-Score: "
                f"{product.get('nutrition_grade') or 'bilinmiyor'}."
            )
        return "İşlem başarıyla tamamlandı."


def build_model_client() -> ModelClient:
    backend = os.getenv("MODEL_BACKEND", "rules").strip().lower()
    if backend == "rules":
        return RuleBasedDevelopmentClient()
    if backend != "transformers":
        raise ValueError("MODEL_BACKEND must be either 'transformers' or 'rules'.")

    return TransformersModelClient(
        model_id=os.getenv("MODEL_ID", "Qwen/Qwen3.5-0.8B"),
        max_new_tokens=int(os.getenv("MAX_NEW_TOKENS", "192")),
        temperature=float(os.getenv("TEMPERATURE", "0.0")),
    )
